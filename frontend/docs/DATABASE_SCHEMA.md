# Internal Database Schema

SQL Migrator uses SQLite for internal application storage. The internal schema includes the following tables:

## `users`
Stores application user accounts.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Unique user ID |
| username | VARCHAR(120) | Unique username |
| email | VARCHAR(255) | Unique email address |
| password_hash | VARCHAR(255) | Bcrypt password hash |
| role | VARCHAR(50) | User role (`User` or `Admin`) |
| created_at | DATETIME | Creation timestamp |

## `migrations`
Stores migration job metadata.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Migration job ID |
| migration_type | VARCHAR(120) | Type of migration (`sql_to_sql`) |
| source_db | VARCHAR(255) | Source connection descriptor |
| target_db | VARCHAR(255) | Target connection descriptor |
| status | VARCHAR(80) | Job status (`pending`, `running`, `completed`, `failed`) |
| error_message | TEXT | Error details if migration failed |
| report_id | INTEGER | Foreign key to `reports.id` |
| created_at | DATETIME | Job creation timestamp |
| updated_at | DATETIME | Last updated timestamp |

## `migration_history`
Stores completed migration records and validation details.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | History record ID |
| migration_type | VARCHAR(120) | Migration workflow type |
| source_db | VARCHAR(255) | Source connection descriptor |
| target_db | VARCHAR(255) | Target connection descriptor |
| status | VARCHAR(80) | Final status |
| errors | TEXT | Validation or migration errors |
| timestamp | DATETIME | Record creation timestamp |
| report_summary | TEXT | Summary of results |

## `reports`
Stores generated report metadata.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Report ID |
| migration_id | INTEGER | Foreign key to `migrations.id` |
| report_format | VARCHAR(20) | Format type (`json`, `text`, `pdf`) |
| file_path | VARCHAR(512) | Path to exported report file |
| summary | TEXT | Summary text of the report |
| created_at | DATETIME | Creation timestamp |

## `settings`
Stores optional application settings.

| Column | Type | Description |
|--------|------|-------------|
| id | INTEGER PRIMARY KEY | Setting ID |
| key | VARCHAR(255) | Setting key |
| value | VARCHAR(1024) | Setting value |
| updated_at | DATETIME | Last update timestamp |

## Notes

- SQLite internal storage is used only for backend metadata, not for source or target migration data.
- Source and target databases are external and connected using request payload values.
