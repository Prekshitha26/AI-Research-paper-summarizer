from langchain_groq import ChatGroq
from langchain_huggingface import HuggingFaceEmbeddings
from flask import Flask, render_template, request, jsonify

from src.load_and_extract_text import extract_text_from_pdf, extract_pdf_sections
from src.detect_and_split_sections import refine_sections, split_sections_with_content
from src.get_summary import generate_detailed_summary
from src.create_vector_db import create_vector_db
from src.RAG_retrival_chain import get_qa_chain


from dotenv import load_dotenv
import os, json

load_dotenv()

app = Flask(__name__)
app.config['UPLOAD_FOLDER'] = 'uploads'

# Ensure upload folder exists
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

groq_api_key = os.getenv("GROQ_API_KEY")
llm_model = os.getenv("LLM_MODEL")
embedding_model = os.getenv("EMBEDDING_MODEL")

# Global variable
full_text = ''
Research_paper_topics = None
vector_db = None


llm  = ChatGroq(groq_api_key = groq_api_key, model_name = llm_model)

# Initialize embeddings using the Hugging Face model
embedder = HuggingFaceEmbeddings(model_name=embedding_model)

# print(llm.invoke("why diwali celebrate ?").content)


@app.route('/')
def index():
    return render_template('index.html')

@app.route('/upload', methods=['POST'])
def upload_pdf():
    global full_text, Research_paper_topics, vector_db
    full_text = ''
    Research_paper_topics = None
    vector_db = None
    
    file = request.files.get('file')
    
    if not file:
        return jsonify({"error": "No file uploaded"}), 400
    
    filename = os.path.join(app.config['UPLOAD_FOLDER'], file.filename)
    # print(filename)
    file.save(filename)
    
    # Get all topics name from research paper
    extracted_text = extract_text_from_pdf(filename)
    full_text = extracted_text
    extracted_sections = extract_pdf_sections(full_text=extracted_text)
    # print(extracted_sections)
    refined_sections = refine_sections(extracted_sections, llm)
    # print(refined_sections)
    section_with_content = split_sections_with_content(extracted_text, refined_sections)
    
    Research_paper_topics = section_with_content
    
    return jsonify({"topics": list(Research_paper_topics.keys())})


@app.route('/summary', methods=['POST'])
def get_summary():
    global Research_paper_topics
    
    topic = request.json.get('topic')
    # print(topic)
    
    topic_content = Research_paper_topics.get(topic, "No summary available.")
    
    summary = generate_detailed_summary(topic_content, llm)
    
    return jsonify({"summary": summary})
    

@app.route('/chat', methods=['POST'])
def chat():
    global full_text
    global vector_db
    
    user_message = request.json.get('message')
    print(user_message)
    
    if not vector_db:
        vectordb = create_vector_db(text=full_text, embedder=embedder)
        vector_db = vectordb
        
    chain = get_qa_chain(vectordb=vector_db, llm=llm)
    
    ai_response = chain.invoke(user_message)['result']
    print(ai_response)
    
    return jsonify({"response": ai_response})

@app.route('/generate_pdf', methods=['POST'])
def generate_pdf():
    data = request.json
    summary = data['summary'][:4000]  # Limit length
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

@app.route('/analyze')
def analyze():
    global Research_paper_topics
    from collections import Counter
    if Research_paper_topics is None:
        return jsonify({'keywords': [], 'topics': [], 'trend_scores': []})
    
    import re
    all_content = ' '.join([str(v) for v in Research_paper_topics.values()])
    # Remove stopwords and filter meaningful words
    words = re.findall(r'\b[a-zA-Z]{4,}\b', all_content.lower())
    stopwords = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'had', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'has', 'him', 'his', 'how', 'its', 'may', 'new', 'now', 'old', 'see', 'two', 'way', 'who', 'boy', 'did', 'its', 'let', 'put', 'say', 'she', 'too', 'use', 'your', 'is', 'to', 'we', 'as', 'a', 'in', 'on', 'of', 'or'}
    filtered_words = [w for w in words if w not in stopwords and len(w) > 3]
    keywords = Counter(filtered_words).most_common(10)
    
    topics = list(Research_paper_topics.keys())[:8]
    
    trend_scores = [len(str(v)) for v in list(Research_paper_topics.values())[:5]]
    
    return jsonify({
        'keywords': keywords,
        'topics': topics,
        'trend_scores': trend_scores
    })

        
    
    
    

if __name__ == "__main__":
    app.run(debug=True)
    
    # extracted_text = extract_text_from_pdf("paper.pdf")
    # print(extracted_text)
    # extracted_sections = extract_pdf_sections(full_text = extracted_text)
    # # with open("extracted_sections.json", "w") as f:
    # #     json.dump(extracted_sections, f, indent=4)
    
    # refined_sections = refine_sections(extracted_sections, llm)
    # # with open("refined_sections.json", "w") as f:
    # #     json.dump(refined_sections, f, indent=4)
    
    # section_with_content = split_sections_with_content(extracted_text, refined_sections)
    # with open("section_with_content.json", "w") as f:
    #     json.dump(section_with_content, f, indent=4)
    
    
    


