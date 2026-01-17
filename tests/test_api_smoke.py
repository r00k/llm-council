"""Smoke tests for API endpoints."""

import pytest
from unittest.mock import patch, AsyncMock


class TestHealthEndpoint:
    """Tests for the health check endpoint."""

    def test_health_check(self, test_client):
        """Health endpoint returns 200 with status ok."""
        response = test_client.get("/health")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ok"
        assert data["service"] == "LLM Council API"


class TestConversationsCRUD:
    """Tests for conversation CRUD operations."""

    def test_create_conversation(self, test_client):
        """Create a new conversation."""
        response = test_client.post("/api/conversations", json={})
        assert response.status_code == 200
        data = response.json()
        assert "id" in data
        assert data["title"] == "New Conversation"
        assert data["messages"] == []

    def test_list_conversations_empty(self, test_client):
        """List conversations when none exist."""
        response = test_client.get("/api/conversations")
        assert response.status_code == 200
        assert response.json() == []

    def test_list_conversations_with_data(self, test_client):
        """List conversations after creating one."""
        test_client.post("/api/conversations", json={})
        response = test_client.get("/api/conversations")
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert "id" in data[0]
        assert data[0]["message_count"] == 0

    def test_get_conversation(self, test_client):
        """Get a specific conversation."""
        create_resp = test_client.post("/api/conversations", json={})
        conv_id = create_resp.json()["id"]

        response = test_client.get(f"/api/conversations/{conv_id}")
        assert response.status_code == 200
        data = response.json()
        assert data["id"] == conv_id
        assert data["messages"] == []

    def test_get_conversation_not_found(self, test_client):
        """Get non-existent conversation returns 404."""
        response = test_client.get("/api/conversations/nonexistent-id")
        assert response.status_code == 404

    def test_delete_conversation(self, test_client):
        """Delete a conversation."""
        create_resp = test_client.post("/api/conversations", json={})
        conv_id = create_resp.json()["id"]

        response = test_client.delete(f"/api/conversations/{conv_id}")
        assert response.status_code == 200

        get_resp = test_client.get(f"/api/conversations/{conv_id}")
        assert get_resp.status_code == 404

    def test_delete_conversation_not_found(self, test_client):
        """Delete non-existent conversation returns 404."""
        response = test_client.delete("/api/conversations/nonexistent-id")
        assert response.status_code == 404


class TestSendMessage:
    """Tests for sending messages (with mocked LLM calls)."""

    @pytest.fixture
    def mock_council(self):
        """Mock the council functions to avoid real API calls."""
        with patch("backend.main.run_full_council", new_callable=AsyncMock) as mock_run:
            with patch("backend.main.generate_conversation_title", new_callable=AsyncMock) as mock_title:
                mock_run.return_value = (
                    [{"model": "test-model", "response": "Test response"}],
                    [{"model": "test-model", "ranking": "1. Response A", "parsed_ranking": ["Response A"]}],
                    {"model": "test-model", "response": "Final answer"},
                    {"label_to_model": {"Response A": "test-model"}, "aggregate_rankings": []}
                )
                mock_title.return_value = "Test Title"
                yield mock_run, mock_title

    def test_send_message(self, test_client, mock_council):
        """Send a message and receive council response."""
        create_resp = test_client.post("/api/conversations", json={})
        conv_id = create_resp.json()["id"]

        response = test_client.post(
            f"/api/conversations/{conv_id}/message",
            json={"content": "What is 2+2?"}
        )
        assert response.status_code == 200
        data = response.json()
        assert "stage1" in data
        assert "stage2" in data
        assert "stage3" in data
        assert "metadata" in data

    def test_send_message_to_nonexistent_conversation(self, test_client, mock_council):
        """Send message to non-existent conversation returns 404."""
        response = test_client.post(
            "/api/conversations/nonexistent-id/message",
            json={"content": "Hello"}
        )
        assert response.status_code == 404


class TestConversationWithMessages:
    """Tests for conversations with messages."""

    @pytest.fixture
    def mock_council(self):
        """Mock the council functions."""
        with patch("backend.main.run_full_council", new_callable=AsyncMock) as mock_run:
            with patch("backend.main.generate_conversation_title", new_callable=AsyncMock) as mock_title:
                mock_run.return_value = (
                    [{"model": "test-model", "response": "Test response"}],
                    [{"model": "test-model", "ranking": "1. Response A", "parsed_ranking": ["Response A"]}],
                    {"model": "test-model", "response": "Final answer"},
                    {"label_to_model": {}, "aggregate_rankings": []}
                )
                mock_title.return_value = "Test Title"
                yield

    def test_send_message_updates_title(self, test_client, mock_council):
        """Sending first message updates conversation title."""
        create_resp = test_client.post("/api/conversations", json={})
        conv_id = create_resp.json()["id"]

        test_client.post(
            f"/api/conversations/{conv_id}/message",
            json={"content": "Hello"}
        )

        conv = test_client.get(f"/api/conversations/{conv_id}").json()
        assert conv["title"] == "Test Title"

    def test_messages_persisted_after_send(self, test_client, mock_council):
        """Messages are persisted after sending."""
        create_resp = test_client.post("/api/conversations", json={})
        conv_id = create_resp.json()["id"]

        test_client.post(
            f"/api/conversations/{conv_id}/message",
            json={"content": "Hello"}
        )

        conv = test_client.get(f"/api/conversations/{conv_id}").json()
        assert len(conv["messages"]) == 2
        assert conv["messages"][0]["role"] == "user"
        assert conv["messages"][0]["content"] == "Hello"
        assert conv["messages"][1]["role"] == "assistant"
