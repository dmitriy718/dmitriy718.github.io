from __future__ import annotations

from typing import Any, Dict

import requests

from ..utils.env import get_env


class GitLabClient:
    def __init__(self, api_base: str = "https://gitlab.com/api/v4", token_env: str = "GITLAB_TOKEN") -> None:
        self.api_base = api_base.rstrip("/")
        self.token_env = token_env

    def _headers(self) -> Dict[str, str]:
        token = get_env(self.token_env, required=True)
        return {"PRIVATE-TOKEN": token}

    def trigger_pipeline(
        self, project_id: str, ref: str, variables: Dict[str, Any]
    ) -> str:
        url = f"{self.api_base}/projects/{project_id}/pipeline"
        payload = {"ref": ref, "variables": [{"key": k, "value": v} for k, v in variables.items()]}
        response = requests.post(url, headers=self._headers(), json=payload, timeout=15)
        if response.status_code not in {200, 201}:
            raise RuntimeError(f"GitLab trigger failed: {response.text}")
        return "Pipeline triggered"
