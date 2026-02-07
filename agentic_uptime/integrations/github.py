from __future__ import annotations

import json
from typing import Any, Dict

import requests

from ..utils.env import get_env


class GitHubClient:
    def __init__(self, api_base: str = "https://api.github.com", token_env: str = "GITHUB_TOKEN") -> None:
        self.api_base = api_base.rstrip("/")
        self.token_env = token_env

    def _headers(self) -> Dict[str, str]:
        token = get_env(self.token_env, required=True)
        return {
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
        }

    def dispatch_workflow(
        self, repo: str, workflow_id: str, ref: str, inputs: Dict[str, Any]
    ) -> str:
        url = f"{self.api_base}/repos/{repo}/actions/workflows/{workflow_id}/dispatches"
        payload = {"ref": ref, "inputs": inputs}
        response = requests.post(url, headers=self._headers(), json=payload, timeout=15)
        if response.status_code not in {200, 201, 204}:
            raise RuntimeError(f"GitHub dispatch failed: {response.text}")
        return "Workflow dispatched"
