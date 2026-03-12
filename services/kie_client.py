"""KIE.ai Unified API Client — async task-based image/video generation.

KIE.ai (NEXUSAI SERVICES LLC) is a unified gateway to dozens of AI models
via a single API key and billing system. Architecture is fully asynchronous:
create a task, poll for result, download generated files.

API Reference:
  Base URL: https://api.kie.ai/api/v1
  Auth: Bearer Token in Authorization header
  Create: POST /jobs/createTask
  Poll:   GET  /jobs/recordInfo?taskId=xxx

Rate limits: 20 requests per 10 seconds, ~100 concurrent tasks.
URLs expire after 14 days — always download immediately.

V-I-V Principe 2: No workarounds — real API calls, proper error handling.
V-I-V Principe 5: Tolerance Zero — validate every response.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.kie.ai/api/v1"

# Task states returned by the API
TERMINAL_STATES = {"success", "fail"}
PENDING_STATES = {"waiting", "queuing", "generating"}


@dataclass
class KieTaskResult:
    """Result of a completed kie.ai task."""
    task_id: str
    state: str
    result_urls: list[str] = field(default_factory=list)
    raw_response: dict = field(default_factory=dict)
    error_message: str = ""
    elapsed_seconds: float = 0.0


class KieClient:
    """Unified client for kie.ai API — image and video generation.

    Usage:
        client = KieClient()
        result = client.generate_image(prompt="...", model="nano-banana-pro")
        result = client.generate_video(prompt="...", model="kling-3.0/video")

    All methods follow: create task → poll → download pattern.
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("KIE_API_KEY", "")
        if not self.api_key:
            raise ValueError(
                "KIE_API_KEY must be set in environment or passed to constructor"
            )
        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        self._client = httpx.Client(timeout=30, headers=self.headers)

    def create_task(self, model: str, input_params: dict) -> str:
        """Create a generation task and return the taskId.

        Args:
            model: Model identifier (e.g., "nano-banana-pro", "kling-3.0/video").
            input_params: Model-specific input parameters.

        Returns:
            Task ID string.

        Raises:
            RuntimeError: If task creation fails.
        """
        payload = {
            "model": model,
            "input": input_params,
        }

        logger.info("KIE create_task: model=%s", model)
        resp = self._client.post(f"{BASE_URL}/jobs/createTask", json=payload)

        if resp.status_code != 200:
            raise RuntimeError(
                f"KIE createTask failed (HTTP {resp.status_code}): {resp.text[:500]}"
            )

        data = resp.json()
        if data.get("data") is None:
            raise RuntimeError(
                f"KIE createTask error (code {data.get('code')}): {data.get('msg', 'unknown')}"
            )
        task_id = data["data"].get("taskId")
        if not task_id:
            raise RuntimeError(f"KIE createTask returned no taskId: {data}")

        logger.info("KIE task created: %s (model=%s)", task_id, model)
        return task_id

    def poll_task(
        self,
        task_id: str,
        poll_interval: float = 5.0,
        max_wait: float = 300.0,
    ) -> KieTaskResult:
        """Poll a task until completion or timeout.

        Args:
            task_id: Task ID from create_task.
            poll_interval: Seconds between polls (default 5s).
            max_wait: Maximum total wait time in seconds (default 5min).

        Returns:
            KieTaskResult with URLs and metadata.

        Raises:
            TimeoutError: If max_wait exceeded.
            RuntimeError: If task fails.
        """
        start = time.time()
        attempt = 0

        while True:
            elapsed = time.time() - start
            if elapsed > max_wait:
                raise TimeoutError(
                    f"KIE task {task_id} timed out after {max_wait}s"
                )

            resp = self._client.get(
                f"{BASE_URL}/jobs/recordInfo",
                params={"taskId": task_id},
            )

            if resp.status_code != 200:
                logger.warning(
                    "KIE poll error (HTTP %d), retrying: %s",
                    resp.status_code, resp.text[:200],
                )
                time.sleep(poll_interval)
                continue

            data = resp.json().get("data", {})
            state = data.get("state", "unknown")
            attempt += 1

            if state == "success":
                # Parse resultUrls from resultJson
                result_urls = []
                result_json_str = data.get("resultJson", "")
                if result_json_str:
                    try:
                        result_json = json.loads(result_json_str)
                        result_urls = result_json.get("resultUrls", [])
                    except (json.JSONDecodeError, TypeError):
                        # Sometimes resultJson is already a dict
                        if isinstance(result_json_str, dict):
                            result_urls = result_json_str.get("resultUrls", [])

                logger.info(
                    "KIE task %s SUCCESS: %d URLs (%.1fs)",
                    task_id, len(result_urls), elapsed,
                )
                return KieTaskResult(
                    task_id=task_id,
                    state="success",
                    result_urls=result_urls,
                    raw_response=data,
                    elapsed_seconds=round(elapsed, 1),
                )

            if state == "fail":
                fail_msg = data.get("failMsg", "Unknown error")
                logger.error("KIE task %s FAILED: %s", task_id, fail_msg)
                return KieTaskResult(
                    task_id=task_id,
                    state="fail",
                    error_message=fail_msg,
                    raw_response=data,
                    elapsed_seconds=round(elapsed, 1),
                )

            # Still pending
            if attempt % 6 == 0:  # Log every ~30s
                logger.info(
                    "KIE task %s: state=%s (%.0fs elapsed)", task_id, state, elapsed,
                )
            time.sleep(poll_interval)

    def download_result(
        self,
        url: str,
        output_path: Path,
        timeout: float = 120.0,
    ) -> Path:
        """Download a result file from kie.ai (URLs expire after 14 days).

        Args:
            url: Result URL from task completion.
            output_path: Local path to save the file.
            timeout: Download timeout in seconds.

        Returns:
            Path to the downloaded file.

        Raises:
            RuntimeError: If download fails.
        """
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        logger.info("Downloading: %s → %s", url[:80], output_path.name)

        with httpx.Client(timeout=timeout, follow_redirects=True) as dl_client:
            resp = dl_client.get(url)

        if resp.status_code != 200:
            raise RuntimeError(
                f"Download failed (HTTP {resp.status_code}): {url[:100]}"
            )

        output_path.write_bytes(resp.content)
        size_mb = len(resp.content) / (1024 * 1024)
        logger.info("Downloaded: %s (%.1f MB)", output_path.name, size_mb)
        return output_path

    def generate_and_download(
        self,
        model: str,
        input_params: dict,
        output_path: Path,
        poll_interval: float = 5.0,
        max_wait: float = 300.0,
        download_index: int = 0,
    ) -> KieTaskResult:
        """Full pipeline: create task → poll → download first result.

        Args:
            model: Model identifier.
            input_params: Model input parameters.
            output_path: Where to save the downloaded file.
            poll_interval: Polling interval in seconds.
            max_wait: Maximum wait time.
            download_index: Which result URL to download (default 0 = first).

        Returns:
            KieTaskResult with local file path in result_urls[0].
        """
        task_id = self.create_task(model, input_params)
        result = self.poll_task(task_id, poll_interval, max_wait)

        if result.state != "success":
            return result

        if not result.result_urls:
            result.error_message = "Task succeeded but returned no URLs"
            result.state = "fail"
            return result

        # Download the specified result
        url = result.result_urls[min(download_index, len(result.result_urls) - 1)]
        local_path = self.download_result(url, output_path)

        # Replace remote URL with local path for caller convenience
        result.result_urls[0] = str(local_path)
        return result

    def close(self):
        """Close the HTTP client."""
        self._client.close()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
