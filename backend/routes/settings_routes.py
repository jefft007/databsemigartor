from flask import request
from flask_restful import Resource
from backend.models.settings_model import Setting
from backend.extensions import db
from flask_jwt_extended import jwt_required

class SettingsResource(Resource):
    """Endpoints for global application settings."""

    @jwt_required()
    def get(self):
        settings = Setting.query.all()
        settings_dict = {s.key: s.value for s in settings}
        return {"settings": settings_dict}, 200

    @jwt_required()
    def put(self):
        data = request.get_json()
        if not data:
            return {"message": "No data provided"}, 400

        for key, value in data.items():
            setting = Setting.query.filter_by(key=key).first()
            if setting:
                setting.value = str(value)
            else:
                setting = Setting(key=key, value=str(value))
                db.session.add(setting)
        
        db.session.commit()
        return {"message": "Settings updated successfully"}, 200
