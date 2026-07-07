"""
app.py
------
FastAPI backend for DocSense — wraps the existing LCEL chain and ingestion
pipeline behind REST endpoints.

Endpoints
---------
POST /chat    — Ask a question, get an answer + source chunks
POST /upload  — Upload a PDF and re-ingest into Chroma
GET  /health  — Simple liveness check
"""

import os
import sys
import traceback
from contextlib import asynccontextmanager

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from langchain_mistralai import ChatMistralAI, MistralAIEmbeddings
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableLambda
from langchain_core.output_parsers import StrOutputParser
from langchain_community.vectorstores import Chroma
from langchain_community.document_loaders import PyPDFLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter

from schemas import ChatRequest, ChatResponse, SourceChunk, UploadResponse, ErrorResponse

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
# .env lives one level up (project root)
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

PERSIST_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", os.getenv("CHROMA_DIR", "chroma-db"))
)
UPLOAD_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "uploads")
)
CHAT_MODEL = os.getenv("CHAT_MODEL", "mistral-small-2506")
EMBED_MODEL = "mistral-embed"
CHUNK_SIZE = int(os.getenv("CHUNK_SIZE", 1000))
CHUNK_OVERLAP = int(os.getenv("CHUNK_OVERLAP", 200))

# ---------------------------------------------------------------------------
# Shared mutable state — rebuilt on startup and after each upload
# ---------------------------------------------------------------------------
_state: dict = {
    "chain": None,
    "retriever": None,
}


# ---------------------------------------------------------------------------
# Chain construction helpers (mirrors main.py logic)
# ---------------------------------------------------------------------------

def _get_embedding_model():
    return MistralAIEmbeddings(model=EMBED_MODEL)


def _load_retriever():
    """Load or reload the Chroma retriever from disk."""
    if not os.path.exists(PERSIST_DIR):
        return None

    vectorstore = Chroma(
        persist_directory=PERSIST_DIR,
        embedding_function=_get_embedding_model(),
    )
    return vectorstore.as_retriever(
        search_type="mmr",
        search_kwargs={"k": 4, "fetch_k": 10, "lambda_mult": 0.5},
    )


def _build_chain(retriever):
    """Build the LCEL chain.  Returns (chain, retriever_runnable) so we can
    also invoke the retriever independently to capture source docs."""

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You are a helpful AI assistant.\n\n"
                "Use ONLY the provided context to answer the question.\n\n"
                'If the answer is not present in the context, say: '
                '"I could not find the answer in the document."',
            ),
            ("human", "Context:\n{context}\n\nQuestion:\n{question}"),
        ]
    )

    llm = ChatMistralAI(model=CHAT_MODEL)

    def format_docs(docs) -> str:
        return "\n\n".join(doc.page_content for doc in docs)

    chain = (
        {
            "context": retriever | RunnableLambda(format_docs),
            "question": RunnablePassthrough(),
        }
        | prompt
        | llm
        | StrOutputParser()
    )

    return chain


def _reset_vectorstore():
    """Clear the existing Chroma collection without deleting locked files."""
    if not os.path.exists(PERSIST_DIR):
        return

    vectorstore = Chroma(
        persist_directory=PERSIST_DIR,
        embedding_function=_get_embedding_model(),
    )
    vectorstore.delete_collection()


def _init_chain():
    """Initialise (or re-initialise) the chain from the persisted vector store."""
    retriever = _load_retriever()
    if retriever is None:
        _state["chain"] = None
        _state["retriever"] = None
        return
    _state["retriever"] = retriever
    _state["chain"] = _build_chain(retriever)


# ---------------------------------------------------------------------------
# Lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Pre-build the chain on startup so the first request isn't slow."""
    _init_chain()
    os.makedirs(UPLOAD_DIR, exist_ok=True)
    yield


# ---------------------------------------------------------------------------
# FastAPI app
# ---------------------------------------------------------------------------

app = FastAPI(
    title="DocSense API",
    description="RAG-powered document Q&A",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "vector_store_ready": _state["chain"] is not None,
    }


@app.post("/chat", response_model=ChatResponse, responses={500: {"model": ErrorResponse}})
async def chat(req: ChatRequest):
    if _state["chain"] is None or _state["retriever"] is None:
        raise HTTPException(
            status_code=503,
            detail="No vector store found. Please upload a PDF first.",
        )

    try:
        # Retrieve source documents separately so we can return them
        source_docs = _state["retriever"].invoke(req.question)

        # Run the full chain for the answer
        answer = _state["chain"].invoke(req.question)

        # Build source chunk previews
        sources = []
        for doc in source_docs:
            preview = doc.page_content[:300].strip()
            if len(doc.page_content) > 300:
                preview += "…"
            sources.append(
                SourceChunk(
                    content=preview,
                    page=doc.metadata.get("page"),
                    source=doc.metadata.get("source"),
                )
            )

        return ChatResponse(answer=answer, sources=sources)

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Error generating answer: {e}")


@app.post("/upload", response_model=UploadResponse, responses={500: {"model": ErrorResponse}})
async def upload_pdf(file: UploadFile = File(...)):
    # Validate file type
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    try:
        # Save uploaded file
        os.makedirs(UPLOAD_DIR, exist_ok=True)
        safe_filename = os.path.basename(file.filename)
        file_path = os.path.join(UPLOAD_DIR, safe_filename)
        with open(file_path, "wb") as f:
            content = await file.read()
            f.write(content)

        # Load & chunk
        docs = PyPDFLoader(file_path).load()
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
        )
        chunks = splitter.split_documents(docs)

        # Wipe existing vector store contents and re-create
        _reset_vectorstore()

        Chroma.from_documents(
            documents=chunks,
            embedding=_get_embedding_model(),
            persist_directory=PERSIST_DIR,
        )

        # Rebuild the chain with the new data
        _init_chain()

        return UploadResponse(
            message=f"Successfully ingested '{file.filename}'",
            chunks_created=len(chunks),
        )

    except Exception as e:
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Ingestion failed: {e}")
