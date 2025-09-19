import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from models.response import Response

# Adjust the path to your responses.db as needed
DB_PATH = os.path.join(os.path.dirname(__file__), '../db/responses.db')
DB_URI = f'sqlite:///{os.path.abspath(DB_PATH)}'

engine = create_engine(DB_URI)
Session = sessionmaker(bind=engine)
session = Session()

cutoff_date = datetime.utcnow() - timedelta(days=30)

deleted = session.query(Response).filter(Response.timestamp < cutoff_date).delete()
session.commit()

print(f"Deleted {deleted} responses older than 30 days.")
