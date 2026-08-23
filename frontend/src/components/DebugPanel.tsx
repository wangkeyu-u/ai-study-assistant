import { DebugInfo } from '../api';
import Icon from './Icon';

interface DebugPanelProps {
  debugInfo: DebugInfo | null;
  onClose: () => void;
}

export default function DebugPanel({ debugInfo, onClose }: DebugPanelProps) {
  return (
    <div className="w-96 bg-white border-l border-gray-200 flex flex-col overflow-hidden">
      {/* Header */}
      <div className="p-4 border-b border-gray-200 flex items-center justify-between bg-orange-50">
        <h3 className="text-sm font-semibold text-orange-800">RAG Debug Panel</h3>
        <button
          onClick={onClose}
          className="grid h-8 w-8 place-items-center rounded-lg text-orange-600 hover:bg-orange-100 hover:text-orange-800"
          aria-label="Close debug panel"
        >
          <Icon name="x" size={14} />
        </button>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-auto p-4 space-y-5">
        {!debugInfo ? (
          <p className="text-sm text-gray-400 text-center py-8">
            进行一次问答后，这里会显示 RAG 内部的详细信息
          </p>
        ) : (
          <>
            {/* Query */}
            <section>
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Query</h4>
              <p className="text-sm text-gray-800 bg-gray-50 rounded-lg p-3">{debugInfo.query}</p>
              {debugInfo.rewritten_query && (
                <div className="mt-2">
                  <p className="text-xs text-gray-400 mb-1">Rewritten</p>
                  <p className="text-xs text-gray-600 bg-blue-50 rounded-lg p-2">
                    {debugInfo.rewritten_query}
                  </p>
                </div>
              )}
              {debugInfo.retrieval_queries && debugInfo.retrieval_queries.length > 1 && (
                <div className="mt-2">
                  <p className="text-xs text-gray-400 mb-1">Retrieval Queries</p>
                  <div className="space-y-1">
                    {debugInfo.retrieval_queries.map((query, index) => (
                      <p
                        key={`${query}-${index}`}
                        className="text-xs text-gray-600 bg-indigo-50 rounded-lg px-2 py-1.5"
                      >
                        {index + 1}. {query}
                      </p>
                    ))}
                  </div>
                </div>
              )}
            </section>

            {/* Query Profile */}
            {(debugInfo.query_intent || debugInfo.context_strategy) && (
              <section>
                <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                  Query Profile
                </h4>
                <div className="rounded-lg bg-blue-50 p-3 text-xs text-blue-900">
                  <div className="grid grid-cols-2 gap-2">
                    <div>
                      <p className="text-blue-500">Intent</p>
                      <p className="font-semibold">{debugInfo.query_intent || 'qa'}</p>
                    </div>
                    <div>
                      <p className="text-blue-500">Style</p>
                      <p className="font-semibold">{debugInfo.answer_style || 'grounded'}</p>
                    </div>
                    <div>
                      <p className="text-blue-500">Query language</p>
                      <p className="font-semibold">{debugInfo.query_language || 'unknown'}</p>
                    </div>
                    <div>
                      <p className="text-blue-500">Answer language</p>
                      <p className="font-semibold">{debugInfo.answer_language || 'auto'}</p>
                    </div>
                  </div>
                  {debugInfo.corpus_languages && debugInfo.corpus_languages.length > 0 && (
                    <p className="mt-2 text-[10px] text-blue-600">
                      Corpus: {debugInfo.corpus_languages.join(', ')}
                    </p>
                  )}
                  {debugInfo.query_keywords && debugInfo.query_keywords.length > 0 && (
                    <div className="mt-2 flex flex-wrap gap-1">
                      {debugInfo.query_keywords.slice(0, 8).map((keyword) => (
                        <span
                          key={keyword}
                          className="rounded bg-white/80 px-1.5 py-0.5 text-[10px] text-blue-700"
                        >
                          {keyword}
                        </span>
                      ))}
                    </div>
                  )}
                </div>
              </section>
            )}

            {/* Embedding Model */}
            <section>
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                Embedding Model
              </h4>
              <p className="text-sm text-gray-700">{debugInfo.embedding_model}</p>
              <p className="text-xs text-gray-400 mt-1">
                Retrieval: {debugInfo.retrieval_mode || 'vector'}
              </p>
              {debugInfo.confidence_rejected && (
                <p className="text-xs text-amber-600 mt-1">
                  Confidence gate rejected
                  {debugInfo.confidence_score != null
                    ? ` (${debugInfo.confidence_score.toFixed(3)})`
                    : ''}
                </p>
              )}
              {debugInfo.context_strategy && (
                <div className="mt-2 rounded-lg bg-gray-50 p-3 text-xs text-gray-600">
                  <p>
                    Context: {debugInfo.context_strategy}
                    {debugInfo.context_chunks_before != null &&
                    debugInfo.context_chunks_after != null
                      ? ` (${debugInfo.context_chunks_before} -> ${debugInfo.context_chunks_after} chunks)`
                      : ''}
                  </p>
                  {debugInfo.context_coverage_score != null && (
                    <p className="mt-1">
                      Query coverage: {(debugInfo.context_coverage_score * 100).toFixed(1)}%
                    </p>
                  )}
                </div>
              )}
            </section>

            {/* Performance */}
            <section>
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Performance</h4>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-500">检索耗时</p>
                  <p className="text-lg font-semibold text-gray-800">
                    {debugInfo.retrieval_time_ms.toFixed(0)}
                    <span className="text-xs font-normal text-gray-400">ms</span>
                  </p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-500">生成耗时</p>
                  <p className="text-lg font-semibold text-gray-800">
                    {debugInfo.generation_time_ms.toFixed(0)}
                    <span className="text-xs font-normal text-gray-400">ms</span>
                  </p>
                </div>
              </div>
            </section>

            {/* Token Usage */}
            <section>
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Token Usage</h4>
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-gray-50 rounded-lg p-2 text-center">
                  <p className="text-xs text-gray-500">Prompt</p>
                  <p className="text-sm font-semibold text-gray-800">
                    {debugInfo.token_usage.prompt_tokens}
                  </p>
                </div>
                <div className="bg-gray-50 rounded-lg p-2 text-center">
                  <p className="text-xs text-gray-500">Completion</p>
                  <p className="text-sm font-semibold text-gray-800">
                    {debugInfo.token_usage.completion_tokens}
                  </p>
                </div>
                <div className="bg-gray-50 rounded-lg p-2 text-center">
                  <p className="text-xs text-gray-500">Total</p>
                  <p className="text-sm font-semibold text-gray-800">
                    {debugInfo.token_usage.total_tokens}
                  </p>
                </div>
              </div>
            </section>

            {/* Retrieved Chunks */}
            <section>
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">
                Retrieved Chunks ({debugInfo.top_k_chunks.length})
              </h4>
              <div className="space-y-2">
                {debugInfo.top_k_chunks.map((chunk, i) => (
                  <div key={i} className="bg-gray-50 rounded-lg p-3">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-xs font-medium text-gray-700">
                        [{i + 1}] {chunk.doc_name}
                      </span>
                      <span
                        className={`text-xs font-semibold px-1.5 py-0.5 rounded ${
                          chunk.similarity_score >= 0.7
                            ? 'bg-green-100 text-green-700'
                            : chunk.similarity_score >= 0.5
                              ? 'bg-yellow-100 text-yellow-700'
                              : 'bg-red-100 text-red-700'
                        }`}
                      >
                        {(chunk.similarity_score * 100).toFixed(1)}%
                      </span>
                    </div>
                    {chunk.page_num && (
                      <p className="text-xs text-gray-400 mb-1">Page {chunk.page_num}</p>
                    )}
                    {chunk.retrieval_sources && chunk.retrieval_sources.length > 0 && (
                      <div className="flex gap-1 mb-1.5">
                        {chunk.retrieval_sources.map((source) => (
                          <span
                            key={source}
                            className="text-[10px] uppercase bg-blue-50 text-blue-600 px-1.5 py-0.5 rounded"
                          >
                            {source}
                          </span>
                        ))}
                      </div>
                    )}
                    {chunk.rerank_score != null && (
                      <p className="text-[10px] text-purple-600 mb-1">
                        Rerank: {chunk.rerank_score.toFixed(4)}
                      </p>
                    )}
                    <p className="text-xs text-gray-600 leading-relaxed">{chunk.text_preview}...</p>
                  </div>
                ))}
              </div>
            </section>
          </>
        )}
      </div>
    </div>
  );
}
