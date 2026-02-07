from __future__ import annotations

from typing import List


class Notifier:
    def send(self, title: str, message: str, level: str = "info") -> None:
        raise NotImplementedError


class NotificationManager:
    def __init__(self, notifiers: List[Notifier]) -> None:
        self.notifiers = notifiers

    def notify(self, title: str, message: str, level: str = "info") -> None:
        for notifier in self.notifiers:
            notifier.send(title, message, level)
