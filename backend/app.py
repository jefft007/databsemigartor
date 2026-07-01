import os
import sys

# Ensure the project root (parent of backend/) is on sys.path so that
# absolute imports like `from backend.config import ...` work when
# running directly with `python app.py` from inside the backend dir.
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

# pyrefly: ignore [missing-import]
from flask import Flask, app, jsonify
# pyrefly: ignore [missing-import]
from flask_restful import Api

from backend.config import Config
from backend.extensions import db, jwt
from backend.auth.auth_routes import RegisterResource, LoginResource, LogoutResource
from backend.routes.migration_routes import SqlToSqlResource, MigrationStatusResource, MigrationHistoryResource, FileImportResource, SqlExportResource, SchemaGeneratorResource, TestConnectionResource, FileValidateResource, FileImportCorrectedResource
from backend.routes.history_routes import HistoryListResource, HistoryAllResource, HistoryDeleteResource
from backend.routes.admin_routes import AdminUserListResource, AdminUserDetailResource, AdminStatsResource
from backend.routes.report_routes import ReportResource, ReportsListResource, ReportsAllResource, ReportGenerateResource, ReportDownloadResource
from backend.utils.logger import setup_logging

from flask_cors import CORS

def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    app.config.from_object(Config)

    CORS(app, resources={r"/api/*": {"origins": ["http://127.0.0.1:5500", "http://localhost:5500", "http://127.0.0.1:5000", "http://localhost:5000"]}}, supports_credentials=True)
    
    if os.getenv("SQLALCHEMY_DATABASE_URI"):
        app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI")

    setup_logging(app)
    db.init_app(app)
    jwt.init_app(app)

    api = Api(app)

    # Authentication endpoints
    api.add_resource(RegisterResource, "/api/auth/register")
    api.add_resource(LoginResource, "/api/auth/login")
    api.add_resource(LogoutResource, "/api/auth/logout")

    # Migration and conversion endpoints
    api.add_resource(SqlToSqlResource, "/api/migration/sql-to-sql")
    api.add_resource(MigrationStatusResource, "/api/migration/status/<int:migration_id>")
    api.add_resource(MigrationHistoryResource, "/api/migration/history")
    api.add_resource(FileImportResource, "/api/import/file-to-sql")
    api.add_resource(FileValidateResource, "/api/import/validate")
    api.add_resource(FileImportCorrectedResource, "/api/import/file-to-sql/corrected")
    api.add_resource(SqlExportResource, "/api/export/sql-to-file")
    api.add_resource(SchemaGeneratorResource, "/api/schema/generate")
    api.add_resource(TestConnectionResource, "/api/test-connection")

    # History endpoints
    api.add_resource(HistoryListResource, "/api/history")
    api.add_resource(HistoryAllResource, "/api/history/all")
    api.add_resource(HistoryDeleteResource, "/api/history/<int:history_id>")

    # Dashboard endpoint
    from backend.routes.dashboard_routes import UserStatsResource
    api.add_resource(UserStatsResource, "/api/user/stats")

    # Admin endpoints
    api.add_resource(AdminUserListResource, "/api/admin/users")
    api.add_resource(AdminUserDetailResource, "/api/admin/user/<int:user_id>")
    api.add_resource(AdminStatsResource, "/api/admin/stats")

    # Reports endpoints
    api.add_resource(ReportsListResource, "/api/reports")
    api.add_resource(ReportsAllResource, "/api/reports/all")
    api.add_resource(ReportResource, "/api/reports/<int:report_id>")
    api.add_resource(ReportGenerateResource, "/api/reports/generate")
    api.add_resource(ReportDownloadResource, "/api/reports/<int:report_id>/download")

    @app.route("/", methods=["GET"])
    def root() -> tuple[dict, int]:
        return {
            "message": "SQL Migrator Backend is running. Use /api endpoints for access."}, 200

    with app.app_context():
        db.create_all()
        
        # Safely upgrade existing schema to add missing columns if they don't exist
        from sqlalchemy import inspect, text
        engine = db.engine
        inspector = inspect(engine)
        if "users" in inspector.get_table_names():
            columns = [col["name"] for col in inspector.get_columns("users")]
            with engine.connect() as conn:
                if "is_active" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1 NOT NULL"))
                if "created_at" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN created_at DATETIME DEFAULT CURRENT_TIMESTAMP"))
                if "last_login" not in columns:
                    conn.execute(text("ALTER TABLE users ADD COLUMN last_login DATETIME"))
                conn.commit()

    return app


if __name__ == "__main__":
    application = create_app()
    port = int(os.getenv("PORT", 5000))
    application.run(host="0.0.0.0", port=port, debug=True)