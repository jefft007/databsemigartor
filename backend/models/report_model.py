from datetime import datetime
from typing import Optional
from backend.extensions import db


class Report(db.Model):
    """Stores report metadata and exported file paths."""
    __tablename__ = "reports"

    id = db.Column(db.Integer, primary_key=True)
    migration_id = db.Column(db.Integer, db.ForeignKey("migrations.id"), nullable=True)
    report_format = db.Column(db.String(20), nullable=False)
    file_path = db.Column(db.String(512), nullable=True)
    summary = db.Column(db.Text, nullable=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    migration_type = db.Column(db.String(120), nullable=True)
    source_db = db.Column(db.String(255), nullable=True)
    target_db = db.Column(db.String(255), nullable=True)
    source_table = db.Column(db.String(255), nullable=True)
    target_table = db.Column(db.String(255), nullable=True)
    rows_processed = db.Column(db.Integer, default=0)
    rows_migrated = db.Column(db.Integer, default=0)
    rows_failed = db.Column(db.Integer, default=0)
    warnings = db.Column(db.Integer, default=0)
    started_at = db.Column(db.DateTime, nullable=True)
    completed_at = db.Column(db.DateTime, nullable=True)
    duration = db.Column(db.String(50), nullable=True)
    status = db.Column(db.String(80), nullable=True)

    def __init__(
        self,
        report_format: str,
        migration_id: Optional[int] = None,
        file_path: Optional[str] = None,
        summary: Optional[str] = None,
        user_id: Optional[int] = None,
        migration_type: Optional[str] = None,
        source_db: Optional[str] = None,
        target_db: Optional[str] = None,
        source_table: Optional[str] = None,
        target_table: Optional[str] = None,
        rows_processed: int = 0,
        rows_migrated: int = 0,
        rows_failed: int = 0,
        warnings: int = 0,
        started_at: Optional[datetime] = None,
        completed_at: Optional[datetime] = None,
        duration: Optional[str] = None,
        status: Optional[str] = None,
    ) -> None:
        """Explicit constructor so type checkers recognize all column kwargs."""
        self.report_format = report_format
        self.migration_id = migration_id
        self.file_path = file_path
        self.summary = summary
        self.user_id = user_id
        self.migration_type = migration_type
        self.source_db = source_db
        self.target_db = target_db
        self.source_table = source_table
        self.target_table = target_table
        self.rows_processed = rows_processed
        self.rows_migrated = rows_migrated
        self.rows_failed = rows_failed
        self.warnings = warnings
        self.started_at = started_at
        self.completed_at = completed_at
        self.duration = duration
        self.status = status

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "migration_id": self.migration_id,
            "report_format": self.report_format,
            "file_path": self.file_path,
            "summary": self.summary,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "migration_type": self.migration_type,
            "source_db": self.source_db,
            "target_db": self.target_db,
            "source_table": self.source_table,
            "target_table": self.target_table,
            "rows_processed": self.rows_processed,
            "rows_migrated": self.rows_migrated,
            "rows_failed": self.rows_failed,
            "warnings": self.warnings,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "duration": self.duration,
            "status": self.status,
        }
