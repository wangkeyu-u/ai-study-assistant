import { useState, useEffect, useRef, useCallback } from 'react';
import {
  ChatSession,
  ChatMessage,
  Citation,
  Collection,
  DebugInfo,
  HistorySearchResult,
  MultiAgentResponse,
  listSessions,
  getSessionMessages,
  deleteSession,
  listCollections,
  exportMessageAsMarkdown,
  searchHistory,
  sendMultiAgentChat,
} from '../api';
import DebugPanel from '../components/DebugPanel';

interface MessageWithCitations extends ChatMessage {
  citations: Citation[];
  agentName?: string;
}

export default function ChatPage() {
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [currentSessionId, setCurrentSessionId] = useState<string | null>(null);
  const [messages, setMessages] = useState<MessageWithCitations[]>([]);
  const [input, setInput] = useState('');
  const [sending, setSending] = useState(false);
  const [streamingText, setStreamingText] = useState('');
  const [streamingCitations, setStreamingCitations] = useState<Citation[]>([]);
  const [debugInfo, setDebugInfo] = useState<DebugInfo | null>(null);
  const [showDebug, setShowDebug] = useState(false);
  const [expandedCitation, setExpandedCitation] = useState<string | null>(null);
  const [chatCollections, setChatCollections] = useState<Collection[]>([]);
  const [chatCollectionId, setChatCollectionId] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<HistorySearchResult[]>([]);
  const [smartMode, setSmartMode] = useState(false);
  const [agentName, setAgentName] = useState<string>('');
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
    listCollections().then(setChatCollections).catch(() => {});
  }, []);

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
    setStreamingCitations([]);
    setDebugInfo(null);
    setAgentName('');
    inputRef.current?.focus();
  };

  const handleDeleteSession = async (sessionId: string) => {
    if (!confirm('确认删除此会话？')) return;
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

  const handleSendMultiAgent = async (message: string) => {
    try {
      const res: MultiAgentResponse = await sendMultiAgentChat(message, currentSessionId || undefined);
      setAgentName(res.agent_name);

      const userMsg: MessageWithCitations = {
        id: `temp-${Date.now()}`,
        role: 'user',
        content: message,
        citations: [],
        created_at: new Date().toISOString(),
      };
      setMessages((prev) => [...prev, userMsg]);

      const assistantMsg: MessageWithCitations = {
        id: `msg-${Date.now()}`,
        role: 'assistant',
        content: res.content,
        citations: [],
        created_at: new Date().toISOString(),
        agentName: res.agent_name,
      };
      setMessages((prev) => [...prev, assistantMsg]);
      await fetchSessions();
    } catch (e: any) {
      setStreamingText(`发送失败: ${e.message}`);
    } finally {
      setSending(false);
    }
  };

  const handleSend = async () => {
    const message = input.trim();
    if (!message || sending) return;

    setInput('');
    setSending(true);
    setStreamingText('');
    setStreamingCitations([]);
    setDebugInfo(null);
    setAgentName('');

    // Smart Mode: use Multi-Agent API
    if (smartMode) {
      await handleSendMultiAgent(message);
      return;
    }

    // Add user message to local state
    const userMsg: MessageWithCitations = {
      id: `temp-${Date.now()}`,
      role: 'user',
      content: message,
      citations: [],
      created_at: new Date().toISOString(),
    };
    setMessages((prev) => [...prev, userMsg]);

    try {
      const res = await fetch('/api/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: currentSessionId,
          message: message,
          collection_id: chatCollectionId,
        }),
      });

      if (!res.ok) {
        throw new Error('请求失败');
      }

      const reader = res.body?.getReader();
      if (!reader) throw new Error('No response stream');

      const decoder = new TextDecoder();
      let buffer = '';
      let currentEvent = '';
      let newSessionId = currentSessionId;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        const lines = buffer.split('\n');
        buffer = lines.pop() || '';

        for (const line of lines) {
          if (line.startsWith('event: ')) {
            currentEvent = line.slice(7).trim();
          } else if (line.startsWith('data: ')) {
            try {
              const data = JSON.parse(line.slice(6));

              switch (currentEvent) {
                case 'session':
                  newSessionId = data.session_id;
                  setCurrentSessionId(newSessionId);
                  break;
                case 'token':
                  setStreamingText((prev) => prev + data.text);
                  break;
                case 'citations':
                  setStreamingCitations(data);
                  break;
                case 'debug':
                  setDebugInfo(data);
                  break;
                case 'done':
                  break;
              }
            } catch {
              // skip malformed JSON
            }
          }
        }
      }

      // Finalize: add assistant message to history
      setStreamingText((fullText) => {
        if (fullText) {
          const assistantMsg: MessageWithCitations = {
            id: `msg-${Date.now()}`,
            role: 'assistant',
            content: fullText,
            citations: streamingCitations,
            created_at: new Date().toISOString(),
          };
          setMessages((prev) => [...prev, assistantMsg]);
        }
        return '';
      });

      await fetchSessions();

    } catch (e: any) {
      setStreamingText(`发送失败: ${e.message}`);
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
    if (lower.includes('tutor') || lower.includes('teacher')) return 'bg-indigo-100 text-indigo-700 border-indigo-200';
    if (lower.includes('examiner') || lower.includes('quiz')) return 'bg-amber-100 text-amber-700 border-amber-200';
    if (lower.includes('summarizer') || lower.includes('summary')) return 'bg-emerald-100 text-emerald-700 border-emerald-200';
    if (lower.includes('analyst') || lower.includes('analysis')) return 'bg-purple-100 text-purple-700 border-purple-200';
    return 'bg-slate-100 text-slate-700 border-slate-200';
  };

  return (
    <div className="h-full flex">
      {/* Session sidebar */}
      <div className="w-64 bg-gradient-to-b from-slate-50 to-white border-r border-gray-200 flex flex-col">
        {/* Collection filter for search scope */}
        <div className="p-3 border-b border-gray-200">
          <select
            value={chatCollectionId || ''}
            onChange={(e) => setChatCollectionId(e.target.value || null)}
            className="w-full text-xs px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          >
            <option value="">全部知识库</option>
            {chatCollections.map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </div>
        <div className="p-3 border-b border-gray-200">
          <input
            type="text"
            placeholder="搜索历史对话..."
            value={searchQuery}
            onChange={(e) => {
              setSearchQuery(e.target.value);
              if (e.target.value.length >= 2) {
                searchHistory(e.target.value).then(setSearchResults).catch(() => {});
              } else {
                setSearchResults([]);
              }
            }}
            className="w-full text-xs px-3 py-2 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          />
          {searchResults.length > 0 && (
            <div className="mt-2 max-h-40 overflow-auto space-y-1">
              {searchResults.map(r => (
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
            className="w-full py-2.5 bg-gradient-to-r from-blue-600 to-blue-500 text-white rounded-lg text-sm hover:from-blue-700 hover:to-blue-600 transition-all duration-200 shadow-sm hover:shadow-md font-medium"
          >
            + 新对话
          </button>
        </div>
        <div className="flex-1 overflow-auto p-2 space-y-0.5">
          {sessions.length === 0 && (
            <div className="text-center py-8 text-gray-400 text-xs">
              <p>暂无对话记录</p>
              <p className="mt-1">点击上方按钮开始新对话</p>
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
              <span
                className="truncate flex-1"
                onClick={() => loadSession(s.id)}
              >
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
      <div className="flex-1 flex flex-col relative bg-gradient-to-b from-gray-50/50 to-white">
        {/* Messages */}
        <div className="flex-1 overflow-auto p-6 space-y-5">
          {messages.length === 0 && !streamingText && (
            <div className="flex items-center justify-center h-full">
              <div className="text-center max-w-sm">
                <div className="w-16 h-16 mx-auto mb-4 bg-gradient-to-br from-blue-100 to-indigo-100 rounded-2xl flex items-center justify-center">
                  <span className="text-3xl">💬</span>
                </div>
                <p className="text-gray-600 font-medium mb-2">开始智能对话</p>
                <p className="text-sm text-gray-400 leading-relaxed">上传学习资料后，在这里提问。每个回答都会标注引用来源。</p>
                <div className="mt-4 flex items-center justify-center gap-2 text-xs text-gray-400">
                  <span className="px-2 py-1 bg-gray-100 rounded-full">Enter 发送</span>
                  <span className="px-2 py-1 bg-gray-100 rounded-full">Shift+Enter 换行</span>
                </div>
              </div>
            </div>
          )}

          {messages.map((msg) => (
            <div
              key={msg.id}
              className={`message-enter flex ${msg.role === 'user' ? 'justify-end' : 'justify-start'}`}
            >
              <div className={`max-w-[75%] ${
                msg.role === 'user'
                  ? 'bg-gradient-to-br from-blue-600 to-blue-500 text-white rounded-2xl rounded-tr-md px-5 py-3.5 shadow-md'
                  : 'bg-white border border-gray-100 rounded-2xl rounded-tl-md px-5 py-3.5 shadow-sm'
              }`}>
                {/* Agent badge */}
                {msg.role === 'assistant' && msg.agentName && (
                  <div className="mb-2">
                    <span className={`inline-flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border ${getAgentBadgeColor(msg.agentName)}`}>
                      <span className="w-1.5 h-1.5 rounded-full bg-current opacity-60"></span>
                      {msg.agentName}
                    </span>
                  </div>
                )}

                <p className="text-sm leading-relaxed whitespace-pre-wrap">{msg.content}</p>

                {/* Citations */}
                {msg.role === 'assistant' && msg.citations.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-gray-100">
                    <p className="text-xs text-gray-400 mb-2">引用来源：</p>
                    <div className="flex flex-wrap gap-1.5">
                      {msg.citations.map((c, i) => (
                        <button
                          key={i}
                          onClick={() => setExpandedCitation(
                            expandedCitation === `${msg.id}-${i}` ? null : `${msg.id}-${i}`
                          )}
                          className="text-xs bg-gray-50 hover:bg-blue-50 text-gray-600 hover:text-blue-700 px-2 py-1 rounded-md transition-all duration-200 border border-transparent hover:border-blue-200"
                        >
                          [{i + 1}] {c.doc_name}{c.page_num ? ` p.${c.page_num}` : ''}
                        </button>
                      ))}
                    </div>
                    {msg.citations.map((c, i) => (
                      expandedCitation === `${msg.id}-${i}` && (
                        <div key={`expand-${i}`} className="mt-2 p-3 bg-gray-50 rounded-lg text-xs text-gray-600 leading-relaxed border border-gray-100">
                          <p className="font-medium text-gray-700 mb-1">
                            {c.doc_name}{c.page_num ? ` · 第${c.page_num}页` : ''} · 块 #{c.chunk_index}
                          </p>
                          <p>{c.text_preview}</p>
                        </div>
                      )
                    ))}
                  </div>
                )}

                {msg.role === 'assistant' && (
                  <div className="mt-2 flex justify-end">
                    <button
                      onClick={() => exportMessageAsMarkdown(msg.id)}
                      className="text-xs text-gray-400 hover:text-blue-600 transition-colors"
                      title="导出为 Markdown 文件"
                    >
                      导出 MD
                    </button>
                  </div>
                )}
              </div>
            </div>
          ))}

          {/* Streaming text with typing indicator */}
          {sending && !streamingText && (
            <div className="message-enter flex justify-start">
              <div className="bg-white border border-gray-100 rounded-2xl rounded-tl-md px-5 py-4 shadow-sm">
                <div className="typing-indicator flex items-center gap-1.5">
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '0ms' }}></span>
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '150ms' }}></span>
                  <span className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: '300ms' }}></span>
                </div>
              </div>
            </div>
          )}

          {streamingText && (
            <div className="message-enter flex justify-start">
              <div className="max-w-[75%] bg-white border border-gray-100 rounded-2xl rounded-tl-md px-5 py-3.5 shadow-sm">
                <p className="text-sm leading-relaxed whitespace-pre-wrap">
                  {streamingText}
                  {sending && <span className="typing-cursor inline-block w-0.5 h-4 bg-blue-500 ml-0.5 align-middle animate-pulse"></span>}
                </p>
              </div>
            </div>
          )}

          <div ref={messagesEndRef} />
        </div>

        {/* Input area */}
        <div className="p-4 border-t border-gray-200 bg-white">
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
              <span className={`text-xs font-medium transition-colors duration-200 ${smartMode ? 'text-indigo-600' : 'text-gray-400'}`}>
                智能模式
              </span>
              {smartMode && (
                <span className="text-xs px-2 py-0.5 bg-indigo-50 text-indigo-500 rounded-full border border-indigo-100">
                  Multi-Agent
                </span>
              )}
            </div>
            {agentName && smartMode && (
              <span className={`text-xs px-2.5 py-1 rounded-full border ${getAgentBadgeColor(agentName)}`}>
                上次回答: {agentName}
              </span>
            )}
          </div>

          <div className="flex gap-2 items-end">
            <textarea
              ref={inputRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={smartMode
                ? "智能模式已开启 — 输入你的问题... (Enter 发送)"
                : "输入你的问题... (Enter 发送, Shift+Enter 换行)"
              }
              rows={1}
              className={`flex-1 px-4 py-3 border rounded-xl text-sm resize-none focus:outline-none focus:ring-2 focus:border-transparent transition-all duration-200 ${
                smartMode
                  ? 'border-indigo-200 focus:ring-indigo-400 bg-indigo-50/30'
                  : 'border-gray-200 focus:ring-blue-500 bg-white'
              }`}
              style={{ minHeight: '44px', maxHeight: '120px' }}
            />
            <button
              onClick={handleSend}
              disabled={sending || !input.trim()}
              className={`px-5 py-3 text-white rounded-xl text-sm disabled:opacity-50 transition-all duration-200 whitespace-nowrap shadow-sm hover:shadow-md font-medium ${
                smartMode
                  ? 'bg-gradient-to-r from-indigo-600 to-purple-600 hover:from-indigo-700 hover:to-purple-700'
                  : 'bg-gradient-to-r from-blue-600 to-blue-500 hover:from-blue-700 hover:to-blue-600'
              }`}
            >
              {sending ? '生成中...' : '发送'}
            </button>
            <button
              onClick={() => setShowDebug(!showDebug)}
              className={`px-3 py-3 rounded-xl text-sm transition-all duration-200 whitespace-nowrap ${
                showDebug ? 'bg-orange-100 text-orange-700 border border-orange-200' : 'bg-gray-100 text-gray-600 hover:bg-gray-200 border border-transparent'
              }`}
              title="RAG Debug Panel"
            >
              Debug
            </button>
          </div>
        </div>
      </div>

      {/* Debug Panel */}
      {showDebug && (
        <DebugPanel debugInfo={debugInfo} onClose={() => setShowDebug(false)} />
      )}
    </div>
  );
}
