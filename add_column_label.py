from sqlalchemy import text
from database import engine

def add_label_column():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE toeic_transcripts ADD COLUMN label VARCHAR DEFAULT 'conversation'"))
            conn.commit()
            print("Successfully added 'label' column to 'toeic_transcripts' table.")
        except Exception as e:
            print(f"Error (might already exist): {e}")

if __name__ == "__main__":
    add_label_column()
