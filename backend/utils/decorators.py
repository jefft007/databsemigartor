from functools import wraps
from flask_jwt_extended import jwt_required, get_jwt

def admin_required(fn):
    @wraps(fn)
    @jwt_required()
    def wrapper(*args, **kwargs):
        claims = get_jwt()
        # role might be 'Admin' or 'admin'
        role = claims.get("role", "")
        if str(role).lower() != "admin":
            return {"message": "Admin access required"}, 403
        return fn(*args, **kwargs)
    return wrapper
