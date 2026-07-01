from urllib.parse import quote_plus
from sqlalchemy import create_engine


def create_oracle_engine(username: str, password: str, host: str, port: str, service_name: str):
    """Create a SQLAlchemy engine for Oracle using python-oracledb."""
    encoded_user = quote_plus(username)
    encoded_password = quote_plus(password)

    connection_string = (
        f"oracle+oracledb://{encoded_user}:{encoded_password}"
        f"@{host}:{port}/?service_name={service_name}"
    )

    return create_engine(connection_string, pool_pre_ping=True)