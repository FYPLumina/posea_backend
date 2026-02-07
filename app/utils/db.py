import mysql.connector
from mysql.connector import Error
import os

# Utility to get a database connection

def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST", "localhost"),
        user=os.environ.get("DB_USER", "root"),
        password=os.environ.get("DB_PASSWORD", ""),
        database=os.environ.get("DB_NAME", "posea_db"),
        autocommit=True
    )
