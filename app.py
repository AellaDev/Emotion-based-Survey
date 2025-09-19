from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify, Response as FlaskResponse
from controllers.auth_controller import AuthController
from flask_sqlalchemy import SQLAlchemy
import base64, cv2, numpy as np, os, random, string, threading, time, uuid
from deepface import DeepFace
from sqlalchemy import create_engine, extract
from sqlalchemy.orm import sessionmaker
from models.response import Response, Base as ResponseBase
from collections import Counter
from datetime import datetime
import RPi.GPIO as GPIO

# --- Flask Setup ---
app = Flask(__name__)
app.secret_key = 'uf0ukgmiep4d41qs5z5rxs453'
basedir = os.path.abspath(os.path.dirname(__file__))
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(basedir, 'db', 'questions.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
db = SQLAlchemy(app)
auth_controller = AuthController()

# --- Response DB Setup ---
responses_engine = create_engine(f"sqlite:///{os.path.join(basedir, 'db', 'responses.db')}")
ResponseSession = sessionmaker(bind=responses_engine)

# --- GPIO Setup ---
RED_PIN = 17
GREEN_PIN = 27
BLUE_PIN = 22
BUZZER_PIN = 18

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(RED_PIN, GPIO.OUT)
GPIO.setup(GREEN_PIN, GPIO.OUT)
GPIO.setup(BLUE_PIN, GPIO.OUT)
GPIO.setup(BUZZER_PIN, GPIO.OUT)

# --- PWM Setup for RGB (0-100% duty cycle) ---
RED_PWM = GPIO.PWM(RED_PIN, 1000)
GREEN_PWM = GPIO.PWM(GREEN_PIN, 1000)
BLUE_PWM = GPIO.PWM(BLUE_PIN, 1000)
RED_PWM.start(0)
GREEN_PWM.start(0)
BLUE_PWM.start(0)

# Cleanup on exit
import atexit
@atexit.register
def cleanup_gpio():
    GPIO.cleanup()

# --- Models ---
class Question(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.String(500), nullable=False)
    code = db.Column(db.String(5), unique=True, nullable=False, default=lambda: ''.join(random.choices(string.ascii_uppercase + string.digits, k=5)))

# --- Routes ---
@app.route('/')
def index():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        # Only trigger feedback for student login on POST, not GET
        return auth_controller.show_login()
    else:
        role = request.form.get('role', '').lower()
        if role == 'student':
            threading.Thread(target=feedback_student_login).start()
        return auth_controller.process_login()

@app.route('/logout')
def logout():
    return auth_controller.logout()

@app.route('/dashboard')
def dashboard():
    return auth_controller.dashboard()

@app.route('/student/survey', methods=['GET', 'POST'])
def student_survey():
    if 'user_role' not in session or session['user_role'] != 'Student':
        return redirect(url_for('login'))
    questions = Question.query.all()
    qidx = session.get('survey_qidx', 0)

    if 'survey_session_id' not in session:
        session['survey_session_id'] = str(uuid.uuid4())

    # Feedback when "Take Survey" is pressed (GET request)
    if request.method == 'GET' and qidx == 0:
        threading.Thread(target=feedback_take_survey).start()

    if request.method == 'POST':
        emotion = request.form.get('emotion')
        answer = request.form.get('answer')
        question_id = request.form.get('question_id')
        question_text = request.form.get('question_text')
        timestamp = request.form.get('timestamp')
        survey_session_id = session.get('survey_session_id')

        if emotion and answer and question_id and question_text and survey_session_id:
            session_db = ResponseSession()
            try:
                ts = datetime.fromisoformat(timestamp) if timestamp else datetime.utcnow()
                response = Response(
                    session_id=survey_session_id,
                    question_id=question_id,
                    question=question_text,
                    answer=int(answer),
                    emotion=emotion,
                    timestamp=ts
                )
                session_db.add(response)
                session_db.commit()
            except Exception as e:
                print("Error saving response:", e)
            finally:
                session_db.close()

            # Feedback for detected emotion (Likert)
            try:
                likert = int(answer)
            except Exception:
                likert = 3
            threading.Thread(target=feedback_detect_emotion, args=(likert,)).start()

        qidx += 1
        session['survey_qidx'] = qidx

    if qidx >= len(questions):
        session.pop('survey_qidx', None)
        session.pop('survey_session_id', None)
        # Feedback for end of survey
        threading.Thread(target=feedback_end_survey).start()
        return redirect(url_for('after_survey'))

    question = questions[qidx]
    return render_template('survey.html', question=question.text, qidx=qidx+1, total=len(questions),
                           question_id=question.code, question_text=question.text)

@app.route('/student/skip')
def student_skip():
    session.pop('survey_qidx', None)
    session.pop('survey_session_id', None)
    return redirect(url_for('after_skip'))

@app.route('/afterSurvey')
def after_survey():
    session.clear()
    return render_template('afterSurvey.html')

@app.route('/afterSkip')
def after_skip():
    session.clear()
    return render_template('afterSkip.html')

@app.route('/camera_feed')
def camera_feed():
    return FlaskResponse(gen_frames(), mimetype='multipart/x-mixed-replace; boundary=frame')

@app.route('/detect_emotion', methods=['POST'])
def detect_emotion():
    try:
        data = request.get_json(silent=True)
        img = None
        if data and 'image' in data:
            image_data = data['image'].split(",")[1]
            image_bytes = base64.b64decode(image_data)
            nparr = np.frombuffer(image_bytes, np.uint8)
            img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        else:
            cam = get_camera()
            for _ in range(3):
                ret, frame = cam.read()
                if ret:
                    img = frame
                    break
        if img is None:
            return jsonify({'error': 'Image not captured'}), 500

        result = DeepFace.analyze(img, actions=['emotion'], enforce_detection=False)
        emotion = result[0]['dominant_emotion']
        region = result[0].get('region', None)

        # --- RGB feedback for likert: light up as soon as detected ---
        likert_map = {
            'happy': 5,
            'surprised': 4,
            'surprise': 4,
            'neutral': 3,
            'sad': 2,
            'fearful': 2,
            'angry': 1,
            'disgust': 1
        }
        likert = likert_map.get(emotion.lower(), 3)

        # --- Prevent RGB flicker: Only allow one feedback at a time, cancel previous ---
        # Use a single global feedback thread and event to control RGB feedback
        if not hasattr(app, 'rgb_feedback_event'):
            app.rgb_feedback_event = threading.Event()
            app.rgb_feedback_thread = None

        # Signal any running feedback to stop
        app.rgb_feedback_event.set()
        # Wait for previous thread to finish (if running)
        if getattr(app, 'rgb_feedback_thread', None) is not None:
            app.rgb_feedback_thread.join(timeout=0.2)

        # Prepare a new event for this feedback
        app.rgb_feedback_event = threading.Event()

        def rgb_likert_feedback(stop_event):
            rgb_set_likert_color(likert)
            # Wait for 1.2s or until told to stop early
            stop_event.wait(1.2)
            rgb_off()
            buzzer_beep(1)

        # Start new feedback thread
        app.rgb_feedback_thread = threading.Thread(target=rgb_likert_feedback, args=(app.rgb_feedback_event,))
        app.rgb_feedback_thread.daemon = True
        app.rgb_feedback_thread.start()

        return jsonify({'emotion': emotion, 'region': region})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/admin/questions')
def admin_questions():
    if not is_admin():
        flash('Admin access required.')
        return redirect(url_for('login'))
    questions = Question.query.all()
    session_db = ResponseSession()
    responses = session_db.query(Response).order_by(Response.timestamp.desc()).all()
    session_db.close()
    return render_template('admin.html', questions=questions, responses=responses)

@app.route('/admin/questions/add', methods=['POST'])
def add_question():
    if not is_admin():
        flash('Admin access required.')
        return redirect(url_for('login'))
    text = request.form.get('text')
    if text:
        q = Question(text=text)
        db.session.add(q)
        db.session.commit()
        flash('Question added.')
    return redirect(url_for('admin_questions'))

@app.route('/admin/questions/edit/<int:question_id>', methods=['POST'])
def edit_question(question_id):
    if not is_admin():
        flash('Admin access required.')
        return redirect(url_for('login'))
    q = Question.query.get_or_404(question_id)
    new_text = request.form.get('text')
    if new_text:
        q.text = new_text
        db.session.commit()
        flash('Question updated.')
    return redirect(url_for('admin_questions'))

@app.route('/admin/questions/delete/<int:question_id>', methods=['POST'])
def delete_question(question_id):
    if not is_admin():
        flash('Admin access required.')
        return redirect(url_for('login'))
    q = Question.query.get_or_404(question_id)
    db.session.delete(q)
    db.session.commit()
    flash('Question deleted.')
    return redirect(url_for('admin_questions'))

@app.route('/admin/summary_data')
def admin_summary_data():
    month = request.args.get('month')
    if not month:
        return jsonify({'error': 'Month required'}), 400
    year, month_num = map(int, month.split('-'))
    session_db = ResponseSession()
    responses = session_db.query(Response).filter(
        extract('year', Response.timestamp) == year,
        extract('month', Response.timestamp) == month_num
    ).all()
    questions = Question.query.all()
    session_ids = set(r.session_id for r in responses)
    total_surveys = len(session_ids)
    question_summaries = []
    for q in questions:
        q_responses = [r for r in responses if r.question_id == q.code]
        if q_responses:
            avg_score = round(sum(r.answer for r in q_responses) / len(q_responses), 2)
            emotions = [r.emotion for r in q_responses]
            most_common_emotion, percent = Counter(emotions).most_common(1)[0] if emotions else (None, 0)
        else:
            avg_score = None
            most_common_emotion, percent = None, 0
        question_summaries.append({
            'question': q.text,
            'avg_score': avg_score,
            'emotion': most_common_emotion,
            'emotion_percent': percent
        })
    session_db.close()
    return jsonify({'total_surveys': total_surveys, 'questions': question_summaries})

# --- Camera Functions ---
camera = None
def get_camera():
    global camera
    if camera is None or not camera.isOpened():
        camera = cv2.VideoCapture(0)
    return camera

def gen_frames():
    cam = get_camera()
    while True:
        success, frame = cam.read()
        if not success:
            break
        ret, buffer = cv2.imencode('.jpg', frame)
        if not ret:
            continue
        yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')

# --- GPIO Feedback Functions (updated for common cathode RGB and active buzzer) ---
def set_rgb_color(r, g, b):
    """
    Set RGB color using PWM.
    r, g, b: 0-255 (intensity, 0=off, 255=full)
    For common cathode: 0% duty = off, 100% = full brightness.
    """
    r = max(0, min(255, int(r)))
    g = max(0, min(255, int(g)))
    b = max(0, min(255, int(b)))
    RED_PWM.ChangeDutyCycle((r / 255.0) * 100)
    GREEN_PWM.ChangeDutyCycle((g / 255.0) * 100)
    BLUE_PWM.ChangeDutyCycle((b / 255.0) * 100)


def rgb_off():
    set_rgb_color(0, 0, 0)

def rgb_flash_red(times=1, duration=0.3, pause=0.2):
    for _ in range(times):
        set_rgb_color(255, 0, 0)
        time.sleep(duration)
        rgb_off()
        time.sleep(pause)

def rgb_flash_blue(times=1, duration=0.3, pause=0.2):
    for _ in range(times):
        set_rgb_color(0, 0, 255)
        time.sleep(duration)
        rgb_off()
        time.sleep(pause)

def buzzer_beep(times=1, duration=0.15, pause=0.1):
    for _ in range(times):
        GPIO.output(BUZZER_PIN, GPIO.HIGH)
        time.sleep(duration)
        GPIO.output(BUZZER_PIN, GPIO.LOW)
        time.sleep(pause)

def rgb_set_likert_color(likert):
    # 5: dark green, 4: apple green, 3: yellow, 2: true orange, 1: red
    colors = {
        5: (0, 255, 0),       # Green
        4: (50, 255, 50),     # Apple green
        3: (255, 255, 0),     # Yellow
        2: (255, 69, 0),      # Orange
        1: (255, 0, 0)        # Red
    }
    rgb = colors.get(likert, (0, 0, 0))
    set_rgb_color(*rgb)

# --- Feedback triggers ---
def feedback_student_login():
    rgb_flash_red(2)
    buzzer_beep(2)

def feedback_take_survey():
    buzzer_beep(1)
    rgb_flash_red(1)

def feedback_detect_emotion(likert):
    # No longer needed in POST, handled in /detect_emotion route
    pass

def feedback_end_survey():
    rgb_flash_blue(2)
    buzzer_beep(2)

def is_admin():
    return session.get('user_role', '').lower() == 'admin'

# --- Run Server ---
if __name__ == '__main__':
    app.run(debug=True)
