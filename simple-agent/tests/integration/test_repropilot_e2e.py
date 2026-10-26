# Copyright 2026 Google LLC

import os
import pytest
from app.repropilot_tools import (
    run_api_diagnostic,
    search_troubleshooting_guide,
    save_case,
    get_case,
    list_cases,
)


def test_repropilot_diagnostic_401():
    res = run_api_diagnostic("/v1/orders", "demo-expired-token")
    assert res["is_simulated"] is True
    assert res["status_code"] == 401
    assert res["response_body"]["code"] == "ERR_AUTH_TOKEN_REVOKED"


def test_repropilot_diagnostic_200():
    res = run_api_diagnostic("/v1/orders", "demo-valid-token")
    assert res["is_simulated"] is True
    assert res["status_code"] == 200
    assert res["response_body"]["status"] == "success"
    assert "account_id" in res["response_body"]


def test_repropilot_search_guide():
    res = search_troubleshooting_guide("password reset")
    assert res["is_simulated"] is True
    assert len(res["articles"]) > 0
    assert any("Credential Changes" in a["title"] for a in res["articles"])


def test_repropilot_save_and_retrieve_case():
    case_id = "CASE-TEST-001"
    save_res = save_case(
        case_id=case_id,
        title="Test Password Reset Auth Failure",
        user_report="API stopped working after password change",
        evidence=[
            {"status_code": 401, "endpoint": "/v1/orders", "token_used": "demo-expired-token"},
            {"status_code": 200, "endpoint": "/v1/orders", "token_used": "demo-valid-token"}
        ],
        hypotheses=["Token revoked on password update"],
        repro_steps=["curl -H 'Authorization: Bearer demo-expired-token' https://api.local/v1/orders"],
        status="Verified",
        next_check="Issue refreshed token to client",
        summary="Verified password change revokes active token.",
        handoff_notes="### Reproduction Steps\nRun curl command with demo-expired-token."
    )
    assert save_res["success"] is True

    get_res = get_case(case_id)
    assert get_res["found"] is True
    case = get_res["case"]
    assert case["case_id"] == case_id
    assert case["status"] == "Verified"
    assert len(case["evidence"]) == 2

    all_cases = list_cases()
    assert any(c["case_id"] == case_id for c in all_cases["cases"])
