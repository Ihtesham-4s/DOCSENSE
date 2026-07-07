# DocSense

DocSense is a small RAG app for asking questions about PDF documents. It uses LangChain, Mistral, Chroma, a FastAPI backend, and a React frontend.

## What’s in the repo

- `main.py` for the CLI version
- `database_create.py` for one-time PDF ingestion
- `backend/` for the FastAPI API
- `frontend/` for the React chat UI
- `dev.py` to start both web servers together

## Setup

1. Create a `.env` file in the project root and add your Mistral API key.

```env
MISTRAL_API_KEY=your_key_here
```

2. Install Python dependencies.

```bash
pip install -r requirements.txt
pip install -r backend/requirements.txt
```

3. Install the frontend dependencies once.

```bash
cd frontend
npm install
```

## Run it

### Web app

From the project root:

```bash
python dev.py
```

That starts the FastAPI backend on `http://localhost:8000` and the React UI on `http://localhost:3000`.

### CLI

```bash
python main.py
```

### First PDF upload

Use the upload button in the web app, or run:

```bash
python database_create.py
```

## API

### `POST /chat`

Request body:

```json
{ "question": "What is cloud computing?" }
```

Response shape:

```json
{
  "answer": "...",
  "sources": [
    {
      "content": "...",
      "page": 4,
      "source": "Cloud_Computing_Exam_Notes.pdf"
    }
  ]
}
```

### `POST /upload`

Send a PDF as `multipart/form-data` with a `file` field. The upload replaces the current Chroma index.

### `GET /health`

Returns a simple status response and whether the vector store is loaded.

## Notes

- The embedding model must match between ingestion and querying.
- The source list is shown in the UI so answers are easier to verify.
- If you upload a new PDF, the previous index is replaced.
