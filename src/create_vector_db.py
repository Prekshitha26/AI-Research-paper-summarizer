from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.schema import Document



def create_vector_db(text, embedder):
    doc = Document(page_content = text)
    
    # Split into chunks
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=100,
        separators=["\n\n", "\n", ".", " "]
    )
    
    docs = splitter.split_documents([doc])
    print(docs)
    
    # Create FAISS vector database
    vectordb = FAISS.from_documents(docs, embedding=embedder)
    
    # Save locally
    vectordb.save_local("research_paper_vector_db")
    
    return vectordb
    

