import { useState, useEffect, useRef, memo } from 'react';
import ReactMarkdown from 'react-markdown';
import Stage1 from './Stage1';
import Stage2 from './Stage2';
import Stage3 from './Stage3';
import './ChatInterface.css';

// Memoized message component to prevent re-renders when only input state changes
const Message = memo(function Message({ msg, onRetry, isLoading, stage3Ref }) {
  return (
    <div className="message-group">
      {msg.role === 'user' ? (
        <div className="user-message">
          <div className="message-label">You</div>
          <div className="user-message-row">
            <div className="message-content">
              <div className="markdown-content">
                <ReactMarkdown>{msg.content}</ReactMarkdown>
              </div>
            </div>
            <button
              className="retry-button"
              onClick={() => onRetry(msg.content)}
              disabled={isLoading}
              title="Re-run council analysis"
            >
              ↻ Retry
            </button>
          </div>
        </div>
      ) : (
        <div className="assistant-message">
          <div className="message-label">LLM Council</div>

          {/* Stage 1 */}
          {msg.loading?.stage1 && (
            <div className="stage-loading">
              <div className="spinner"></div>
              <span>Running Stage 1: Collecting individual responses...</span>
            </div>
          )}
          {msg.stage1 && <Stage1 responses={msg.stage1} />}

          {/* Stage 2 */}
          {msg.loading?.stage2 && (
            <div className="stage-loading">
              <div className="spinner"></div>
              <span>Running Stage 2: Peer rankings...</span>
            </div>
          )}
          {msg.stage2 && (
            <Stage2
              rankings={msg.stage2}
              labelToModel={msg.metadata?.label_to_model}
              aggregateRankings={msg.metadata?.aggregate_rankings}
            />
          )}

          {/* Stage 3 */}
          {msg.loading?.stage3 && (
            <div className="stage-loading">
              <div className="spinner"></div>
              <span>Running Stage 3: Final synthesis...</span>
            </div>
          )}
          {msg.stage3 && <Stage3 finalResponse={msg.stage3} ref={stage3Ref} />}
        </div>
      )}
    </div>
  );
});

export default function ChatInterface({
  conversation,
  onSendMessage,
  onRetry,
  isLoading,
}) {
  const [input, setInput] = useState('');
  const stage3Ref = useRef(null);

  const scrollToStage3 = () => {
    stage3Ref.current?.scrollIntoView({ behavior: 'auto', block: 'start' });
  };

  useEffect(() => {
    // Only scroll when stage3 appears or changes
    if (conversation?.messages?.length > 0) {
      const lastMsg = conversation.messages[conversation.messages.length - 1];
      if (lastMsg?.role === 'assistant' && lastMsg?.stage3) {
        scrollToStage3();
      }
    }
  }, [conversation?.messages]);

  const handleSubmit = (e) => {
    e.preventDefault();
    if (input.trim() && !isLoading) {
      onSendMessage(input);
      setInput('');
    }
  };

  const handleKeyDown = (e) => {
    // Submit on Enter (without Shift)
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  if (!conversation) {
    return (
      <div className="chat-interface">
        <div className="empty-state">
          <h2>Welcome to LLM Council</h2>
          <p>Create a new conversation to get started</p>
        </div>
      </div>
    );
  }

  return (
    <div className="chat-interface">
      <div className="messages-container">
        {conversation.messages.length === 0 ? (
          <div className="empty-state">
            <h2>Start a conversation</h2>
            <p>Ask a question to consult the LLM Council</p>
          </div>
        ) : (
          conversation.messages.map((msg, index, arr) => {
            // Only attach ref to the last assistant message with stage3
            const isLastAssistant =
              msg.role === 'assistant' &&
              index === arr.length - 1;

            return (
              <Message
                key={index}
                msg={msg}
                onRetry={onRetry}
                isLoading={isLoading}
                stage3Ref={isLastAssistant ? stage3Ref : null}
              />
            );
          })
        )}

        {isLoading && (
          <div className="loading-indicator">
            <div className="spinner"></div>
            <span>Consulting the council...</span>
          </div>
        )}
      </div>

      <form className="input-form" onSubmit={handleSubmit}>
        <textarea
          className="message-input"
          placeholder={conversation.messages.length === 0
            ? "Ask your question... (Shift+Enter for new line, Enter to send)"
            : "Ask a follow-up question... (Shift+Enter for new line, Enter to send)"
          }
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isLoading}
          rows={3}
        />
        <button
          type="submit"
          className="send-button"
          disabled={!input.trim() || isLoading}
        >
          Send
        </button>
      </form>
    </div>
  );
}
