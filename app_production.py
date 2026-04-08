from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file, flash
from flask_session import Session
import secrets
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter

from src.load_and_extract_text import extract_text_from_pdf, extract_pdf_sections
from src.detect_and_split_sections import refine_sections, split_sections_with_content
from src.get_summary import generate_detailed_summary
from src.create_vector_db import create_vector_db
from src.RAG_retrival_chain import get_qa_chain

from dotenv import load_dotenv
import os, json
from collections import Counter
import re
from werkzeug.utils import secure_filename

load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024  # 50MB
Session(app)

os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

USERS_FILE = 'users.json'

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            try:
                data = json.load(f)
                if isinstance(data, dict):
                    normalized = {}
                    for key, value in data.items():
                        if isinstance(value, dict) and value.get('password'):
                            normalized[key.lower()] = value
                        else:
                            normalized[key.lower()] = {
                                'name': key.split('@')[0].title(),
                                'password': value
                            }
                    return normalized
            except ValueError:
                pass
    return {'admin@example.com': {'name': 'Admin', 'password': 'admin123'}}

def save_users(users_data):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users_data, f, indent=2)

users = load_users()

groq_api_key = os.getenv("GROQ_API_KEY")
llm_model = os.getenv("LLM_MODEL", "llama-3.3-70b-versatile")
embedding_model = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

llm = ChatGroq(groq_api_key = groq_api_key, model_name = llm_model)
embedder = HuggingFaceEmbeddings(model_name=embedding_model)

def require_login():
    if 'username' not in session:
        return redirect(url_for('login'))

@app.route('/')
def index():
    if 'username' in session:
        return redirect(url_for('home'))
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('home'))

    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        user_record = users.get(email)

        if not email or not password:
            error = 'Enter both email and password.'
        elif not user_record or user_record.get('password') != password:
            error = 'Invalid email or password.'
        else:
            session['username'] = email
            session['user_name'] = user_record.get('name', 'Researcher')
            return redirect(url_for('home'))

    return render_template('login.html', error=error)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'username' in session:
        return redirect(url_for('home'))

    error = None
    if request.method == 'POST':
        full_name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not all([full_name, email, password, confirm_password]):
            error = 'Please fill all fields.'
        elif '@' not in email:
            error = 'Valid email required.'
        elif password != confirm_password:
            error = 'Passwords do not match.'
        elif email in users:
            error = 'Email already exists.'
        else:
            users[email] = {'name': full_name, 'password': password}
            save_users(users)
            session['username'] = email
            session['user_name'] = full_name
            return redirect(url_for('home'))

    return render_template('signup.html', error=error)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/home')
@login_required_decorator
def home():
    return render_template('home.html', user_name=session.get('user_name', 'User'))

def login_required_decorator(f):
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

@app.route('/about')
@login_required_decorator
def about():
    return render_template('about.html')

@app.route('/features')
@login_required_decorator
def features():
    return render_template('features.html')

@app.route('/upload', methods=['GET', 'POST'])
@login_required_decorator
def upload():
    if request.method == 'POST':
        file = request.files.get('file')
        if not file or not file.filename.lower().endswith('.pdf'):
            return jsonify({"error": "PDF only"}), 400

        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], f"{secrets.token_hex(8)}_{filename}")
        file.save(filepath)

        extracted_text = extract_text_from_pdf(filepath)
        session['full_text'] = extracted_text
        extracted_sections = extract_pdf_sections(full_text=extracted_text)
        refined_sections = refine_sections(extracted_sections, llm)
        section_with_content = split_sections_with_content(extracted_text, refined_sections)

        session['topics'] = section_with_content
        session.modified = True

        return jsonify({"topics": list(section_with_content.keys())})

    return render_template('upload.html')

@app.route('/qa')
@login_required_decorator
def qa():
    return render_template('qa.html')

@app.route('/visualization')
@login_required_decorator
def visualization():
    return render_template('visualization.html')

@app.route('/summary', methods=['POST'])
@login_required_decorator
def get_summary():
    topics = session.get('topics', {})
    topic = request.json.get('topic')
    topic_content = topics.get(topic, "No summary available.")
    summary = generate_detailed_summary(topic_content, llm)
    return jsonify({"summary": summary})

@app.route('/chat', methods=['POST'])
@login_required_decorator
def chat():
    full_text = session.get('full_text')
    if not full_text:
        return jsonify({"response": "Please upload a document first."}), 400
    
    user_message = request.json.get('message')
    if not user_message:
        return jsonify({"response": "No message provided."}), 400
    
    try:
        vectordb = create_vector_db(text=full_text, embedder=embedder)
        chain = get_qa_chain(vectordb=vectordb, llm=llm)
        ai_response = chain.invoke(user_message)['result']
        return jsonify({"response": ai_response})
    except Exception as e:
        return jsonify({"response": f"Error: {str(e)[:100]}"}), 500

@app.route('/analyze')
@login_required_decorator
def analyze():
    topics = session.get('topics', {})
    if not topics:
        return jsonify({'keywords': [], 'topics': [], 'trend_scores': []})
    
    all_content = ' '.join([str(v) for v in topics.values()])
    words = re.findall(r'\b[a-zA-Z]{4,}\b', all_content.lower())
    stopwords = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'way', 'who', 'boy', 'did', 'its', 'let', 'put', 'say', 'she', 'too', 'use', 'your', 'is', 'to', 'we', 'as', 'a', 'in', 'on', 'of', 'or'}
    filtered_words = [w for w in words if w not in stopwords and len(w) > 3]
    keywords = Counter(filtered_words).most_common(10)
    
    topics_list = list(topics.keys())[:8]
    trend_scores = [len(str(v)) for v in list(topics.values())[:5]]
    
    return jsonify({
        'keywords': keywords,
        'topics': topics_list,
        'trend_scores': trend_scores
    })

@app.route('/translate_summary', methods=['POST'])
@login_required_decorator
def translate_summary():
    summary = request.json.get('summary')
    if not summary:
        return jsonify({'hindi_summary': ''}), 400
    
    prompt = f"Translate the following English research paper summary to Hindi naturally and accurately. Keep technical terms appropriate:\n\n{summary}"
    hindi_summary = llm.invoke(prompt).content
    return jsonify({'hindi_summary': hindi_summary})

@app.route('/generate_pdf', methods=['POST'])
@login_required_decorator
def generate_pdf():
    data = request.json
    summary = data['summary'][:4000]
    buffer = BytesIO()
    p = canvas.Canvas(buffer, pagesize=letter)
    width, height = letter
    y = height - 50
    lines = p.beginText(40, y)
    for line in summary.split('\n'):
        lines.textLine(line)
        y -= 14
        if y < 50:
            p.drawText(lines)
            p.showPage()
            lines = p.beginText(40, height - 50)
            y = height - 50
    p.drawText(lines)
    p.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='summary.pdf', mimetype='application/pdf')

if __name__ == "__main__":
    app.run(debug=False, host='0.0.0.0', port=5000)

