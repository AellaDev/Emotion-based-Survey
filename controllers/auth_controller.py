from flask import render_template, request, redirect, url_for, session
from models.user_model import UserModel
import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from datetime import datetime, timedelta
from models.response import Response

# Helper to delete responses older than 30 days
def cleanup_old_responses():
    DB_PATH = os.path.join(os.path.dirname(__file__), '../db/responses.db')
    DB_URI = f'sqlite:///{os.path.abspath(DB_PATH)}'
    engine = create_engine(DB_URI)
    Session = sessionmaker(bind=engine)
    session = Session()
    cutoff_date = datetime.utcnow() - timedelta(days=30)
    session.query(Response).filter(Response.timestamp < cutoff_date).delete()
    session.commit()
    session.close()

class AuthController:
    def __init__(self):
        self.user_model = UserModel()
    
    def show_login(self):
        return render_template('login.html')
    
    def process_login(self):
        role = request.form.get('role')
        password = request.form.get('password', '')
        
        if not role or role == '--Select role--':
            return render_template('login.html')
        
        if role == 'Student':
            session['user_role'] = 'Student'
            session['logged_in'] = True
            return render_template('student.html')
        
        elif role == 'Admin':
            if not password:
                return render_template('login.html')
            if self.user_model.validate_admin_password(password):
                # Cleanup old responses on admin login
                cleanup_old_responses()
                session['user_role'] = 'Admin'
                session['logged_in'] = True
                return redirect(url_for('admin_questions'))
            else:
                return render_template('login.html')
        
        return render_template('login.html')
    
    def logout(self):
        session.clear()
        return redirect(url_for('login'))
    
    def dashboard(self):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        
        user_role = session.get('user_role')
        return render_template('dashboard.html', role=user_role)
