# Data Migration Issue Resolution Guide

## Problem
When migrating data, some rows get cancelled/skipped, leaving gaps that are filled by subsequent data, causing:
- Data loss
- Incorrect row positions
- Lack of visibility into what went wrong
- No way to recover cancelled data

## Solution Overview
This solution implements a **Migration Tracking System** that:

1. **Flags cancelled data** - Captures rows that fail validation or are empty
2. **Preserves data positions** - Maintains original row indices and only inserts valid data
3. **Provides detailed reports** - Generates reports showing what failed and why
4. **Enables recovery** - Allows retry of failed rows after fixing issues

---

## Architecture

### 1. **Migration Tracker Module** (`migration_tracker.py`)
Handles row-level tracking during data migration.

**Key Components:**
- `MigrationTracker`: Tracks successes, failures, and cancellations
- `validate_row_data()`: Validates each row before insertion
- `migrate_with_tracking()`: Main migration function with per-row error handling

**How it works:**
```python
# Before: All or nothing approach
data_frame.to_sql(table_name, engine)  # If one row fails, all fail

# After: Row-by-row tracking
migration_report = migrate_with_tracking(
    data_frame, 
    engine, 
    table_name
)
# Returns: {
#     "successful_count": 95,
#     "failed_rows": [...],
#     "cancelled_rows": [...]
# }
```

### 2. **Database Model** (`migration_row_issue_model.py`)
Stores failed/cancelled rows in the database for persistence and recovery.

```python
class MigrationRowIssue:
    - id: Unique identifier
    - migration_id: Which migration this belongs to
    - table_name: Which table had the issue
    - row_index: Original position in source data
    - status: 'failed' or 'cancelled'
    - error_message: Why it failed
    - row_data: The actual row data (JSON)
```

### 3. **API Endpoints** (`migration_issues_routes.py`)
REST endpoints to query and recover flagged data.

---

## Usage Guide

### Step 1: Integrate Tracking into Your Migrations

**For file-to-SQL imports:**
```python
# backend/converters/file_to_sql.py
from backend.converters.migration_tracker import migrate_with_tracking

migration_report = migrate_with_tracking(data_frame, target_engine, table_name)

# Response now includes:
# - rows_imported: Successfully migrated rows
# - rows_failed: Rows with validation errors
# - rows_cancelled: Empty/null rows
# - migration_report: Detailed breakdown
```

**For SQL-to-SQL migrations:**
```python
# backend/converters/sql_converter.py
migration_report = migrate_with_tracking(data_frame, target_engine, table_name)

# Automatically tracks which rows failed per table
```

### Step 2: Register API Routes

Add to your `app.py`:
```python
from flask_restful import Api
from backend.routes.migration_issues_routes import (
    MigrationRowIssuesResource,
    MigrationRetryFailedRowsResource,
    MigrationSummaryResource
)

api = Api(app)

# View failed/cancelled rows
api.add_resource(
    MigrationRowIssuesResource, 
    '/api/migrations/<int:migration_id>/issues'
)

# Retry specific rows
api.add_resource(
    MigrationRetryFailedRowsResource,
    '/api/migrations/<int:migration_id>/retry'
)

# Get summary
api.add_resource(
    MigrationSummaryResource,
    '/api/migrations/<int:migration_id>/summary'
)
```

### Step 3: Create Database Table

```bash
# In your Flask shell or migration script
from backend.extensions import db
from backend.models.migration_row_issue_model import MigrationRowIssue

db.create_all()  # Creates migration_row_issues table
```

---

## API Usage Examples

### Get Migration Summary
```bash
GET /api/migrations/1/summary

Response:
{
  "migration_id": 1,
  "total_issues": 15,
  "failed_rows": 10,
  "cancelled_rows": 5,
  "tables_affected": {
    "employees": {"failed": 5, "cancelled": 2},
    "departments": {"failed": 5, "cancelled": 3}
  }
}
```

### View Failed Rows for a Table
```bash
GET /api/migrations/1/issues

Response:
{
  "total_issues": 15,
  "issues": [
    {
      "id": 1,
      "table_name": "employees",
      "row_index": 5,
      "status": "failed",
      "error_message": "Column 'age' expected INTEGER, got str",
      "row_data": {
        "name": "John",
        "age": "twenty-five",
        "email": "john@example.com"
      },
      "created_at": "2024-01-15T10:30:00"
    }
  ]
}
```

### Retry Failed Rows
```bash
POST /api/migrations/1/retry
Body:
{
  "row_issue_ids": [1, 3, 5]
}

Response:
{
  "attempted": 3,
  "successful": 2,
  "failed": 1,
  "details": [
    {"row_id": 1, "status": "recovered"},
    {"row_id": 3, "status": "recovered"},
    {"row_id": 5, "status": "failed_retry", "error": "..."}
  ]
}
```

---

## Custom Validation Rules

You can add custom validation logic to `migrate_with_tracking()`:

```python
def custom_validator(row, row_index):
    """Custom validation for domain-specific rules."""
    if row['salary'] < 0:
        return False, "Salary cannot be negative"
    
    if pd.isna(row['email']):
        return False, "Email is required"
    
    return True, ""

# Use it
migration_report = migrate_with_tracking(
    data_frame,
    engine,
    table_name,
    validator_callback=custom_validator
)
```

---

## Troubleshooting

### Issue: Still getting data loss
**Solution:** Ensure you're using `migrate_with_tracking()` instead of `DataFrame.to_sql()`

### Issue: High failure rate
**Solution:** 
1. Check error messages in API response
2. Run validation query: `SELECT * FROM migration_row_issues WHERE migration_id = X`
3. Fix source data and retry

### Issue: Can't retry rows
**Solution:**
1. Ensure `MigrationRowIssue` table exists: `db.create_all()`
2. Check migration ID is correct
3. Verify target database connection in app.py

---

## Best Practices

1. **Always check migration summary** before considering migration complete
2. **Review failed rows** - they often indicate data quality issues in source
3. **Fix source data** when possible, rather than relaxing validations
4. **Use custom validators** for business rule enforcement
5. **Keep failed row logs** for audit trail
6. **Test with small datasets** first before full migrations

---

## Performance Considerations

- **Batch size:** Defaults to 100 rows. Increase for large datasets, decrease for memory constraints
  ```python
  migrate_with_tracking(df, engine, table, batch_size=500)
  ```

- **Large migrations:** Use `chunksize` parameter for reading:
  ```python
  for chunk in pd.read_csv('large_file.csv', chunksize=10000):
      migrate_with_tracking(chunk, engine, table_name)
  ```

---

## Summary of Changes

| File | Change | Purpose |
|------|--------|---------|
| `migration_tracker.py` | New | Core tracking logic |
| `migration_row_issue_model.py` | New | Database persistence |
| `migration_issues_routes.py` | New | API endpoints |
| `file_to_sql.py` | Updated | Use tracker for file imports |
| `sql_converter.py` | Updated | Use tracker for SQL-to-SQL migrations |

---

## Next Steps

1. **Run migrations with tracking enabled**
2. **Monitor migration summaries** for issues
3. **Use API to investigate failed rows**
4. **Fix source data or adjust validation rules**
5. **Retry failed rows** using the retry endpoint
