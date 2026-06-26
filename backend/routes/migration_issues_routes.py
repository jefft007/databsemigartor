"""
API routes for viewing and managing migration row issues (failed/cancelled rows).
"""

from flask import request
from flask_restful import Resource
from backend.extensions import db
from backend.models.migration_row_issue_model import MigrationRowIssue
from backend.models.migration_model import Migration


class MigrationRowIssuesResource(Resource):
    """Endpoint to view and manage row-level migration issues."""
    
    def get(self, migration_id=None):
        """Get failed/cancelled rows for a specific migration or all migrations."""
        try:
            if migration_id:
                # Validate migration exists
                migration = Migration.query.get(migration_id)
                if not migration:
                    return {"error": "Migration not found"}, 404
                
                issues = MigrationRowIssue.query.filter_by(migration_id=migration_id).all()
            else:
                # Get all issues
                issues = MigrationRowIssue.query.all()
            
            return {
                "total_issues": len(issues),
                "issues": [issue.to_dict() for issue in issues],
            }, 200
        
        except Exception as e:
            return {"error": str(e)}, 500
    
    def get_by_table(self, migration_id, table_name):
        """Get issues for a specific table in a migration."""
        try:
            migration = Migration.query.get(migration_id)
            if not migration:
                return {"error": "Migration not found"}, 404
            
            issues = MigrationRowIssue.query.filter_by(
                migration_id=migration_id,
                table_name=table_name
            ).all()
            
            failed = [i for i in issues if i.status == "failed"]
            cancelled = [i for i in issues if i.status == "cancelled"]
            
            return {
                "table_name": table_name,
                "total_issues": len(issues),
                "failed_count": len(failed),
                "cancelled_count": len(cancelled),
                "failed_rows": [i.to_dict() for i in failed],
                "cancelled_rows": [i.to_dict() for i in cancelled],
            }, 200
        
        except Exception as e:
            return {"error": str(e)}, 500


class MigrationRetryFailedRowsResource(Resource):
    """Endpoint to retry migration of failed rows."""
    
    def post(self, migration_id):
        """Retry migration of specific failed rows."""
        try:
            payload = request.get_json() or {}
            row_issue_ids = payload.get("row_issue_ids", [])
            
            if not row_issue_ids:
                return {"error": "No row IDs specified"}, 400
            
            migration = Migration.query.get(migration_id)
            if not migration:
                return {"error": "Migration not found"}, 404
            
            issues = MigrationRowIssue.query.filter(
                MigrationRowIssue.id.in_(row_issue_ids),
                MigrationRowIssue.migration_id == migration_id
            ).all()
            
            retry_results = {
                "attempted": len(issues),
                "successful": 0,
                "failed": 0,
                "details": []
            }
            
            for issue in issues:
                try:
                    # Attempt to reinsert the row data
                    import json
                    import pandas as pd
                    from backend.database.connection_manager import create_engine_for_config
                    
                    row_data = json.loads(issue.row_data)
                    df = pd.DataFrame([row_data])
                    
                    # Create target engine from migration config
                    target_config = {
                        "db_type": migration.target_db.split("://")[0],
                        "host": "localhost",
                        "database": "target_db"
                    }
                    
                    target_engine = create_engine_for_config(target_config)
                    df.to_sql(issue.table_name, target_engine, if_exists="append", index=False)
                    
                    # Mark as resolved
                    db.session.delete(issue)
                    db.session.commit()
                    
                    retry_results["successful"] += 1
                    retry_results["details"].append({
                        "row_id": issue.id,
                        "status": "recovered"
                    })
                
                except Exception as e:
                    retry_results["failed"] += 1
                    retry_results["details"].append({
                        "row_id": issue.id,
                        "status": "failed_retry",
                        "error": str(e)
                    })
            
            return retry_results, 200
        
        except Exception as e:
            return {"error": str(e)}, 500


class MigrationSummaryResource(Resource):
    """Get a summary of migration issues."""
    
    def get(self, migration_id):
        """Get summary statistics for a migration."""
        try:
            migration = Migration.query.get(migration_id)
            if not migration:
                return {"error": "Migration not found"}, 404
            
            all_issues = MigrationRowIssue.query.filter_by(migration_id=migration_id).all()
            
            failed_count = sum(1 for i in all_issues if i.status == "failed")
            cancelled_count = sum(1 for i in all_issues if i.status == "cancelled")
            
            tables = {}
            for issue in all_issues:
                if issue.table_name not in tables:
                    tables[issue.table_name] = {"failed": 0, "cancelled": 0}
                if issue.status == "failed":
                    tables[issue.table_name]["failed"] += 1
                else:
                    tables[issue.table_name]["cancelled"] += 1
            
            return {
                "migration_id": migration_id,
                "total_issues": len(all_issues),
                "failed_rows": failed_count,
                "cancelled_rows": cancelled_count,
                "tables_affected": tables,
            }, 200
        
        except Exception as e:
            return {"error": str(e)}, 500
