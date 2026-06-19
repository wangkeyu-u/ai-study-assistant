import { useState, useEffect, useRef, useCallback } from 'react';
import { useTranslation } from 'react-i18next';
import { useSearchParams } from 'react-router-dom';
import {
  ChatSession,
  ChatMessage,
  Citation,
  Collection,
  DebugInfo,
  HistorySearchResult,
  listSessions,
  getSessionMessages,
  deleteSession,
  listCollections,
  exportMessageAsMarkdown,
  searchHistory,
  sendChatMessage,
  sendMultiAgentChat,
} from '../api';
import DebugPanel from '../components/DebugPanel';

interface MessageWithCitations extends ChatMessage {
  citations: Citation[];
  agentName?: string;
}

export default function ChatPage() {
  const { t } = useTranslation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageWithCitations[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const [debugInfo, setDebugInfo] = useState<DebugInfo | null>(null);
  const [showDebug, setShowDebug] = useState(false);
  const [expandedCitation, setExpandedCitation] = useState<string | null>(null);
  const [chatCollections, setChatCollections] = useState<Collection[]>([]);
  const [chatCollectionId, setChatCollectionId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<HistorySearchResult[]>([]);
  const [smartMode, setSmartMode] = useState(false);
  const [agentName, setAgentName] = useState<string>('');
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [scopedDocumentIds, setScopedDocumentIds] = useState<string[]>([]);
  const [scopeNames, setScopeNames] = useState<string[]>([]);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  const fetchSessions = useCallback(async () => {
    try {
      const data = await listSessions();
      setSessions(data);
    } catch {
      // silently ignore
    }
  }, []);

  useEffect(() => {
    fetchSessions();
  }, [fetchSessions]);

  useEffect(() => {
    listCollections()
      .then(setChatCollections)
      .catch(() => {});
  }, []);

  useEffect(() => {
    const suggestedQuestion = searchParams.get('q');
    const documentIds = (searchParams.get('documents') || '').split(',').filter(Boolean);
    const documentNames = (searchParams.get('names') || '').split('|').filter(Boolean);
    if (suggestedQuestion) {
      setInput(suggestedQuestion);
      inputRef.current?.focus();
    }
    if (documentIds.length > 0) {
      setScopedDocumentIds(documentIds);
      setScopeNames(documentNames);
      setSmartMode(false);
    }
    if (!suggestedQuestion && documentIds.length === 0) return;
    setSearchParams({}, { replace: true });
  }, [searchParams, setSearchParams]);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, streamingText]);

  const loadSession = async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    try {
      const data = await getSessionMessages(sessionId);
      setMessages(data);
    } catch {
      setMessages([]);
    }
  };

  const handleNewChat = () => {
    setCurrentSessionId(null);
    setMessages([]);
    setStreamingText('');
    setDebugInfo(null);
    setAgentName('');
    setErrorMessage(null);
    inputRef.current?.focus();
  };

  const handleDeleteSession = async (sessionId: string) => {
    if (!confirm(t('chat.confirmDelete'))) return;
    try {
      await deleteSession(sessionId);
      if (currentSessionId === sessionId) {
        handleNewChat();
      }
      await fetchSessions();
    } catch {
      // ignore
    }
  };

  const handleSend = async () => {
    const message = input.trim();
    if (!message || sending) return;

    setInput('');
    setSending(true);
    setStreamingText('');
    setDebugInfo(null);
    setAgentName('');
    setErrorMessage(null);

    const previousSessionId = currentSessionId;
    const tempMessageId = `temp-${Date.now()}`;
    const userMsg: MessageWithCitations = {
      id: tempMessageId,
      role: 'user',
      content: message,
      citations: [],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const handlers = {
        onToken: (text: string) => setStreamingText((prev) => prev + text),
        onSessionId: (id: string) => setCurrentSessionId(id),
        onDebug: (debug: DebugInfo) => setDebugInfo(debug),
      };
      const result =
        smartMode && scopedDocumentIds.length === 0
          ? await sendMultiAgentChat(
              message,
              currentSessionId || undefined,
              chatCollectionId,
              handlers
            )
          : await sendChatMessage(
              message,
              currentSessionId || undefined,
              chatCollectionId,
              handlers,
              scopedDocumentIds
            );

      setStreamingText('');
      if (result.content) {
        const assistantMsg: MessageWithCitations = {
          id: result.messageId || `msg-${Date.now()}`,
          role: 'assistant',
          content: result.content,
          citations: result.citations,
          created_at: new Date().toISOString(),
          agentName: result.agentName,
        };
        setMessages((prev) => [...prev, assistantMsg]);
      }
      setAgentName(result.agentName || '');

      await fetchSessions();
    } catch (error: unknown) {
      const detail = error instanceof Error ? error.message : String(error);
      setMessages((prev) => prev.filter((item) => item.id !== tempMessageId));
      setCurrentSessionId(previousSessionId);
      setStreamingText('');
      setInput(message);
      setErrorMessage(`${t('chat.sendFailed')}: ${detail}`);
    } finally {
      setSending(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const getAgentBadgeColor = (name: string) => {
    const lower = name.toLowerCase();
    if (lower.includes('tutor') || lower.includes('teacher'))
      return 'bg-indigo-100 text-indigo-700 border-indigo-200';
    if (lower.includes('examiner') || lower.includes('quiz'))
      return 'bg-amber-100 text-amber-700 border-amber-200';
    if (lower.includes('summarizer') || lower.includes('summary'))
      return 'bg-emerald-100 text-emerald-700 border-emerald-200';
    if (lower.includes('analyst') || lower.includes('analysis'))
      return 'bg-purple-100 text-purple-700 border-purple-200';
    return 'bg-slate-100 text-slate-700 border-slate-200';
  };

  return (
    <div className="spell-page chat-workspace h-full flex">
      {/* Session sidebar */}
      <div className="chat-rail w-64 border-r border-gray-200 flex flex-col">
        {/* Collection filter for search scope */}
        <div className="p-3 border-b border-gray-200">
          <select
            value={chatCollectionId || ''}
            onChange={(e) => setChatCollectionId(e.target.value || null)}
            className="w-full text-xs px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          >
            <option value="">{t('chat.allKnowledgeBases')}</option>
            {chatCollections.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name}
              </option>
            ))}
          </select>
        </div>
        <div className="p-3 border-b border-gray-200">
          <input
            type="text"
            placeholder={t('chat.searchPlaceholder')}
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              if (e.target.value.length >= 2) {
                searchHistory(e.target.value)
                  .then(setSearchResults)
                  .catch(() => {});
              } else {
                setSearchResults([]);
              }
            }}
            className="w-full text-xs px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          />
          {searchResults.length > 0 && (
            <div className="mt-2 max-h-40 overflow-auto space-y-1">
              {searchResults.map((r) => (
                <button
                  key={r.message_id}
                  onClick={() => {
                    loadSession(r.session_id);
                    setSearchQuery('');
                    setSearchResults([]);
                  }}
                  className="w-full text-left text-xs p-2.5 bg-white hover:bg-blue-50 rounded-lg transition-all duration-200 border border-gray-100 hover:border-blue-200 hover:shadow-sm"
                >
                  <p className="text-gray-500 truncate">{r.session_title}</p>
                  <p className="text-gray-700 truncate mt-0.5">{r.content_preview}</p>
                </button>
              ))}
            </div>
          )}
        </div>
        <div className="p-3 border-b border-gray-200">
          <button
            onClick={handleNewChat}
            className="spell-button w-full py-2.5 bg-gradient-to-r from-blue-600 to-indigo-500 text-white rounded-lg text-sm hover:from-blue-700 hover:to-indigo-600 transition-all duration-200 shadow-sm hover:shadow-md font-medium"
          >
            {t('chat.newChat')}
          </button>
        </div>
        <div className="flex-1 overflow-auto p-2 space-y-0.5">
          {sessions.length === 0 && (
            <div className="text-center py-8 text-gray-400 text-xs">
              <p>{t('chat.noConversations')}</p>
              <p className="mt-1">{t('chat.noConversationsHint')}</p>
            </div>
          )}
          {sessions.map((s) => (
            <div
              key={s.id}
              className={`group flex items-center justify-between px-3 py-2.5 rounded-lg cursor-pointer text-sm transition-all duration-200 ${
                currentSessionId === s.id
                  ? 'bg-blue-50 text-blue-700 shadow-sm border border-blue-100'
                  : 'text-gray-600 hover:bg-gray-50 hover:text-gray-800 border border-transparent'
              }`}
            >
              <span className="truncate flex-1" onClick={() => loadSession(s.id)}>
                {s.title}
              </span>
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleDeleteSession(s.id);
                }}
                className="opacity-0 group-hover:opacity-100 text-xs text-red-400 hover:text-red-600 ml-1 transition-all duration-200 w-5 h-5 flex items-center justify-center rounded hover:bg-red-50"
              >
                x
              </button>
            </div>
          ))}
        </div>
      </div>

      {/* Chat area */}
      <div className="chat-stage flex-1 flex flex-col relative">
        {scopedDocumentIds.length > 0 && (
          <div className="flex items-center gap-3 border-b border-indigo-100 bg-indigo-50/80 px-5 py-2.5 text-xs text-indigo-800">
            <span className="font-semibold">
              {scopedDocumentIds.length > 1 ? t('chat.compareScope') : t('chat.documentScope')}
            </span>
            <span className="min-w-0 flex-1 truncate">
              {scopeNames.length > 0 ? scopeNames.join(' · ') : t('chat.selectedDocuments')}
            </span>
            <button
              onClick={() => {
                setScopedDocumentIds([]);
                setScopeNames([]);
              }}
              className="rounded-md px-2 py-1 text-indigo-600 hover:bg-indigo-100"
            >
              {t('chat.clearScope')}
            </button>
          </div>
        )}
        {/* Messages */}
        <div className="chat-scroll flex-1 overflow-auto p-6 space-y-5">
          {messages.length === 0 && !streamingText && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center max-w-sm">
                <div className="knowledge-orbit" aria-hidden="true">
                  <div className="knowledge-core">
                    <span>AI</span>
                  </div>
                </div>
                <p className="text-gray-600 font-medium mb-2">{t('chat.startChat')}</p>
                <p className="text-sm text-gray-400 leading-relaxed">{t('chat.startChatHint')}</p>
                <div className="mt-4 flex items-center justify-center gap-2 text-xs text-gray-400">
                  <span className="px-2 py-1 bg-gray-100 rounded-full">
                    {t('chat.enterToSend')}
                  </span>
                  <span className="px-2 py-1 bg-gray-100 rounded-full">
                    {t('chat.shiftEnterBreak')}
                  </span>
                </div>
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`message-enter flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div
                className={`max-w-[75%] ${
                  msg.role === 'user'
                    ? 'message-bubble message-bubble-user bg-gradient-to-br from-blue-600 to-indigo-500 text-white rounded-2xl rounded-tr-md px-5 py-3.5 shadow-md'
                    : 'message-bubble message-bubble-assistant bg-white border border-gray-100 rounded-2xl rounded-tl-md px-5 py-3.5 shadow-sm'
                }`}
              >
                {/* Agent badge */}
                {msg.role === 'assistant' && msg.agentName && (
                  <div className="mb-2">
                    <span
                      className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border ${getAgentBadgeColor(msg.agentName)}`}
                    >
                      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-60"></span>
                      {msg.agentName}
                    </span>
                  </div>
                )}

                <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>

                {/* Citations */}
                {msg.role === 'assistant' && msg.citations.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-100">
                    <p className="text-xs text-gray-400 mb-2">{t('chat.citations')}</p>
                    <div className="flex flex-wrap gap-1.5">
                      {msg.citations.map((c, i) => (
                        <button
                          key={i}
                          onClick={() =>
                            setExpandedCitation(
                              expandedCitation === `${msg.id}-${i}` ? null : `${msg.id}-${i}`
                            )
                          }
                          className="text-xs bg-gray-50 hover:bg-blue-50 text-gray-600 hover:text-blue-700 px-2 py-1 rounded-md transition-all duration-200 border border-transparent hover:border-blue-200"
                        >
                          [{i + 1}] {c.doc_name}
                          {c.page_num ? ` p.${c.page_num}` : ''}
                        </button>
                      ))}
                    </div>
                    {msg.citations.map(
                      (c, i) =>
                        expandedCitation === `${msg.id}-${i}` && (
                          <div
                            key={`expand-${i}`}
                            className="mt-2 p-3 bg-gray-50 rounded-lg text-xs text-gray-600 leading-relaxed border border-gray-100"
                          >
                            <p className="font-medium text-gray-700 mb-1">
                              {c.doc_name}
                              {c.page_num
                                ? ` · ${t('chat.page', { page: c.page_num })}`
                                : ''} · {t('chat.chunk', { index: c.chunk_index })}
                            </p>
                            <p>{c.text_preview}</p>
                            {c.doc_id && (
                              <button
                                onClick={() =>
                                  window.open(
                                    `/api/documents/${encodeURIComponent(c.doc_id)}/file${
                                      c.page_num ? `#page=${c.page_num}` : ''
                                    }`,
                                    '_blank',
                                    'noopener,noreferrer'
                                  )
                                }
                                className="mt-2 font-medium text-blue-600 hover:text-blue-700 hover:underline"
                              >
                                {t('chat.openSource')}
                              </button>
                            )}
                          </div>
                        )
                    )}
                  </div>
                )}

                {msg.role === 'assistant' && (
                  <div className="mt-2 flex justify-end">
                    <button
                      onClick={() => exportMessageAsMarkdown(msg.id)}
                      className="text-xs text-gray-400 hover:text-blue-600 transition-colors"
                      title={t('chat.exportMDTitle')}
                    >
                      {t('chat.exportMD')}
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Streaming text with typing indicator */}
          {sending && !streamingText && (
            <div className="message-enter flex justify-start">
              <div className="message-bubble message-bubble-assistant bg-white border border-gray-100 rounded-2xl rounded-tl-md px-5 py-4 shadow-sm">
                <div className="thinking-orbit" aria-label={t('common.loading')}>
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            </div>
          )}

          {streamingText && (
            <div className="message-enter flex justify-start">
              <div className="message-bubble message-bubble-assistant max-w-[75%] bg-white border border-gray-100 rounded-2xl rounded-tl-md px-5 py-3.5 shadow-sm">
                <p className="text-sm leading-relaxed whitespace-pre-wrap">
                  {streamingText}
                  {sending && (
                    <span className="typing-cursor inline-block w-0.5 h-4 bg-blue-500 ml-0.5 align-middle animate-pulse"></span>
                  )}
                </p>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        <div className="composer-dock p-4 border-t border-gray-200 bg-white">
          {/* Error banner */}
          {errorMessage && (
            <div className="mb-3 flex items-center gap-2 px-4 py-2.5 bg-red-50 border border-red-200 rounded-xl text-sm text-red-700">
              <span className="flex-1">{errorMessage}</span>
              <button
                onClick={() => setErrorMessage(null)}
                className="text-red-400 hover:text-red-600 transition-colors px-1"
              >
                ✕
              </button>
            </div>
          )}

          {/* Smart Mode Toggle */}
          <div className="flex items-center justify-between mb-3">
            <div className="flex items-center gap-2.5">
              <button
                onClick={() => setSmartMode(!smartMode)}
                className={`relative inline-flex h-6 w-11 items-center rounded-full transition-all duration-300 ${
                  smartMode ? 'bg-gradient-to-r from-indigo-500 to-purple-500' : 'bg-gray-200'
                }`}
              >
                <span
                  className={`inline-block h-4 w-4 transform rounded-full bg-white shadow-sm transition-all duration-300 ${
                    smartMode ? 'translate-x-6' : 'translate-x-1'
                  }`}
                />
              </button>
              <span
                className={`text-xs font-medium transition-colors duration-200 ${smartMode ? 'text-indigo-600' : 'text-gray-400'}`}
              >
                {t('chat.smartMode')}
              </span>
              {smartMode && (
                <span className="text-xs px-2 py-0.5 bg-indigo-50 text-indigo-500 rounded-full border border-indigo-100">
                  Multi-Agent
                </span>
              )}
            </div>
            {agentName && smartMode && (
              <span
                className={`text-xs px-2.5 py-1 rounded-full border ${getAgentBadgeColor(agentName)}`}
              >
                {t('chat.lastResponse')}: {agentName}
              </span>
            )}
          </div>

          <div className="composer-shell flex gap-2 items-end">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={smartMode ? t('chat.smartModePlaceholder') : t('chat.inputPlaceholder')}
              rows={1}
              className={`spell-input flex-1 px-4 py-3 border-0 rounded-xl text-sm resize-none focus:outline-none focus:ring-0 transition-all duration-200 ${
                smartMode
                  ? 'border-indigo-200 focus:ring-indigo-400 bg-indigo-50/30'
                  : 'border-gray-200 focus:ring-blue-500 bg-white'
              }`}
              style={{ minHeight: '44px', maxHeight: '120px' }}
            />
            <button
              onClick={handleSend}
              disabled={sending || !input.trim()}
              className={`spell-button px-5 py-3 text-white rounded-xl text-sm disabled:opacity-50 transition-all duration-200 whitespace-nowrap shadow-sm hover:shadow-md font-medium ${
                smartMode
                  ? 'bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700'
                  : 'bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-700 hover:to-blue-600'
              }`}
            >
              {sending ? t('common.sending') : t('common.send')}
            </button>
            <button
              onClick={() => setShowDebug(!showDebug)}
              className={`px-3 py-3 rounded-xl text-sm transition-all duration-200 whitespace-nowrap ${
                showDebug
                  ? 'bg-orange-100 text-orange-700 border border-orange-200'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200 border border-transparent'
              }`}
              title="RAG Debug Panel"
            >
              Debug
            </button>
          </div>
        </div>
      </div>

      {/* Debug Panel */}
      {showDebug && <DebugPanel debugInfo={debugInfo} onClose={() => setShowDebug(false)} />}
    </div>
  );
}
