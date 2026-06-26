import os
import tempfile
import pandas as pd
from backend.app import create_app
from backend.extensions import db


def test_schema_generator_creates_sql():
    with tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", encoding="utf-8") as temp_file:
        temp_file.write("name,age,is_active\nAlice,30,True\nBob,25,False\n")
        path = temp_file.name

    app = create_app()
    with app.app_context():
        sql = None
        from backend.processors.schema_generator import generate_create_table_schema
        sql = generate_create_table_schema(path, "test_users")
        assert "CREATE TABLE IF NOT EXISTS test_users" in sql
        assert "name TEXT" in sql or "name VARCHAR" in sql

    os.unlink(path)


def test_file_import_placeholder_returns_summary():
    os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app = create_app()
    app.config["TESTING"] = True
    with app.app_context():
        from backend.converters.file_to_sql import import_file_to_sql

        path = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", encoding="utf-8").name
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("name,age\nAlice,30\n")

        payload = {
            "file_path": path,
            "target_db_type": "sqlite",
            "target_database": ":memory:",
            "target_table": "imported_users",
            "if_exists": "replace",
        }
        result = import_file_to_sql(payload)
        assert result["table_name"] == "imported_users"

        os.unlink(path)


def test_file_import_records_history():
    os.environ["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    app = create_app()
    app.config["TESTING"] = True
    with app.app_context():
        db.create_all()

        from backend.models.history_model import MigrationHistory
        from backend.models.migration_model import Migration
        
        path = tempfile.NamedTemporaryFile(suffix=".csv", delete=False, mode="w", encoding="utf-8").name
        with open(path, "w", encoding="utf-8") as handle:
            handle.write("name,age\nAlice,30\n")

        try:
            with app.test_client() as client:
                payload = {
                    "file_path": path,
                    "target_db_type": "sqlite",
                    "target_database": ":memory:",
                    "target_table": "imported_users",
                    "if_exists": "replace",
                }
                response = client.post(
                    "/api/import/file-to-sql",
                    json=payload,
                )
                assert response.status_code == 200

                # Verify Migration and MigrationHistory exist
                migration = Migration.query.filter_by(migration_type="tabular").first()
                assert migration is not None
                assert migration.status == "completed"

                history = MigrationHistory.query.filter_by(migration_type="tabular").first()
                assert history is not None
                assert history.status == "completed"
                assert "imported_users" in history.report_summary
        finally:
            os.unlink(path)

