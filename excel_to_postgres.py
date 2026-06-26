import os
from dotenv import load_dotenv, find_dotenv

import pandas as pd
from sqlalchemy import create_engine

load_dotenv(find_dotenv())

excel_path = os.getenv("EXCEL_FILE_PATH", "Stockason_10032026.xlsx")
database_url = os.getenv("DB_URL", "sqlite:///local_data.db")
target_table = os.getenv("TARGET_TABLE", "stockason")

if not os.path.exists(excel_path):
    raise FileNotFoundError(
        f"Excel file not found: {excel_path}. "
        "Set EXCEL_FILE_PATH in .env or place the file next to this script."
    )

print(f"Loading Excel file: {excel_path}")
df = pd.read_excel(excel_path, sheet_name=0)

engine = create_engine(database_url)

df.to_sql(
    target_table,
    engine,
    if_exists="replace",
    index=False,
)

print(f"Imported {len(df)} rows from {excel_path} into {database_url}.")
