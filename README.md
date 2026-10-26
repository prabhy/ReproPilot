# ReproPilot — Autonomous API Bug Investigator & Reproduction Pilot

ReproPilot turns vague API bug reports into evidence-backed investigations, reproducible test steps, and structured engineering handoffs. Built on Google Agent Development Kit (ADK) and Gemini 3.8 Flash, it integrates with Google Cloud Storage for persistent case isolation and GitHub for automated issue tracking.

---

## 🌟 Key Features

1. **Simulated Diagnostic Execution & Isolation Testing**:
   - Tests endpoints against predefined demo credentials (`demo-expired-token` returning `401 Unauthorized "Demo token rejected."`, and `demo-valid-token` returning `200 OK`).
   - Clearly separates **observed facts** from **active hypotheses** (a 401 response alone never asserts password revocation until verified through isolation and documentation).
2. **Troubleshooting Guide Retrieval**:
   - Matches symptom patterns against internal engineering runbooks (e.g. `KB-AUTH-101` for credential modifications).
3. **Google Cloud Storage Persistence**:
   - Each investigation is stored as an independent, isolated JSON object at `gs://<BUCKET_NAME>/cases/{case_id}.json`.
   - User explanation preferences (`concise` vs. `detailed`) persist under `gs://<BUCKET_NAME>/preferences/{user_id}.json`.
   - Does not use a shared monolithic file, preventing race conditions and overwrites.
4. **GitHub Issues Integration**:
   - Previews issue titles and engineering handoffs in an interactive modal.
   - Prominently labels all diagnostic evidence as **simulated**.
   - Requires explicit user confirmation prior to creating issues.
   - Tracks created issue URLs and prevents duplicate creations.
5. **Interactive Split-View Dashboard**:
   - Interactive chat on the left communicating with ADK via `/chat`.
   - Real-time Investigation Board on the right displaying observed evidence feeds, facts vs. hypotheses, and copyable handoffs.

---

## 🏗️ Architecture

```
┌────────────────────────────────────────────────────────┐
│                   ReproPilot Dashboard                 │
│         (Interactive Split-View HTML5 / Vanilla JS)    │
└──────────────┬──────────────────────────┬──────────────┘
               │                          │
       REST / Chat SSE             Issue Preview / GCS
               │                          │
               ▼                          ▼
┌────────────────────────────────────────────────────────┐
│                   FastAPI Application                  │
│       - ADK Runner (gemini-3.8-flash)                  │
│       - GCS Storage Client (app/storage_client.py)     │
│       - GitHub Integration Client (app/github_client.py│
└──────────────┬──────────────────────────┬──────────────┘
               │                          │
      ┌────────┴────────┐        ┌────────┴────────┐
      ▼                 ▼        ▼                 ▼
Vertex AI Agent    GCS Bucket:   GitHub REST API   Troubleshooting
  (Gemini 3.8)    cases/{id}.json / gh CLI           Playbooks
```

---

## 🔑 Environment Variables

| Variable Name | Required | Description | Example |
| :--- | :--- | :--- | :--- |
| `GOOGLE_CLOUD_PROJECT` | Yes | Google Cloud Project ID hosting Vertex AI & GCS | `my-gcp-project` |
| `GOOGLE_CLOUD_LOCATION` | Yes | Vertex AI location / region | `global` or `us-central1` |
| `GOOGLE_GENAI_USE_VERTEXAI` | Yes | Enables Vertex AI mode for ADK | `true` |
| `REPROPILOT_GCS_BUCKET` | Yes | GCS bucket name for case persistence | `repropilot-storage-<project>` |
| `GITHUB_REPOSITORY` | Optional | Target repo for issue export | `owner/repropilot` |
| `GITHUB_TOKEN` | Optional | GitHub Personal Access Token (or authenticate via `gh auth login`) | `ghp_xxxx` |

---

## 🚀 Getting Started

### 1. Installation

```bash
cd simple-agent
uv sync
```

### 2. Configure Environment

```bash
export GOOGLE_GENAI_USE_VERTEXAI=true
export GOOGLE_CLOUD_PROJECT="<YOUR_GCP_PROJECT_ID>"
export GOOGLE_CLOUD_LOCATION="global"
export REPROPILOT_GCS_BUCKET="repropilot-storage-<YOUR_GCP_PROJECT_ID>"
```

### 3. Run the Dashboard

```bash
uv run python -m uvicorn app.fast_api_app:app --host 0.0.0.0 --port 8080
```

Open your browser to **`http://localhost:8080/dashboard/`**.

---

## 🧪 Interactive Demo Walkthrough

1. **Load Issue**: Click **"⚡ Load Demo Issue"** or use chip **"1. Report Issue"**.
2. **Execute Diagnostic**: Click **"2. Run 401 Diagnostic"** to simulate the initial failure (`"Demo token rejected."`).
3. **Lookup Runbook**: Click **"3. Search KB Playbook"** to view `KB-AUTH-101` credential revocation guidance.
4. **Approve Retry**: Click **"4. Retry with valid demo token"** to run isolation testing with `demo-valid-token` (`200 OK`).
5. **Persist to Cloud Storage**: Click **"5. Save Case & Handoff"** to save to `gs://<BUCKET_NAME>/cases/{case_id}.json`.
6. **Export to GitHub**: Click **"🐙 Create GitHub Issue"**, preview the simulated evidence notice and handoff, and confirm creation.
