import pandas as pd


def read_excel_file(file_path: str) -> pd.DataFrame:
    """Read an Excel file into a pandas DataFrame."""
    try:
        df = pd.read_excel(file_path)
        # Replace NaN with None so SQLAlchemy handles it as NULL
        return df.where(pd.notnull(df), None)
    except ImportError as e:
        if "openpyxl" in str(e):
            raise ValueError("Excel import requires 'openpyxl'. Please install it using 'pip install openpyxl'.")
        raise e
