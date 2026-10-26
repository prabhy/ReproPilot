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

"""Tools for ReproPilot: API diagnostic simulation, troubleshooting guide lookup, and case/preference persistence."""

import datetime
import json
import logging
import os
from typing import Any, Dict, List, Optional

from app.storage_client import (
    BUCKET_NAME,
    download_json_blob,
    list_blobs_with_prefix,
    upload_json_blob,
)

logger = logging.getLogger(__name__)

DATA_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "data"
)
CASES_DIR = os.path.join(DATA_DIR, "cases")
PREFS_DIR = os.path.join(DATA_DIR, "preferences")

os.makedirs(CASES_DIR, exist_ok=True)
os.makedirs(PREFS_DIR, exist_ok=True)


def run_api_diagnostic(endpoint: str, auth_token: str, scenario: Optional[str] = "auth") -> Dict[str, Any]:
    """Runs a simulated API diagnostic call using predefined demo tokens.

    Args:
        endpoint: The simulated API endpoint being tested (e.g. '/v1/orders' or '/api/v2/user').
        auth_token: The demo authentication token being used (e.g. 'demo-expired-token' or 'demo-valid-token').
        scenario: The simulated test scenario ('auth', 'rate_limit', or 'timeout').

    Returns:
        A dictionary containing the simulated HTTP response status code, headers, payload, and execution timestamp.
    """
    timestamp = datetime.datetime.now(datetime.timezone.utc).isoformat()
    clean_token = auth_token.strip() if auth_token else ""

    if clean_token == "demo-expired-token":
        return {
            "is_simulated": True,
            "status_code": 401,
            "status_text": "Unauthorized",
            "endpoint": endpoint,
            "token_used": "demo-expired-token",
            "response_headers": {
                "content-type": "application/json",
                "www-authenticate": 'Bearer error="invalid_token", error_description="Demo token rejected."',
                "x-request-id": "req-sim-401-9871"
            },
            "response_body": {
                "error": "unauthorized",
                "message": "Demo token rejected.",
                "code": "ERR_DEMO_TOKEN_REJECTED"
            },
            "timestamp": timestamp,
            "latency_ms": 42
        }

    if clean_token == "demo-valid-token":
        return {
            "is_simulated": True,
            "status_code": 200,
            "status_text": "OK",
            "endpoint": endpoint,
            "token_used": "demo-valid-token",
            "response_headers": {
                "content-type": "application/json",
                "x-request-id": "req-sim-200-5542"
            },
            "response_body": {
                "status": "success",
                "account_id": "acc_enterprise_8829",
                "organization": "Acme Global Corp",
                "scopes": ["orders:read", "orders:write"],
                "token_type": "Bearer",
                "expires_in": 3600
            },
            "timestamp": timestamp,
            "latency_ms": 38
        }

    if clean_token == "demo-ratelimit-token":
        return {
            "is_simulated": True,
            "status_code": 429,
            "status_text": "Too Many Requests",
            "endpoint": endpoint,
            "token_used": "demo-ratelimit-token",
            "response_headers": {
                "content-type": "application/json",
                "retry-after": "60",
                "x-request-id": "req-sim-429-1102"
            },
            "response_body": {
                "error": "rate_limit_exceeded",
                "message": "Rate limit exceeded. Maximum 100 requests per minute.",
                "code": "ERR_RATE_LIMIT"
            },
            "timestamp": timestamp,
            "latency_ms": 15
        }

    return {
        "is_simulated": True,
        "status_code": 401,
        "status_text": "Unauthorized",
        "endpoint": endpoint,
        "token_used": clean_token or "unspecified",
        "response_headers": {
            "content-type": "application/json",
            "www-authenticate": 'Bearer error="invalid_token", error_description="Demo token rejected."'
        },
        "response_body": {
            "error": "unauthorized",
            "message": "Demo token rejected.",
            "code": "ERR_DEMO_TOKEN_REJECTED"
        },
        "timestamp": timestamp,
        "latency_ms": 25
    }


def search_troubleshooting_guide(query: str, category: Optional[str] = None) -> Dict[str, Any]:
    """Searches the simulated internal engineering troubleshooting playbooks and runbooks.

    Args:
        query: Search keywords (e.g. 'password reset token revocation', '401 Unauthorized', 'orders api').
        category: Optional category filter (e.g. 'Authentication', 'Rate Limiting', 'Routing').

    Returns:
        A dictionary with matched simulated runbook articles.
    """
    guide_entries = [
        {
            "article_id": "KB-AUTH-101",
            "title": "Credential Changes and Active Bearer Token Invalidation",
            "category": "Authentication & Security",
            "summary": (
                "When an account password or security key is modified, all active access tokens and "
                "refresh tokens previously issued under that principal are revoked immediately for security."
            ),
            "common_symptoms": [
                "401 Unauthorized errors on endpoints previously working",
                "Header WWW-Authenticate returning invalid_token",
                "Automated background workers encountering authentication failures"
            ],
            "diagnostic_steps": [
                "1. Verify recent password or credential reset timestamps on account.",
                "2. Observe whether simulated diagnostic with demo-expired-token produces 401.",
                "3. Perform trial request with demo-valid-token to isolate token invalidation from permissions."
            ],
            "resolution": (
                "Clients must complete a re-authentication cycle using updated credentials to obtain a fresh "
                "active token (or switch to demo-valid-token in testing)."
            )
        },
        {
            "article_id": "KB-RATE-204",
            "title": "API Gateway Rate Limit Throttling and Exponential Backoff",
            "category": "Rate Limiting",
            "summary": (
                "Client requests exceeding tier limits receive HTTP 429 with Retry-After header. "
                "Clients should implement jittered exponential backoff."
            ),
            "common_symptoms": [
                "HTTP 429 Too Many Requests response",
                "Spikes in concurrent batch jobs"
            ],
            "diagnostic_steps": [
                "Inspect client request throughput over 60-second sliding windows."
            ],
            "resolution": "Respect Retry-After header and queue outgoing requests."
        }
    ]

    q = query.lower()
    matches = []
    for entry in guide_entries:
        if (
            q in entry["title"].lower()
            or q in entry["summary"].lower()
            or q in entry["article_id"].lower()
            or any(q in s.lower() for s in entry.get("common_symptoms", []))
            or (category and category.lower() in entry.get("category", "").lower())
        ):
            matches.append(entry)

    if not matches:
        matches = [guide_entries[0]]

    return {
        "is_simulated": True,
        "query": query,
        "total_results": len(matches),
        "articles": matches
    }


def save_case(
    case_id: str,
    title: str,
    user_report: str,
    evidence: List[Dict[str, Any]],
    hypotheses: List[str],
    repro_steps: List[str],
    status: str,
    next_check: str,
    summary: Optional[str] = "",
    handoff_notes: Optional[str] = "",
    github_issue_url: Optional[str] = None
) -> Dict[str, Any]:
    """Persists an individual investigation case as its own separate JSON object in Cloud Storage.

    Falls back to local file storage only when Cloud Storage is unavailable.
    """
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    existing = get_case(case_id).get("case", {})

    # Guard: Never mark resolved unless explicitly instructed
    final_status = status
    if not final_status or final_status.lower() not in ("investigating", "resolved"):
        final_status = existing.get("status", "Investigating")

    case_record = {
        "case_id": case_id,
        "title": title,
        "user_report": user_report,
        "evidence": evidence,
        "hypotheses": hypotheses,
        "repro_steps": repro_steps,
        "status": final_status,
        "next_check": next_check,
        "summary": summary or existing.get("summary", ""),
        "handoff_notes": handoff_notes or existing.get("handoff_notes", ""),
        "github_issue_url": github_issue_url or existing.get("github_issue_url"),
        "created_at": existing.get("created_at", now),
        "updated_at": now
    }

    blob_path = f"cases/{case_id}.json"
    gcs_res = upload_json_blob(blob_path, case_record)

    if gcs_res.get("success"):
        # Keep local copy in sync as backup
        local_path = os.path.join(CASES_DIR, f"{case_id}.json")
        try:
            with open(local_path, "w", encoding="utf-8") as f:
                json.dump(case_record, f, indent=2)
        except Exception:
            pass

        return {
            "success": True,
            "case_id": case_id,
            "status": final_status,
            "storage_backend": "gcs",
            "bucket": gcs_res.get("bucket"),
            "blob_path": blob_path,
            "evidence_count": len(evidence),
            "updated_at": now
        }

    # If GCS upload failed, report explicit failure
    err_detail = gcs_res.get("error", "Unknown GCS error")
    logger.error(f"GCS save failed for {case_id}: {err_detail}")
    return {
        "success": False,
        "case_id": case_id,
        "error": f"Failed to save case to Cloud Storage: {err_detail}. The case was NOT saved."
    }


def get_case(case_id: str) -> Dict[str, Any]:
    """Retrieves an existing investigation case from Cloud Storage (or local fallback)."""
    blob_path = f"cases/{case_id}.json"
    gcs_res = download_json_blob(blob_path)
    if gcs_res.get("found"):
        return {"found": True, "case": gcs_res["data"], "source": "gcs"}

    # Local fallback
    local_path = os.path.join(CASES_DIR, f"{case_id}.json")
    if os.path.exists(local_path):
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                return {"found": True, "case": json.load(f), "source": "local_fallback"}
        except Exception:
            pass

    return {"found": False, "error": f"Case with ID '{case_id}' was not found in Cloud Storage."}


def list_cases() -> Dict[str, Any]:
    """Lists all stored investigation cases from individual JSON objects in Cloud Storage."""
    case_list = []
    blobs = list_blobs_with_prefix("cases/")

    if blobs:
        for b in blobs:
            case_id = b["name"].split("/")[-1].replace(".json", "")
            res = download_json_blob(b["name"])
            if res.get("found"):
                c = res["data"]
                case_list.append({
                    "case_id": c.get("case_id", case_id),
                    "title": c.get("title", "Untitled Case"),
                    "status": c.get("status", "Investigating"),
                    "evidence_count": len(c.get("evidence", [])),
                    "github_issue_url": c.get("github_issue_url"),
                    "updated_at": c.get("updated_at", b.get("updated"))
                })
    else:
        # Check local fallback
        if os.path.exists(CASES_DIR):
            for fn in os.listdir(CASES_DIR):
                if fn.endswith(".json"):
                    try:
                        with open(os.path.join(CASES_DIR, fn), "r", encoding="utf-8") as f:
                            c = json.load(f)
                            case_list.append({
                                "case_id": c.get("case_id", fn.replace(".json", "")),
                                "title": c.get("title", "Untitled"),
                                "status": c.get("status", "Investigating"),
                                "evidence_count": len(c.get("evidence", [])),
                                "github_issue_url": c.get("github_issue_url"),
                                "updated_at": c.get("updated_at", "")
                            })
                    except Exception:
                        pass

    case_list.sort(key=lambda x: x.get("updated_at") or "", reverse=True)
    return {
        "total": len(case_list),
        "cases": case_list,
        "bucket": BUCKET_NAME
    }


def set_user_preference(user_id: str, detail_level: str) -> Dict[str, Any]:
    """Stores the user's preferred explanation detail level separately in Cloud Storage.

    Args:
        user_id: The identifier for the user (e.g. 'pilot_dev').
        detail_level: Either 'concise' or 'detailed'.
    """
    clean_level = detail_level.lower().strip()
    if clean_level not in ("concise", "detailed"):
        clean_level = "concise" if "con" in clean_level else "detailed"

    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    record = {
        "user_id": user_id,
        "detail_level": clean_level,
        "updated_at": now
    }

    blob_path = f"preferences/{user_id}.json"
    upload_res = upload_json_blob(blob_path, record)

    # Local mirror
    local_path = os.path.join(PREFS_DIR, f"{user_id}.json")
    try:
        with open(local_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)
    except Exception:
        pass

    if upload_res.get("success"):
        return {"success": True, "user_id": user_id, "detail_level": clean_level, "storage": "gcs"}

    return {"success": True, "user_id": user_id, "detail_level": clean_level, "storage": "local_fallback"}


def get_user_preference(user_id: str) -> Dict[str, Any]:
    """Retrieves user's preferred explanation detail level from Cloud Storage."""
    blob_path = f"preferences/{user_id}.json"
    res = download_json_blob(blob_path)
    if res.get("found"):
        return {"user_id": user_id, "detail_level": res["data"].get("detail_level", "balanced"), "source": "gcs"}

    local_path = os.path.join(PREFS_DIR, f"{user_id}.json")
    if os.path.exists(local_path):
        try:
            with open(local_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return {"user_id": user_id, "detail_level": data.get("detail_level", "balanced"), "source": "local"}
        except Exception:
            pass

    return {"user_id": user_id, "detail_level": "balanced", "source": "default"}
