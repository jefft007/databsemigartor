from flask import request
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from backend.models.report_model import Report
from backend.models.migration_model import Migration
from backend.models.history_model import MigrationHistory
from backend.extensions import db
import json


def safe_json_load(value, default=None):
    if default is None:
        default = {}

    if value is None:
        return default

    if isinstance(value, (dict, list)):
        return value

    try:
        return json.loads(value)
    except Exception:
        return default


def normalize_status(status):
    return (status or "").strip().lower()


def is_completed_status(status):
    return normalize_status(status) in [
        "completed",
        "complete",
        "success",
        "successful",
    ]


def build_report_response(report):
    migration = None
    history = None

    if getattr(report, "migration_id", None):
        migration = Migration.query.get(report.migration_id)

    if migration:
        history = (
            MigrationHistory.query
            .order_by(MigrationHistory.id.desc())
            .first()
        )

    report_summary = getattr(report, "summary", "{}")

    if history and getattr(history, "report_summary", None):
        report_summary = history.report_summary

    return {
        "id": report.id,
        "report_name": f"Migration Report #{report.id}",
        "type": getattr(migration, "migration_type", "Migration Report") if migration else "Migration Report",
        "generated_by": "System",
        "date": report.created_at.isoformat() if getattr(report, "created_at", None) else "N/A",
        "status": getattr(migration, "status", "Generated") if migration else "Generated",
        "migration_id": getattr(report, "migration_id", None),
        "source_db": getattr(migration, "source_db", "N/A") if migration else "N/A",
        "target_db": getattr(migration, "target_db", "N/A") if migration else "N/A",
        "report_format": getattr(report, "report_format", ".sql"),
        "summary": getattr(report, "summary", "{}")
    }


class ReportResource(Resource):
    @jwt_required()
    def delete(self, report_id):
        user_id = get_jwt_identity()
        role = get_jwt().get("role", "")
        report = Report.query.get(report_id)

        if not report:
            return {"message": "Report not found"}, 404

        if str(role).lower() != "admin" and str(report.user_id) != str(user_id):
            return {"message": "Unauthorized"}, 403

        db.session.delete(report)
        db.session.commit()

        return {"message": "Report deleted successfully"}, 200


class ReportsListResource(Resource):
    @jwt_required()
    def get(self):
        user_id = get_jwt_identity()
        role = get_jwt().get("role", "")
        
        try:
            if str(role).lower() == "admin":
                reports = Report.query.order_by(Report.id.desc()).all()
                history_records = MigrationHistory.query.order_by(MigrationHistory.timestamp.desc()).all()
            else:
                reports = Report.query.filter_by(user_id=user_id).order_by(Report.id.desc()).all()
                history_records = MigrationHistory.query.filter_by(user_id=user_id).order_by(MigrationHistory.timestamp.desc()).all()
                
            report_results = [build_report_response(report) for report in reports]
            
            # Since MigrationHistory doesn't have migration_id, we can't reliably deduplicate by migration_id.
            # Just append them if they don't exactly match generated reports, or simply append them all.
            # We will rely on frontend deduplication if needed, or just return them as historical reports.
            for record in history_records:
                # Create a mock report response for old history records
                history_report = {
                    "id": f"H-{record.id}",
                    "report_name": f"Migration Report H-{record.id}",
                    "type": getattr(record, "migration_type", "Migration Report"),
                    "generated_by": "System",
                    "date": record.timestamp.isoformat() if getattr(record, "timestamp", None) else "N/A",
                    "status": getattr(record, "status", "Generated"),
                    "migration_id": None,
                    "source_db": getattr(record, "source_db", "N/A"),
                    "target_db": getattr(record, "target_db", "N/A"),
                    "report_format": "N/A",
                    "summary": "{}"
                }
                report_results.append(history_report)
                
            return {
                "reports": report_results,
                "history": report_results,
                "summary": {
                    "total_reports": len(report_results),
                    "reports_generated": len(report_results),
                },
            }, 200
        except Exception as e:
            return {
                "message": str(e)
            }, 500


class ReportGenerateResource(Resource):
    @jwt_required()
    def post(self):
        user_id = get_jwt_identity()
        role = get_jwt().get("role", "")
        
        data = request.get_json() or {}

        migration_id = data.get("migration_id")
        report_format = data.get("report_format") or ".sql"

        if not migration_id:
            query = Migration.query.filter(Migration.status.in_([
                    "completed", "Completed", "complete", "Complete",
                    "success", "Success", "successful", "Successful"
                ]))
            if str(role).lower() != "admin":
                query = query.filter_by(user_id=user_id)
            
            completed_migrations = query.order_by(Migration.id.desc()).all()

            # Find the latest one that doesn't have a report yet
            migration_id_to_use = None
            for mig in completed_migrations:
                existing = Report.query.filter_by(migration_id=mig.id).first()
                if not existing:
                    migration_id_to_use = mig.id
                    break
            
            if not migration_id_to_use:
                return {
                    "message": "Reports already exist for all completed migrations."
                }, 400
                
            migration_id = migration_id_to_use

        migration = Migration.query.get(migration_id)

        if not migration:
            return {"message": "Migration not found."}, 404

        if not is_completed_status(migration.status):
            return {
                "message": "Can only generate reports for completed migrations."
            }, 400

        existing_report = Report.query.filter_by(migration_id=migration.id).first()

        if existing_report:
            return {
                "message": "Report already exists for this migration.",
                "report": build_report_response(existing_report),
            }, 200

        history = (
            MigrationHistory.query
            .order_by(MigrationHistory.id.desc())
            .first()
        )

        history_summary = (
            safe_json_load(getattr(history, "report_summary", None), {})
            if history
            else {}
        )

        summary_data = {
            "migration_id": migration.id,
            "migration_type": getattr(migration, "migration_type", None),
            "source_db": getattr(migration, "source_db", None),
            "target_db": getattr(migration, "target_db", None),
            "status": getattr(migration, "status", None),
            "total_records": history_summary.get("total_records", history_summary.get("total", 0)),
            "successful_records": history_summary.get("successful_records", history_summary.get("success", 0)),
            "failed_records": history_summary.get("failed_records", history_summary.get("failed", 0)),
            "flagged_records": history_summary.get("flagged_records", history_summary.get("flagged", 0)),
            "warnings": getattr(history, "warnings", None) if history else None,
            "errors": getattr(history, "errors", None) if history else None,
        }

        new_report = Report(
            report_format=report_format,
            migration_id=migration.id,
            summary=json.dumps(summary_data),
            user_id=user_id,
        )

        db.session.add(new_report)
        db.session.commit()

        return {
            "message": "Report generated successfully.",
            "report": build_report_response(new_report),
        }, 201