# 📄 AI Research Paper Analyzer

## 📌 Overview

This project is developed as part of an internship and focuses on building an AI-powered system to analyze and understand research papers. The application allows users to upload PDF documents and automatically generates summaries, extracts key insights, and enables interactive question-answering.

The goal of this system is to simplify complex research content using Natural Language Processing (NLP) techniques and make it easier for users to quickly grasp important information.

---

## 🎯 Objectives

* To simplify lengthy research papers
* To automate content summarization using AI
* To enable intelligent question-answering from documents
* To provide a clean and user-friendly web interface

---

## 🚀 Features

* 📄 Upload research papers (PDF)
* 🤖 AI-based detailed summarization
* 🧠 Topic-wise content extraction
* ❓ Question & Answer system (RAG-based)
* 🌐 Web interface with login/signup
* 📊 Basic visualization and keyword analysis
* 🌍 Summary translation (English → Hindi)
* 📥 Export summary as PDF

---

## 🛠️ Technologies Used

* Python
* Flask
* LangChain (Groq API)
* HuggingFace Embeddings
* NLP Techniques
* HTML, CSS, JavaScript
* ReportLab (PDF generation)

---

## 📂 Project Structure

```
├── app_prod_file.py        # Main application file (production)
├── src/                   # Core processing modules
├── templates/             # HTML pages
├── static/                # CSS & JS files
├── requirements.txt       # Dependencies
├── README.md
```

---

## ▶️ How to Run

### 1. Install dependencies

```
pip install -r requirements.txt
```

### 2. Set environment variables

Create a `.env` file and add:

```
GROQ_API_KEY=your_api_key_here
LLM_MODEL=llama3-8b-8192
```

### 3. Run the application

```
python app_prod_file.py
```

### 4. Open in browser

```
http://localhost:5000
```

---

## ⚙️ Working

1. User logs in and uploads a research paper
2. System extracts text from the PDF
3. AI processes and divides content into sections
4. Generates:

   * Topic-wise summaries
   * Detailed explanations
   * Keywords and insights
5. User can ask questions based on the document
6. Results can be translated or exported as PDF

---

## 📊 Output

* Structured summaries
* Topic-wise insights
* Keyword analysis
* AI-generated answers
* Downloadable PDF summary

---


## 👩‍💻 Author

**Prekshitha M**

---
