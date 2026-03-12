from sqlalchemy import Column, Integer, String
from database import Base

class ToeicWord(Base):
    __tablename__ = "toeic_word"

    id = Column(Integer, primary_key=True, index=True)
    word = Column(String)
    meaning = Column(String)
    sheet_name = Column(String)

