import re

with open(r"c:\Users\jefft\Updated-SQLMigrator\backend\routes\report_routes.py", "r", encoding="utf-8") as f:
    content = f.read()

if "from flask_jwt_extended" not in content:
    content = content.replace(
        "from flask_restful import Resource",
        "from flask_restful import Resource\nfrom flask_jwt_extended import jwt_required, get_jwt_identity, get_jwt"
    )

delete_report = """    @jwt_required()
    def delete(self, report_id):
        user_id = get_jwt_identity()
        role = get_jwt().get("role", "")
        report = Report.query.get(report_id)

        if not report:
            return {"message": "Report not found"}, 404

        if str(role).lower() != "admin" and str(report.user_id) != str(user_id):
            return {"message": "Unauthorized"}, 403

        db.session.delete(report)
        db.session.commit()

        return {"message": "Report deleted successfully"}, 200"""

content = re.sub(r'(class ReportResource\(Resource\):\s+def delete\(self, report_id\):[\s\S]*?\}, 200)', f"class ReportResource(Resource):\n{delete_report}", content)

get_reports = """    @jwt_required()
    def get(self):
        user_id = get_jwt_identity()
        role = get_jwt().get("role", "")
        
        try:
            if str(role).lower() == "admin":
                reports = Report.query.order_by(Report.id.desc()).all()
                history_records = MigrationHistory.query.order_by(MigrationHistory.timestamp.desc()).all()
            else:
                reports = Report.query.filter_by(user_id=user_id).order_by(Report.id.desc()).all()
                history_records = MigrationHistory.query.filter_by(user_id=user_id).order_by(MigrationHistory.timestamp.desc()).all()
                
            report_results = [build_report_response(report) for report in reports]"""

content = re.sub(r'(\s+def get\(self\):\s+try:\s+# Fetch actual generated reports\s+reports = Report.query.order_by\(Report.id.desc\(\)\).all\(\)\s+report_results = \[build_report_response\(report\) for report in reports\]\s+# Fetch old migration history for backward compatibility\s+history_records = MigrationHistory.query.order_by\(MigrationHistory.timestamp.desc\(\)\).all\(\))', get_reports, content)

post_report = """    @jwt_required()
    def post(self):
        user_id = get_jwt_identity()
        role = get_jwt().get("role", "")
        
        data = request.get_json() or {}

        migration_id = data.get("migration_id")
        report_format = data.get("report_format") or ".sql"

        if not migration_id:
            query = Migration.query.filter(Migration.status.in_([
                    "completed", "Completed", "complete", "Complete",
                    "success", "Success", "successful", "Successful"
                ]))
            if str(role).lower() != "admin":
                query = query.filter_by(user_id=user_id)
            
            completed_migrations = query.order_by(Migration.id.desc()).all()"""

content = re.sub(r'(\s+def post\(self\):[\s\S]*?order_by\(Migration.id.desc\(\)\)\s*.all\(\)\s*\))', post_report, content)

# ensure report uses user_id when generated
content = re.sub(r'(new_report = Report\([\s\S]*?summary=json.dumps\(summary_data\),\s*\))', r'new_report = Report(\n            report_format=report_format,\n            migration_id=migration.id,\n            summary=json.dumps(summary_data),\n            user_id=user_id,\n        )', content)

with open(r"c:\Users\jefft\Updated-SQLMigrator\backend\routes\report_routes.py", "w", encoding="utf-8") as f:
    f.write(content)
