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

"""GitHub integration client for ReproPilot issue tracking."""

import json
import logging
import os
import shutil
import subprocess
from typing import Any, Dict, Optional
import urllib.request
import urllib.error

logger = logging.getLogger(__name__)


def get_github_auth_info() -> Dict[str, Any]:
    """Checks whether GitHub token or gh CLI is authenticated."""
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY") or os.environ.get("REPROPILOT_GITHUB_REPO")
    
    if token:
        return {
            "authenticated": True,
            "method": "token",
            "repo": repo,
            "message": "Authenticated via environment token."
        }

    gh_path = shutil.which("gh") or os.path.expanduser("~/.local/bin/gh")
    if os.path.exists(gh_path):
        try:
            res = subprocess.run([gh_path, "auth", "status"], capture_output=True, text=True)
            if res.returncode == 0:
                return {
                    "authenticated": True,
                    "method": "gh_cli",
                    "repo": repo,
                    "message": "Authenticated via GitHub CLI."
                }
        except Exception:
            pass

    return {
        "authenticated": False,
        "method": "none",
        "repo": repo,
        "connection_step": (
            "To connect GitHub, either set GITHUB_TOKEN and GITHUB_REPOSITORY environment variables, "
            "or run 'gh auth login' in the terminal using the GitHub device code flow."
        )
    }


def create_github_issue(
    title: str,
    body: str,
    repo: Optional[str] = None,
    labels: Optional[list] = None
) -> Dict[str, Any]:
    """Creates an issue in the designated GitHub repository.
    
    Uses server-side GITHUB_TOKEN or local gh CLI.
    """
    target_repo = repo or os.environ.get("GITHUB_REPOSITORY") or os.environ.get("REPROPILOT_GITHUB_REPO")
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")

    if not target_repo:
        return {
            "success": False,
            "error": "No GitHub repository specified. Set GITHUB_REPOSITORY (e.g. 'owner/repo') or configure repo."
        }

    # Ensure simulated notice is prominent
    simulated_header = (
        "> [!IMPORTANT]\n"
        "> **SIMULATED EVIDENCE NOTICE:**\n"
        "> The reproduction traces and diagnostic responses in this issue were produced using simulated demo endpoints and predefined test tokens for investigation demonstration.\n\n"
    )
    if not body.startswith("> [!IMPORTANT]"):
        full_body = simulated_header + body
    else:
        full_body = body

    # 1. Try REST API with token if present
    if token:
        api_url = f"https://api.github.com/repos/{target_repo}/issues"
        payload = {
            "title": title,
            "body": full_body,
            "labels": labels or ["bug", "repropilot", "simulated-evidence"]
        }
        req = urllib.request.Request(
            api_url,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "ReproPilot-Agent"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                return {
                    "success": True,
                    "issue_number": data.get("number"),
                    "issue_url": data.get("html_url"),
                    "title": data.get("title")
                }
        except urllib.error.HTTPError as e:
            err_msg = e.read().decode("utf-8")
            return {
                "success": False,
                "error": f"GitHub API error ({e.code}): {err_msg}"
            }
        except Exception as e:
            return {
                "success": False,
                "error": f"Failed calling GitHub API: {str(e)}"
            }

    # 2. Try gh CLI if token is not directly in env
    gh_path = shutil.which("gh") or os.path.expanduser("~/.local/bin/gh")
    if os.path.exists(gh_path):
        cmd = [
            gh_path, "issue", "create",
            "--repo", target_repo,
            "--title", title,
            "--body", full_body
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True)
            if res.returncode == 0:
                issue_url = res.stdout.strip()
                return {
                    "success": True,
                    "issue_url": issue_url,
                    "title": title
                }
            else:
                return {
                    "success": False,
                    "error": f"GitHub CLI failed: {res.stderr.strip()}",
                    "connection_step": "Run 'gh auth login' or export GITHUB_TOKEN to enable issue creation."
                }
        except Exception as e:
            return {"success": False, "error": f"Execution error: {str(e)}"}

    return {
        "success": False,
        "error": "GitHub connection unavailable.",
        "connection_step": (
            "No active GitHub session found. Please run 'gh auth login' in terminal or export GITHUB_TOKEN."
        )
    }
