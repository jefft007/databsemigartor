from flask import request, send_file
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt
from backend.models.report_model import Report
from backend.models.migration_model import Migration
from backend.models.history_model import MigrationHistory
from backend.models.migration_row_issue_model import MigrationRowIssue
from backend.extensions import db
import json
import os


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
        "flagged",
    ]


def build_report_response(report):
    migration = None

    if getattr(report, "migration_id", None):
        migration = Migration.query.get(report.migration_id)

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
        "summary": getattr(report, "summary", "{}"),
        "file_path": getattr(report, "file_path", None),
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
            for record in history_records:
                raw_summary = safe_json_load(getattr(record, "report_summary", None), default={})

                # Pull row counts from whatever shape the summary was stored in
                rows_imported = (
                    raw_summary.get("rows_imported") or
                    raw_summary.get("total_records") or
                    raw_summary.get("rows_transferred") or
                    0
                )
                rows_failed = (
                    raw_summary.get("rows_failed") or
                    raw_summary.get("failed_count") or
                    0
                )
                rows_cancelled = (
                    raw_summary.get("rows_cancelled") or
                    raw_summary.get("cancelled_count") or
                    0
                )

                # Build a warnings list from the raw summary if present
                warnings_list = raw_summary.get("warnings", [])
                warning_count = int(
                    raw_summary.get("warning_count") or
                    len(warnings_list) or
                    rows_failed or
                    0
                )

                enriched_summary = {
                    **raw_summary,
                    "rows_imported": rows_imported,
                    "total_records": rows_imported,
                    "failed_count": rows_failed,
                    "cancelled_count": rows_cancelled,
                    "warning_count": warning_count,
                    "warnings": warnings_list,
                    "migration_type": getattr(record, "migration_type", None),
                    "source_db": getattr(record, "source_db", "N/A"),
                    "target_db": getattr(record, "target_db", "N/A"),
                    "status": getattr(record, "status", "Generated"),
                }

                history_report = {
                    "id": f"H-{record.id}",
                    "report_name": f"Migration Report H-{record.id}",
                    "type": getattr(record, "migration_type", "Migration Report"),
                    "migration_type": getattr(record, "migration_type", "Migration Report"),
                    "generated_by": "System",
                    "date": record.timestamp.isoformat() if getattr(record, "timestamp", None) else "N/A",
                    "timestamp": record.timestamp.isoformat() if getattr(record, "timestamp", None) else "N/A",
                    "status": getattr(record, "status", "Generated"),
                    "migration_id": None,
                    "source_db": getattr(record, "source_db", "N/A"),
                    "target_db": getattr(record, "target_db", "N/A"),
                    "report_format": "N/A",
                    "summary": json.dumps(enriched_summary, default=str),
                    "report_summary": json.dumps(enriched_summary, default=str),
                    "errors": getattr(record, "errors", None),
                    "file_path": None,
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
        report_format = data.get("report_format") or "pdf"

        if not migration_id:
            query = Migration.query.filter(Migration.status.in_([
                    "completed", "Completed", "complete", "Complete",
                    "success", "Success", "successful", "Successful",
                    "flagged", "Flagged",
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

        # Pull row-level issue data scoped correctly to THIS migration only
        # (fixes the old bug where stats were pulled from whatever
        # MigrationHistory row happened to be created most recently,
        # regardless of which migration it actually belonged to).
        row_issues = MigrationRowIssue.query.filter_by(migration_id=migration.id).all()

        failed_count = sum(1 for r in row_issues if r.status == "failed")
        cancelled_count = sum(1 for r in row_issues if r.status == "cancelled")
        warning_count = sum(1 for r in row_issues if r.status == "warning")

        warnings_list = [
            {"row_index": r.row_index, "table": r.table_name, "reason": r.reason}
            for r in row_issues if r.status == "warning"
        ]
        errors_list = [
            {"row_index": r.row_index, "table": r.table_name, "reason": r.error_message}
            for r in row_issues if r.status == "failed"
        ]

        table_name = row_issues[0].table_name if row_issues else (
            getattr(migration, "target_db", None) or getattr(migration, "migration_type", "table")
        )

        # Shape the data the way build_text_report / build_json_report expect:
        # a list of tables, even when there's only one (file import/export).
        pdf_summary = {
            "source_db": migration.source_db,
            "target_db": migration.target_db,
            "tables": [table_name],
            "summary": [
                {
                    "table": table_name,
                    "status": migration.status,
                    "rows_transferred": None,
                    "error": migration.error_message,
                }
            ],
        }

        from backend.utils.report_generator import generate_pdf_report

        pdf_filename = f"report_migration_{migration.id}.pdf"
        pdf_path = generate_pdf_report(pdf_summary, filename=pdf_filename)

        summary_data = {
            "migration_id": migration.id,
            "migration_type": getattr(migration, "migration_type", None),
            "source_db": getattr(migration, "source_db", None),
            "target_db": getattr(migration, "target_db", None),
            "status": getattr(migration, "status", None),
            "failed_records": failed_count,
            "cancelled_records": cancelled_count,
            "flagged_records": warning_count,
            "warnings": warnings_list,
            "errors": errors_list,
        }

        new_report = Report(
            report_format=report_format,
            migration_id=migration.id,
            file_path=pdf_path,
            summary=json.dumps(summary_data, default=str),
            user_id=user_id,
        )

        db.session.add(new_report)
        db.session.commit()

        return {
            "message": "Report generated successfully.",
            "report": build_report_response(new_report),
        }, 201


class ReportDownloadResource(Resource):
    """Serves the actual generated PDF report file for download."""

    @jwt_required()
    def get(self, report_id):
        user_id = get_jwt_identity()
        role = get_jwt().get("role", "")

        report = Report.query.get(report_id)

        if not report:
            return {"message": "Report not found."}, 404

        if str(role).lower() != "admin" and str(report.user_id) != str(user_id):
            return {"message": "Unauthorized"}, 403

        if not report.file_path or not os.path.exists(report.file_path):
            return {"message": "Report file not found on disk. It may have been cleared from temp storage."}, 404

        download_name = f"migration_report_{report.migration_id}.pdf"

        return send_file(
            report.file_path,
            as_attachment=True,
            download_name=download_name,
            mimetype="application/pdf",
        )