# SQL Migrator API Documentation

This document describes the backend REST APIs for SQL Migrator. All endpoints are backend-only and expect JSON payloads.

## Authentication

### POST `/api/auth/register`

Register a new user.

Request body:
```json
{
  "username": "<FRONTEND_USERNAME>",
  "email": "<FRONTEND_EMAIL>",
  "password": "<FRONTEND_PASSWORD>",
  "role": "User"
}
```

Example response:
```json
{
  "message": "User registered successfully.",
  "user": {
    "id": 1,
    "username": "testuser",
    "email": "testuser@example.com",
    "role": "User",
    "created_at": "2026-01-01T12:00:00"
  }
}
```

Error response:
```json
{
  "message": "User registration failed. Username or email may already exist."
}
```

---

### POST `/api/auth/login`

Login and receive a JWT token.

Request body:
```json
{
  "username": "<FRONTEND_USERNAME>",
  "password": "<FRONTEND_PASSWORD>"
}
```

Example response:
```json
{
  "access_token": "<JWT_TOKEN>",
  "role": "User",
  "message": "Login successful."
}
```

Error response:
```json
{
  "message": "Invalid username or password."
}
```

---

### POST `/api/auth/logout`

Invalidate the current JWT token (logical logout).

Headers:
- `Authorization: Bearer <JWT_TOKEN>`

Example response:
```json
{
  "message": "Logout successful.",
  "user": {
    "id": 1,
    "role": "User"
  }
}
```

## SQL-to-SQL Migration

### POST `/api/migration/sql-to-sql`

Run a SQL-to-SQL migration job.

Request body:
```json
{
  "source_db_type": "<FRONTEND_SOURCE_DB_TYPE>",
  "source_host": "<FRONTEND_SOURCE_HOST>",
  "source_port": "<FRONTEND_SOURCE_PORT>",
  "source_username": "<FRONTEND_SOURCE_USERNAME>",
  "source_password": "<FRONTEND_SOURCE_PASSWORD>",
  "source_database": "<FRONTEND_SOURCE_DATABASE>",
  "target_db_type": "<FRONTEND_TARGET_DB_TYPE>",
  "target_host": "<FRONTEND_TARGET_HOST>",
  "target_port": "<FRONTEND_TARGET_PORT>",
  "target_username": "<FRONTEND_TARGET_USERNAME>",
  "target_password": "<FRONTEND_TARGET_PASSWORD>",
  "target_database": "<FRONTEND_TARGET_DATABASE>",
  "tables": ["table1", "table2"]
}
```

Example response:
```json
{
  "message": "Migration completed.",
  "report": {
    "summary": [
      {
        "table": "users",
        "rows_transferred": 120,
        "validation": {
          "source_row_count": 120,
          "target_row_count": 120,
          "match": true
        },
        "status": "completed"
      }
    ],
    "tables": ["users"],
    "source_db": { ... },
    "target_db": { ... }
  }
}
```

Error response:
```json
{
  "message": "Migration failed.",
  "error": "<error details>"
}
```

---

### GET `/api/migration/status/<id>`

Get the current status of a migration job.

Example response:
```json
{
  "migration": {
    "id": 1,
    "migration_type": "sql_to_sql",
    "source_db": "mysql://localhost",
    "target_db": "postgresql://localhost",
    "status": "completed",
    "error_message": null,
    "report_id": 1,
    "created_at": "2026-01-01T12:00:00",
    "updated_at": "2026-01-01T12:10:00"
  }
}
```

---

### GET `/api/migration/history`

List migration history records.

Example response:
```json
{
  "history": [...],
  "count": 3
}
```

## File-to-SQL Import

### POST `/api/import/file-to-sql`

Import a CSV or Excel file into a SQL database.

Request body:
```json
{
  "file_path": "<FRONTEND_FILE_PATH>",
  "target_db_type": "sqlite",
  "target_database": "./backend/database/app_data.db",
  "target_table": "<FRONTEND_TABLE_NAME>",
  "if_exists": "append"
}
```

Example response:
```json
{
  "message": "File import completed.",
  "result": {
    "table_name": "imported_users",
    "rows_imported": 2,
    "schema_sql": "CREATE TABLE ...",
    "target_database": "./backend/database/app_data.db"
  }
}
```

## SQL-to-File Export

### POST `/api/export/sql-to-file`

Export SQL table rows to CSV or Excel.

Request body:
```json
{
  "source_db_type": "sqlite",
  "source_database": "./backend/database/app_data.db",
  "source_table": "<FRONTEND_SOURCE_TABLE>",
  "columns": ["id", "name"],
  "filters": "age > 18",
  "export_format": "csv",
  "export_path": "<FRONTEND_EXPORT_PATH>"
}
```

Example response:
```json
{
  "message": "Export completed.",
  "result": {
    "table_name": "users",
    "rows_exported": 120,
    "export_format": "csv",
    "export_path": "backend/exports/export_users.csv"
  }
}
```

## Schema Generator

### POST `/api/schema/generate`

Generate a SQL `CREATE TABLE` statement from a file.

Request body:
```json
{
  "file_path": "<FRONTEND_FILE_PATH>",
  "table_name": "<FRONTEND_TABLE_NAME>"
}
```

Example response:
```json
{
  "schema_sql": "CREATE TABLE IF NOT EXISTS users (...)"
}
```

## History Management

### GET `/api/history`

Retrieve all stored migration history records.

### DELETE `/api/history/<id>`

Delete a migration history record by ID.

## Admin Endpoints

### GET `/api/admin/users`

List all registered users. Requires JWT with role `Admin`.

### DELETE `/api/admin/user/<id>`

Delete a user by ID. Requires JWT with role `Admin`.

### GET `/api/admin/stats`

Get migration metrics and failed job counts. Requires JWT with role `Admin`.

## Report Endpoint

### GET `/api/reports/<id>`

Retrieve stored report metadata by report ID.

Example response:
```json
{
  "report": {
    "id": 1,
    "migration_id": 1,
    "report_format": "json",
    "file_path": "",
    "summary": "Migration completed.",
    "created_at": "2026-01-01T12:10:00"
  }
}
```

## Notes

- All requests should send JSON payloads.
- Placeholder values are used in examples and should be replaced by frontend-provided values.
- The backend uses SQLite for internal storage and connects to external databases using provided credentials.
