from sqlalchemy import create_engine
from models.response import Base

engine = create_engine('sqlite:///db/responses.db')
Base.metadata.create_all(engine)
