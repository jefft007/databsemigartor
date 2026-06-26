import os
import json
import math
import pandas as pd
from typing import Dict, Any, List
from backend.database.connection_manager import create_engine_for_config
from backend.processors.csv_processor import read_csv_file
from backend.processors.excel_processor import read_excel_file
from backend.processors.schema_generator import generate_create_table_schema
from backend.processors.sql_dump_processor import import_sql_dump
from backend.utils.file_handler import resolve_upload_path
from backend.converters.migration_tracker import migrate_with_tracking

# Absolute path to the default SQLite database, resolved relative to this file
_DEFAULT_SQLITE_DB = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "database", "app_data.db")
)


class FileValidationError(Exception):
    """Raised when a file fails pre-import validation. Carries the list of
    row/column issues so the route layer can return them to the frontend
    without inserting anything into the database."""

    def __init__(self, issues: List[Dict[str, Any]]):
        self.issues = issues
        super().__init__(f"File failed validation with {len(issues)} issue(s).")


def _is_empty_value(value) -> bool:
    if value is None:
        return True
    if isinstance(value, float) and math.isnan(value):
        return True
    if pd.isna(value):
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    return False


def find_empty_cell_issues_in_frame(data_frame: pd.DataFrame, table_name: str) -> List[Dict[str, Any]]:
    """Validate an already-loaded DataFrame for empty/missing cells.

    This validates the EXACT data that is about to be written, rather than
    re-reading the file independently from disk.
    """
    issues = []
    for row_index, row in data_frame.iterrows():
        for column_name, value in row.items():
            if _is_empty_value(value):
                issues.append({
                    "table": table_name,
                    "row_index": int(row_index) + 1,
                    "column": column_name,
                    "reason": f"Empty value found in column '{column_name}'",
                })
    return issues


def _read_file(file_path: str) -> pd.DataFrame:
    """Read a CSV, JSON, or Excel file into a pandas DataFrame."""
    ext = os.path.splitext(file_path)[1].lower()
    if ext == ".csv":
        return read_csv_file(file_path)
    if ext == ".json":
        with open(file_path, "r", encoding="utf-8") as fh:
            raw = json.load(fh)
        # Accept both a list-of-records and a dict with a data key
        if isinstance(raw, list):
            return pd.DataFrame(raw)
        if isinstance(raw, dict):
            # Try common wrapper keys
            for key in ("data", "rows", "records", "results"):
                if key in raw and isinstance(raw[key], list):
                    return pd.DataFrame(raw[key])
            return pd.DataFrame([raw])
        raise ValueError(f"Unsupported JSON structure in {file_path}.")
    if ext in (".xlsx", ".xls"):
        return read_excel_file(file_path)
    raise ValueError(
        f"Unsupported file extension '{ext}'. Supported types: .csv, .json, .xlsx, .xls"
    )


def _coerce_to_column_dtype(value, series: pd.Series):
    """Convert a value (often a plain string from a browser input) to match
    the dtype of the column it's being written into.

    Corrections arrive as strings from the staging table's text inputs.
    Assigning a raw string into a numeric (float64/int64) column via
    .iat[] raises 'Invalid value ... for dtype ...' on recent pandas
    versions, since it no longer silently coerces types on item assignment.
    """
    if value is None:
        return None

    dtype = series.dtype

    try:
        if pd.api.types.is_float_dtype(dtype):
            return float(value)
        if pd.api.types.is_integer_dtype(dtype):
            # Route through float first so values like "6" or "6.0" both work
            return int(float(value))
        if pd.api.types.is_bool_dtype(dtype):
            if isinstance(value, str):
                return value.strip().lower() in ("true", "1", "yes")
            return bool(value)
        if pd.api.types.is_datetime64_any_dtype(dtype):
            return pd.to_datetime(value)
    except (ValueError, TypeError):
        # If it doesn't convert cleanly (e.g. user typed "abc" into a price
        # column), leave it as the raw string — re-validation downstream
        # will flag the type mismatch instead of crashing here.
        return value

    # Object/text columns: keep as-is (string)
    return value


def import_corrected_file_to_sql(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Re-read the original uploaded file, apply user-entered corrections on
    top of it (keyed by "rowIndex:column" from the staging review table),
    and import the result if it's now clean.

    This re-reads from disk rather than trusting client-sent row data, so
    the corrections are always applied against the real source file.
    """
    file_path = payload.get("file_path")
    if file_path is None:
        raise ValueError("File path is required for import.")

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    corrections = payload.get("corrections") or {}

    data_frame = _read_file(file_path)
    data_frame.columns = [col.strip() for col in data_frame.columns]
    table_name = payload.get("target_table") or os.path.splitext(os.path.basename(file_path))[0]

    for key, new_value in corrections.items():
        try:
            row_idx_str, col_name = key.split(":", 1)
            row_idx = int(row_idx_str)
        except (ValueError, AttributeError):
            continue

        if col_name not in data_frame.columns:
            continue
        if row_idx < 0 or row_idx >= len(data_frame):
            continue

        # An empty string from the input box means "still missing" — keep it
        # as a true missing value (None) so validation flags it again,
        # rather than treating "" as if it were a real value.
        if new_value is None or str(new_value).strip() == "":
            cleaned_value = None
        else:
            cleaned_value = _coerce_to_column_dtype(new_value, data_frame[col_name])

        data_frame.iat[row_idx, data_frame.columns.get_loc(col_name)] = cleaned_value

    # --- VALIDATE BEFORE WRITING ANYTHING --------------------------------
    validation_issues = find_empty_cell_issues_in_frame(data_frame, table_name)
    if validation_issues:
        raise FileValidationError(validation_issues)
    # ----------------------------------------------------------------------

    target_db_type = payload.get("target_db_type", "sqlite").lower()
    target_database = payload.get("target_database")
    if not target_database:
        target_database = _DEFAULT_SQLITE_DB if target_db_type == "sqlite" else ""

    target_config = {
        "db_type": target_db_type,
        "username": payload.get("target_username", ""),
        "password": payload.get("target_password", ""),
        "host": payload.get("target_host", "localhost"),
        "port": payload.get("target_port", ""),
        "database": target_database,
    }
    target_engine = create_engine_for_config(target_config)

    if_exists = payload.get("if_exists", "append")
    migration_report = migrate_with_tracking(data_frame, target_engine, table_name, if_exists=if_exists)

    schema_sql = generate_create_table_schema(file_path, table_name)
    return {
        "import_type": "tabular",
        "file_name": os.path.basename(file_path),
        "table_name": table_name,
        "rows_imported": migration_report["successful_count"],
        "rows_failed": migration_report["summary"]["failed"],
        "rows_cancelled": migration_report["summary"]["cancelled"],
        "schema_sql": schema_sql,
        "target_database": target_config.get("database"),
        "migration_report": migration_report,
    }


def import_file_to_sql(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Import a CSV, JSON, Excel, or SQL dump file into a target database.

    For tabular files (.csv/.json/.xlsx/.xls) the data is loaded via pandas
    and written with ``DataFrame.to_sql``.

    For SQL dump files (.sql) the statements are executed directly against
    the target engine inside a single transaction (strict mode).
    """
    file_path = payload.get("file_path")
    if file_path is None:
        raise ValueError("File path is required for import.")

    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    ext = os.path.splitext(file_path)[1].lower()

    # Use absolute path as the default SQLite database so it works regardless of CWD
    target_db_type = payload.get("target_db_type", "sqlite").lower()
    target_database = payload.get("target_database")
    if not target_database:
        target_database = _DEFAULT_SQLITE_DB if target_db_type == "sqlite" else ""
        
    target_config = {
        "db_type": target_db_type,
        "username": payload.get("target_username", ""),
        "password": payload.get("target_password", ""),
        "host": payload.get("target_host", "localhost"),
        "port": payload.get("target_port", ""),
        "database": target_database,
    }
    target_engine = create_engine_for_config(target_config)

    # ------------------------------------------------------------------ SQL dump
    if ext == ".sql":
        dump_result = import_sql_dump(file_path, target_engine)
        return {
            "import_type": "sql_dump",
            "file_name": os.path.basename(file_path),
            "statements_executed": dump_result["statements_executed"],
            "statements_skipped": dump_result["statements_skipped"],
            "rows_imported": None,
            "schema_sql": None,
            "target_database": dump_result["target_database"],
        }

    # ------------------------------------------------ Tabular: CSV / JSON / Excel
    data_frame = _read_file(file_path)
    table_name = payload.get("target_table") or os.path.splitext(os.path.basename(file_path))[0]

    # Sanitize column names: strip surrounding whitespace to avoid hard-to-query column names
    # (e.g. 'selling rate ' with trailing space becomes 'selling rate')
    data_frame.columns = [col.strip() for col in data_frame.columns]

    # --- VALIDATE BEFORE WRITING ANYTHING --------------------------------
    # Block the entire import if any row has a missing/empty value. Nothing
    # is written to the target database until the file is corrected and
    # re-submitted.
    validation_issues = find_empty_cell_issues_in_frame(data_frame, table_name)
    if validation_issues:
        raise FileValidationError(validation_issues)
    # ----------------------------------------------------------------------

    if_exists = payload.get("if_exists", "append")

    # Use tracking migration for better row-level error handling
    migration_report = migrate_with_tracking(data_frame, target_engine, table_name, if_exists=if_exists)

    schema_sql = generate_create_table_schema(file_path, table_name)
    return {
        "import_type": "tabular",
        "file_name": os.path.basename(file_path),
        "table_name": table_name,
        "rows_imported": migration_report["successful_count"],
        "rows_failed": migration_report["summary"]["failed"],
        "rows_cancelled": migration_report["summary"]["cancelled"],
        "schema_sql": schema_sql,
        "target_database": target_config.get("database"),
        "migration_report": migration_report,
    }