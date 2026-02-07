from __future__ import annotations

import json

import requests

from ..utils.env import get_env
from .base import Notifier


class SlackNotifier(Notifier):
    def __init__(self, webhook_env: str) -> None:
        self.webhook_env = webhook_env

    def send(self, title: str, message: str, level: str = "info") -> None:
        webhook = get_env(self.webhook_env, required=True)
        payload = {
            "text": f"*{title}* [{level}]\n{message}",
        }
        response = requests.post(webhook, data=json.dumps(payload), timeout=10)
        response.raise_for_status()
