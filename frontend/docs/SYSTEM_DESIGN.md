# SQL Migrator System Design

## Overview

SQL Migrator is designed as a backend-only ETL platform that separates frontend concerns from backend services. The backend exposes RESTful APIs for migration workflows, validation, reporting, and administrative control.

## Core Layers

### Application Layer
- `backend/app.py` initializes Flask, RESTful routes, database connections, and JWT authentication.
- `backend/config.py` loads environment variables and configures the SQLite application database.
- `backend/extensions.py` provides shared Flask extension objects used across the application.

### Authentication Layer
- `backend/auth/auth_routes.py` defines HTTP resources for register, login, and logout.
- `backend/auth/auth_service.py` manages user creation, password hashing, and authentication.
- `backend/auth/jwt_handler.py` generates JWT access tokens.

### Data Layer
- `backend/models/` contains SQLAlchemy ORM models for internal storage:
  - `User`
  - `Migration`
  - `MigrationHistory`
  - `Report`
  - `Setting`

### Conversion and Processing Layer
- `backend/converters/sql_converter.py` implements SQL-to-SQL migration workflows.
- `backend/converters/file_to_sql.py` handles CSV/Excel import into SQL.
- `backend/converters/sql_to_file.py` exports SQL query results to CSV/Excel.
- `backend/converters/datatype_mapper.py` maps source SQL types to generic SQLAlchemy types.
- `backend/processors/schema_generator.py` builds CREATE TABLE statements from uploaded files.

### Validation Layer
- `backend/validators/migration_validator.py` compares row counts between source and target tables.
- `backend/validators/compatibility_checker.py` inspects column compatibility.

### Reporting Layer
- `backend/reports/report_generator.py` outputs JSON, text, and PDF reports.
- `backend/reports/report_templates.py` formats summary and report content.

### Database Connectivity
- `backend/database/connection_manager.py` selects the correct engine based on DB type.
- `backend/database/mysql_connection.py` creates MySQL engines.
- `backend/database/postgres_connection.py` creates PostgreSQL engines.
- `backend/database/sqlite_connection.py` creates SQLite engines.
- `backend/database/oracle_connection.py` creates Oracle engines.

### Utilities
- `backend/utils/logger.py` configures rotating file logging.
- `backend/utils/encryption.py` hashes passwords and verifies logins.
- `backend/utils/helpers.py` sanitizes values and creates placeholders.
- `backend/utils/file_handler.py` resolves safe upload/export paths.

## Workflow

1. User registers or logs in.
2. Request data is accepted with placeholders when frontend input is missing.
3. For SQL migration, external source and target engines are built from request payloads.
4. Source tables are reflected, mapped, and copied to the target database.
5. Imported or exported files are processed using pandas and OpenPyXL.
6. Results are validated, persisted in migration history, and stored in reports.
7. Admin endpoints allow user management and migration monitoring.

## Design Principles

- Separation of concerns: authentication, routes, models, and services are isolated.
- Modular architecture: each module has a well-defined responsibility.
- Security: hashed passwords, JWT authentication, input sanitization, and error handling.
- Beginner-friendly: clear naming, comments, and doc-driven structure.
- Placeholder-driven data flow for frontend integration.
