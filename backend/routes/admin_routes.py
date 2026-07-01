from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.models.user_model import User
from backend.models.migration_model import Migration
from backend.models.history_model import MigrationHistory
from backend.models.report_model import Report
from backend.utils.decorators import admin_required


from flask import request
from backend.utils.encryption import hash_password

class AdminUserListResource(Resource):
    """Admin-only endpoint to list all registered users."""

    @admin_required
    def get(self):
        users = [user.to_dict() for user in User.query.all()]
        return {"users": users, "count": len(users)}, 200

    @admin_required
    def post(self):
        payload = request.get_json(silent=True) or {}
        username = payload.get("username") or payload.get("fullname")
        email = payload.get("email")
        password = payload.get("password")
        role = payload.get("role", "user")
        is_active = payload.get("is_active", True)
        
        if not username or not email or not password:
            return {"message": "Username, email, and password are required."}, 400
            
        from backend.extensions import db
        if User.query.filter_by(email=email).first():
            return {"message": "User with this email already exists."}, 409
            
        new_user = User(
            username=username,
            email=email,
            password_hash=hash_password(password),
            role=role,
            is_active=is_active
        )
        db.session.add(new_user)
        db.session.commit()
        return {"message": "User created successfully.", "user": new_user.to_dict()}, 201


class AdminUserDetailResource(Resource):
    """Admin-only endpoint to manage a specific user."""

    @admin_required
    def put(self, user_id: int):
        user = User.query.get(user_id)
        if user is None:
            return {"message": "User not found."}, 404
            
        payload = request.get_json(silent=True) or {}
        if "username" in payload or "fullname" in payload:
            user.username = payload.get("username") or payload.get("fullname")
        if "email" in payload:
            user.email = payload.get("email")
        if "password" in payload and payload["password"]:
            user.password_hash = hash_password(payload["password"])
        if "role" in payload:
            user.role = str(payload.get("role")).lower()
        if "is_active" in payload:
            user.is_active = bool(payload.get("is_active"))
            
        from backend.extensions import db
        db.session.commit()
        return {"message": "User updated successfully.", "user": user.to_dict()}, 200

    @admin_required
    def delete(self, user_id: int):

        user = User.query.get(user_id)
        if user is None:
            return {"message": "User not found."}, 404

        from backend.extensions import db
        db.session.delete(user)
        db.session.commit()
        return {"message": f"User {user.username} deleted."}, 200


class AdminStatsResource(Resource):
    """Admin-only endpoint for migration statistics and failed jobs."""

    @admin_required
    def get(self):
        total_users = User.query.count()
        total_migrations = MigrationHistory.query.count()
        total_reports = Report.query.count()
        
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
            "total_reports": total_reports,
            "successful_migrations": successful_migrations,
            "failed_migrations": failed_migrations,
            "recent_migrations": recent_migrations
        }, 200
