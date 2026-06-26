import re

with open("demo_production.sql", "r", encoding="utf-8") as f:
    sql_text = f.read()

table = "acc_account_head"

matches = re.findall(
    rf"INSERT INTO `{table}` VALUES\s*(.*?);",
    sql_text,
    re.DOTALL
)

print("Rows found:", len(matches))