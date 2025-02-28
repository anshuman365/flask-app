import eventlet
eventlet.monkey_patch()  # Apply monkey patching before importing anything

from flask import Flask, render_template, request, redirect, url_for, session, flash, send_file, send_from_directory, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
import os
import json
import sqlite3
from datetime import timedelta
from authlib.integrations.flask_client import OAuth
import random
import nltk
from werkzeug.utils import secure_filename
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin, login_user, login_required, logout_user, current_user, LoginManager
from dotenv import load_dotenv

nltk.download('punkt')
nltk.download('averaged_perceptron_tagger')
nltk.download('wordnet')
nltk.download('stopwords')
nltk.download('vader_lexicon')

# Initialize Flask App
app = Flask(__name__)

socketio = SocketIO(app, async_mode='eventlet')  # ✅ Ensure eventlet is used

app.secret_key = 'your_unique_secret_key'  # Replace with a secure key
app.config['SECRET_KEY'] = 'your_secret_key'  # Replace with your secret key
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///site.db'  # SQLite database
db = SQLAlchemy(app)

# Folder configurations
UPLOAD_FOLDER = 'uploads'
UPLOAD_FOLDER1 = '/storage/emulated/0/flask-app/static/music'
MUSIC_FOLDER = '/storage/emulated/0/VidMate/download'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['UPLOAD_FOLDER1'] = UPLOAD_FOLDER1

# OAuth Configuration
oauth = OAuth(app)

# Load environment variables from .env file
load_dotenv()

GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET")
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI")

google = oauth.register(
    name="google",
    client_id=GOOGLE_CLIENT_ID,
    client_secret=GOOGLE_CLIENT_SECRET,
    authorize_url=os.getenv("GOOGLE_AUTH_URI"),
    access_token_url=os.getenv("GOOGLE_TOKEN_URI"),
    api_base_url="https://www.googleapis.com/oauth2/v1/",
    client_kwargs={"scope": "openid email profile"}
)

rooms = {}

# SQLite database initialization
conn = sqlite3.connect('chat.db', check_same_thread=False)
cursor = conn.cursor()
cursor.execute('''CREATE TABLE IF NOT EXISTS chat (id INTEGER PRIMARY KEY AUTOINCREMENT, room TEXT, username TEXT, message TEXT)''')
conn.commit()

# JSON database file
USER_DB_FILE = 'users.json'

# Ensure the JSON file exists
if not os.path.exists(USER_DB_FILE):
    with open(USER_DB_FILE, 'w') as f:
        json.dump({}, f)

# Helper functions to read/write user data
def load_users():
    with open(USER_DB_FILE, 'r') as f:
        return json.load(f)

def save_users(users):
    with open(USER_DB_FILE, 'w') as f:
        json.dump(users, f)

# Routes
@app.route('/')
def home():
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('home.html')

@app.route('/home')
def home_page():
    return render_template('home.html')

@app.route('/admin-login')
def admin_login():
    return render_template('admin_login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = load_users()

        if username in users:
            flash("Username already exists. Try a different one.")
            return redirect(url_for('signup'))

        users[username] = password
        save_users(users)
        flash("Signup successful. Please log in.")
        return redirect(url_for('login'))
    return render_template('signup.html')

app.permanent_session_lifetime = timedelta(days=30)  # Session lasts for 30 days

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        users = load_users()

        if username in users and users[username] == password:
            session.permanent = True  # Make the session permanent
            session['username'] = username
            flash("Login successful!")

            return redirect(url_for('dashboard'))
        flash("Invalid username or password.")
        return redirect(url_for('login'))
    return render_template('login.html')

# Detect environment (Local vs Render)
if os.getenv("RENDER") == "true":
    REDIRECT_URI = "https://nexora-industries.onrender.com/google/callback"
else:
    REDIRECT_URI = "http://127.0.0.1:5000/google/callback"

@app.route('/google/callback')
def google_callback():
    # Handle the OAuth callback
    state = session.pop('oauth_state', None)  # Retrieve state from session
    if not state or state != request.args.get('state'):
        flash("CSRF error: State mismatch.")
        return redirect(url_for('login'))

    token = google.authorize_access_token()
    user_info = google.get('userinfo').json()

    if not user_info:
        flash("Google login failed, please try again.")
        return redirect(url_for('login'))

    # Store user info in session
    session.permanent = True
    session['username'] = user_info['name']
    session['email'] = user_info['email']
    session['profile_pic'] = user_info['picture']

    flash("Login successful!")
    return redirect(url_for('dashboard'))

@app.route('/logout')
def logout():
    session.pop('username', None)
    flash("You have been logged out.")
    return redirect(url_for('home'))

@app.route('/dashboard')
def dashboard():
    if 'username' not in session:
        flash("Please log in to access the dashboard.")
        return redirect(url_for('login'))
    return render_template('main.html', username=session['username'])