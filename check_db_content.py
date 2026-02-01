from sqlalchemy.orm import Session
from database import SessionLocal
import models

def check_db():
    db = SessionLocal()
    try:
        print("Checking DB Content...")
        
        # Check Audio Files
        audios = db.query(models.ToeicAudioFile).all()
        print(f"Total Audio Files: {len(audios)}")
        for a in audios:
            print(f" - [ID: {a.id}] Filename: {a.filename}, Status: {a.status}")

        # Check Questions
        questions = db.query(models.ToeicQuestion).all()
        print(f"Total Questions: {len(questions)}")
        
        # Check Transcripts
        transcripts = db.query(models.ToeicTranscript).all()
        print(f"Total Transcripts: {len(transcripts)}")

    finally:
        db.close()

if __name__ == "__main__":
    check_db()
