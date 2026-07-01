from datetime import datetime
from backend.extensions import db


class MigrationHistory(db.Model):
    """Stores migration history, validation results, and execution metadata."""
    __tablename__ = "migration_history"

    id = db.Column(db.Integer, primary_key=True)
    migration_type = db.Column(db.String(120), nullable=False)
    source_db = db.Column(db.String(255), nullable=False)
    target_db = db.Column(db.String(255), nullable=False)
    source_table = db.Column(db.String(255), nullable=True)
    target_table = db.Column(db.String(255), nullable=True)
    status = db.Column(db.String(80), nullable=False)
    errors = db.Column(db.Text, nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.utcnow)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    duration = db.Column(db.String(50), nullable=True)
    report_summary = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    user = db.relationship("User", lazy="joined")

    def to_dict(self) -> dict:
        is_flagged = False
        failed_count = 0
        warnings_count = 0
        success_count = 0

        if self.errors:
            is_flagged = True
        
        if self.report_summary:
            import json
            try:
                summary_data = json.loads(self.report_summary)
                if isinstance(summary_data, list):
                    for item in summary_data:
                        failed_count += int(item.get("rows_failed") or 0)
                        failed_count += int(item.get("rows_cancelled") or 0)
                        success_count += int(item.get("rows_transferred") or 0)
                        success_count += int(item.get("rows_imported") or 0)
                        if item.get("warnings"):
                            warnings_count += len(item.get("warnings"))
                elif isinstance(summary_data, dict):
                    failed_count += int(summary_data.get("rows_failed") or 0)
                    failed_count += int(summary_data.get("rows_cancelled") or 0)
                    success_count += int(summary_data.get("rows_transferred") or 0)
                    success_count += int(summary_data.get("rows_imported") or 0)
                    if summary_data.get("warnings"):
                        warnings_count += len(summary_data.get("warnings"))
            except Exception:
                pass
        
        if failed_count > 0 or warnings_count > 0:
            is_flagged = True

        total_records = success_count + failed_count

        return {
            "id": self.id,
            "migration_type": self.migration_type,
            "source_db": self.source_db,
            "target_db": self.target_db,
            "source_table": self.source_table,
            "target_table": self.target_table,
            "status": self.status,
            "errors": self.errors,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration": self.duration,
            "report_summary": self.report_summary,
            "user_id": self.user_id,
            "user_name": getattr(self.user, "username", None) if getattr(self, "user", None) else None,
            "user_email": getattr(self.user, "email", None) if getattr(self, "user", None) else None,
            "is_flagged": is_flagged,
            "failed_count": failed_count,
            "warnings_count": warnings_count,
            "success_count": success_count,
            "total_records": total_records,
        }
