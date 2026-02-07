from __future__ import annotations

import requests

from ..utils.env import get_env
from .base import Notifier


class TelegramNotifier(Notifier):
    def __init__(self, bot_token_env: str, chat_id: str) -> None:
        self.bot_token_env = bot_token_env
        self.chat_id = chat_id

    def send(self, title: str, message: str, level: str = "info") -> None:
        token = get_env(self.bot_token_env, required=True)
        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": self.chat_id,
            "text": f"{title} [{level}]\n{message}",
        }
        response = requests.post(url, json=payload, timeout=10)
        response.raise_for_status()
