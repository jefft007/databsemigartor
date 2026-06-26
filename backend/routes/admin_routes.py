from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.models.user_model import User
from backend.models.migration_model import Migration
from backend.models.history_model import MigrationHistory
from backend.utils.decorators import admin_required


class AdminUserListResource(Resource):
    """Admin-only endpoint to list all registered users."""

    @admin_required
    def get(self):

        users = [user.to_dict() for user in User.query.all()]
        return {"users": users, "count": len(users)}, 200


class AdminUserDeleteResource(Resource):
    """Admin-only endpoint to delete a specific user."""

    @admin_required
    def delete(self, user_id: int):

        user = User.query.get(user_id)
        if user is None:
            return {"message": "User not found."}, 404

        User.query.filter_by(id=user.id).delete()
        from backend.extensions import db
        db.session.commit()
        return {"message": f"User {user.username} deleted."}, 200


class AdminStatsResource(Resource):
    """Admin-only endpoint for migration statistics and failed jobs."""

    @admin_required
    def get(self):
        total_users = User.query.count()
        total_migrations = MigrationHistory.query.count()
        
        successful_migrations = MigrationHistory.query.filter(
            MigrationHistory.status.ilike("%success%") | MigrationHistory.status.ilike("%completed%")
        ).count()
        
        failed_migrations = MigrationHistory.query.filter(
            MigrationHistory.status.ilike("%failed%")
        ).count()

        recent_records = MigrationHistory.query.order_by(MigrationHistory.timestamp.desc()).limit(10).all()
        recent_migrations = []
        for r in recent_records:
            d = r.to_dict()
            recent_migrations.append({
                "id": d["id"],
                "user_name": d.get("user_name") or "Unknown",
                "user_email": d.get("user_email") or "Unknown",
                "source_type": d["source_db"],
                "target_type": d["target_db"],
                "status": d["status"],
                "created_at": d["timestamp"]
            })

        return {
            "total_users": total_users,
            "total_migrations": total_migrations,
            "successful_migrations": successful_migrations,
            "failed_migrations": failed_migrations,
            "recent_migrations": recent_migrations
        }, 200
