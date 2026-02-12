import mysql.connector
from mysql.connector import Error
import os

from dotenv import load_dotenv
load_dotenv()

#database connection utility
def get_db_connection():
    return mysql.connector.connect(
        host=os.environ.get("DB_HOST"),
        user=os.environ.get("DB_USER"),
        password=os.environ.get("DB_PASSWORD"),
        database=os.environ.get("DB_NAME"),
        autocommit=True
    )
