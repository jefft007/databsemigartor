import os
import pandas as pd
from typing import Dict, Any

from backend.database.connection_manager import create_engine_for_config
from backend.utils.file_handler import resolve_export_path


def export_sql_to_file(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Export SQL table data to a CSV or Excel file."""

    # Absolute path to the default SQLite database, resolved relative to this file
    _DEFAULT_SQLITE_DB = os.path.abspath(
        os.path.join(os.path.dirname(__file__), "..", "database", "app_data.db")
    )

    source_db_type = payload.get("source_db_type", "sqlite").lower()
    source_database = payload.get("source_database")
    if not source_database:
        source_database = _DEFAULT_SQLITE_DB if source_db_type == "sqlite" else ""

    source_config = {
        "db_type": source_db_type,
        "username": payload.get("source_username", ""),
        "password": payload.get("source_password", ""),
        "host": payload.get("source_host", "localhost"),
        "port": payload.get("source_port", ""),
        "database": source_database,
    }

    source_engine = create_engine_for_config(source_config)

    table_name = payload.get("source_table")
    export_format = payload.get("export_format", "csv").lower()
    export_path = payload.get("export_path")
    filters = payload.get("filters")
    columns = payload.get("columns") or []

    if not table_name:
        raise ValueError("Source table name is required for export.")

    if export_format not in ["csv", "xlsx"]:
        raise ValueError("Export format must be csv or xlsx.")

    query = f"SELECT {', '.join(columns) if columns else '*'} FROM {table_name}"

    if filters:
        query += f" WHERE {filters}"

    df = pd.read_sql_query(query, source_engine)

    EXPORT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "exports"))
    os.makedirs(EXPORT_DIR, exist_ok=True)

    filename = f"export_{table_name}.{export_format}"
    file_path = os.path.join(EXPORT_DIR, filename)
    
    if export_format == "csv":
        df.to_csv(file_path, index=False)
    else:
        try:
            df.to_excel(file_path, index=False)
        except ImportError as e:
            if "openpyxl" in str(e):
                raise ValueError("Excel export requires 'openpyxl'. Please install it using 'pip install openpyxl'.")
            raise e

    return {
        "filename": filename,
        "file_path": file_path,
        "rows_exported": len(df),
        "export_format": export_format,
        "download_url": f"/export/download/{filename}"
    }