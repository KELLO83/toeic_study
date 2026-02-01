from sqlalchemy import text
from database import engine

def add_progress_column():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE toeic_audio_files ADD COLUMN progress INTEGER DEFAULT 0"))
            conn.commit()
            print("Successfully added 'progress' column to 'toeic_audio_files' table.")
        except Exception as e:
            print(f"Error (might already exist): {e}")

if __name__ == "__main__":
    add_progress_column()
