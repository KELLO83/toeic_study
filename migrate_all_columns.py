from sqlalchemy import create_engine, text
import os
from dotenv import load_dotenv

load_dotenv()

DATABASE_URL = os.getenv("DATABASE_URL")
engine = create_engine(DATABASE_URL)

with engine.connect() as conn:
    # Add set_number column to toeic_questions table
    try:
        conn.execute(text("ALTER TABLE toeic_questions ADD COLUMN set_number INTEGER"))
        conn.commit()
        print("SUCCESS: 'set_number' column added to toeic_questions table.")
    except Exception as e:
        print(f"Error (column may already exist): {e}")

    # Add label column to toeic_transcripts table
    try:
        conn.execute(text("ALTER TABLE toeic_transcripts ADD COLUMN label VARCHAR DEFAULT 'conversation'"))
        conn.commit()
        print("SUCCESS: 'label' column added to toeic_transcripts table.")
    except Exception as e:
        print(f"Error (column may already exist): {e}")
