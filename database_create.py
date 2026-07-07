"""
database_create.py
-------------------
Ingestion pipeline for the RAG system.

Steps:
    1. Load a PDF
    2. Split it into overlapping chunks
    3. Embed each chunk (Mistral embeddings)
    4. Persist the embeddings into a local Chroma vector store

Run this ONCE whenever you add/change the source PDF.
Querying happens separately in main.py.
"""

import os
import sys
from dotenv import load_dotenv
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_mistralai import MistralAIEmbeddings
from langchain_community.vectorstores import Chroma

load_dotenv()

# ---- Config (change these as needed) ----
PDF_PATH = os.getenv("PDF_PATH", "document_loaders/Cloud_Computing_Exam_Notes.pdf")
PERSIST_DIR = os.getenv("CHROMA_DIR", "chroma-db")
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 1000))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 200))
EMBED_MODEL = "mistral-embed"


def build_vectorstore() -> None:
    if not os.getenv("MISTRAL_API_KEY"):
        sys.exit(
            "ERROR: MISTRAL_API_KEY not found. "
            "Add it to a .env file in this folder (see .env.example)."
        )

    if not os.path.exists(PDF_PATH):
        sys.exit(f"ERROR: PDF not found at '{PDF_PATH}'. Check PDF_PATH in .env.")

    print(f"[1/4] Loading PDF from: {PDF_PATH}")
    docs = PyPDFLoader(PDF_PATH).load()
    print(f"      Loaded {len(docs)} page(s).")

    print(f"[2/4] Splitting into chunks (size={CHUNK_SIZE}, overlap={CHUNK_OVERLAP})")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
    )
    chunks = splitter.split_documents(docs)
    print(f"      Created {len(chunks)} chunk(s).")

    print(f"[3/4] Embedding chunks with '{EMBED_MODEL}'")
    embedding_model = MistralAIEmbeddings(model=EMBED_MODEL)

    print(f"[4/4] Persisting vector store to: {PERSIST_DIR}")
    Chroma.from_documents(
        documents=chunks,
        embedding=embedding_model,
        persist_directory=PERSIST_DIR,
    )

    print("\nDone. Vector store is ready — run main.py to start querying.")


if __name__ == "__main__":
    build_vectorstore()
