-- SQLite schema for LLM Council conversations

CREATE TABLE IF NOT EXISTS conversations (
    id TEXT PRIMARY KEY,
    created_at TEXT NOT NULL,
    title TEXT NOT NULL DEFAULT 'New Conversation'
);

CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id TEXT NOT NULL,
    role TEXT NOT NULL CHECK (role IN ('user', 'assistant')),
    content TEXT,  -- For user messages
    stage1_json TEXT,  -- JSON for assistant stage1
    stage2_json TEXT,  -- JSON for assistant stage2
    stage3_json TEXT,  -- JSON for assistant stage3
    metadata_json TEXT,  -- JSON for assistant metadata
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES conversations(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created ON conversations(created_at DESC);
