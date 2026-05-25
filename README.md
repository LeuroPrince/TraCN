# TraCN

TraCN is a local mentor-tracking system for computational neuroscience graduate applications. It keeps faculty data, source evidence, research-direction weights, review status, and AI-assisted CV/PS matching in one dense workspace.

## Stack

- Backend: FastAPI, SQLAlchemy, SQLite
- Frontend: React, TypeScript, Vite
- LLM: OpenAI-compatible chat completion API configured through local environment variables

## Quick Start

### Backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
uvicorn app.main:app --reload --port 8000
```

### Frontend

```powershell
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`.

## LLM Configuration

Edit `backend/.env`:

```env
LLM_PROVIDER=openai-compatible
LLM_MODEL=your-model-name
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY_ENV_NAME=OPENAI_API_KEY
OPENAI_API_KEY=your-key
```

The API key is never returned by backend APIs and should not be committed.

## CSV Import

Use the review page to import pending teacher candidates from CSV. Supported headers:

```csv
name,institution,department,city,latitude,title,homepage_url,lab_url,email,phone,bio,direction_keys,evidence_sentence,source_url,source_type
```

`direction_keys` can contain comma- or semicolon-separated values:

- `network_dynamics_modeling`
- `neural_representation`
- `brain_inspired_intelligence`
- `neuroimaging`
- `ai_for_neuroscience`

Imported teachers enter the `pending` review queue.

## Official Data Batches

The public repository does not commit `backend/tracn.db`, because the local SQLite database can contain private model configuration. Official mentor data is kept as JSON import batches under `data/import_batches/`.

To rebuild the local database from a batch:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\import_teachers.py ..\data\import_batches\national_batch_001.json
.\.venv\Scripts\python.exe scripts\import_teachers.py ..\data\import_batches\national_batch_002.json
.\.venv\Scripts\python.exe scripts\import_teachers.py ..\data\import_batches\official_enrichment_001.json
```

Each user should create their own `backend/.env` and configure their own API key locally.

To enrich local teacher profiles from official homepages:

```powershell
cd backend
.\.venv\Scripts\python.exe scripts\enrich_official_pages.py
```

The enrichment script extracts research-direction text and publication entries only from official pages that can be fetched as text. Dynamic pages or pages without a clear publications section are left unchanged rather than filled with guessed data.
