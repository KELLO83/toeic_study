from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    # Add progress column to toeic_audio_files table
    try:
        conn.execute(text("ALTER TABLE toeic_audio_files ADD COLUMN progress INTEGER DEFAULT 0"))
        conn.commit()
        print("SUCCESS: 'progress' column added to toeic_audio_files table.")
    except Exception as e:
        print(f"Error (column may already exist): {e}")
