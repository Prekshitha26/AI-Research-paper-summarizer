from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file, flash
from flask_session import Session
import secrets
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import os, json
from collections import Counter
import re

load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024
Session(app)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

USERS_FILE = 'users.json'

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r') as f:
            return json.load(f)
    return {'admin@example.com': {'name': 'Admin', 'password': 'admin123'}}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

users = load_users()

groq_api_key = os.getenv("GROQ_API_KEY")
llm = ChatGroq(groq_api_key=groq_api_key, model_name=os.getenv("LLM_MODEL", "llama3-8b-8192"))
embedder = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")

from src.load_and_extract_text import extract_text_from_pdf, extract_pdf_sections
from src.detect_and_split_sections import refine_sections, split_sections_with_content
from src.get_summary import generate_detailed_summary
from src.create_vector_db import create_vector_db
from src.RAG_retrival_chain import get_qa_chain

def login_required():
    if 'username' not in session:
        return redirect(url_for('login'))

@app.route('/')
def index():
    return redirect(url_for('login' if 'username' not in session else 'home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('home'))
    if request.method == 'POST':
        email = request.form['email'].lower().strip()
        password = request.form['password']
        user = users.get(email)
        if user and user['password'] == password:
            session['username'] = email
            session['user_name'] = user['name']
            return redirect(url_for('home'))
        flash('Invalid login')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'username' in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        email = request.form['email'].lower().strip()
        name = request.form['name'].strip()
        password = request.form['password']
        if not password == request.form['confirm_password']:
            flash('Passwords do not match')
        elif email in users:
            flash('User already exists')
        else:
            users[email] = {'name': name, 'password': password}
            save_users(users)
            flash('Account created! Please login.')
            return redirect(url_for('login'))
        return render_template('signup.html')
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/home')
def home():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('home.html', user_name=session['user_name'])

@app.route('/about')
def about():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('about.html')

@app.route('/features')
def features():
    if 'username' not in session:
        return redirect(url_for('login'))
    return render_template('features.html')

@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if 'username' not in session:
        return redirect(url_for('login'))
    if request.method == 'POST':
        file = request.files['file']
        if file and file.filename.lower().endswith('.pdf'):
            name = secure_filename(file.filename)
            path = os.path.join(app.config['UPLOAD_FOLDER'], secrets.token_hex(8) + '_' + name)
            file.save(path)
            text = extract_text_from_pdf(path)
            session['full_text'] = text
            sections = extract_pdf_sections(text)
            refined = refine_sections(sections, llm)
            topics = split_sections_with_content(text, refined)
            session['topics'] = topics
            return jsonify({'topics': list(topics.keys())})
        return jsonify({'error': 'PDF only'}), 400
    return render_template('upload.html')

@app.route('/qa')
def qa():
    login_required()
    return render_template('qa.html')

@app.route('/visualization')
def visualization():
    login_required()
    return render_template('visualization.html')

@app.route('/summary', methods=['POST'])
def get_summary():
    if 'username' not in session:
        return jsonify({'error': 'Login required'}), 401
    topic = request.json['topic']
    content = session['topics'][topic]
    summary = generate_detailed_summary(content, llm)
    return jsonify({'summary': summary})

@app.route('/chat', methods=['POST'])
def chat():
    login_required()
    text = session.get('full_text', '')
    if not text:
        return jsonify({'response': 'Upload first'})
    msg = request.json['message']
    try:
        vectordb = create_vector_db(text=text, embedder=embedder)
        chain = get_qa_chain(vectordb=vectordb, llm=llm)
        response = chain.invoke(msg)['result']
        return jsonify({'response': response})
    except Exception as e:
        return jsonify({'response': str(e)})

@app.route('/analyze')
def analyze():
    login_required()
    topics = session.get('topics', {})
    if not topics:
        return jsonify({'keywords': [], 'topics': [], 'trend_scores': []})
    content = ' '.join(topics.values())
    words = re.findall(r'\w{4,}', content.lower())
    stopwords = {'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for', 'of', 'with', 'by', 'is', 'are', 'was', 'were'}
    keywords = Counter([w for w in words if w not in stopwords]).most_common(10)
    return jsonify({'keywords': keywords, 'topics': list(topics)[:8], 'trend_scores': [len(str(v)) for v in list(topics.values())[:5]]})

@app.route('/translate_summary', methods=['POST'])
def translate_summary():
    login_required()
    summary = request.json['summary']
    prompt = f"Translate to Hindi: {summary}"
    return jsonify({'hindi_summary': llm.invoke(prompt).content})

@app.route('/generate_pdf', methods=['POST'])
def generate_pdf():
    login_required()
    summary = request.json['summary']
    
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y_position = height - 50
    line_height = 14
    font_size = 10
    max_width = width - 100
    c.setFont('Helvetica', font_size)
    
    lines = summary.split('\n')
    
    for line in lines:
        # Skip empty lines (double newlines = paragraph spacing)
        if not line.strip():
            y_position -= line_height * 0.5  # Extra spacing
            if y_position < 50:
                c.showPage()
                y_position = height - 50
            continue
        
        # Bullet point handling
        if line.strip().startswith(('- ', '• ', '* ')):
            bullet = line[0:2]
            text = line[2:].strip()
        else:
            bullet = ''
            text = line.strip()
        
        # Word wrap this line
        words = text.split()
        current_line = ''
        
        for word in words:
            test_line = current_line + (' ' if current_line else '') + word
            if c.stringWidth(test_line, 'Helvetica', font_size) < max_width:
                current_line = test_line
            else:
                # Draw line with bullet if any
                full_line = (bullet + ' ' if bullet else '') + current_line.rstrip()
                c.drawString(50, y_position, full_line)
                y_position -= line_height
                if y_position < 50:
                    c.showPage()
                    y_position = height - 50
                current_line = word
                bullet = ''  # Bullet only on first line
        
        # Draw last line of this paragraph
        if current_line:
            full_line = (bullet + ' ' if bullet else '') + current_line.rstrip()
            c.drawString(50, y_position, full_line)
            y_position -= line_height
        
        if y_position < 50:
            c.showPage()
            y_position = height - 50
    
    c.save()
    buffer.seek(0)
    
    return send_file(buffer, as_attachment=True, download_name='summary.pdf', mimetype='application/pdf')

if __name__ == '__main__':
    app.run(debug=False, host='0.0.0.0', port=5000)
