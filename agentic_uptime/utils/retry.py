from __future__ import annotations

import time
from typing import Callable, Iterable, Optional, Tuple, Type


def retry(
    func: Callable[[], object],
    retries: int = 3,
    delay_sec: float = 1.0,
    backoff: float = 2.0,
    retry_on: Tuple[Type[BaseException], ...] = (Exception,),
) -> object:
    attempt = 0
    while True:
        try:
            return func()
        except retry_on:
            attempt += 1
            if attempt > retries:
                raise
            time.sleep(delay_sec)
            delay_sec *= backoff
