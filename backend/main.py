"""FastAPI backend for LLM Council."""

import base64
import secrets
import time
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from typing import List, Dict, Any
import uuid
import json
import asyncio
import os
from pathlib import Path

from . import storage
from .council import run_full_council, generate_conversation_title, stage1_collect_responses, stage2_collect_rankings, stage3_synthesize_final, calculate_aggregate_rankings

app = FastAPI(title="LLM Council API")

# Auth password from environment variable
AUTH_PASSWORD = os.environ.get("AUTH_PASSWORD")

# Rate limiting: track failed auth attempts by IP
# {ip: [timestamp1, timestamp2, ...]}
failed_attempts: Dict[str, List[float]] = {}
RATE_LIMIT_WINDOW = 900  # 15 minutes
RATE_LIMIT_MAX_ATTEMPTS = 5


def is_rate_limited(ip: str) -> bool:
    """Check if an IP is rate limited due to too many failed attempts."""
    now = time.time()
    if ip not in failed_attempts:
        return False
    # Clean old attempts outside the window
    failed_attempts[ip] = [t for t in failed_attempts[ip] if now - t < RATE_LIMIT_WINDOW]
    return len(failed_attempts[ip]) >= RATE_LIMIT_MAX_ATTEMPTS


def record_failed_attempt(ip: str):
    """Record a failed auth attempt for an IP."""
    now = time.time()
    if ip not in failed_attempts:
        failed_attempts[ip] = []
    failed_attempts[ip].append(now)


def clear_failed_attempts(ip: str):
    """Clear failed attempts after successful auth."""
    if ip in failed_attempts:
        del failed_attempts[ip]


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    """Require auth for all routes except health check."""
    # Skip auth for health check endpoint
    if request.url.path == "/health":
        return await call_next(request)

    # Skip auth if no password is set (local dev)
    if not AUTH_PASSWORD:
        return await call_next(request)

    # Get client IP (check X-Forwarded-For for proxies like Railway)
    client_ip = request.headers.get("x-forwarded-for", request.client.host or "unknown")
    if "," in client_ip:
        client_ip = client_ip.split(",")[0].strip()

    # Check rate limiting
    if is_rate_limited(client_ip):
        return Response(
            status_code=429,
            content="Too many failed attempts. Try again in 15 minutes.",
        )

    # Check for Basic auth header
    auth_header = request.headers.get("authorization", "")
    if auth_header.startswith("Basic "):
        try:
            credentials = base64.b64decode(auth_header[6:]).decode("utf-8")
            _, password = credentials.split(":", 1)
            if secrets.compare_digest(password.encode(), AUTH_PASSWORD.encode()):
                clear_failed_attempts(client_ip)
                return await call_next(request)
        except Exception:
            pass

    # Record failed attempt
    record_failed_attempt(client_ip)

    # Return 401 to trigger browser's Basic auth prompt
    return Response(
        status_code=401,
        headers={"WWW-Authenticate": 'Basic realm="LLM Council"'},
    )

# Get the frontend build directory
FRONTEND_DIST = Path(__file__).parent.parent / "frontend" / "dist"


def build_conversation_history(messages: List[Dict[str, Any]]) -> List[Dict[str, str]]:
    """
    Build conversation history from stored messages.

    Extracts previous question/verdict pairs for context in follow-up questions.

    Args:
        messages: List of stored messages (user and assistant)

    Returns:
        List of dicts with 'question' and 'verdict' keys
    """
    history = []
    i = 0
    while i < len(messages) - 1:  # -1 because we don't include the current question
        msg = messages[i]
        if msg.get("role") == "user":
            # Look for the corresponding assistant message
            if i + 1 < len(messages):
                next_msg = messages[i + 1]
                if next_msg.get("role") == "assistant" and next_msg.get("stage3"):
                    history.append({
                        "question": msg.get("content", ""),
                        "verdict": next_msg["stage3"].get("response", "")
                    })
                    i += 2
                    continue
        i += 1
    return history

# Enable CORS for local development and production
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://localhost:3000",
        "*"  # Allow all origins in production (served from same domain)
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class CreateConversationRequest(BaseModel):
    """Request to create a new conversation."""
    pass


class SendMessageRequest(BaseModel):
    """Request to send a message in a conversation."""
    content: str


class ConversationMetadata(BaseModel):
    """Conversation metadata for list view."""
    id: str
    created_at: str
    title: str
    message_count: int


class Conversation(BaseModel):
    """Full conversation with all messages."""
    id: str
    created_at: str
    title: str
    messages: List[Dict[str, Any]]


@app.get("/health")
async def health():
    """Health check endpoint."""
    return {"status": "ok", "service": "LLM Council API"}


@app.get("/api/conversations", response_model=List[ConversationMetadata])
async def list_conversations():
    """List all conversations (metadata only)."""
    return storage.list_conversations()


@app.post("/api/conversations", response_model=Conversation)
async def create_conversation(request: CreateConversationRequest):
    """Create a new conversation."""
    conversation_id = str(uuid.uuid4())
    conversation = storage.create_conversation(conversation_id)
    return conversation


@app.get("/api/conversations/{conversation_id}", response_model=Conversation)
async def get_conversation(conversation_id: str):
    """Get a specific conversation with all its messages."""
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return conversation


@app.delete("/api/conversations/{conversation_id}")
async def delete_conversation(conversation_id: str):
    """Delete a specific conversation."""
    deleted = storage.delete_conversation(conversation_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Conversation not found")
    return {"status": "deleted", "id": conversation_id}


@app.post("/api/conversations/{conversation_id}/message")
async def send_message(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and run the 3-stage council process.
    Returns the complete response with all stages.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Build conversation history from previous messages (before adding new user message)
    conversation_history = build_conversation_history(conversation["messages"])

    # Add user message
    storage.add_user_message(conversation_id, request.content)

    # If this is the first message, generate a title
    if is_first_message:
        title = await generate_conversation_title(request.content)
        storage.update_conversation_title(conversation_id, title)

    # Run the 3-stage council process with conversation history
    stage1_results, stage2_results, stage3_result, metadata = await run_full_council(
        request.content,
        conversation_history if conversation_history else None
    )

    # Add assistant message with all stages and metadata
    storage.add_assistant_message(
        conversation_id,
        stage1_results,
        stage2_results,
        stage3_result,
        metadata
    )

    # Return the complete response with metadata
    return {
        "stage1": stage1_results,
        "stage2": stage2_results,
        "stage3": stage3_result,
        "metadata": metadata
    }


@app.post("/api/conversations/{conversation_id}/message/stream")
async def send_message_stream(conversation_id: str, request: SendMessageRequest):
    """
    Send a message and stream the 3-stage council process.
    Returns Server-Sent Events as each stage completes.
    """
    # Check if conversation exists
    conversation = storage.get_conversation(conversation_id)
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    # Check if this is the first message
    is_first_message = len(conversation["messages"]) == 0

    # Build conversation history from previous messages (before adding new user message)
    conversation_history = build_conversation_history(conversation["messages"])
    history_for_council = conversation_history if conversation_history else None

    async def event_generator():
        try:
            # Add user message
            storage.add_user_message(conversation_id, request.content)

            # Start title generation in parallel (don't await yet)
            title_task = None
            if is_first_message:
                title_task = asyncio.create_task(generate_conversation_title(request.content))

            # Stage 1: Collect responses
            yield f"data: {json.dumps({'type': 'stage1_start'})}\n\n"
            stage1_results = await stage1_collect_responses(request.content, history_for_council)
            yield f"data: {json.dumps({'type': 'stage1_complete', 'data': stage1_results})}\n\n"

            # Stage 2: Collect rankings
            yield f"data: {json.dumps({'type': 'stage2_start'})}\n\n"
            stage2_results, label_to_model = await stage2_collect_rankings(request.content, stage1_results, history_for_council)
            aggregate_rankings = calculate_aggregate_rankings(stage2_results, label_to_model)
            yield f"data: {json.dumps({'type': 'stage2_complete', 'data': stage2_results, 'metadata': {'label_to_model': label_to_model, 'aggregate_rankings': aggregate_rankings}})}\n\n"

            # Stage 3: Synthesize final answer
            yield f"data: {json.dumps({'type': 'stage3_start'})}\n\n"
            stage3_result = await stage3_synthesize_final(request.content, stage1_results, stage2_results, history_for_council)
            yield f"data: {json.dumps({'type': 'stage3_complete', 'data': stage3_result})}\n\n"

            # Wait for title generation if it was started
            if title_task:
                title = await title_task
                storage.update_conversation_title(conversation_id, title)
                yield f"data: {json.dumps({'type': 'title_complete', 'data': {'title': title}})}\n\n"

            # Save complete assistant message with metadata
            metadata = {
                'label_to_model': label_to_model,
                'aggregate_rankings': aggregate_rankings
            }
            storage.add_assistant_message(
                conversation_id,
                stage1_results,
                stage2_results,
                stage3_result,
                metadata
            )

            # Send completion event
            yield f"data: {json.dumps({'type': 'complete'})}\n\n"

        except Exception as e:
            # Send error event
            yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )


# Mount static files for production (frontend build)
if FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=str(FRONTEND_DIST), html=True), name="static")


if __name__ == "__main__":
    import uvicorn
    # Use PORT environment variable if available (Railway sets this)
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
