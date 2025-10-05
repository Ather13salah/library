import os
from dotenv import load_dotenv
import mysql.connector as sql
from urllib.parse import urlparse

load_dotenv()
def create_connection():
    """Create connection with Railway MySQL"""
    db_url = os.getenv("DATABASE_URL")  # موجود في Railway env vars
    url = urlparse(db_url)

    return sql.connect(
        host=url.hostname,
        user=url.username,
        password=url.password,
        database=url.path.lstrip("/"),
        port=url.port,
        auth_plugin='mysql_native_password'
    )
