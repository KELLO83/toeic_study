import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

db_url = os.getenv("DATABASE_URL")
print(f"DEBUG: Attempting to connect to DATABASE_URL: {db_url}")

try:
    conn = psycopg2.connect(db_url)
    print("SUCCESS: Database connection established!")
    cur = conn.cursor()
    cur.execute("SELECT version();")
    print(f"DB Version: {cur.fetchone()}")
    cur.close()
    conn.close()
except Exception as e:
    print(f"FAILURE: Could not connect to database.")
    print(f"Error: {e}")
