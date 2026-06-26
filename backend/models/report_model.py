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

    def __init__(
        self,
        report_format: str,
        migration_id: Optional[int] = None,
        file_path: Optional[str] = None,
        summary: Optional[str] = None,
        user_id: Optional[int] = None,
    ) -> None:
        """Explicit constructor so type checkers recognize all column kwargs.

        SQLAlchemy generates this automatically at runtime; we declare it
        explicitly only to satisfy static analysis tools (Pyrefly / Pylance).
        """
        self.report_format = report_format
        self.migration_id = migration_id
        self.file_path = file_path
        self.summary = summary
        self.user_id = user_id

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "migration_id": self.migration_id,
            "report_format": self.report_format,
            "file_path": self.file_path,
            "summary": self.summary,
            "user_id": self.user_id,
            "created_at": self.created_at.isoformat(),
        }
