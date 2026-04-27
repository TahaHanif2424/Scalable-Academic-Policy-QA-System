# Scalable Academic Policy QA System

Simple academic policy Q&A service with one API route.

The app accepts a PDF file and a question, then runs:

1. PDF ingestion and chunking
2. MinHash retrieval
3. SimHash retrieval
4. TF-IDF retrieval
5. LLM answer generation from merged evidence

All of this is handled in a single endpoint in `main.py`.

## Practical Performance Behavior

- First request for a new PDF: ingestion + all index builds run.
- Next requests for the same PDF: app reuses stored chunks and indexes.
- Follow-up questions can be sent without re-uploading the PDF, as long as one document is already indexed.
- This avoids expensive rebuilds on every request and makes repeated queries much faster.

## Setup

1. Install dependencies:

```bash
pip install -r requirements.txt
```

2. Add `.env` file:

```env
MONGO_URL=mongodb://localhost:27017
MONGO_DB=qa_system
GROQ_API_KEY=your-groq-key-here
LLM_MODEL=llama-3.3-70b-versatile
```

If `GROQ_API_KEY` is missing, the app returns a fallback answer from top retrieved text.

3. Start MongoDB.

## Run Server

```bash
python main.py
```

Server starts on:

- `http://localhost:8000`

Health check:

- `GET /health`

## Main Route

- `POST /process`

### Input (multipart/form-data)

- `file`: PDF file (required only for first/new document)
- `question`: user question
- `top_k`: optional integer (default: 5)

### Output

JSON response includes:

- `top_k`
- `top_chunks` (top retrieved chunks with full chunk text + metadata)
- `answer`
- `model`
- `evidence`
- `chunks_saved`
- `index_rebuilt` (true on first/new PDF, false when cache is reused)

## Example Request (curl)

```bash
curl -X POST "http://localhost:8000/process" \
	-F "file=@data/UG.pdf" \
	-F "question=What is the minimum GPA requirement for graduation?" \
	-F "top_k=5"
```

## Project Structure

```
.
├── data/
├── src/
│   ├── data_ingestion.py
│   ├── database.py
│   ├── minhash.py
│   ├── simhash.py
│   ├── tfidf.py
│   ├── query_processor.py
│   └── answer_generator.py
├── main.py
├── requirements.txt
└── README.md
```


ruff check . --fix
ruff format .

Invoke-RestMethod -Uri "http://localhost:8000/insights/query-patterns?min_support=0.2&max_itemset_size=3&top_n=20" -Method Get
