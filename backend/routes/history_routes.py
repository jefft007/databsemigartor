from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt

from backend.models.history_model import MigrationHistory
from backend.extensions import db


class HistoryListResource(Resource):
    """Endpoint to list migration history records."""
    @jwt_required()
    def get(self):
        user_id = get_jwt_identity()
        claims = get_jwt()
        role = claims.get("role", "")
        
        if str(role).lower() == "admin":
            records = MigrationHistory.query.order_by(MigrationHistory.timestamp.desc()).all()
        else:
            records = MigrationHistory.query.filter_by(user_id=user_id).order_by(MigrationHistory.timestamp.desc()).all()
            
        history = [record.to_dict() for record in records]

        return {
            "history": history,
            "count": len(history)
        }, 200


class HistoryDeleteResource(Resource):
    """Endpoint to delete a migration history record by ID."""
    @jwt_required()
    def delete(self, history_id: int):
        user_id = get_jwt_identity()
        claims = get_jwt()
        role = claims.get("role", "")
        
        record = MigrationHistory.query.get(history_id)

        if record is None:
            return {
                "message": "History record not found."
            }, 404
            
        if str(role).lower() != "admin" and str(record.user_id) != str(user_id):
            return {"message": "Unauthorized"}, 403

        db.session.delete(record)
        db.session.commit()

        return {
            "message": "History record deleted successfully."
        }, 200
