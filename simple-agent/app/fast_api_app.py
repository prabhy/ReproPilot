# Copyright 2026 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import contextlib
import json
import logging
import os
import uuid
from collections.abc import AsyncIterator

from a2a.server.tasks import InMemoryTaskStore
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.cli.fast_api import get_fast_api_app
from google.adk.runners import Runner
from google.genai import types

from app.app_utils import services
from app.app_utils.a2a import attach_a2a_routes
from app.app_utils.reasoning_engine_adapter import (
    attach_reasoning_engine_routes,
)
from app.github_client import create_github_issue, get_github_auth_info
from app.repropilot_tools import (
    get_case,
    get_user_preference,
    list_cases,
    save_case,
    set_user_preference,
)
from app.storage_client import BUCKET_NAME

logger = logging.getLogger(__name__)
load_dotenv()
otel_to_cloud = os.environ.get(
    "GOOGLE_CLOUD_AGENT_ENGINE_ENABLE_TELEMETRY", ""
).lower() in ("true", "1")
allow_origins = (
    os.getenv("ALLOW_ORIGINS", "").split(",") if os.getenv("ALLOW_ORIGINS") else None
)

AGENT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_web_sessions: dict[str, str] = {}


@contextlib.asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    from app.agent import app as adk_app
    from app.agent import root_agent

    runner = Runner(
        app=adk_app,
        session_service=services.get_session_service(),
        artifact_service=services.get_artifact_service(),
        auto_create_session=True,
    )
    app.state.runner = runner
    app.state.agent_app_name = adk_app.name
    await attach_a2a_routes(
        app,
        agent=root_agent,
        runner=runner,
        task_store=InMemoryTaskStore(),
        rpc_path=f"/a2a/{adk_app.name}",
    )
    yield


app: FastAPI = get_fast_api_app(
    agents_dir=AGENT_DIR,
    web=True,
    artifact_service_uri=services.ARTIFACT_SERVICE_URI,
    allow_origins=allow_origins,
    session_service_uri=services.SESSION_SERVICE_URI,
    otel_to_cloud=otel_to_cloud,
    lifespan=lifespan,
)
app.title = "repropilot-agent"
app.description = "API for interacting with ReproPilot"

attach_reasoning_engine_routes(app)


# REST endpoints for ReproPilot Investigation Dashboard
@app.get("/api/storage/info")
async def api_storage_info():
    return {
        "bucket": BUCKET_NAME,
        "project": os.environ.get("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-04-d32f9369da59"),
        "backend": "Google Cloud Storage",
        "temporary_notice": "Workshop Qwiklabs GCP projects and GCS buckets are temporary and are torn down when the lab session expires."
    }


@app.get("/api/cases")
async def api_list_cases():
    return list_cases()


@app.get("/api/cases/{case_id}")
async def api_get_case(case_id: str):
    res = get_case(case_id)
    if not res.get("found"):
        raise HTTPException(status_code=404, detail="Case not found")
    return res["case"]


@app.post("/api/cases")
async def api_save_case(payload: dict):
    res = save_case(**payload)
    if not res.get("success"):
        raise HTTPException(status_code=500, detail=res.get("error", "Failed saving case"))
    return res


@app.get("/api/preferences/{user_id}")
async def api_get_preference(user_id: str):
    return get_user_preference(user_id)


@app.post("/api/preferences/{user_id}")
async def api_set_preference(user_id: str, payload: dict):
    detail_level = payload.get("detail_level", "balanced")
    return set_user_preference(user_id, detail_level)


# GitHub Integration Endpoints
@app.get("/api/github/status")
async def api_github_status():
    return get_github_auth_info()


@app.post("/api/cases/{case_id}/github_issue/preview")
async def api_preview_github_issue(case_id: str):
    res = get_case(case_id)
    if not res.get("found"):
        raise HTTPException(status_code=404, detail="Case not found")
    c = res["case"]

    title = f"[{c.get('case_id')}] API Authentication Failure — /v1/orders"
    handoff = c.get("handoff_notes") or c.get("summary") or "Investigation details."
    
    body = (
        "> [!IMPORTANT]\n"
        "> **SIMULATED EVIDENCE NOTICE:**\n"
        "> The reproduction traces and diagnostic responses in this issue were produced using simulated endpoints and predefined demo credentials (`demo-expired-token`, `demo-valid-token`).\n\n"
        f"### Case ID: {c.get('case_id')}\n"
        f"**Status:** {c.get('status', 'Investigating')}\n\n"
        f"### Engineering Handoff\n\n{handoff}\n"
    )

    return {
        "case_id": case_id,
        "title": title,
        "body": body,
        "already_created": bool(c.get("github_issue_url")),
        "existing_url": c.get("github_issue_url")
    }


@app.post("/api/cases/{case_id}/github_issue/create")
async def api_create_github_issue(case_id: str, payload: dict):
    res = get_case(case_id)
    if not res.get("found"):
        raise HTTPException(status_code=404, detail="Case not found")
    c = res["case"]

    # Duplicate creation check
    if c.get("github_issue_url"):
        return {
            "success": True,
            "duplicate": True,
            "issue_url": c.get("github_issue_url"),
            "message": f"GitHub Issue already exists for {case_id}."
        }

    title = payload.get("title") or f"[{case_id}] API Authentication Failure — /v1/orders"
    body = payload.get("body") or c.get("handoff_notes") or c.get("summary")

    issue_res = create_github_issue(title=title, body=body)
    if not issue_res.get("success"):
        return JSONResponse(status_code=400, content=issue_res)

    # Save issue URL back to GCS case
    issue_url = issue_res.get("issue_url")
    c["github_issue_url"] = issue_url
    save_case(
        case_id=case_id,
        title=c.get("title", ""),
        user_report=c.get("user_report", ""),
        evidence=c.get("evidence", []),
        hypotheses=c.get("hypotheses", []),
        repro_steps=c.get("repro_steps", []),
        status=c.get("status", "Investigating"),
        next_check=c.get("next_check", ""),
        summary=c.get("summary", ""),
        handoff_notes=c.get("handoff_notes", ""),
        github_issue_url=issue_url
    )

    return {
        "success": True,
        "issue_url": issue_url,
        "case_id": case_id
    }


# Clean JSON /chat endpoint used by dashboard
@app.post("/chat")
async def chat_handler(req: Request):
    try:
        body = await req.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON body")

    message_text = body.get("message", "").strip()
    if not message_text:
        return JSONResponse({"reply": "Please provide a non-empty message.", "status": "ok"})

    user_id = body.get("user_id") or "pilot_dev"
    runner: Runner = app.state.runner
    session_service = runner.session_service

    session_id = body.get("session_id") or _web_sessions.get(user_id)
    if not session_id:
        try:
            sess = await session_service.create_session(user_id=user_id, app_name=app.state.agent_app_name)
            session_id = sess.id
            _web_sessions[user_id] = session_id
        except Exception:
            session_id = str(uuid.uuid4())
            _web_sessions[user_id] = session_id
    else:
        _web_sessions[user_id] = session_id

    msg = types.Content(
        role="user",
        parts=[types.Part.from_text(text=message_text)]
    )

    try:
        collected_text = []
        async for event in runner.run_async(
            new_message=msg,
            user_id=user_id,
            session_id=session_id,
            run_config=RunConfig(streaming_mode=StreamingMode.NONE)
        ):
            if event.content and event.content.parts:
                for part in event.content.parts:
                    if part.text:
                        collected_text.append(part.text)

        full_reply = "".join(collected_text).strip()
        if not full_reply:
            full_reply = "Investigation step processed. Please check the investigation board on the right for updated evidence."

        return JSONResponse({
            "reply": full_reply,
            "session_id": session_id,
            "status": "success"
        })
    except Exception as e:
        return JSONResponse(
            status_code=500,
            content={
                "error": f"Agent execution failed: {str(e)}",
                "session_id": session_id,
                "status": "error"
            }
        )


STATIC_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static")
INDEX_PATH = os.path.join(STATIC_DIR, "index.html")

@app.get("/")
async def root_index():
    if os.path.exists(INDEX_PATH):
        return FileResponse(INDEX_PATH)
    return {"message": "ReproPilot API running."}

if os.path.exists(STATIC_DIR):
    app.mount("/dashboard", StaticFiles(directory=STATIC_DIR, html=True), name="dashboard")


if __name__ == "__main__":
    import uvicorn

    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
