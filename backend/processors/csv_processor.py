import pandas as pd


def read_csv_file(file_path: str) -> pd.DataFrame:
    """Read a CSV file into a pandas DataFrame."""
    df = pd.read_csv(file_path)
    # Replace NaN with None so SQLAlchemy handles it as NULL
    return df.where(pd.notnull(df), None)
