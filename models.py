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
