import os
import json
import traceback

from backend.converters.file_to_sql import import_file_to_sql


def main():
    cwd = os.getcwd()
    sample_csv = os.path.join(cwd, "test_import.csv")

    payload = {
        "file_path": sample_csv,
        # target_db_type defaults to sqlite and will use backend/database/app_data.db
        "if_exists": "replace",
    }

    try:
        result = import_file_to_sql(payload)
        out_path = os.path.join(cwd, "migration_report_demo.json")
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(result, fh, indent=2, default=str)

        print("Migration completed. Summary:")
        print(json.dumps({
            "table": result.get("table_name"),
            "rows_imported": result.get("rows_imported"),
            "rows_failed": result.get("rows_failed"),
            "rows_cancelled": result.get("rows_cancelled"),
        }, indent=2))
        print(f"Full report written to: {out_path}")

    except Exception as e:
        print("Migration failed:")
        traceback.print_exc()


if __name__ == "__main__":
    main()
