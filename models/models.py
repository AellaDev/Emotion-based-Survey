from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class Response(Base):
    __tablename__ = 'responses'
    # your columns here
