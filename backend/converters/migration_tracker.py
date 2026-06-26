"""
Enhanced migration tracking system to flag cancelled/failed rows and maintain data integrity.
This module prevents data loss by tracking which rows fail and preserving their positions.
"""

import pandas as pd
from typing import Dict, List, Any, Tuple
from datetime import datetime
import json


class MigrationTracker:
    """Tracks migration progress, flags failed rows, and maintains data integrity."""
    
    def __init__(self, table_name: str):
        self.table_name = table_name
        self.failed_rows: List[Dict[str, Any]] = []
        self.cancelled_rows: List[Dict[str, Any]] = []
        self.successful_rows: List[Dict[str, Any]] = []
        self.row_statuses: List[Dict[str, Any]] = []
        self.migration_summary = {
            "table": table_name,
            "total_rows": 0,
            "successful": 0,
            "failed": 0,
            "cancelled": 0,
            "timestamp": datetime.now().isoformat(),
        }
    
    def flag_row_cancelled(self, row_index: int, row_data: Dict, reason: str):
        """Flag a row as cancelled and track why."""
        cancelled_row = {
            "original_index": row_index,
            "data": row_data,
            "reason": reason,
            "status": "cancelled",
            "timestamp": datetime.now().isoformat(),
        }
        self.cancelled_rows.append(cancelled_row)
        self.row_statuses.append(cancelled_row)
        self.migration_summary["cancelled"] += 1
    
    def flag_row_failed(self, row_index: int, row_data: Dict, error: str):
        """Flag a row as failed and track the error."""
        failed_row = {
            "original_index": row_index,
            "data": row_data,
            "error": error,
            "status": "failed",
            "timestamp": datetime.now().isoformat(),
        }
        self.failed_rows.append(failed_row)
        self.row_statuses.append(failed_row)
        self.migration_summary["failed"] += 1
    
    def mark_row_successful(self, row_index: int, row_data: Dict):
        """Mark a row as successfully migrated."""
        success_row = {
            "original_index": row_index,
            "data": row_data,
            "status": "success",
            "timestamp": datetime.now().isoformat(),
        }
        self.successful_rows.append(success_row)
        self.row_statuses.append(success_row)
        self.migration_summary["successful"] += 1
    
    def get_report(self) -> Dict[str, Any]:
        """Generate a comprehensive migration report."""
        return {
            "summary": self.migration_summary,
            "failed_rows": self.failed_rows,
            "cancelled_rows": self.cancelled_rows,
            "row_statuses": self.row_statuses,
            "successful_count": self.migration_summary["successful"],
            "failure_rate": f"{(self.migration_summary['failed'] / max(self.migration_summary['total_rows'], 1) * 100):.2f}%",
        }


def validate_row_data(row: pd.Series, row_index: int, column_types: Dict[str, str]) -> Tuple[bool, str]:
    """
    Validate a single row before migration.
    
    Args:
        row: A pandas Series representing the row
        row_index: Index of the row
        column_types: Dictionary mapping column names to expected types
    
    Returns:
        Tuple of (is_valid, error_message)
    """
    errors = []
    
    for col_name, col_value in row.items():
        # Check for null/NaN in critical columns
        if pd.isna(col_value) and col_name not in ["optional_field", "nullable_column"]:
            # You can customize nullable columns per table
            pass
        
        # Basic type validation
        if col_value is not None and not pd.isna(col_value):
            expected_type = column_types.get(col_name, "TEXT")
            
            # Check for obvious type mismatches
            if expected_type.upper() == "INTEGER":
                try:
                    int(col_value)
                except (ValueError, TypeError):
                    errors.append(f"Column '{col_name}' expected INTEGER, got {type(col_value).__name__}")
            
            elif expected_type.upper() in ["REAL", "FLOAT", "DECIMAL"]:
                try:
                    float(col_value)
                except (ValueError, TypeError):
                    errors.append(f"Column '{col_name}' expected REAL, got {type(col_value).__name__}")
    
    if errors:
        return False, "; ".join(errors)
    
    return True, ""


def migrate_with_tracking(
    dataframe: pd.DataFrame,
    target_engine,
    table_name: str,
    validator_callback=None,
    batch_size: int = 100,
    if_exists: str = "append"
) -> Dict[str, Any]:
    """
    Migrate data with row-level tracking to flag cancelled/failed rows.
    
    Args:
        dataframe: Source data
        target_engine: SQLAlchemy engine for target database
        table_name: Target table name
        validator_callback: Optional custom validation function
        batch_size: Number of rows to process before commit
    
    Returns:
        Migration report with details on successes and failures
    """
    tracker = MigrationTracker(table_name)
    tracker.migration_summary["total_rows"] = len(dataframe)
    
    # Infer column types
    column_types = {col: str(dtype) for col, dtype in dataframe.dtypes.items()}
    
    # Initialize the table to handle the if_exists logic (replace, append, fail)
    try:
        dataframe.head(0).to_sql(table_name, target_engine, if_exists=if_exists, index=False)
    except ValueError as e:
        # e.g., if_exists='fail' and table already exists
        tracker.migration_summary["error"] = str(e)
        raise ValueError(f"Table {table_name} already exists.") from e

    # Process rows in batches
    rows_to_insert = []
    indices_to_keep = []
    
    for idx, (row_idx, row) in enumerate(dataframe.iterrows()):
        # Run validation
        is_valid, error_msg = validate_row_data(row, row_idx, column_types)
        
        # Run custom validator if provided
        if is_valid and validator_callback:
            is_valid, error_msg = validator_callback(row, row_idx)
        
        if is_valid:
            rows_to_insert.append(row)
            indices_to_keep.append(row_idx)
            # We will mark it successful only after insertion succeeds
        else:
            # Check if row is completely empty (cancelled) vs has errors (failed)
            if row.isna().all():
                tracker.flag_row_cancelled(row_idx, row.to_dict(), "All columns are empty")
            else:
                tracker.flag_row_failed(row_idx, row.to_dict(), error_msg)
        
        # Insert in batches
        if len(rows_to_insert) >= batch_size or idx == len(dataframe) - 1:
            if rows_to_insert:
                batch_df = pd.DataFrame(rows_to_insert)
                try:
                    batch_df.to_sql(table_name, target_engine, if_exists="append", index=False)
                    # If batch succeeds, mark all as successful
                    for row_obj in rows_to_insert:
                        tracker.mark_row_successful(row_obj.name, row_obj.to_dict())
                except Exception as e:
                    # If batch fails, try row-by-row
                    for row_obj in rows_to_insert:
                        try:
                            pd.DataFrame([row_obj]).to_sql(table_name, target_engine, if_exists="append", index=False)
                            tracker.mark_row_successful(row_obj.name, row_obj.to_dict())
                        except Exception as row_error:
                            tracker.flag_row_failed(row_obj.name, row_obj.to_dict(), str(row_error))
            
            rows_to_insert = []
            indices_to_keep = []
    
    return tracker.get_report()


def generate_migration_report_file(report: Dict[str, Any], output_path: str):
    """Save migration report to a JSON file for reference."""
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(report, f, indent=2, default=str)
