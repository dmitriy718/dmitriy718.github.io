from __future__ import annotations

import smtplib
from email.message import EmailMessage
from typing import List

from ..utils.env import get_env
from .base import Notifier


class EmailNotifier(Notifier):
    def __init__(
        self,
        smtp_host: str,
        smtp_port: int,
        username_env: str,
        password_env: str,
        from_addr: str,
        to_addrs: List[str],
    ) -> None:
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username_env = username_env
        self.password_env = password_env
        self.from_addr = from_addr
        self.to_addrs = to_addrs

    def send(self, title: str, message: str, level: str = "info") -> None:
        username = get_env(self.username_env, required=True)
        password = get_env(self.password_env, required=True)
        email = EmailMessage()
        email["Subject"] = f"{title} [{level}]"
        email["From"] = self.from_addr
        email["To"] = ", ".join(self.to_addrs)
        email.set_content(message)
        with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
            server.starttls()
            server.login(username, password)
            server.send_message(email)
