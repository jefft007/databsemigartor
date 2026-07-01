import oracledb

conn = oracledb.connect(
    user="system",
    password="oracle123",
    host="127.0.0.1",
    port=1522,
    service_name="FREEPDB1"
)

print("Connected successfully!")

conn.close()