from sqlalchemy import text
from database import engine

def add_set_number_column():
    with engine.connect() as conn:
        try:
            conn.execute(text("ALTER TABLE toeic_questions ADD COLUMN set_number INTEGER DEFAULT NULL"))
            conn.commit()
            print("Successfully added 'set_number' column to 'toeic_questions' table.")
        except Exception as e:
            print(f"Error (might already exist): {e}")

if __name__ == "__main__":
    add_set_number_column()
