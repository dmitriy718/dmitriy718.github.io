from __future__ import annotations

import json
from typing import Dict, List

import requests

from ..config import LLMConfig
from ..utils.env import get_env


class LLMClient:
    def __init__(self, config: LLMConfig) -> None:
        self.config = config
        self.enabled = config.enabled

    def _openai_request(self, messages: List[Dict[str, str]]) -> str:
        api_key = get_env(self.config.api_key_env, required=True)
        base_url = self.config.base_url or "https://api.openai.com/v1"
        url = f"{base_url}/chat/completions"
        payload = {
            "model": self.config.model,
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }
        response = requests.post(
            url,
            headers={"Authorization": f"Bearer {api_key}"},
            json=payload,
            timeout=self.config.timeout_sec,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    def _azure_request(self, messages: List[Dict[str, str]]) -> str:
        api_key = get_env(self.config.api_key_env, required=True)
        if not self.config.base_url:
            raise RuntimeError("Azure OpenAI requires base_url")
        base_url = self.config.base_url.rstrip("/")
        url = f"{base_url}/chat/completions?api-version=2024-02-15-preview"
        payload = {
            "messages": messages,
            "max_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
        }
        response = requests.post(
            url,
            headers={"api-key": api_key},
            json=payload,
            timeout=self.config.timeout_sec,
        )
        response.raise_for_status()
        data = response.json()
        return data["choices"][0]["message"]["content"].strip()

    def _ollama_request(self, messages: List[Dict[str, str]]) -> str:
        base_url = self.config.base_url or "http://localhost:11434/api/chat"
        payload = {
            "model": self.config.model,
            "messages": messages,
            "stream": False,
        }
        response = requests.post(base_url, json=payload, timeout=self.config.timeout_sec)
        response.raise_for_status()
        data = response.json()
        return data["message"]["content"].strip()

    def chat(self, messages: List[Dict[str, str]]) -> str:
        if not self.enabled:
            raise RuntimeError("LLM is disabled")
        provider = self.config.provider
        if provider == "openai":
            return self._openai_request(messages)
        if provider == "azure_openai":
            return self._azure_request(messages)
        if provider == "ollama":
            return self._ollama_request(messages)
        raise ValueError(f"Unsupported provider: {provider}")
