from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.models.history_model import MigrationHistory
from backend.models.report_model import Report

class UserStatsResource(Resource):
    """Endpoint to fetch migration statistics for the current user."""

    @jwt_required()
    def get(self):
        user_id = get_jwt_identity()
        
        total_migrations = MigrationHistory.query.filter_by(user_id=user_id).count()
        total_reports = Report.query.filter_by(user_id=user_id).count()
        
        successful_migrations = MigrationHistory.query.filter(
            MigrationHistory.user_id == user_id,
            (MigrationHistory.status.ilike("%success%") | MigrationHistory.status.ilike("%completed%"))
        ).count()
        
        failed_migrations = MigrationHistory.query.filter(
            MigrationHistory.user_id == user_id,
            MigrationHistory.status.ilike("%failed%")
        ).count()

        recent_records = MigrationHistory.query.filter_by(user_id=user_id).order_by(MigrationHistory.timestamp.desc()).limit(10).all()
        recent_migrations = []
        for r in recent_records:
            d = r.to_dict()
            recent_migrations.append({
                "id": d["id"],
                "source_type": d["source_db"],
                "target_type": d["target_db"],
                "status": d["status"],
                "created_at": d["timestamp"]
            })

        return {
            "total_migrations": total_migrations,
            "total_reports": total_reports,
            "successful_migrations": successful_migrations,
            "failed_migrations": failed_migrations,
            "recent_migrations": recent_migrations
        }, 200
