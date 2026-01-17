#!/usr/bin/env python3
"""Test script for SQLite storage migration."""

import sys
from backend import storage

def test_storage():
    """Test all storage operations."""
    print("Testing SQLite storage...")

    # Test 1: Create conversation
    print("\n1. Creating conversation...")
    conv = storage.create_conversation("test-123")
    assert conv["id"] == "test-123"
    assert conv["title"] == "New Conversation"
    assert conv["messages"] == []
    print("✓ Conversation created")

    # Test 2: Get conversation
    print("\n2. Getting conversation...")
    conv = storage.get_conversation("test-123")
    assert conv is not None
    assert conv["id"] == "test-123"
    print("✓ Conversation retrieved")

    # Test 3: Add user message
    print("\n3. Adding user message...")
    storage.add_user_message("test-123", "Hello, council!")
    conv = storage.get_conversation("test-123")
    assert len(conv["messages"]) == 1
    assert conv["messages"][0]["role"] == "user"
    assert conv["messages"][0]["content"] == "Hello, council!"
    print("✓ User message added")

    # Test 4: Add assistant message
    print("\n4. Adding assistant message...")
    storage.add_assistant_message(
        "test-123",
        stage1=[{"model": "gpt-4", "content": "Hi!"}],
        stage2=[{"model": "gpt-4", "ranking": ["Response A"]}],
        stage3={"content": "Final answer"},
        metadata={"label_to_model": {"Response A": "gpt-4"}}
    )
    conv = storage.get_conversation("test-123")
    assert len(conv["messages"]) == 2
    assert conv["messages"][1]["role"] == "assistant"
    assert "stage1" in conv["messages"][1]
    assert "stage2" in conv["messages"][1]
    assert "stage3" in conv["messages"][1]
    assert "metadata" in conv["messages"][1]
    print("✓ Assistant message added")

    # Test 5: Update conversation title
    print("\n5. Updating conversation title...")
    storage.update_conversation_title("test-123", "Test Conversation")
    conv = storage.get_conversation("test-123")
    assert conv["title"] == "Test Conversation"
    print("✓ Title updated")

    # Test 6: List conversations
    print("\n6. Listing conversations...")
    convs = storage.list_conversations()
    assert len(convs) >= 1
    assert any(c["id"] == "test-123" for c in convs)
    test_conv = next(c for c in convs if c["id"] == "test-123")
    assert test_conv["message_count"] == 2
    print("✓ Conversations listed")

    # Test 7: Delete conversation
    print("\n7. Deleting conversation...")
    deleted = storage.delete_conversation("test-123")
    assert deleted is True
    conv = storage.get_conversation("test-123")
    assert conv is None
    print("✓ Conversation deleted")

    # Test 8: Delete non-existent conversation
    print("\n8. Deleting non-existent conversation...")
    deleted = storage.delete_conversation("nonexistent")
    assert deleted is False
    print("✓ Non-existent deletion handled")

    # Test 9: Add turn atomically
    print("\n9. Testing atomic turn creation...")
    conv = storage.create_conversation("test-456")
    storage.add_turn("test-456", "Test question", "turn-001")
    conv = storage.get_conversation("test-456")
    assert len(conv["messages"]) == 2  # user + assistant placeholder
    assert conv["messages"][0]["role"] == "user"
    assert conv["messages"][0]["content"] == "Test question"
    assert conv["messages"][1]["role"] == "assistant"
    print("✓ Atomic turn created")

    # Test 10: Update turn assistant
    print("\n10. Testing turn assistant update...")
    storage.update_turn_assistant(
        "test-456",
        "turn-001",
        stage1=[{"model": "gpt-4", "content": "Response"}],
        stage2=[{"model": "gpt-4", "ranking": ["Response A"]}],
        stage3={"content": "Final"},
        metadata={"label_to_model": {"Response A": "gpt-4"}}
    )
    conv = storage.get_conversation("test-456")
    assert conv["messages"][1]["stage3"]["content"] == "Final"
    print("✓ Turn assistant updated")

    # Test 11: Delete last turn
    print("\n11. Testing delete last turn...")
    deleted = storage.delete_last_turn("test-456")
    assert deleted is True
    conv = storage.get_conversation("test-456")
    assert len(conv["messages"]) == 0
    print("✓ Last turn deleted")

    # Cleanup
    storage.delete_conversation("test-456")

    print("\n✅ All tests passed!")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(test_storage())
    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
