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

"""Google Cloud Storage client wrapper for ReproPilot cases and user preferences."""

import json
import logging
import os
from typing import Any, Dict, List, Optional
from google.cloud import storage

logger = logging.getLogger(__name__)

BUCKET_NAME = os.environ.get(
    "REPROPILOT_GCS_BUCKET",
    "repropilot-storage-qwiklabs-gcp-04-d32f9369da59"
)

_client = None

def get_storage_client() -> Optional[storage.Client]:
    """Returns initialized storage client using default credentials or None if unavailable."""
    global _client
    if _client is not None:
        return _client
    try:
        project = os.environ.get("GOOGLE_CLOUD_PROJECT", "qwiklabs-gcp-04-d32f9369da59")
        _client = storage.Client(project=project)
        return _client
    except Exception as e:
        logger.warning(f"Could not initialize Google Cloud Storage client: {e}")
        return None


def get_bucket(client: Optional[storage.Client] = None):
    """Retrieves the GCS bucket or None if client/bucket inaccessible."""
    c = client or get_storage_client()
    if not c or not BUCKET_NAME:
        return None
    try:
        return c.bucket(BUCKET_NAME)
    except Exception as e:
        logger.warning(f"Failed to get bucket {BUCKET_NAME}: {e}")
        return None


def upload_json_blob(blob_path: str, data: Dict[str, Any]) -> Dict[str, Any]:
    """Uploads a dictionary as a JSON object in the configured GCS bucket."""
    bucket = get_bucket()
    if not bucket:
        return {
            "success": False,
            "error": f"GCS bucket '{BUCKET_NAME}' unavailable or storage client not configured."
        }
    try:
        blob = bucket.blob(blob_path)
        payload = json.dumps(data, indent=2)
        blob.upload_from_string(payload, content_type="application/json")
        return {
            "success": True,
            "bucket": BUCKET_NAME,
            "blob_path": blob_path,
            "size_bytes": len(payload)
        }
    except Exception as e:
        logger.error(f"Failed uploading blob {blob_path} to {BUCKET_NAME}: {e}")
        return {
            "success": False,
            "error": f"Failed saving to Cloud Storage ({BUCKET_NAME}/{blob_path}): {str(e)}"
        }


def download_json_blob(blob_path: str) -> Dict[str, Any]:
    """Downloads and parses a JSON blob from GCS."""
    bucket = get_bucket()
    if not bucket:
        return {"found": False, "error": "Storage client unavailable"}
    try:
        blob = bucket.blob(blob_path)
        if not blob.exists():
            return {"found": False, "error": f"Blob {blob_path} does not exist."}
        content = blob.download_as_text()
        data = json.loads(content)
        return {"found": True, "data": data}
    except Exception as e:
        logger.error(f"Failed downloading blob {blob_path}: {e}")
        return {"found": False, "error": str(e)}


def list_blobs_with_prefix(prefix: str) -> List[Dict[str, Any]]:
    """Lists blobs with given prefix in the GCS bucket."""
    c = get_storage_client()
    bucket = get_bucket(c)
    if not c or not bucket:
        return []
    try:
        blobs = c.list_blobs(bucket, prefix=prefix)
        results = []
        for b in blobs:
            if b.name.endswith(".json"):
                results.append({
                    "name": b.name,
                    "updated": b.updated.isoformat() if b.updated else None,
                    "size": b.size
                })
        return results
    except Exception as e:
        logger.error(f"Error listing blobs with prefix '{prefix}': {e}")
        return []
