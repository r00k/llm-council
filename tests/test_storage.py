"""Tests for storage module."""

import pytest
from backend import storage


class TestStorageOperations:
    """Tests for SQLite storage operations."""

    def test_create_conversation(self, temp_db):
        """Create a new conversation."""
        conv = storage.create_conversation("test-123")
        assert conv["id"] == "test-123"
        assert conv["title"] == "New Conversation"
        assert conv["messages"] == []

    def test_get_conversation(self, temp_db):
        """Retrieve an existing conversation."""
        storage.create_conversation("test-123")
        conv = storage.get_conversation("test-123")
        assert conv is not None
        assert conv["id"] == "test-123"

    def test_get_conversation_not_found(self, temp_db):
        """Get non-existent conversation returns None."""
        conv = storage.get_conversation("nonexistent")
        assert conv is None

    def test_add_user_message(self, temp_db):
        """Add a user message to a conversation."""
        storage.create_conversation("test-123")
        storage.add_user_message("test-123", "Hello!")

        conv = storage.get_conversation("test-123")
        assert len(conv["messages"]) == 1
        assert conv["messages"][0]["role"] == "user"
        assert conv["messages"][0]["content"] == "Hello!"

    def test_add_user_message_not_found(self, temp_db):
        """Add user message to non-existent conversation raises error."""
        with pytest.raises(ValueError, match="not found"):
            storage.add_user_message("nonexistent", "Hello!")

    def test_add_assistant_message(self, temp_db):
        """Add an assistant message with all stages."""
        storage.create_conversation("test-123")
        storage.add_assistant_message(
            "test-123",
            stage1=[{"model": "gpt-4", "response": "Hi!"}],
            stage2=[{"model": "gpt-4", "ranking": "1. Response A"}],
            stage3={"model": "gpt-4", "response": "Final answer"},
            metadata={"label_to_model": {"Response A": "gpt-4"}}
        )

        conv = storage.get_conversation("test-123")
        assert len(conv["messages"]) == 1
        msg = conv["messages"][0]
        assert msg["role"] == "assistant"
        assert msg["stage1"] == [{"model": "gpt-4", "response": "Hi!"}]
        assert msg["stage2"] == [{"model": "gpt-4", "ranking": "1. Response A"}]
        assert msg["stage3"] == {"model": "gpt-4", "response": "Final answer"}
        assert msg["metadata"]["label_to_model"]["Response A"] == "gpt-4"

    def test_update_conversation_title(self, temp_db):
        """Update conversation title."""
        storage.create_conversation("test-123")
        storage.update_conversation_title("test-123", "My Conversation")

        conv = storage.get_conversation("test-123")
        assert conv["title"] == "My Conversation"

    def test_list_conversations(self, temp_db):
        """List all conversations with metadata."""
        storage.create_conversation("test-1")
        storage.create_conversation("test-2")
        storage.add_user_message("test-1", "Hello!")

        convs = storage.list_conversations()
        assert len(convs) == 2
        
        test1 = next(c for c in convs if c["id"] == "test-1")
        assert test1["message_count"] == 1

    def test_delete_conversation(self, temp_db):
        """Delete a conversation."""
        storage.create_conversation("test-123")
        assert storage.delete_conversation("test-123") is True
        assert storage.get_conversation("test-123") is None

    def test_delete_conversation_not_found(self, temp_db):
        """Delete non-existent conversation returns False."""
        assert storage.delete_conversation("nonexistent") is False


class TestMultipleMessages:
    """Tests for multi-message conversations."""

    def test_full_conversation_flow(self, temp_db):
        """Test a full conversation with multiple exchanges."""
        storage.create_conversation("test-123")
        
        storage.add_user_message("test-123", "Hello!")
        storage.add_assistant_message(
            "test-123",
            stage1=[{"model": "gpt-4", "response": "Hi!"}],
            stage2=[{"model": "gpt-4", "ranking": "1. Response A"}],
            stage3={"model": "gpt-4", "response": "Final answer 1"},
            metadata={"label_to_model": {"Response A": "gpt-4"}}
        )
        
        storage.add_user_message("test-123", "Follow-up question")
        storage.add_assistant_message(
            "test-123",
            stage1=[{"model": "gpt-4", "response": "Follow-up response"}],
            stage2=[{"model": "gpt-4", "ranking": "1. Response A"}],
            stage3={"model": "gpt-4", "response": "Final answer 2"},
            metadata={"label_to_model": {"Response A": "gpt-4"}}
        )

        conv = storage.get_conversation("test-123")
        assert len(conv["messages"]) == 4
        assert conv["messages"][0]["role"] == "user"
        assert conv["messages"][1]["role"] == "assistant"
        assert conv["messages"][2]["role"] == "user"
        assert conv["messages"][3]["role"] == "assistant"

    def test_cascade_delete(self, temp_db):
        """Deleting conversation should delete all messages."""
        storage.create_conversation("test-123")
        storage.add_user_message("test-123", "Hello!")
        storage.add_assistant_message(
            "test-123",
            stage1=[], stage2=[], stage3={},
            metadata={}
        )
        
        assert storage.delete_conversation("test-123") is True
        assert storage.get_conversation("test-123") is None
