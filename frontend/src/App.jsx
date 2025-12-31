import { useState, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import { api } from './api';
import './App.css';

function App() {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  // Cache conversation state per-conversation to preserve streaming state when switching
  const [conversationCache, setConversationCache] = useState({});
  // Track which conversations have active streaming
  const [loadingConversations, setLoadingConversations] = useState({});

  // Ref to track current conversation ID for streaming event handlers
  const currentConversationIdRef = useRef(currentConversationId);
  useEffect(() => {
    currentConversationIdRef.current = currentConversationId;
  }, [currentConversationId]);

  // Derive current conversation from cache
  const currentConversation = currentConversationId ? conversationCache[currentConversationId] : null;
  const isLoading = currentConversationId ? loadingConversations[currentConversationId] : false;

  // Load conversations on mount
  useEffect(() => {
    loadConversations();
  }, []);

  // Load conversation details when selected (only if not already cached or loading)
  useEffect(() => {
    if (currentConversationId && !conversationCache[currentConversationId] && !loadingConversations[currentConversationId]) {
      loadConversation(currentConversationId);
    }
  }, [currentConversationId]);

  const loadConversations = async () => {
    try {
      const convs = await api.listConversations();
      setConversations(convs);
    } catch (error) {
      console.error('Failed to load conversations:', error);
    }
  };

  const loadConversation = async (id) => {
    try {
      const conv = await api.getConversation(id);
      setConversationCache((prev) => ({ ...prev, [id]: conv }));
    } catch (error) {
      console.error('Failed to load conversation:', error);
    }
  };

  const handleNewConversation = async () => {
    try {
      const newConv = await api.createConversation();
      setConversations([
        { id: newConv.id, created_at: newConv.created_at, message_count: 0 },
        ...conversations,
      ]);
      setConversationCache((prev) => ({ ...prev, [newConv.id]: newConv }));
      setCurrentConversationId(newConv.id);
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  };

  const handleSelectConversation = (id) => {
    setCurrentConversationId(id);
    // Loading state is now per-conversation, no need to clear globally
  };

  const handleDeleteConversation = async (id) => {
    try {
      await api.deleteConversation(id);
      // Remove from conversations list
      setConversations(conversations.filter((conv) => conv.id !== id));
      // Remove from cache
      setConversationCache((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      setLoadingConversations((prev) => {
        const next = { ...prev };
        delete next[id];
        return next;
      });
      // If we deleted the current conversation, clear selection
      if (currentConversationId === id) {
        setCurrentConversationId(null);
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    }
  };

  const handleSendMessage = async (content) => {
    if (!currentConversationId) return;

    // Capture the target conversation ID for this request
    const targetConversationId = currentConversationId;

    setLoadingConversations((prev) => ({ ...prev, [targetConversationId]: true }));
    try {
      // Optimistically add user message to UI
      const userMessage = { role: 'user', content };
      setConversationCache((prev) => ({
        ...prev,
        [targetConversationId]: {
          ...prev[targetConversationId],
          messages: [...prev[targetConversationId].messages, userMessage],
        },
      }));

      // Create a partial assistant message that will be updated progressively
      const assistantMessage = {
        role: 'assistant',
        stage1: null,
        stage2: null,
        stage3: null,
        metadata: null,
        loading: {
          stage1: false,
          stage2: false,
          stage3: false,
        },
      };

      // Add the partial assistant message
      setConversationCache((prev) => ({
        ...prev,
        [targetConversationId]: {
          ...prev[targetConversationId],
          messages: [...prev[targetConversationId].messages, assistantMessage],
        },
      }));

      // Helper to safely update the last assistant message for a specific conversation
      const safeUpdateLastAssistant = (prev, convId, updateFn) => {
        const conv = prev[convId];
        if (!conv?.messages?.length) return prev;
        const messages = [...conv.messages];
        const lastMsg = messages[messages.length - 1];
        // Only update if it's an assistant message with the expected structure
        if (lastMsg?.role !== 'assistant' || !lastMsg?.loading) return prev;
        updateFn(lastMsg);
        return { ...prev, [convId]: { ...conv, messages } };
      };

      // Send message with streaming
      await api.sendMessageStream(targetConversationId, content, (eventType, event) => {
        switch (eventType) {
          case 'stage1_start':
            setConversationCache((prev) => safeUpdateLastAssistant(prev, targetConversationId, (msg) => {
              msg.loading.stage1 = true;
            }));
            break;

          case 'stage1_complete':
            setConversationCache((prev) => safeUpdateLastAssistant(prev, targetConversationId, (msg) => {
              msg.stage1 = event.data;
              msg.loading.stage1 = false;
            }));
            break;

          case 'stage2_start':
            setConversationCache((prev) => safeUpdateLastAssistant(prev, targetConversationId, (msg) => {
              msg.loading.stage2 = true;
            }));
            break;

          case 'stage2_complete':
            setConversationCache((prev) => safeUpdateLastAssistant(prev, targetConversationId, (msg) => {
              msg.stage2 = event.data;
              msg.metadata = event.metadata;
              msg.loading.stage2 = false;
            }));
            break;

          case 'stage3_start':
            setConversationCache((prev) => safeUpdateLastAssistant(prev, targetConversationId, (msg) => {
              msg.loading.stage3 = true;
            }));
            break;

          case 'stage3_complete':
            setConversationCache((prev) => safeUpdateLastAssistant(prev, targetConversationId, (msg) => {
              msg.stage3 = event.data;
              msg.loading.stage3 = false;
            }));
            break;

          case 'title_complete':
            // Always reload conversations to get updated title
            loadConversations();
            break;

          case 'complete':
            // Stream complete, reload conversations list
            loadConversations();
            // Clear loading state for this conversation
            setLoadingConversations((prev) => ({ ...prev, [targetConversationId]: false }));
            break;

          case 'error':
            console.error('Stream error:', event.message);
            setLoadingConversations((prev) => ({ ...prev, [targetConversationId]: false }));
            break;

          default:
            console.log('Unknown event type:', eventType);
        }
      });
    } catch (error) {
      console.error('Failed to send message:', error);
      // Remove optimistic messages on error
      setConversationCache((prev) => {
        const conv = prev[targetConversationId];
        if (!conv) return prev;
        return {
          ...prev,
          [targetConversationId]: {
            ...conv,
            messages: conv.messages.slice(0, -2),
          },
        };
      });
      setLoadingConversations((prev) => ({ ...prev, [targetConversationId]: false }));
    }
  };

  const handleRetry = async (content, messageIndex) => {
    if (!currentConversationId) return;

    // Remove the user message at messageIndex and its following assistant response
    setConversationCache((prev) => {
      const conv = prev[currentConversationId];
      if (!conv) return prev;
      const messages = [...conv.messages];
      // Remove user message and the assistant response that follows it
      messages.splice(messageIndex, 2);
      return {
        ...prev,
        [currentConversationId]: { ...conv, messages },
      };
    });

    // Now send the message again
    await handleSendMessage(content);
  };

  return (
    <div className="app">
      <Sidebar
        conversations={conversations}
        currentConversationId={currentConversationId}
        onSelectConversation={handleSelectConversation}
        onNewConversation={handleNewConversation}
        onDeleteConversation={handleDeleteConversation}
      />
      <ChatInterface
        conversation={currentConversation}
        onSendMessage={handleSendMessage}
        onRetry={handleRetry}
        isLoading={isLoading}
      />
    </div>
  );
}

export default App;
