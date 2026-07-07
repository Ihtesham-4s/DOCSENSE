# DocSense

DocSense is a document Q&A app built with LangChain, Mistral, Chroma, FastAPI, and React.

## Project layout

- `main.py` runs the CLI version.
- `database_create.py` builds the Chroma index from a PDF.
- `backend/` contains the API server.
- `frontend/` contains the React chat UI.
- `dev.py` starts the backend and frontend together.

## Setup

Create a `.env` file in the project root:

```env
MISTRAL_API_KEY=your_key_here
```

Install dependencies:

```bash
pip install -r requirements.txt
pip install -r backend/requirements.txt
cd frontend
npm install
```

## Run

From the project root:

```bash
python dev.py
```

That starts the API on `http://localhost:8000` and the UI on `http://localhost:3000`.

If you want the CLI instead:

```bash
python main.py
```

To build the initial index manually:

```bash
python database_create.py
```

## API

- `POST /chat` asks a question and returns an answer plus source chunks.
- `POST /upload` uploads a PDF and rebuilds the Chroma index.
- `GET /health` returns backend status.

## Notes

- The embedding model must match between ingestion and query time.
- Uploading a new PDF replaces the current index.
- The UI shows the source chunks used for each answer.
