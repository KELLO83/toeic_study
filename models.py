from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from database import Base
from datetime import datetime

class AudioFile(Base):
    __tablename__ = "audio_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    saved_path = Column(String)
    status = Column(String, default="pending")  # pending, processing, completed, error
    upload_date = Column(DateTime, default=datetime.utcnow)

    transcripts = relationship("Transcript", back_populates="audio_file", cascade="all, delete-orphan")

class Transcript(Base):
    __tablename__ = "transcripts"

    id = Column(Integer, primary_key=True, index=True)
    audio_id = Column(Integer, ForeignKey("audio_files.id"))
    start_time = Column(Float)
    end_time = Column(Float)
    text = Column(Text)

    audio_file = relationship("AudioFile", back_populates="transcripts")

# --- TOEIC LC Specific Models ---

class ToeicAudioFile(Base):
    __tablename__ = "toeic_audio_files"

    id = Column(Integer, primary_key=True, index=True)
    filename = Column(String, index=True)
    saved_path = Column(String)
    upload_date = Column(DateTime, default=datetime.utcnow)
    status = Column(String, default="processing") # processing, completed, error
    progress = Column(Integer, default=0)

    questions = relationship("ToeicQuestion", back_populates="audio_file", cascade="all, delete-orphan")

class ToeicQuestion(Base):
    __tablename__ = "toeic_questions"

    id = Column(Integer, primary_key=True, index=True)
    audio_id = Column(Integer, ForeignKey("toeic_audio_files.id"))
    question_number = Column(Integer)  # 1, 2, ..., 100
    part = Column(Integer)             # 1, 2, 3, 4
    set_number = Column(Integer, nullable=True) # Start number of the set (e.g., 4 for Questions 4-6)
    start_time = Column(Float)
    end_time = Column(Float)
    
    audio_file = relationship("ToeicAudioFile", back_populates="questions")
    transcripts = relationship("ToeicTranscript", back_populates="question", cascade="all, delete-orphan")

class ToeicTranscript(Base):
    __tablename__ = "toeic_transcripts"

    id = Column(Integer, primary_key=True, index=True)
    question_id = Column(Integer, ForeignKey("toeic_questions.id"))
    start_time = Column(Float)
    end_time = Column(Float)
    text = Column(Text)
    label = Column(String, default="conversation") # 'conversation', 'question', 'instruction'

    question = relationship("ToeicQuestion", back_populates="transcripts")

class ToeicWord(Base):
    __tablename__ = "toeic_word"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String)
    meaning = Column(String)
    sheet_name = Column(String)

