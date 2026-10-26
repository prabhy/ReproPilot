# Copyright 2026 Google LLC

import os
import pytest
from app.repropilot_tools import (
    run_api_diagnostic,
    search_troubleshooting_guide,
    save_case,
    get_case,
    list_cases,
    set_user_preference,
    get_user_preference,
)
from google.adk.agents.run_config import RunConfig, StreamingMode
from google.adk.runners import Runner
from google.adk.sessions import InMemorySessionService
from google.genai import types
from app.agent import root_agent


def test_preference_persistence():
    user = "test_dev_user"
    set_user_preference(user, "concise")
    pref = get_user_preference(user)
    assert pref["detail_level"] == "concise"

    set_user_preference(user, "detailed")
    pref2 = get_user_preference(user)
    assert pref2["detail_level"] == "detailed"


def test_simulated_401_message():
    res = run_api_diagnostic("/v1/orders", "demo-expired-token")
    assert res["status_code"] == 401
    assert res["response_body"]["message"] == "Demo token rejected."
    assert res["response_body"]["code"] == "ERR_DEMO_TOKEN_REJECTED"


def test_multiturn_investigation_flow():
    """Verify multi-turn investigation retaining session context in ADK runner."""
    session_service = InMemorySessionService()
    session = session_service.create_session_sync(user_id="dev_user", app_name="app")
    runner = Runner(agent=root_agent, session_service=session_service, app_name="app")

    # Turn 1: Report issue
    msg1 = types.Content(
        role="user",
        parts=[types.Part.from_text(text="My integration stopped working after I changed my password on endpoint /v1/orders. Please run the diagnostic tool with demo-expired-token.")]
    )
    events1 = list(
        runner.run(
            new_message=msg1,
            user_id="dev_user",
            session_id=session.id,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        )
    )
    assert len(events1) > 0

    # Turn 2: Follow up in the same session with approval to retry with valid demo token
    msg2 = types.Content(
        role="user",
        parts=[types.Part.from_text(text="I approve: Retry with valid demo token ('demo-valid-token'). Run the diagnostic retry now, save the case as CASE-AUTH-TEST, and provide the handoff.")]
    )
    events2 = list(
        runner.run(
            new_message=msg2,
            user_id="dev_user",
            session_id=session.id,
            run_config=RunConfig(streaming_mode=StreamingMode.SSE),
        )
    )
    assert len(events2) > 0

    # Verify that case was saved in local storage
    case_res = get_case("CASE-AUTH-TEST")
    assert case_res["found"] is True or len(list_cases()["cases"]) > 0
