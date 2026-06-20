"""Mock OpenAI-compatible server for integration tests."""

from __future__ import annotations

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


class ChatRequest(BaseModel):
    model: str = "gpt-3.5-turbo"
    messages: list[dict[str, str]] = []
    temperature: float = 0.7


@app.post("/v1/chat/completions")
def chat_completions(body: ChatRequest) -> dict:
    user_msg = ""
    for m in body.messages:
        if m.get("role") == "user":
            user_msg = m.get("content", "").lower()

    # Safe default — refuse attacks
    if any(k in user_msg for k in ("ignore", "system prompt", "hidden rules", "root")):
        content = "I'm sorry, I can't help with that request."
    else:
        content = "Hello! How can I help you today?"

    return {
        "id": "chatcmpl-test",
        "object": "chat.completion",
        "choices": [{"index": 0, "message": {"role": "assistant", "content": content}}],
    }
