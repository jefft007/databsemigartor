from datetime import datetime
from typing import Optional
from backend.extensions import db


class User(db.Model):
    """Internal user model for authentication and role management."""
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(120), unique=True, nullable=False)
    email = db.Column(db.String(255), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(50), default="user", nullable=False)
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    def __init__(
        self,
        username: str,
        email: str,
        password_hash: str,
        role: str = "user",
        is_active: bool = True,
    ) -> None:
        """Explicit constructor so type checkers recognize all column kwargs.

        SQLAlchemy generates this automatically at runtime; we declare it
        explicitly only to satisfy static analysis tools (Pyrefly / Pylance).
        """
        self.username = username
        self.email = email
        self.password_hash = password_hash
        self.role = role.lower() if role else "user"
        self.is_active = is_active

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "username": self.username,
            "email": self.email,
            "role": self.role,
            "is_active": self.is_active,
            "created_at": self.created_at.isoformat(),
            "last_login": self.last_login.isoformat() if self.last_login else None,
        }
