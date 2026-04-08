from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file
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
        with open(USERS_FILE, 'r', encoding='utf-8') as f:
            try:
                return json.load(f)
            except:
                pass
    return {'admin@example.com': {'name': 'Admin', 'password': 'admin123'}}

def save_users(users):
    with open(USERS_FILE, 'w') as f:
        json.dump(users, f)

users = load_users()

groq_api_key = os.getenv("GROQ_API_KEY")
llm_model = os.getenv("LLM_MODEL", "llama3-8b-8192")
embedding_model = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

llm = ChatGroq(groq_api_key=groq_api_key, model_name=llm_model)
embedder = HuggingFaceEmbeddings(model_name=embedding_model)

def login_required(f):
    def decorated(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated

@app.route('/')
def index():
    return redirect(url_for('login' if 'username' not in session else 'home'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session:
        return redirect(url_for('home'))
    if request.method == 'POST':
        email = request.form['email'].lower()
        password = request.form['password']
        user = users.get(email)
        if user and user['password'] == password:
            session['username'] = email
            session['user_name'] = user['name']
            return redirect(url_for('home'))
        flash('Invalid credentials')
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if 'username' in session:
        return redirect(url_for('home'))
    if request.method == 'POST':
        email = request.form['email'].lower()
        name = request.form['name']
        password = request.form['password']
        if password == request.form['confirm_password'] and email not in users:
            users[email] = {'name': name, 'password': password}
            save_users(users)
            session['username'] = email
            session['user_name'] = name
            return redirect(url_for('home'))
        flash('Signup failed')
    return render_template('signup.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/home')
@login_required
def home():
    return render_template('home.html', user_name=session['user_name'])

@app.route('/about')
@login_required
def about():
    return render_template('about.html')

@app.route('/features')
@login_required
def features():
    return render_template('features.html')

@app.route('/upload', methods=['GET', 'POST'])
@login_required
def upload():
    if request.method == 'POST':
        file = request.files['file']
        if file and file.filename.endswith('.pdf'):
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
        flash('PDF only')
    return render_template('upload.html')

@app.route('/qa')
@login_required
def qa():
    return render_template('qa.html')

@app.route('/visualization')
@login_required
def visualization():
    return render_template('visualization.html')

@app.route('/summary', methods=['POST'])
@login_required
def get_summary():
    topic = request.json['topic']
    content = session['topics'][topic]
    summary = generate_detailed_summary(content, llm)
    return jsonify({'summary': summary})

@app.route('/chat', methods=['POST'])
@login_required
def chat():
    text = session.get('full_text')
    if not text:
        return jsonify({'response': 'Upload first'}), 400
    msg = request.json['message']
    vectordb = create_vector_db(text=text, embedder=embedder)
    chain = get_qa_chain(vectordb=vectordb, llm=llm)
    response = chain.invoke(msg)['result']
    return jsonify({'response': response})

@app.route('/analyze')
@login_required
def analyze():
    topics = session.get('topics', {})
    content = ' '.join(topics.values())
    words = re.findall(r'\w{4,}', content.lower())
    stopwords = set('the and for are but not you all can had her was one our out day get has him his how its may new now old see two way who boy did let put say she too use your is to we as a in on of or'.split())
    filtered = [w for w in words if w not in stopwords]
    keywords = Counter(filtered).most_common(10)
    return jsonify({'keywords': keywords, 'topics': list(topics.keys())[:8], 'trend_scores': [len(str(v)) for v in list(topics.values())[:5]]})

@app.route('/translate_summary', methods=['POST'])
@login_required
def translate_summary():
    summary = request.json['summary']
    prompt = f"Translate to Hindi: {summary}"
    return jsonify({'hindi_summary': llm.invoke(prompt).content})

@app.route('/generate_pdf', methods=['POST'])
@login_required
def generate_pdf():
    summary = request.json['summary'][:4000]
    buffer = BytesIO()
    c = canvas.Canvas(buffer, pagesize=letter)
    text_object = c.beginText(50, 800)
    for line in summary.split('\n'):
        text_object.textLine(line[:100])
    c.drawText(text_object)
    c.save()
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name='summary.pdf')

if __name__ == '__main__':
    app.run(debug=False)

