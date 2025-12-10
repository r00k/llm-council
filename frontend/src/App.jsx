import { useState, useEffect, useRef } from 'react';
import Sidebar from './components/Sidebar';
import ChatInterface from './components/ChatInterface';
import { api } from './api';
import './App.css';

function App() {
  const [conversations, setConversations] = useState([]);
  const [currentConversationId, setCurrentConversationId] = useState(null);
  const [currentConversation, setCurrentConversation] = useState(null);
  const [isLoading, setIsLoading] = useState(false);

  // Ref to track current conversation ID for streaming event handlers
  const currentConversationIdRef = useRef(currentConversationId);
  useEffect(() => {
    currentConversationIdRef.current = currentConversationId;
  }, [currentConversationId]);

  // Load conversations on mount
  useEffect(() => {
    loadConversations();
  }, []);

  // Load conversation details when selected
  useEffect(() => {
    if (currentConversationId) {
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
      setCurrentConversation(conv);
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
      setCurrentConversationId(newConv.id);
    } catch (error) {
      console.error('Failed to create conversation:', error);
    }
  };

  const handleSelectConversation = (id) => {
    setCurrentConversationId(id);
    // Clear loading state when switching conversations
    // This allows starting new queries while others process in background
    setIsLoading(false);
  };

  const handleDeleteConversation = async (id) => {
    try {
      await api.deleteConversation(id);
      // Remove from conversations list
      setConversations(conversations.filter((conv) => conv.id !== id));
      // If we deleted the current conversation, clear it
      if (currentConversationId === id) {
        setCurrentConversationId(null);
        setCurrentConversation(null);
      }
    } catch (error) {
      console.error('Failed to delete conversation:', error);
    }
  };

  const handleSendMessage = async (content) => {
    if (!currentConversationId) return;

    // Capture the target conversation ID for this request
    const targetConversationId = currentConversationId;

    setIsLoading(true);
    try {
      // Optimistically add user message to UI
      const userMessage = { role: 'user', content };
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, userMessage],
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
      setCurrentConversation((prev) => ({
        ...prev,
        messages: [...prev.messages, assistantMessage],
      }));

      // Send message with streaming
      await api.sendMessageStream(targetConversationId, content, (eventType, event) => {
        // Skip UI updates if user navigated away from this conversation
        const isStillViewing = currentConversationIdRef.current === targetConversationId;

        // Helper to safely update the last assistant message
        // Returns prev unchanged if the message structure isn't what we expect
        // (e.g., user navigated away and back, reloading partial data from backend)
        const safeUpdateLastAssistant = (prev, updateFn) => {
          if (!prev?.messages?.length) return prev;
          const messages = [...prev.messages];
          const lastMsg = messages[messages.length - 1];
          // Only update if it's an assistant message with the expected structure
          if (lastMsg?.role !== 'assistant' || !lastMsg?.loading) return prev;
          updateFn(lastMsg);
          return { ...prev, messages };
        };

        switch (eventType) {
          case 'stage1_start':
            if (!isStillViewing) return;
            setCurrentConversation((prev) => safeUpdateLastAssistant(prev, (msg) => {
              msg.loading.stage1 = true;
            }));
            break;

          case 'stage1_complete':
            if (!isStillViewing) return;
            setCurrentConversation((prev) => safeUpdateLastAssistant(prev, (msg) => {
              msg.stage1 = event.data;
              msg.loading.stage1 = false;
            }));
            break;

          case 'stage2_start':
            if (!isStillViewing) return;
            setCurrentConversation((prev) => safeUpdateLastAssistant(prev, (msg) => {
              msg.loading.stage2 = true;
            }));
            break;

          case 'stage2_complete':
            if (!isStillViewing) return;
            setCurrentConversation((prev) => safeUpdateLastAssistant(prev, (msg) => {
              msg.stage2 = event.data;
              msg.metadata = event.metadata;
              msg.loading.stage2 = false;
            }));
            break;

          case 'stage3_start':
            if (!isStillViewing) return;
            setCurrentConversation((prev) => safeUpdateLastAssistant(prev, (msg) => {
              msg.loading.stage3 = true;
            }));
            break;

          case 'stage3_complete':
            if (!isStillViewing) return;
            setCurrentConversation((prev) => safeUpdateLastAssistant(prev, (msg) => {
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
            // Only clear loading state if still viewing this conversation
            if (isStillViewing) {
              setIsLoading(false);
            }
            break;

          case 'error':
            console.error('Stream error:', event.message);
            if (isStillViewing) {
              setIsLoading(false);
            }
            break;

          default:
            console.log('Unknown event type:', eventType);
        }
      });
    } catch (error) {
      console.error('Failed to send message:', error);
      // Remove optimistic messages on error (only if still viewing)
      if (currentConversationIdRef.current === targetConversationId) {
        setCurrentConversation((prev) => ({
          ...prev,
          messages: prev.messages.slice(0, -2),
        }));
        setIsLoading(false);
      }
    }
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
        isLoading={isLoading}
      />
    </div>
  );
}

export default App;
