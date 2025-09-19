import threading
import webview
from app import app

def run_flask():
    app.run(debug=False, port=5000, use_reloader=False)

if __name__ == '__main__':
    flask_thread = threading.Thread(target=run_flask)
    flask_thread.daemon = True
    flask_thread.start()
    webview.create_window(
        'Course Satisfaction Survey',
        'http://127.0.0.1:5000',
        gui='edgechromium'  # Force Edge backend
    )