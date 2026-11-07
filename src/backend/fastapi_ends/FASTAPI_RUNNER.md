# FastAPI Server — Run Instructions

## Folder Structure
```
src/
└── backend/
    └── fastapi_ends/
        ├── api_endpoint.py
        ├── linkdin.py
        ├── jobs_profile.py
        └── test_api.py
```

---

## Step 1 — Navigate to the Folder

```bash
cd src/backend/fastapi_ends
```

---

## Step 2 — Create a Virtual Environment

```bash
python -m venv venv
```

Activate it:

- **Windows**
```powershell
venv\Scripts\activate
```
- **Mac / Linux**
```bash
source venv/bin/activate
```

---

## Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

Contents of `requirements.txt`:
```
fastapi
uvicorn
beautifulsoup4
requests
```

---

## Step 4 — Start the Server



```powershell
uv run uvicorn api_endpoint:app --reload
```

You should see:
```
INFO:     Uvicorn running on http://127.0.0.1:8000 (Press CTRL+C to quit)
INFO:     Started reloader process using StatReload
INFO:     Application startup complete.
```

> `--reload` auto-restarts the server on every file save. Keep this terminal open.

---

## Step 5 — View the Docs

Open your browser and go to:

```
http://localhost:8000/docs
```

For the cleaner read-only version:

```
http://localhost:8000/redoc
```

---

## Step 6 — Run the Test Script (optional)

Open a **second terminal**, activate the environment, navigate to the same folder, then:

```powershell
python test_api.py
```

This will hit all 4 endpoints and write the responses to:
- `test_all_jobs.json`
- `test_sliced_jobs.json`
- `test_enriched_profiles.json`
- `test_full_pipeline.json`

---

## Endpoints at a Glance

| Endpoint | Method | What it does |
|---|---|---|
| `/jobs` | POST | Scrape LinkedIn, return all jobs |
| `/jobs/slice?n=3` | POST | Same, return first n jobs |
| `/profiles?n=3` | POST | Enrich a job list with full descriptions |
| `/jobs-with-profiles` | POST | Scrape + enrich in one shot |

---

## Stop the Server

```powershell
Ctrl + C
```
