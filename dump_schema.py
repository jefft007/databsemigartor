import sqlite3

conn = sqlite3.connect('C:/SQLMigratorData/app_data.db')
tables = conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()

for (table_name,) in tables:
    print(f'--- {table_name} ---')
    for row in conn.execute(f'PRAGMA table_info({table_name})').fetchall():
        print(row)
    print()

conn.close()
