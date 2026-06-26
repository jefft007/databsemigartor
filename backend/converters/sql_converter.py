from typing import Any, Dict, List
from sqlalchemy import MetaData, Table, Column, inspect
from sqlalchemy.exc import SQLAlchemyError
import pandas as pd

from backend.database.connection_manager import create_engine_for_config
from backend.validators.migration_validator import validate_table_counts
from backend.converters.datatype_mapper import map_datatype, check_datatype_mismatch
from backend.converters.migration_tracker import migrate_with_tracking


def build_table_schema(source_engine, table_name: str, target_db_type: str) -> tuple[Table, list]:
    """Build a target SQLAlchemy Table object from a source table schema."""
    source_meta = MetaData()
    target_meta = MetaData()
    source_table = Table(table_name, source_meta, autoload_with=source_engine)

    columns = []
    warnings = []

    for column in source_table.columns:
        mapped_type = map_datatype(str(column.type), target_db_type)
        mismatch = check_datatype_mismatch(str(column.type), mapped_type, target_db_type)

        if mismatch:
            mismatch["column"] = column.name
            warnings.append(mismatch)

        column_args = {
            "primary_key": column.primary_key,
            "nullable": column.nullable,
        }

        columns.append(Column(column.name, mapped_type, **column_args))

    return Table(table_name, target_meta, *columns), warnings


def find_empty_cell_warnings(data_frame: pd.DataFrame) -> list:
    """Find empty/null/blank values in SQL table data."""
    warning_rows = []

    for index, row in data_frame.iterrows():
        for column_name, value in row.items():
            if pd.isna(value) or str(value).strip() == "":
                warning_rows.append({
                    "original_index": int(index) + 1,
                    "column": column_name,
                    "reason": f"Empty value found in column '{column_name}'",
                    "data": row.to_dict()
                })

    return warning_rows


def migrate_sql_to_sql(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Perform a SQL-to-SQL migration workflow between two databases."""

    source_config = {
        "db_type": payload.get("source_db_type"),
        "username": payload.get("source_username"),
        "password": payload.get("source_password"),
        "host": payload.get("source_host"),
        "port": payload.get("source_port"),
        "database": payload.get("source_database"),
    }

    target_config = {
        "db_type": payload.get("target_db_type"),
        "username": payload.get("target_username"),
        "password": payload.get("target_password"),
        "host": payload.get("target_host"),
        "port": payload.get("target_port"),
        "database": payload.get("target_database"),
    }

    selected_tables = payload.get("tables") or []

    source_engine = create_engine_for_config(source_config)
    target_engine = create_engine_for_config(target_config)

    inspector = inspect(source_engine)
    source_tables = inspector.get_table_names()
    tables = selected_tables if selected_tables else source_tables

    if not tables:
        raise ValueError("No tables were selected for migration.")

    summary: List[Dict[str, Any]] = []

    for table_name in tables:
        if table_name not in source_tables:
            summary.append({
                "table": table_name,
                "status": "skipped",
                "reason": "Table not found on source."
            })
            continue

        try:
            target_table, warnings = build_table_schema(
                source_engine,
                table_name,
                target_config["db_type"]
            )

            target_table.metadata.create_all(target_engine)

            data_frame = pd.read_sql_table(table_name, source_engine)

            if not data_frame.empty:
                empty_warnings = find_empty_cell_warnings(data_frame)

                migration_report = migrate_with_tracking(
                    data_frame,
                    target_engine,
                    table_name
                )

                migration_report["warning_rows"] = empty_warnings
                migration_report["warning_count"] = len(empty_warnings)
                migration_report["flagged"] = len(empty_warnings) > 0

                validation = validate_table_counts(
                    source_engine,
                    target_engine,
                    table_name
                )

                failed_count = migration_report["summary"].get("failed", 0)
                cancelled_count = migration_report["summary"].get("cancelled", 0)
                warning_count = len(empty_warnings)

                is_flagged = (
                    failed_count > 0
                    or cancelled_count > 0
                    or warning_count > 0
                )

                summary.append({
                    "table": table_name,
                    "rows_transferred": migration_report["successful_count"],
                    "rows_failed": failed_count,
                    "rows_cancelled": cancelled_count,
                    "warning_count": warning_count,
                    "flagged": is_flagged,
                    "validation": validation,
                    "migration_report": migration_report,
                    "warnings": warnings + empty_warnings,
                    "status": "flagged" if is_flagged else "completed",
                })

            else:
                summary.append({
                    "table": table_name,
                    "rows_transferred": 0,
                    "validation": {
                        "source_row_count": 0,
                        "target_row_count": 0,
                        "match": True
                    },
                    "warnings": warnings,
                    "warning_count": 0,
                    "flagged": False,
                    "status": "completed",
                })

        except SQLAlchemyError as error:
            summary.append({
                "table": table_name,
                "status": "failed",
                "flagged": True,
                "error": str(error)
            })

    return {
        "summary": summary,
        "tables": tables,
        "source_db": source_config,
        "target_db": target_config,
    }