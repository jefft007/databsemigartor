import re

with open(r"c:\Users\jefft\Updated-SQLMigrator\backend\routes\history_routes.py", "r", encoding="utf-8") as f:
    content = f.read()

if "from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt" not in content:
    content = content.replace(
        "from flask_jwt_extended import jwt_required",
        "from flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt"
    )

get_replacement = """    @jwt_required()
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
        }, 200"""

content = re.sub(r'(\s+@jwt_required\(\)\s+def get\(self\):[\s\S]*?\}, 200)', get_replacement, content)

delete_replacement = """    @jwt_required()
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
        }, 200"""

content = re.sub(r'(\s+@jwt_required\(\)\s+def delete\(self, history_id: int\):[\s\S]*?\}, 200)', delete_replacement, content)

with open(r"c:\Users\jefft\Updated-SQLMigrator\backend\routes\history_routes.py", "w", encoding="utf-8") as f:
    f.write(content)
