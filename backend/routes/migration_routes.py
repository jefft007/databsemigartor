from flask import request
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity
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
from datetime import datetime, timezone

def format_duration(td):
    total_seconds = int(td.total_seconds())
    minutes, seconds = divmod(total_seconds, 60)
    hours, minutes = divmod(minutes, 60)
    if hours > 0:
        return f"{hours} hr {minutes} min {seconds} sec"
    if minutes > 0:
        return f"{minutes} min {seconds} sec"
    return f"{seconds} sec"


class SqlToSqlResource(Resource):
    """Endpoint to migrate tables from one SQL database to another."""

    @jwt_required(optional=True)
    def post(self):
        user_id = get_jwt_identity()
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

        started_at = datetime.now(timezone.utc)
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
            completed_at = datetime.now(timezone.utc)
            duration_td = completed_at - started_at
            duration_str = format_duration(duration_td)
            
            migration_record.status = "completed"
            report = Report(
                migration_id=migration_record.id,
                report_format="json",
                file_path="",
                summary=json.dumps(
                    report_data.get("summary", []),
                    default=str
                ),
                user_id=user_id,
                migration_type="sql_to_sql",
                source_db=migration_record.source_db,
                target_db=migration_record.target_db,
                source_table="Multiple" if len(payload.get("tables", [])) > 1 else payload.get("tables", [""])[0] if payload.get("tables") else "",
                target_table="Multiple" if len(payload.get("tables", [])) > 1 else payload.get("tables", [""])[0] if payload.get("tables") else "",
                started_at=started_at,
                completed_at=completed_at,
                duration=duration_str,
                status="completed"
            )
            db.session.add(report)
            db.session.commit()
            migration_record.report_id = report.id
            db.session.commit()
            history = MigrationHistory(
                migration_type="sql_to_sql",
                source_db=migration_record.source_db,
                target_db=migration_record.target_db,
                source_table="Multiple" if len(payload.get("tables", [])) > 1 else payload.get("tables", [""])[0] if payload.get("tables") else "",
                target_table="Multiple" if len(payload.get("tables", [])) > 1 else payload.get("tables", [""])[0] if payload.get("tables") else "",
                status="completed",
                errors=None,
                report_summary=report.summary,
                user_id=user_id,
                started_at=started_at,
                completed_at=completed_at,
                duration=duration_str
            )
            db.session.add(history)
            db.session.commit()
            return {
                "message": "Migration completed.",
                "report": report_data
            }, 200
        except Exception as exc:
            completed_at = datetime.now(timezone.utc)
            duration_td = completed_at - started_at
            duration_str = format_duration(duration_td)
            
            migration_record.status = "failed"
            migration_record.error_message = str(exc)
            db.session.rollback()
            db.session.add(migration_record)
            db.session.commit()
            history = MigrationHistory(
                migration_type="sql_to_sql",
                source_db=migration_record.source_db,
                target_db=migration_record.target_db,
                source_table="Multiple" if len(payload.get("tables", [])) > 1 else payload.get("tables", [""])[0] if payload.get("tables") else "",
                target_table="Multiple" if len(payload.get("tables", [])) > 1 else payload.get("tables", [""])[0] if payload.get("tables") else "",
                status="failed",
                errors=str(exc),
                report_summary="Migration failed.",
                user_id=user_id,
                started_at=started_at,
                completed_at=completed_at,
                duration=duration_str
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

        started_at = datetime.now(timezone.utc)
        migration_record = Migration(
            migration_type="file_to_sql",
            source_db="file",
            target_db=payload.get("target_db_type") or "sqlite",
            status="running",
        )
        db.session.add(migration_record)
        db.session.commit()

        try:
            import_result = import_file_to_sql(payload)
            completed_at = datetime.now(timezone.utc)
            duration_td = completed_at - started_at
            duration_str = format_duration(duration_td)
            
            migration_report = import_result.get("migration_report", {}).get("summary", {})
            failed = migration_report.get("failed", 0)
            cancelled = migration_report.get("cancelled", 0)
            status = "completed"
            if failed > 0 or cancelled > 0:
                status = "Completed with Warnings"
                
            migration_record.status = status
            
            report = Report(
                migration_id=migration_record.id,
                report_format="json",
                file_path="",
                summary=json.dumps(import_result, default=str),
                user_id=get_jwt_identity() if request.headers.get("Authorization") else None,
                migration_type="file_to_sql",
                source_db="file",
                target_db=migration_record.target_db,
                source_table="file",
                target_table=payload.get("target_table", "table"),
                started_at=started_at,
                completed_at=completed_at,
                duration=duration_str,
                status=status
            )
            db.session.add(report)
            db.session.commit()
            migration_record.report_id = report.id
            db.session.commit()
            
            history = MigrationHistory(
                migration_type="file_to_sql",
                source_db="file",
                target_db=migration_record.target_db,
                source_table="file",
                target_table=payload.get("target_table", "table"),
                status=status,
                errors=None,
                report_summary=report.summary,
                user_id=get_jwt_identity() if request.headers.get("Authorization") else None,
                started_at=started_at,
                completed_at=completed_at,
                duration=duration_str
            )
            db.session.add(history)
            db.session.commit()

            return make_json_safe({"message": "File import completed.", "result": import_result}), 200
        except FileValidationError as exc:
            migration_record.status = "failed"
            migration_record.error_message = str(exc)
            db.session.commit()
            return make_json_safe({
                "message": "Import blocked: the file still contains missing values.",
                "rejected": True,
                "warning_count": len(exc.issues),
                "warnings": exc.issues,
            }), 400
        except FileNotFoundError:
            migration_record.status = "failed"
            migration_record.error_message = f"File not found: {file_path}"
            db.session.commit()
            return {"message": f"File not found: {file_path}"}, 404
        except Exception as exc:
            completed_at = datetime.now(timezone.utc)
            duration_td = completed_at - started_at
            duration_str = format_duration(duration_td)
            
            migration_record.status = "failed"
            migration_record.error_message = str(exc)
            db.session.commit()
            
            history = MigrationHistory(
                migration_type="file_to_sql",
                source_db="file",
                target_db=migration_record.target_db,
                source_table="file",
                target_table=payload.get("target_table", "table"),
                status="failed",
                errors=str(exc),
                report_summary="Migration failed.",
                user_id=get_jwt_identity() if request.headers.get("Authorization") else None,
                started_at=started_at,
                completed_at=completed_at,
                duration=duration_str
            )
            db.session.add(history)
            db.session.commit()
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

        started_at = datetime.now(timezone.utc)
        migration_record = Migration(
            migration_type="file_to_sql",
            source_db="file",
            target_db=payload.get("target_db_type") or "sqlite",
            status="running",
        )
        db.session.add(migration_record)
        db.session.commit()

        try:
            import_result = import_corrected_file_to_sql(payload)
            completed_at = datetime.now(timezone.utc)
            duration_td = completed_at - started_at
            duration_str = format_duration(duration_td)
            
            migration_report = import_result.get("migration_report", {}).get("summary", {})
            failed = migration_report.get("failed", 0)
            cancelled = migration_report.get("cancelled", 0)
            status = "completed"
            if failed > 0 or cancelled > 0:
                status = "Completed with Warnings"
                
            migration_record.status = status
            
            report = Report(
                migration_id=migration_record.id,
                report_format="json",
                file_path="",
                summary=json.dumps(import_result, default=str),
                user_id=get_jwt_identity() if request.headers.get("Authorization") else None,
                migration_type="file_to_sql",
                source_db="file",
                target_db=migration_record.target_db,
                source_table="file",
                target_table=payload.get("target_table", "table"),
                started_at=started_at,
                completed_at=completed_at,
                duration=duration_str,
                status=status
            )
            db.session.add(report)
            db.session.commit()
            migration_record.report_id = report.id
            db.session.commit()
            
            history = MigrationHistory(
                migration_type="file_to_sql",
                source_db="file",
                target_db=migration_record.target_db,
                source_table="file",
                target_table=payload.get("target_table", "table"),
                status=status,
                errors=None,
                report_summary=report.summary,
                user_id=get_jwt_identity() if request.headers.get("Authorization") else None,
                started_at=started_at,
                completed_at=completed_at,
                duration=duration_str
            )
            db.session.add(history)
            db.session.commit()

            return make_json_safe({"message": "File import completed.", "result": import_result}), 200
        except FileValidationError as exc:
            migration_record.status = "failed"
            migration_record.error_message = str(exc)
            db.session.commit()
            return make_json_safe({
                "message": "Import blocked: some rows still have missing values after correction.",
                "rejected": True,
                "warning_count": len(exc.issues),
                "warnings": exc.issues,
            }), 400
        except FileNotFoundError:
            migration_record.status = "failed"
            migration_record.error_message = f"File not found: {file_path}"
            db.session.commit()
            return {"message": f"File not found: {file_path}"}, 404
        except Exception as exc:
            completed_at = datetime.now(timezone.utc)
            duration_td = completed_at - started_at
            duration_str = format_duration(duration_td)
            
            migration_record.status = "failed"
            migration_record.error_message = str(exc)
            db.session.commit()
            
            history = MigrationHistory(
                migration_type="file_to_sql",
                source_db="file",
                target_db=migration_record.target_db,
                source_table="file",
                target_table=payload.get("target_table", "table"),
                status="failed",
                errors=str(exc),
                report_summary="Migration failed.",
                user_id=get_jwt_identity() if request.headers.get("Authorization") else None,
                started_at=started_at,
                completed_at=completed_at,
                duration=duration_str
            )
            db.session.add(history)
            db.session.commit()
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

        started_at = datetime.now(timezone.utc)
        migration_record = Migration(
            migration_type="sql_to_file",
            source_db=payload.get("source_db_type", "sqlite"),
            target_db="file",
            status="running",
        )
        db.session.add(migration_record)
        db.session.commit()

        try:
            export_result = export_sql_to_file(payload)
            completed_at = datetime.now(timezone.utc)
            duration_td = completed_at - started_at
            duration_str = format_duration(duration_td)
            
            migration_record.status = "completed"
            
            report = Report(
                migration_id=migration_record.id,
                report_format="json",
                file_path="",
                summary=json.dumps(export_result, default=str),
                user_id=get_jwt_identity() if request.headers.get("Authorization") else None,
                migration_type="sql_to_file",
                source_db=migration_record.source_db,
                target_db="file",
                source_table=source_table,
                target_table="file",
                started_at=started_at,
                completed_at=completed_at,
                duration=duration_str,
                status="completed"
            )
            db.session.add(report)
            db.session.commit()
            migration_record.report_id = report.id
            db.session.commit()
            
            history = MigrationHistory(
                migration_type="sql_to_file",
                source_db=migration_record.source_db,
                target_db="file",
                source_table=source_table,
                target_table="file",
                status="completed",
                errors=None,
                report_summary=report.summary,
                user_id=get_jwt_identity() if request.headers.get("Authorization") else None,
                started_at=started_at,
                completed_at=completed_at,
                duration=duration_str
            )
            db.session.add(history)
            db.session.commit()

            return {"message": "Export completed.", "result": export_result}, 200
        except ValueError as exc:
            migration_record.status = "failed"
            migration_record.error_message = str(exc)
            db.session.commit()
            return {"message": str(exc)}, 400
        except Exception as exc:
            completed_at = datetime.now(timezone.utc)
            duration_td = completed_at - started_at
            duration_str = format_duration(duration_td)
            
            migration_record.status = "failed"
            migration_record.error_message = str(exc)
            db.session.commit()
            
            history = MigrationHistory(
                migration_type="sql_to_file",
                source_db=migration_record.source_db,
                target_db="file",
                source_table=source_table,
                target_table="file",
                status="failed",
                errors=str(exc),
                report_summary="Export failed.",
                user_id=get_jwt_identity() if request.headers.get("Authorization") else None,
                started_at=started_at,
                completed_at=completed_at,
                duration=duration_str
            )
            db.session.add(history)
            db.session.commit()
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


import pandas as pd
import numpy as np
from datetime import date, datetime
from flask import jsonify

def make_json_safe(value):
    from datetime import datetime, date
    import pandas as pd
    import numpy as np

    if isinstance(value, dict):
        return {k: make_json_safe(v) for k, v in value.items()}

    if isinstance(value, list):
        return [make_json_safe(v) for v in value]

    if isinstance(value, tuple):
        return [make_json_safe(v) for v in value]

    if isinstance(value, (datetime, date)):
        return value.isoformat()

    if isinstance(value, pd.Timestamp):
        return value.isoformat()

    if isinstance(value, np.integer):
        return int(value)

    if isinstance(value, np.floating):
        return float(value)

    if isinstance(value, np.bool_):
        return bool(value)

    try:
        if pd.isna(value):
            return None
    except Exception:
        pass

    return value

class FileValidateResource(Resource):
    """Validate a file before importing — returns all rows with issue flags.
    Does NOT write to any database.
    """

    def post(self):
        import json as _json
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

        if "<FRONTEND" in str(file_path):
            return {"message": "Replace placeholder file path with a real file path."}, 400

        try:
            overrides_raw = payload.get("column_type_overrides") or "{}"

            if isinstance(overrides_raw, str):
                overrides = _json.loads(overrides_raw)
            else:
                overrides = overrides_raw

            enum_values_raw = payload.get("column_enum_values") or "{}"
            if isinstance(enum_values_raw, str):
                enum_values = _json.loads(enum_values_raw)
            else:
                enum_values = enum_values_raw

            corrections_raw = payload.get("corrections") or "{}"
            if isinstance(corrections_raw, str):
                corrections = _json.loads(corrections_raw)
            else:
                corrections = corrections_raw

            page = int(payload.get("page", 1))
            page_size = int(payload.get("page_size", 100))

            result = validate_file_for_import(
                file_path=file_path,
                column_type_overrides=overrides,
                column_enum_values=enum_values,
                corrections=corrections,
                page=page,
                page_size=page_size,
            )

            result["file_path"] = file_path
            
            
            return make_json_safe(result), 200

        except FileNotFoundError:
            return {"message": f"File not found: {file_path}"}, 404

        except Exception as exc:
            return {"message": "Validation failed.", "error": str(exc)}, 500