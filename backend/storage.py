"""SQLite-based storage for conversations."""

import json
from datetime import datetime
from typing import List, Dict, Any, Optional
from .db import get_connection


def create_conversation(conversation_id: str) -> Dict[str, Any]:
    """
    Create a new conversation.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        New conversation dict
    """
    created_at = datetime.utcnow().isoformat()

    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO conversations (id, created_at, title) VALUES (?, ?, ?)",
            (conversation_id, created_at, "New Conversation")
        )
        conn.commit()
    finally:
        conn.close()

    return {
        "id": conversation_id,
        "created_at": created_at,
        "title": "New Conversation",
        "messages": []
    }


def get_conversation(conversation_id: str) -> Optional[Dict[str, Any]]:
    """
    Load a conversation from storage.

    Args:
        conversation_id: Unique identifier for the conversation

    Returns:
        Conversation dict or None if not found
    """
    conn = get_connection()
    try:
        # Get conversation metadata
        cursor = conn.execute(
            "SELECT id, created_at, title FROM conversations WHERE id = ?",
            (conversation_id,)
        )
        row = cursor.fetchone()

        if row is None:
            return None

        conversation = {
            "id": row["id"],
            "created_at": row["created_at"],
            "title": row["title"],
            "messages": []
        }

        # Get messages
        cursor = conn.execute(
            """
            SELECT role, content, stage1_json, stage2_json, stage3_json, metadata_json
            FROM messages
            WHERE conversation_id = ?
            ORDER BY id ASC
            """,
            (conversation_id,)
        )

        for msg_row in cursor.fetchall():
            if msg_row["role"] == "user":
                conversation["messages"].append({
                    "role": "user",
                    "content": msg_row["content"]
                })
            else:  # assistant
                message = {
                    "role": "assistant",
                    "stage1": json.loads(msg_row["stage1_json"]),
                    "stage2": json.loads(msg_row["stage2_json"]),
                    "stage3": json.loads(msg_row["stage3_json"])
                }
                if msg_row["metadata_json"]:
                    message["metadata"] = json.loads(msg_row["metadata_json"])
                conversation["messages"].append(message)

        return conversation

    finally:
        conn.close()


def save_conversation(conversation: Dict[str, Any]):
    """
    Save a conversation to storage.

    Note: This function exists for API compatibility but is not needed
    with SQLite as individual operations already persist to the database.

    Args:
        conversation: Conversation dict to save
    """
    # With SQLite, we save incrementally via add_user_message and add_assistant_message
    # This function is kept for API compatibility but doesn't need to do anything
    pass


def list_conversations() -> List[Dict[str, Any]]:
    """
    List all conversations (metadata only).

    Returns:
        List of conversation metadata dicts
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            """
            SELECT c.id, c.created_at, c.title, COUNT(m.id) as message_count
            FROM conversations c
            LEFT JOIN messages m ON c.id = m.conversation_id
            GROUP BY c.id
            ORDER BY c.created_at DESC
            """
        )

        conversations = []
        for row in cursor.fetchall():
            conversations.append({
                "id": row["id"],
                "created_at": row["created_at"],
                "title": row["title"],
                "message_count": row["message_count"]
            })

        return conversations

    finally:
        conn.close()


def add_user_message(conversation_id: str, content: str):
    """
    Add a user message to a conversation.

    Args:
        conversation_id: Conversation identifier
        content: User message content
    """
    conn = get_connection()
    try:
        # Verify conversation exists
        cursor = conn.execute(
            "SELECT id FROM conversations WHERE id = ?",
            (conversation_id,)
        )
        if cursor.fetchone() is None:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Insert message
        conn.execute(
            "INSERT INTO messages (conversation_id, role, content) VALUES (?, ?, ?)",
            (conversation_id, "user", content)
        )
        conn.commit()
    finally:
        conn.close()


def add_assistant_message(
    conversation_id: str,
    stage1: List[Dict[str, Any]],
    stage2: List[Dict[str, Any]],
    stage3: Dict[str, Any],
    metadata: Optional[Dict[str, Any]] = None
):
    """
    Add an assistant message with all 3 stages to a conversation.

    Args:
        conversation_id: Conversation identifier
        stage1: List of individual model responses
        stage2: List of model rankings
        stage3: Final synthesized response
        metadata: Optional metadata including label_to_model mapping
    """
    conn = get_connection()
    try:
        # Verify conversation exists
        cursor = conn.execute(
            "SELECT id FROM conversations WHERE id = ?",
            (conversation_id,)
        )
        if cursor.fetchone() is None:
            raise ValueError(f"Conversation {conversation_id} not found")

        # Insert message
        conn.execute(
            """
            INSERT INTO messages
            (conversation_id, role, stage1_json, stage2_json, stage3_json, metadata_json)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (
                conversation_id,
                "assistant",
                json.dumps(stage1),
                json.dumps(stage2),
                json.dumps(stage3),
                json.dumps(metadata) if metadata else None
            )
        )
        conn.commit()
    finally:
        conn.close()


def update_conversation_title(conversation_id: str, title: str):
    """
    Update the title of a conversation.

    Args:
        conversation_id: Conversation identifier
        title: New title for the conversation
    """
    conn = get_connection()
    try:
        conn.execute(
            "UPDATE conversations SET title = ? WHERE id = ?",
            (title, conversation_id)
        )
        conn.commit()

        # Verify it was updated
        cursor = conn.execute(
            "SELECT id FROM conversations WHERE id = ?",
            (conversation_id,)
        )
        if cursor.fetchone() is None:
            raise ValueError(f"Conversation {conversation_id} not found")

    finally:
        conn.close()


def delete_conversation(conversation_id: str) -> bool:
    """
    Delete a conversation from storage.

    Args:
        conversation_id: Conversation identifier

    Returns:
        True if deleted, False if not found
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            "DELETE FROM conversations WHERE id = ?",
            (conversation_id,)
        )
        conn.commit()
        return cursor.rowcount > 0
    finally:
        conn.close()
