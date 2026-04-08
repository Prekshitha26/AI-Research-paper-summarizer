from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
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

load_dotenv()

app = Flask(__name__)
app.secret_key = secrets.token_hex(16)
app.config['SESSION_TYPE'] = 'filesystem'
app.config['SESSION_PERMANENT'] = False
app.config['SESSION_USE_SIGNER'] = True
app.config['UPLOAD_FOLDER'] = 'uploads'
Session(app)

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

USERS_FILE = 'users.json'

def load_users():
    if os.path.exists(USERS_FILE):
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except ValueError:
                return {}
    return {'admin': 'admin123'}


def save_users(users_data):
    with open(USERS_FILE, 'w', encoding='utf-8') as f:
        json.dump(users_data, f)


users = load_users()

groq_api_key = os.getenv("GROQ_API_KEY")
llm_model = os.getenv("LLM_MODEL")
embedding_model = os.getenv("EMBEDDING_MODEL")

llm = ChatGroq(groq_api_key = groq_api_key, model_name = llm_model)
embedder = HuggingFaceEmbeddings(model_name=embedding_model)

def require_login():
    if not session.get('username'):
        return redirect(url_for('login'))


@app.route('/')
def index():
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('username'):
        return redirect(url_for('home'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            error = 'Enter both username and password.'
        elif users.get(username) != password:
            error = 'Invalid username or password.'
        else:
            session['username'] = username
            return redirect(url_for('home'))

    return render_template('login.html', error=error)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if session.get('username'):
        return redirect(url_for('home'))

    error = None
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()
        if not username or not password:
            error = 'Enter both username and password.'
        elif username in users:
            error = 'Username already exists.'
        else:
            users[username] = password
            save_users(users)
            session['username'] = username
            return redirect(url_for('home'))

    return render_template('signup.html', error=error)


@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))


@app.route('/home')
def home():
    redirect_response = require_login()
    if redirect_response:
        return redirect_response
    return render_template('home.html')


@app.route('/about')
def about():
    redirect_response = require_login()
    if redirect_response:
        return redirect_response
    return render_template('about.html')


@app.route('/features')
def features():
    redirect_response = require_login()
    if redirect_response:
        return redirect_response
    return render_template('features.html')


@app.route('/upload', methods=['GET', 'POST'])
def upload():
    redirect_response = require_login()
    if redirect_response:
        return redirect_response

    if request.method == 'POST':
        file = request.files.get('file')
        if not file:
            return jsonify({"error": "No file uploaded"}), 400

        filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
        file.save(filename)

        extracted_text = extract_text_from_pdf(filename)
        session['full_text'] = extracted_text
        extracted_sections = extract_pdf_sections(full_text=extracted_text)
        refined_sections = refine_sections(extracted_sections, llm)
        section_with_content = split_sections_with_content(extracted_text, refined_sections)

        session['topics'] = section_with_content
        session.modified = True

        return jsonify({"topics": list(section_with_content.keys())})

    return render_template('upload.html')


@app.route('/qa')
def qa():
    redirect_response = require_login()
    if redirect_response:
        return redirect_response
    return render_template('qa.html')


@app.route('/visualization')
def visualization():
    redirect_response = require_login()
    if redirect_response:
        return redirect_response
    return render_template('visualization.html')


@app.route('/summary', methods=['POST'])
def get_summary():
    topics = session.get('topics', {})
    topic = request.json.get('topic')
    topic_content = topics.get(topic, "No summary available.")
    summary = generate_detailed_summary(topic_content, llm)
    return jsonify({"summary": summary})

@app.route('/chat', methods=['POST'])
def chat():
    full_text = session.get('full_text')
    if not full_text:
        return jsonify({"response": "Please upload a document first."}), 400
    
    vector_db = session.get('vector_db')
    if not vector_db:
        vectordb = create_vector_db(text=full_text, embedder=embedder)
        session['vector_db'] = str(vectordb)  # Simple str for session
        session.modified = True
        vector_db = vectordb
        
    chain = get_qa_chain(vectordb=vector_db, llm=llm)
    user_message = request.json.get('message')
    ai_response = chain.invoke(user_message)['result']
    return jsonify({"response": ai_response})

@app.route('/analyze')
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
def translate_summary():
    summary = request.json.get('summary')
    if not summary:
        return jsonify({'hindi_summary': ''}), 400
    
    prompt = f"Translate the following English research paper summary to Hindi naturally and accurately. Keep technical terms appropriate:\n\n{summary}"
    hindi_summary = llm.invoke(prompt).content
    return jsonify({'hindi_summary': hindi_summary})

@app.route('/generate_pdf', methods=['POST'])
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
    app.run(debug=True)
