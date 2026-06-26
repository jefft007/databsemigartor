from flask import request
from flask_restful import Resource
from flask_jwt_extended import jwt_required, get_jwt_identity

from backend.auth.auth_service import register_user, authenticate_user, get_user_by_id
from backend.auth.jwt_handler import create_user_token
from backend.utils.helpers import get_placeholder_data, sanitize_string
from backend.utils.encryption import hash_password, check_password
from backend.extensions import db


class RegisterResource(Resource):
    """Endpoint to register a new application user."""

    def post(self):
        payload = request.get_json(silent=True) or {}

        defaults = {
            "username": None,
            "email": None,
            "password": None,
            "role": "User",
        }

        if not payload:
            payload = get_placeholder_data(defaults)

        username = sanitize_string(payload.get("username", "") or payload.get("fullname", ""))
        email = sanitize_string(payload.get("email", ""))
        password = payload.get("password", "")
        role = "User"

        if (
            "<FRONTEND" in username
            or "<FRONTEND" in email
            or "<FRONTEND" in password
        ):
            return {
                "message": "Registration payload uses placeholder values. Replace placeholders with frontend data."
            }, 400

        user = register_user(
            username=username,
            email=email,
            password=password,
            role=role,
        )

        if user is None:
            return {
                "message": "User registration failed. Username or email may already exist."
            }, 409

        return {
            "message": "User registered successfully.",
            "user": user.to_dict(),
        }, 201


class LoginResource(Resource):
    """Endpoint to login and receive a JWT token."""

    def post(self):
        payload = request.get_json(silent=True) or {}

        if not payload:
            payload = get_placeholder_data({
                "username": None,
                "email": None,
                "password": None,
            })

        login_id = sanitize_string(
            payload.get("username")
            or payload.get("email")
            or ""
        )

        password = payload.get("password", "")

        if "<FRONTEND" in login_id or "<FRONTEND" in password:
            return {
                "message": "Login payload uses placeholder values. Replace placeholders with real credentials."
            }, 400

        user = authenticate_user(login_id, password)

        if user is None:
            return {
                "message": "Invalid username/email or password."
            }, 401

        token = create_user_token(
            identity=user.id,
            role=user.role,
        )

        return {
            "token": token,
            "user": {
                "name": user.username,
                "email": user.email,
                "role": user.role,
            },
            "message": "Login successful.",
        }, 200


class LogoutResource(Resource):
    """Endpoint to simulate a logout by acknowledging the token expiration."""

    @jwt_required()
    def post(self):
        identity = get_jwt_identity()

        return {
            "message": "Logout successful.",
            "user": identity,
        }, 200


class ChangePasswordResource(Resource):
    """Endpoint to change the authenticated user's password."""

    @jwt_required()
    def post(self):
        payload = request.get_json(silent=True) or {}
        current_password = payload.get("current_password", "")
        new_password = payload.get("new_password", "")

        if not current_password or not new_password:
            return {"message": "Current password and new password are required."}, 400

        if len(new_password) < 6:
            return {"message": "New password must be at least 6 characters long."}, 400

        user_id = get_jwt_identity()
        user = get_user_by_id(user_id)

        if not user:
            return {"message": "User not found."}, 404

        if not check_password(current_password, user.password_hash):
            return {"message": "Incorrect current password."}, 400

        user.password_hash = hash_password(new_password)
        db.session.commit()

        return {"message": "Password changed successfully."}, 200