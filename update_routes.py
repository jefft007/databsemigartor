import re

with open(r"c:\Users\jefft\Updated-SQLMigrator\backend\routes\migration_routes.py", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Add jwt imports
if "from flask_jwt_extended" not in content:
    content = content.replace(
        "from flask_restful import Resource",
        "from flask_restful import Resource\nfrom flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt"
    )

# 2. Add @jwt_required() to all get/post methods
def add_jwt_required(match):
    prefix = match.group(1)
    method = match.group(2)
    
    # Check if we already have it
    if "@jwt_required()" in prefix:
        return match.group(0)
        
    return f"{prefix}    @jwt_required()\n    def {method}("

content = re.sub(r'(\n\s*)def (get|post)\(', add_jwt_required, content)

# 3. Add user_id assignment inside get/post methods
def add_user_id(match):
    prefix = match.group(1)
    if "user_id = get_jwt_identity()" in prefix:
        return match.group(0)
    return f"{match.group(0)}\n        user_id = get_jwt_identity()"

content = re.sub(r'(\s+@jwt_required\(\)\s+def (?:get|post)\(self[^)]*\):)', add_user_id, content)

# 4. Inject user_id into Migration, Report, MigrationHistory constructors
content = re.sub(r'(Migration\([\s\S]*?status="[^"]*",)', r'\1 user_id=user_id,', content)
content = re.sub(r'(Report\([\s\S]*?summary=[^,]*,)', r'\1 user_id=user_id,', content)
content = re.sub(r'(MigrationHistory\([\s\S]*?errors=[^,]*,)', r'\1 user_id=user_id,', content)

# 5. Modify MigrationHistoryResource to filter by role
history_get_replacement = """    @jwt_required()
    def get(self):
        user_id = get_jwt_identity()
        claims = get_jwt()
        role = claims.get("role", "")
        
        history = []
        if str(role).lower() == "admin":
            records = MigrationHistory.query.order_by(MigrationHistory.timestamp.desc()).all()
        else:
            records = MigrationHistory.query.filter_by(user_id=user_id).order_by(MigrationHistory.timestamp.desc()).all()"""

content = re.sub(r'(\s+@jwt_required\(\)\s+def get\(self\):\s+user_id = get_jwt_identity\(\)\s+history = \[\]\s+records = MigrationHistory.query.order_by\(\s*MigrationHistory.timestamp.desc\(\)\s*\).all\(\))', history_get_replacement, content)

# 6. Similarly modify CompletedMigrationsResource
completed_get_replacement = """    @jwt_required()
    def get(self):
        user_id = get_jwt_identity()
        role = get_jwt().get("role", "")
        
        if str(role).lower() == "admin":
            migrations = Migration.query.filter(Migration.status.in_(["completed", "success"])).all()
        else:
            migrations = Migration.query.filter(Migration.status.in_(["completed", "success"]), Migration.user_id == user_id).all()"""

content = re.sub(r'(\s+@jwt_required\(\)\s+def get\(self\):\s+user_id = get_jwt_identity\(\)\s+# Fetch migrations.*?\s+# Only return.*?\s+migrations = Migration.query.filter\(\s*Migration.status.in_\(\["completed", "success"\]\)\s*\).all\(\))', completed_get_replacement, content)


with open(r"c:\Users\jefft\Updated-SQLMigrator\backend\routes\migration_routes.py", "w", encoding="utf-8") as f:
    f.write(content)
