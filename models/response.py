from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, Integer, String, DateTime
from datetime import datetime

Base = declarative_base()

class Response(Base):
    __tablename__ = 'responses'
    id = Column(Integer, primary_key=True)  # unique id for the response row
    session_id = Column(String(64))         # unique id for the survey session
    question_id = Column(String(5))         # code from questions.db
    question = Column(String(500))          # the question text
    answer = Column(Integer)                # likert scale value
    emotion = Column(String(50))            # detected emotion
    timestamp = Column(DateTime, default=datetime.utcnow)  # time of survey
