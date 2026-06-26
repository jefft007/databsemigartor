from flask import request
from flask_restful import Resource
from werkzeug.utils import secure_filename

from backend.models.migration_model import Migration
from backend.models.history_model import MigrationHistory
from backend.models.report_model import Report
from backend.extensions import db
from backend.utils.helpers import get_placeholder_data, sanitize_string
from backend.utils.file_handler import resolve_upload_path
from backend.converters.sql_converter import migrate_sql_to_sql
from backend.converters.file_to_sql import import_file_to_sql, import_corrected_file_to_sql, FileValidationError
from backend.converters.sql_to_file import export_sql_to_file
from backend.processors.schema_generator import generate_create_table_schema
from backend.database.connection_manager import create_engine_for_config, _DEFAULT_SQLITE_DB_FALLBACK

import json
from sqlalchemy import text


class SqlToSqlResource(Resource):
    """Endpoint to migrate tables from one SQL database to another."""

    def post(self):
        payload = request.get_json(silent=True) or {}
        defaults = {
            "source_db_type": "mysql",
            "source_host": None,
            "source_port": None,
            "source_username": None,
            "source_password": None,
            "source_database": None,
            "target_db_type": "postgresql",
            "target_host": None,
            "target_port": None,
            "target_username": None,
            "target_password": None,
            "target_database": None,
            "tables": [],
        }
        if not payload:
            payload = get_placeholder_data(defaults)

        migration_record = Migration(
            migration_type="sql_to_sql",
            source_db=f"{payload.get('source_db_type')}://{payload.get('source_host')}",
            target_db=f"{payload.get('target_db_type')}://{payload.get('target_host')}",
            status="running",
        )
        db.session.add(migration_record)
        db.session.commit()

        try:
            report_data = migrate_sql_to_sql(payload)
            migration_record.status = "completed"
            report = Report(
                migration_id=migration_record.id,
                report_format="json",
                file_path="",
                summary=json.dumps(
                    report_data.get("summary", []),
                    default=str
                ),
            )
            db.session.add(report)
            db.session.commit()
            migration_record.report_id = report.id
            db.session.commit()
            history = MigrationHistory(
                migration_type="sql_to_sql",
                source_db=migration_record.source_db,
                target_db=migration_record.target_db,
                status="completed",
                errors=None,
                report_summary=report.summary,
            )
            db.session.add(history)
            db.session.commit()
            return {
                "message": "Migration completed.",
                "report": report_data
            }, 200
        except Exception as exc:
            migration_record.status = "failed"
            migration_record.error_message = str(exc)
            db.session.rollback()
            db.session.add(migration_record)
            db.session.commit()
            history = MigrationHistory(
                migration_type="sql_to_sql",
                source_db=migration_record.source_db,
                target_db=migration_record.target_db,
                status="failed",
                errors=str(exc),
                report_summary="Migration failed.",
            )
            db.session.add(history)
            db.session.commit()
            return {
                "message": "Migration failed.",
                "error": str(exc)
            }, 500


class MigrationStatusResource(Resource):
    """Endpoint to check the status of a migration by ID."""

    def get(self, migration_id: int):
        migration = db.session.get(Migration, migration_id)
        if migration is None:
            return {"message": "Migration not found."}, 404
        return {"migration": migration.to_dict()}, 200


class MigrationHistoryResource(Resource):
    """Endpoint to list migration history entries."""

    def get(self):
        history = [record.to_dict() for record in MigrationHistory.query.order_by(MigrationHistory.timestamp.desc()).all()]
        return {"history": history, "count": len(history)}, 200


class FileImportResource(Resource):
    """Endpoint to import a CSV or Excel file into a SQL database."""

    def post(self):
        if request.is_json:
            payload = request.get_json(silent=True) or {}
            file_obj = None
        else:
            payload = request.form.to_dict()
            file_obj = request.files.get("file")

        if not payload and not file_obj:
            return {"message": "Request body is required."}, 400

        file_path = payload.get("file_path")

        if file_obj and file_obj.filename:
            filename = secure_filename(file_obj.filename)
            file_path = resolve_upload_path(filename)
            file_obj.save(file_path)
            payload["file_path"] = file_path

        if not file_path:
            return {"message": "A file upload is required."}, 400

        if "<FRONTEND" in str(file_path):
            return {"message": "Replace placeholder file path with a real file path."}, 400

        try:
            import_result = import_file_to_sql(payload)
            return {"message": "File import completed.", "result": import_result}, 200
        except FileValidationError as exc:
            return {
                "message": "Import blocked: the file still contains missing values.",
                "rejected": True,
                "warning_count": len(exc.issues),
                "warnings": exc.issues,
            }, 400
        except FileNotFoundError:
            return {"message": f"File not found: {file_path}"}, 404
        except Exception as exc:
            return {"message": "File import failed.", "error": str(exc)}, 500


class FileImportCorrectedResource(Resource):
    """Endpoint to import a file after the user has corrected flagged cells
    in the staging review table. Re-reads the original file from disk,
    applies the corrections by row index + column, re-validates, and
    imports if the result is now clean.
    """

    def post(self):
        payload = request.get_json(silent=True) or {}

        if not payload:
            return {"message": "Request body is required."}, 400

        file_path = payload.get("file_path")
        if not file_path:
            return {"message": "file_path is required."}, 400

        try:
            import_result = import_corrected_file_to_sql(payload)
            return {"message": "File import completed.", "result": import_result}, 200
        except FileValidationError as exc:
            return {
                "message": "Import blocked: some rows still have missing values after correction.",
                "rejected": True,
                "warning_count": len(exc.issues),
                "warnings": exc.issues,
            }, 400
        except FileNotFoundError:
            return {"message": f"File not found: {file_path}"}, 404
        except Exception as exc:
            return {"message": "File import failed.", "error": str(exc)}, 500


class SqlExportResource(Resource):
    """Endpoint to export SQL data to CSV or Excel."""

    def post(self):
        payload = request.get_json(silent=True) or {}

        if not payload:
            return {"message": "Request body is required."}, 400

        source_table = payload.get("source_table")

        if not source_table:
            return {"message": "source_table is required."}, 400

        try:
            export_result = export_sql_to_file(payload)
            return {"message": "Export completed.", "result": export_result}, 200
        except ValueError as exc:
            return {"message": str(exc)}, 400
        except Exception as exc:
            return {"message": "Export failed.", "error": str(exc)}, 500


class SchemaGeneratorResource(Resource):
    """Endpoint to generate CREATE TABLE schema from a file."""

    def post(self):
        payload = request.get_json(silent=True) or {}

        if not payload:
            return {"message": "Request body is required."}, 400

        file_path = payload.get("file_path")
        table_name = payload.get("table_name")

        if not file_path:
            return {"message": "file_path is required."}, 400

        if "<FRONTEND" in str(file_path):
            return {"message": "Replace placeholder file path with a real file path."}, 400

        try:
            schema_sql = generate_create_table_schema(file_path, table_name)
            return {"schema_sql": schema_sql}, 200
        except FileNotFoundError:
            return {"message": f"File not found: {file_path}"}, 404
        except Exception as exc:
            return {"message": "Schema generation failed.", "error": str(exc)}, 500


class TestConnectionResource(Resource):
    """Endpoint to test a database connection without performing a migration."""

    def post(self):
        payload = request.get_json(silent=True) or {}

        if not payload:
            return {"status": "error", "message": "Request body is required."}, 400

        db_type = (payload.get("db_type") or "").strip().lower()
        if not db_type:
            return {"status": "error", "message": "db_type is required."}, 400

        config = {
            "db_type": db_type,
            "username": payload.get("username") or "",
            "password": payload.get("password") or "",
            "host": payload.get("host") or "localhost",
            "port": payload.get("port") or "",
            "database": payload.get("database") or (
                _DEFAULT_SQLITE_DB_FALLBACK if db_type == "sqlite" else ""
            ),
        }

        # Per-driver connect timeout (5 s) so a bad host doesn't stall the server
        _CONNECT_ARGS: dict = {}
        if db_type in ("postgres", "postgresql"):
            _CONNECT_ARGS = {"connect_timeout": 5}
        elif db_type == "mysql":
            _CONNECT_ARGS = {"connect_timeout": 5}

        try:
            engine = create_engine_for_config(config, connect_args=_CONNECT_ARGS)
            with engine.connect() as conn:
                conn.execute(text("SELECT 1"))
            return {
                "status": "ok",
                "message": f"Connected successfully to {db_type}.",
                "db_type": db_type,
            }, 200
        except Exception as exc:
            # Strip verbose SQLAlchemy boilerplate from the error message
            raw = str(exc)
            # Take only the first meaningful line before the long traceback hint
            short = raw.split("\n")[0].split("(Background")[0].strip()
            return {
                "status": "error",
                "message": short or raw,
                "db_type": db_type,
            }, 200   # Always 200 so the frontend receives JSON, not a fetch error


class FileValidateResource(Resource):
    """Validate a file before importing — returns all rows with issue flags.
    Does NOT write to any database.
    """

    def post(self):
        import os
        from backend.converters.validate_import import validate_file_for_import

        if request.is_json:
            payload = request.get_json(silent=True) or {}
            file_obj = None
        else:
            payload = request.form.to_dict()
            file_obj = request.files.get("file")

        if not payload and not file_obj:
            return {"message": "Request body is required."}, 400

        file_path = payload.get("file_path")

        if file_obj and file_obj.filename:
            filename = secure_filename(file_obj.filename)
            file_path = resolve_upload_path(filename)
            file_obj.save(file_path)
            payload["file_path"] = file_path

        if not file_path:
            return {"message": "A file upload is required."}, 400

        try:
            overrides_raw = payload.get("column_type_overrides") or "{}"
            if isinstance(overrides_raw, str):
                import json as _json
                overrides = _json.loads(overrides_raw)
            else:
                overrides = overrides_raw

            enum_values_raw = payload.get("column_enum_values") or "{}"
            if isinstance(enum_values_raw, str):
                import json as _json
                enum_values = _json.loads(enum_values_raw)
            else:
                enum_values = enum_values_raw

            page = int(payload.get("page", 1))
            page_size = int(payload.get("page_size", 100))

            result = validate_file_for_import(
                file_path,
                column_type_overrides=overrides,
                column_enum_values=enum_values,
                page=page,
                page_size=page_size,
            )
            result["file_path"] = file_path
            return {"validation": result}, 200

        except FileNotFoundError:
            return {"message": f"File not found: {file_path}"}, 404
        except Exception as exc:
            return {"message": "Validation failed.", "error": str(exc)}, 500