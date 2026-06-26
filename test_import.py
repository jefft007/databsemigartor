import re
import sqlite3
import ast

with open("demo_production.sql", "r", encoding="utf-8") as f:
    sql_text = f.read()

matches = re.findall(
    r"INSERT INTO `acc_account_head` VALUES\s*(.*?);",
    sql_text,
    re.DOTALL
)

conn = sqlite3.connect("temp.db")
cursor = conn.cursor()

cursor.execute("DROP TABLE IF EXISTS acc_account_head")

cursor.execute("""
CREATE TABLE acc_account_head(
    acc_head TEXT,
    acc_head_name TEXT,
    flag TEXT,
    code TEXT,
    mode TEXT,
    priority TEXT,
    dc TEXT
)
""")

for row_text in matches:
    row = ast.literal_eval(row_text)
    cursor.execute(
        "INSERT INTO acc_account_head VALUES (?, ?, ?, ?, ?, ?, ?)",
        row
    )

conn.commit()
conn.close()

print("Inserted", len(matches), "rows")