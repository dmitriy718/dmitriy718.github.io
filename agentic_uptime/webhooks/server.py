from __future__ import annotations

import hmac
import hashlib
from typing import Any, Dict

from fastapi import FastAPI, Header, HTTPException, Request


def _verify_secret(secret: str, body: bytes, signature: str) -> bool:
    if not signature:
        return False
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    expected = f"sha256={digest}"
    return hmac.compare_digest(expected, signature)


def create_app(queue, shared_secret: str) -> FastAPI:
    app = FastAPI()

    @app.post("/webhook")
    async def webhook(
        request: Request,
        x_webhook_secret: str | None = Header(default=None),
        x_hub_signature_256: str | None = Header(default=None),
    ) -> Dict[str, Any]:
        body = await request.body()
        if shared_secret:
            if x_webhook_secret and x_webhook_secret == shared_secret:
                pass
            elif x_hub_signature_256 and _verify_secret(
                shared_secret, body, x_hub_signature_256
            ):
                pass
            else:
                raise HTTPException(status_code=401, detail="Invalid secret")
        payload = await request.json()
        await queue.put(payload)
        return {"status": "queued"}

    return app
