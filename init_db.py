from app import app, db  # Ensure you import the Flask app instance

with app.app_context():  # This sets up the application context
    db.create_all()
