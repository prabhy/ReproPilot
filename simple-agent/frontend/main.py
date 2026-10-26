"""FastAPI proxy and dashboard server for ReproPilot."""

import json
import os
import uuid
import httpx
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles

app = FastAPI(title="ReproPilot Dashboard")

AGENT_SERVICE_URL = os.environ.get("AGENT_SERVICE_URL", "http://127.0.0.1:8000")
AGENT_ENGINE_RESOURCE_NAME = os.environ.get("AGENT_ENGINE_RESOURCE_NAME", "")
AGENT_DIRECTORY = os.environ.get("AGENT_DIRECTORY", "app")

# In-memory session tracking for web users
_sessions: dict[str, str] = {}


@app.get("/api/health")
async def health():
    return {"status": "ok", "agent_target": AGENT_SERVICE_URL}


@app.get("/api/cases")
async def get_cases():
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{AGENT_SERVICE_URL}/api/cases")
            return resp.json()
        except Exception as e:
            return {"total": 0, "cases": [], "error": str(e)}


@app.get("/api/cases/{case_id}")
async def get_case_detail(case_id: str):
    async with httpx.AsyncClient(timeout=10) as client:
        try:
            resp = await client.get(f"{AGENT_SERVICE_URL}/api/cases/{case_id}")
            return resp.json()
        except Exception as e:
            return {"error": str(e)}


@app.post("/chat")
async def chat_handler(req: Request):
    body = await req.json()
    message = body.get("message", "")
    user_id = body.get("user_id") or "pilot_dev"
    
    # Connect directly to local ADK FastAPI endpoint
    async with httpx.AsyncClient(timeout=120) as client:
        session_id = _sessions.get(user_id)
        if not session_id:
            try:
                # Create session on ADK
                sess_resp = await client.post(
                    f"{AGENT_SERVICE_URL}/apps/app/users/{user_id}/sessions",
                    json={"state": {"explanation_detail": "balanced"}},
                    headers={"Content-Type": "application/json"}
                )
                if sess_resp.status_code == 200:
                    session_id = sess_resp.json().get("id")
                    _sessions[user_id] = session_id
                else:
                    session_id = str(uuid.uuid4())
            except Exception:
                session_id = str(uuid.uuid4())

        # Call ADK /run_sse
        payload = {
            "app_name": "app",
            "user_id": user_id,
            "session_id": session_id,
            "new_message": {"role": "user", "parts": [{"text": message}]},
            "streaming": True
        }

        try:
            resp = await client.post(
                f"{AGENT_SERVICE_URL}/run_sse",
                json=payload,
                headers={"Content-Type": "application/json"}
            )
            
            # Aggregate response text
            reply_texts = []
            for line in resp.text.splitlines():
                if line.startswith("data: "):
                    try:
                        chunk = json.loads(line[6:])
                        content = chunk.get("content")
                        if content and content.get("parts"):
                            for p in content["parts"]:
                                if p.get("text"):
                                    reply_texts.append(p["text"])
                    except Exception:
                        pass

            full_reply = "".join(reply_texts).strip() or "No response from agent."
            return JSONResponse({
                "parts": [{"kind": "text", "text": full_reply}],
                "session_id": session_id
            })
        except Exception as e:
            return JSONResponse({
                "parts": [{"kind": "text", "text": f"Error communicating with agent: {str(e)}"}]
            })


app.mount("/", StaticFiles(directory="static", html=True), name="static")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=int(os.environ.get("PORT", 8080)))
