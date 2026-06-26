"""
Database model for tracking failed and cancelled rows during migration.
"""

from backend.extensions import db
from datetime import datetime
import json


class MigrationRowIssue(db.Model):
    """Track rows that fail or are cancelled during migration for debugging and recovery."""
    
    __tablename__ = 'migration_row_issues'
    
    id = db.Column(db.Integer, primary_key=True)
    migration_id = db.Column(db.Integer, db.ForeignKey('migrations.id'), nullable=False)
    table_name = db.Column(db.String(255), nullable=False)
    row_index = db.Column(db.Integer, nullable=False)
    status = db.Column(db.String(50), nullable=False)  # 'failed' or 'cancelled'
    reason = db.Column(db.Text)
    error_message = db.Column(db.Text)
    row_data = db.Column(db.Text)  # JSON string of the row
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __init__(self, migration_id, table_name, row_index, status, reason=None, error_message=None, row_data=None):
        self.migration_id = migration_id
        self.table_name = table_name
        self.row_index = row_index
        self.status = status
        self.reason = reason
        self.error_message = error_message
        self.row_data = json.dumps(row_data) if row_data else None
    
    def to_dict(self):
        """Convert to dictionary for API responses."""
        return {
            'id': self.id,
            'migration_id': self.migration_id,
            'table_name': self.table_name,
            'row_index': self.row_index,
            'status': self.status,
            'reason': self.reason,
            'error_message': self.error_message,
            'row_data': json.loads(self.row_data) if self.row_data else None,
            'created_at': self.created_at.isoformat(),
        }
