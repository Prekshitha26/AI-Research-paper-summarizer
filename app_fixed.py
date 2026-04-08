from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_file, flash, current_app
from flask_session import Session
from flask_login import LoginManager, login_user, logout_user, login_required, current_user
from flask_wtf.csrf import CSRFProtect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from models import db, User, Document
from config import config
from io import BytesIO
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import letter
from werkzeug.utils import secure_filename
from werkzeug.security import check_password_hash
import secrets
import os
import json
from collections import Counter
import re
from dotenv import load_dotenv

load_dotenv()

login_manager = LoginManager()
login_manager.login_view = 'login'

def create_app(config_name='default'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Init extensions
    db.init_app(app)
    login_manager.init_app(app)
    Session(app)
    csrf = CSRFProtect(app)
    limiter = Limiter(
        key_func=get_remote_address,
        app=app,
        default_limits=["200 per day", "50 per hour"]
    )
    
    # Ensure upload folder
    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
    
    # Login loader
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    @login_manager.unauthorized_handler
    def unauthorized():
        return redirect(url_for('login'))
    
    return app

app = create_app()


login_manager = LoginManager()
login_manager.login_view = 'login'

groq_api_key = os.getenv("GROQ_API_KEY")
llm_model = os.getenv("LLM_MODEL", "llama3-8b-8192")
embedding_model = os.getenv("EMBEDDING_MODEL", "sentence-transformers/all-MiniLM-L6-v2")

llm = ChatGroq(groq_api_key = groq_api_key, model_name = llm_model)
embedder = HuggingFaceEmbeddings(model_name=embedding_model)


def require_login():
    return login_required(lambda: None)()



@app.route('/')
def index():
    if current_user.is_authenticated:
        return redirect(url_for('home'))
    return redirect(url_for('login'))


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    error = None
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        user = User.query.filter_by(email=email).first()
        if user and user.check_password(password):
            login_user(user)
            session['user_name'] = user.name
            return redirect(url_for('home'))
        else:
            error = 'Invalid email or password.'

    return render_template('login.html', error=error)


@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if current_user.is_authenticated:
        return redirect(url_for('home'))

    error = None
    if request.method == 'POST':
        full_name = request.form.get('name', '').strip()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '').strip()
        confirm_password = request.form.get('confirm_password', '').strip()

        if not full_name or not email or not password or not confirm_password:
            error = 'Please enter name, email, password, and confirm password.'
        elif '@' not in email or '.' not in email:
            error = 'Enter a valid email address.'
        elif password != confirm_password:
            error = 'Passwords do not match.'
        elif User.query.filter_by(email=email).first():
            error = 'An account with this email already exists.'
        else:
            user = User(email=email, name=full_name)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            login_user(user)
            return redirect(url_for('home'))

    return render_template('signup.html', error=error)


@app.route('/logout')
@logout_user
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
    
    user_message = request.json.get('message')
    if not user_message:
        return jsonify({"response": "No message provided."}), 400
    
    try:
        vectordb = create_vector_db(text=full_text, embedder=embedder)
        chain = get_qa_chain(vectordb=vectordb, llm=llm)
        ai_response = chain.invoke(user_message)['result']
        return jsonify({"response": ai_response})
    except Exception as e:
        print(f"Chat error: {str(e)}")
        return jsonify({"response": f"Sorry, some error occurred: {str(e)[:100]}"}), 500

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
