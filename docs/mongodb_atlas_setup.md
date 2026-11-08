# MongoDB Atlas setup (vector database + storage)

## 0. Current live deployment (created 2026-11-08 with the Atlas CLI)
| Item | Value |
|---|---|
| Atlas account / organisation | `sani260105@gmail.com` / "Saanvi's Org - 2026-11-07" |
| Project | **SkillPath AI** (`6aef8bc9b64186873a8b7606`) |
| Cluster | **skillpath-cluster**, M0 free, AWS Mumbai (`AP_SOUTH_1`), host `skillpath-cluster.fozgv6t.mongodb.net` |
| Database user | `skillpath_app` (readWriteAnyDatabase). Random 32-char password, stored **only** in `.env` (`MONGODB_URI`) |
| Network access | The project Mac's IP (added by `--currentIp`). Teammates: `atlas accessLists create --currentIp` |
| Database | `skillpath_ai`: `careers_embeddings_v1` (2,899), `knowledge_chunks_v1` (17 guides + 153 jobs), `user_profile_chunks_v1` (39) |
| Vector indexes | `career_vector_index`, `knowledge_vector_index`, `profile_vector_index`: all READY/queryable |
| Verification | `python -m src.rag.check_atlas --query "Python SQL data analyst"` → top 5 = Data Analyst records (0.50–0.52); Atlas top 5 = exact local top 5 (5/5); retrieval median 359 ms. Saved in `reports/embeddings/atlas_check_latest.txt` |

Commands that created it:
```bash
atlas auth login                                   # browser approval (UserAccount)
atlas projects create "SkillPath AI" --orgId <org-id>
atlas config set project_id <project-id>
atlas setup --projectId <project-id> --clusterName skillpath-cluster --provider AWS --region AP_SOUTH_1 \
  --tier M0 --username skillpath_app --password '<random>' --currentIp --skipSampleData --connectWith skip --force
python -m src.rag.ingest --sources all --backend mongo
```

**Giving teammates access:** Atlas → Project *SkillPath AI* → **Project Identity & Access → Invite to Project** (their email, role *Project Data Access Read/Write* or *Project Owner*). For the app, they need the same `MONGODB_URI` (share it privately, never in Git or chat), and their IP added under Network Access.


Until `MONGODB_URI` is set, the app uses a local numpy store with exactly the same collections, so everything runs offline. These steps switch it to Atlas.

> **Account login ≠ database login.** The Atlas *website* account (email + password) is only for the web UI. The application connects with a **database user** inside a `mongodb+srv://` connection string, created in step 1. Never put the website password in code or `.env`.

## 0b. Access from other devices and the deployed app (E34)

| Who connects | Database user | Network access needed |
|---|---|---|
| Project Mac (development) | `skillpath_app` (readWriteAnyDatabase) | its own IP (added with `--currentIp`; re-add when the ISP rotates it, e.g. 49.37.117.224 → 49.37.113.161 on 2026-11-08) |
| **Deployed app (Streamlit Cloud)** | **`skillpath_cloud`**: read/write on **`skillpath_ai` only** (verified: writes to any other database are denied) | **`0.0.0.0/0`** (Streamlit Cloud has no fixed outbound IPs) |
| Teammates' laptops | `skillpath_cloud` (or their own user) | their IPs, or covered by `0.0.0.0/0` |

**Step 1: allow access from anywhere** (done by the project owner. Our automation policy does not open a database to the internet by itself):
```bash
atlas accessLists create 0.0.0.0/0 --comment "Deployed SkillPath app + team devices" --projectId 6aef8bc9b64186873a8b7606
```
or Atlas → project *SkillPath AI* → **Security → Network Access → + Add IP Address → Allow access from anywhere → Confirm**.

> ⚠️ **Select the right project first** (top-left project dropdown = **SkillPath AI**). The organisation also contains an empty **"Project 0"**. An entry added there shows **Inactive** (that project has no cluster) and does nothing for `skillpath-cluster`. This happened on 2026-11-08. Check with:
> `atlas accessLists list --projectId 6aef8bc9b64186873a8b7606` (the SkillPath AI project). It must list `0.0.0.0/0`.

**Secrets:** paste the **contents** of the generated TOML (3 `KEY = "value"` lines), not the file path. A path gives *"Invalid format: please enter valid TOML"*.

**Step 2: give the deployed app the connection string.** In Streamlit Cloud → your app → **⋮ → Settings → Secrets**, paste:
```toml
MONGODB_URI = "mongodb+srv://skillpath_cloud:<password>@skillpath-cluster.fozgv6t.mongodb.net/?retryWrites=true&w=majority&appName=SkillPathCloud"
MONGODB_DB = "skillpath_ai"
PIPELINE_MODE = "inprocess"
```
(The exact text with the password was generated locally and handed over privately. It is never committed.) Save. The app restarts and the status chip shows **MongoDB Atlas · 2,899 career records**. Feedback (👍/👎) is then stored in `feedback_v1` and survives redeploys.

**Why this is acceptable:** with `0.0.0.0/0`, security rests on the credentials. `skillpath_cloud` has a random 32-character password and can only touch `skillpath_ai`. Rotate it (Atlas → Database Access → Edit → Autogenerate) if it ever leaks. The app keeps working without Atlas (local vector copy + circuit breaker).

## 1. Create the cluster and get the connection string

There are two ways. **Path A** is fastest: one browser approval, then everything runs from the terminal. **Path B** is the same thing done by clicking through the website.

### Path A: Atlas CLI (already installed on the project Mac: `atlas --version`)
1. Log in once (opens a browser page; choose **UserAccount**, sign in, click **Confirm/Authorize**):
   ```bash
   atlas auth login
   ```
2. Create a free cluster, a database user, IP access, and print the connection string, all in one command:
   ```bash
   atlas setup --clusterName skillpath-cluster --provider AWS --region AP_SOUTH_1 --tier M0 \
     --username skillpath_app --password '<choose-a-strong-password>' \
     --currentIp --skipSampleData --connectWith skip --force
   ```
   It prints `mongodb+srv://skillpath-cluster.xxxxx.mongodb.net`. Your URI is
   `mongodb+srv://skillpath_app:<password>@skillpath-cluster.xxxxx.mongodb.net/?retryWrites=true&w=majority&appName=SkillPath`
3. Useful commands later:
   ```bash
   atlas clusters list                                  # status (IDLE = ready)
   atlas clusters connectionStrings describe skillpath-cluster
   atlas accessLists create --currentIp                 # add a teammate's / new network IP
   atlas dbusers create readWriteAnyDatabase --username <teammate> --password '<pw>'
   ```

### Path B: website, click by click (about 10 minutes, free)
1. Open https://cloud.mongodb.com and sign in. If asked for a "goal" or "experience", pick anything and continue.
2. **Create a project:** at the top-left, open the project dropdown → **+ New Project** → name it `SkillPath AI` → **Next** → (optionally add teammates' emails as *Project Owner*) → **Create Project**.
3. **Create the cluster:** **+ Create** (or "Build a Database") → choose **M0 Free** → Provider **AWS**, Region **Mumbai (ap-south-1)** → name it `skillpath-cluster` → **Create Deployment**. It takes 1–3 minutes.
4. **Create a database user:** the "Connect to skillpath-cluster" dialog opens. Under *Create a database user*, set username `skillpath_app`, click **Autogenerate Secure Password**, **copy the password somewhere safe**, then **Create Database User**. (Or later: left menu **Security → Database Access → + Add New Database User** → Password auth → *Built-in role: Read and write to any database* → **Add User**.)
5. **Allow your IP:** in the same dialog, *Add your current IP address* → **Add**. (Later: **Security → Network Access → + Add IP Address → Add Current IP Address → Confirm**. For a Hugging Face deployment, also add `0.0.0.0/0` = "Allow access from anywhere".)
6. **Get the connection string:** **Choose a connection method → Drivers** → Driver **Python**, version **3.12 or later** → copy the string that looks like
   `mongodb+srv://skillpath_app:<db_password>@skillpath-cluster.abcde.mongodb.net/?retryWrites=true&w=majority&appName=skillpath-cluster`
7. Replace `<db_password>` with the password from step 4. If it contains `@ : / ? # %`, URL-encode them (`@` → `%40`).
8. Put it in `.env` as `MONGODB_URI=...` (section 2) and run the commands in section 3.

Either way, **you don't create any collections or indexes by hand**. The ingest script does that.

## 2. Configure
In `.env` (git-ignored, never commit):
```
MONGODB_URI=mongodb+srv://skillpath_app:<db-password>@<cluster>.mongodb.net/?retryWrites=true&w=majority&appName=SkillPath
MONGODB_DB=skillpath_ai
VECTOR_BACKEND=auto
```
URL-encode special characters in the password (`@` → `%40`, `#` → `%23`).

## 3. Collections and indexes (created automatically)

| Collection | Contents | Vector index | Access |
|---|---|---|---|
| `careers_embeddings_v1` | 2,899 career records + vectors (source of truth) | `career_vector_index` | shared, read-mostly |
| `knowledge_chunks_v1` | career and study guides (`source=knowledge`) **and** scraped jobs (`source=jobs`) | `knowledge_vector_index` | shared |
| `user_profile_chunks_v1` | a user's resume/JD analysis chunks | `profile_vector_index` | **private**, filtered by `user_id` |

> **M0 limit: at most 3 Atlas Search / Vector Search indexes per cluster.** The first design used 4 collections and failed with `The maximum number of FTS indexes has been reached for this instance size`. Jobs therefore share the knowledge collection, separated by the indexed `source` filter (E19). A paid tier (M10+) would allow a separate `job_listings_v1`: set `MONGODB_JOBS_COLLECTION`.

```bash
python -m src.rag.ingest --sources all --backend mongo     # embed + upsert + create indexes + wait until queryable
python -m src.rag.check_atlas --query "Python SQL data analyst"
```
`check_atlas` pings the cluster. For each collection it prints index status (`queryable`), counts and the stored `embedding_model`, then runs a real career query. That's the doc §14.3 checkpoint: "Atlas collection and Vector Search index verified through at least one real query".

To create an index by hand instead (**Atlas Search → Create Search Index → Vector Search → JSON editor**):
```json
{"fields": [
  {"type": "vector", "path": "embedding", "numDimensions": 384, "similarity": "cosine"},
  {"type": "filter", "path": "source"}, {"type": "filter", "path": "user_id"},
  {"type": "filter", "path": "doc_type"}, {"type": "filter", "path": "domain"}
]}
```

## 4. Query used by the app
```js
db.careers_embeddings_v1.aggregate([
  { $vectorSearch: { index: "career_vector_index", path: "embedding",
      queryVector: [/* 384 floats from MiniLM */], numCandidates: 100, limit: 5,
      filter: { source: { $in: ["careers"] }, user_id: { $in: ["global"] } } } },
  { $project: { embedding: 0, score: { $meta: "vectorSearchScore" } } }
])
```
Atlas returns `(1 + cos) / 2`. The code converts it back to cosine, so the thresholds are identical locally and on Atlas.

## 5. Safety rules built into the code
- **Model guard:** searching a collection whose stored `embedding_model` differs from `EMBEDDING_MODEL` raises an error, so a teammate's MiniLM vectors can never be searched with another model.
- **Idempotent ingest:** upsert by `_id`, then prune stale IDs. Re-running never duplicates.
- **Privacy:** resume-derived chunks live only in `user_profile_chunks_v1`, tagged `user_id`, and every search filters by `user_id ∈ {global, current user}`.

## 6. Sizing
About 3.1k vectors × (1.5 KB vector + ~0.7 KB text and metadata) ≈ **7 MB**, against M0's 512 MB. M0 also limits throughput (about 100 ops/s) and allows 3 search indexes.

## 7. Troubleshooting
| Symptom | Fix |
|---|---|
| `ServerSelectionTimeoutError` | Your IP isn't in Network Access, or the URI or password is wrong |
| `bad auth : authentication failed` | You used the *website* password. Use the database user's password |
| Search returns `[]` right after ingest | The index is still building. `check_atlas` waits until `queryable: true` |
| `maximum number of FTS indexes has been reached` | M0 allows 3 search indexes. Don't add collections. After dropping one, wait about 30 s for its index to be deleted |
| `holds vectors from <model>` error | The collection was written with another model. Re-ingest, or set `EMBEDDING_MODEL` to match |
