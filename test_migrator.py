import csv
import json
import os
import sys
import time

import requests

# ───────────────────────── CONFIG — edit these ─────────────────────────
BASE_URL = "http://localhost:5000/api"

MYSQL = {
    "db_type": "mysql",
    "host": "localhost",
    "port": "3306",
    "username": "root",
    "password": "YOURPASSWORD",
    "database": "OWNDATABASE",  #CREATE YOUR OWN DATABASE 
}

POSTGRES = {
    "db_type": "postgresql",
    "host": "localhost",
    "port": "5432",
    "username": "postgres",
    "password": "YOURPASSWORD",
    "database": "OWNPASSWORD",   # must already exist: CREATE DATABASE migrator_test;
}

CSV_PATH = os.path.abspath("test_products.csv")
EXPORT_PATH = os.path.abspath("exported_products.csv")
TABLE_NAME = "test_products"
# ─────────────────────────────────────────────────────────────────────

PASS = "\033[92mPASS\033[0m"
FAIL = "\033[91mFAIL\033[0m"
results = []


def record(name, ok, detail=""):
    results.append((name, ok, detail))
    print(f"[{PASS if ok else FAIL}] {name}" + (f" — {detail}" if detail else ""))


def make_csv():
    with open(CSV_PATH, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["id", "name", "price"])
        writer.writerow([1, "Widget", 9.99])
        writer.writerow([2, "Gadget", 19.99])
        writer.writerow([3, "Gizmo", 4.50])
    print(f"Created test file: {CSV_PATH}")


def step_1_file_to_sql():
    """Import the CSV into the default SQLite database."""
    payload = {"file_path": CSV_PATH, "target_table": TABLE_NAME, "if_exists": "replace"}
    try:
        resp = requests.post(f"{BASE_URL}/import/file-to-sql", json=payload, timeout=30)
        data = resp.json()
        ok = resp.status_code == 200 and data.get("result", {}).get("rows_imported") == 3
        record("File -> SQL import (CSV into SQLite)", ok, json.dumps(data)[:200])
        return ok
    except Exception as exc:
        record("File -> SQL import (CSV into SQLite)", False, str(exc))
        return False


def step_2_sqlite_to_mysql():
    """Migrate the imported table from SQLite into MySQL."""
    payload = {
        "source_db_type": "sqlite",
        "source_database": None,  # backend defaults to its own app_data.db
        "target_db_type": MYSQL["db_type"],
        "target_host": MYSQL["host"],
        "target_port": MYSQL["port"],
        "target_username": MYSQL["username"],
        "target_password": MYSQL["password"],
        "target_database": MYSQL["database"],
        "tables": [TABLE_NAME],
    }
    try:
        resp = requests.post(f"{BASE_URL}/migration/sql-to-sql", json=payload, timeout=60)
        data = resp.json()
        summary = data.get("report", {}).get("summary", [])
        ok = resp.status_code == 200 and any(
            s.get("table") == TABLE_NAME and s.get("status") == "completed" for s in summary
        )
        record("SQL -> SQL migration (SQLite -> MySQL)", ok, json.dumps(data)[:300])
        return ok
    except Exception as exc:
        record("SQL -> SQL migration (SQLite -> MySQL)", False, str(exc))
        return False


def step_3_mysql_to_postgres():
    """Migrate the same table from MySQL into PostgreSQL."""
    payload = {
        "source_db_type": MYSQL["db_type"],
        "source_host": MYSQL["host"],
        "source_port": MYSQL["port"],
        "source_username": MYSQL["username"],
        "source_password": MYSQL["password"],
        "source_database": MYSQL["database"],
        "target_db_type": POSTGRES["db_type"],
        "target_host": POSTGRES["host"],
        "target_port": POSTGRES["port"],
        "target_username": POSTGRES["username"],
        "target_password": POSTGRES["password"],
        "target_database": POSTGRES["database"],
        "tables": [TABLE_NAME],
    }
    try:
        resp = requests.post(f"{BASE_URL}/migration/sql-to-sql", json=payload, timeout=60)
        data = resp.json()
        summary = data.get("report", {}).get("summary", [])
        ok = resp.status_code == 200 and any(
            s.get("table") == TABLE_NAME and s.get("status") == "completed" for s in summary
        )
        record("SQL -> SQL migration (MySQL -> PostgreSQL)", ok, json.dumps(data)[:300])
        return ok
    except Exception as exc:
        record("SQL -> SQL migration (MySQL -> PostgreSQL)", False, str(exc))
        return False


def step_4_postgres_to_file():
    """Export the PostgreSQL table back out to CSV."""
    payload = {
        "source_db_type": POSTGRES["db_type"],
        "source_host": POSTGRES["host"],
        "source_port": POSTGRES["port"],
        "source_username": POSTGRES["username"],
        "source_password": POSTGRES["password"],
        "source_database": POSTGRES["database"],
        "source_table": TABLE_NAME,
        "export_format": "csv",
        "export_path": EXPORT_PATH,
    }
    try:
        resp = requests.post(f"{BASE_URL}/export/sql-to-file", json=payload, timeout=30)
        data = resp.json()
        ok = (
            resp.status_code == 200
            and data.get("result", {}).get("rows_exported") == 3
            and os.path.isfile(EXPORT_PATH)
        )
        record("SQL -> File export (PostgreSQL -> CSV)", ok, json.dumps(data)[:200])
        return ok
    except Exception as exc:
        record("SQL -> File export (PostgreSQL -> CSV)", False, str(exc))
        return False


def step_5_test_connection():
    """Test connection endpoint: one good config, one deliberately bad one."""
    good_ok = bad_ok = False
    try:
        resp = requests.post(f"{BASE_URL}/test-connection", json=MYSQL, timeout=15)
        data = resp.json()
        good_ok = data.get("status") == "ok"
        record("Test Connection (valid MySQL credentials)", good_ok, json.dumps(data)[:150])
    except Exception as exc:
        record("Test Connection (valid MySQL credentials)", False, str(exc))

    bad_config = dict(MYSQL)
    bad_config["password"] = "definitely_wrong_password"
    try:
        resp = requests.post(f"{BASE_URL}/test-connection", json=bad_config, timeout=15)
        data = resp.json()
        bad_ok = data.get("status") == "error"
        record("Test Connection (invalid credentials correctly rejected)", bad_ok, json.dumps(data)[:150])
    except Exception as exc:
        record("Test Connection (invalid credentials correctly rejected)", False, str(exc))

    return good_ok and bad_ok


def step_6_history_logged():
    """Confirm migration_history now contains entries for everything above."""
    try:
        resp = requests.get(f"{BASE_URL}/migration/history", timeout=15)
        data = resp.json()
        history = data.get("history", [])
        types_seen = {h.get("migration_type") for h in history}
        ok = len(history) > 0 and ("sql_to_sql" in types_seen or "tabular" in types_seen)
        record(
            "Migration History reflects the runs above",
            ok,
            f"{len(history)} record(s), types seen: {types_seen}",
        )
        return ok
    except Exception as exc:
        record("Migration History reflects the runs above", False, str(exc))
        return False


def main():
    print(f"Testing SQL Migrator at {BASE_URL}\n" + "-" * 60)
    make_csv()

    step_1_file_to_sql()
    time.sleep(0.5)
    step_2_sqlite_to_mysql()
    time.sleep(0.5)
    step_3_mysql_to_postgres()
    time.sleep(0.5)
    step_4_postgres_to_file()
    time.sleep(0.5)
    step_5_test_connection()
    time.sleep(0.5)
    step_6_history_logged()

    print("-" * 60)
    passed = sum(1 for _, ok, _ in results if ok)
    print(f"\n{passed}/{len(results)} checks passed.")
    if passed != len(results):
        print("See FAIL lines above for details — common causes:")
        print("  - Wrong MySQL/Postgres password in the CONFIG block")
        print("  - Target database (migrator_test) doesn't exist yet")
        print("  - Backend not running on port 5000")
        sys.exit(1)


if __name__ == "__main__":
    main()
