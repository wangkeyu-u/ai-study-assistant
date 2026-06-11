import { DebugInfo } from '../api';

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
          className="text-orange-600 hover:text-orange-800 text-sm"
        >
          ✕
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
            </section>

            {/* Embedding Model */}
            <section>
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Embedding Model</h4>
              <p className="text-sm text-gray-700">{debugInfo.embedding_model}</p>
            </section>

            {/* Performance */}
            <section>
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Performance</h4>
              <div className="grid grid-cols-2 gap-2">
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-500">检索耗时</p>
                  <p className="text-lg font-semibold text-gray-800">{debugInfo.retrieval_time_ms.toFixed(0)}<span className="text-xs font-normal text-gray-400">ms</span></p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-500">生成耗时</p>
                  <p className="text-lg font-semibold text-gray-800">{debugInfo.generation_time_ms.toFixed(0)}<span className="text-xs font-normal text-gray-400">ms</span></p>
                </div>
              </div>
            </section>

            {/* Token Usage */}
            <section>
              <h4 className="text-xs font-semibold text-gray-500 uppercase mb-2">Token Usage</h4>
              <div className="grid grid-cols-3 gap-2">
                <div className="bg-gray-50 rounded-lg p-2 text-center">
                  <p className="text-xs text-gray-500">Prompt</p>
                  <p className="text-sm font-semibold text-gray-800">{debugInfo.token_usage.prompt_tokens}</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-2 text-center">
                  <p className="text-xs text-gray-500">Completion</p>
                  <p className="text-sm font-semibold text-gray-800">{debugInfo.token_usage.completion_tokens}</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-2 text-center">
                  <p className="text-xs text-gray-500">Total</p>
                  <p className="text-sm font-semibold text-gray-800">{debugInfo.token_usage.total_tokens}</p>
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
                      <span className={`text-xs font-semibold px-1.5 py-0.5 rounded ${
                        chunk.similarity_score >= 0.7 ? 'bg-green-100 text-green-700' :
                        chunk.similarity_score >= 0.5 ? 'bg-yellow-100 text-yellow-700' :
                        'bg-red-100 text-red-700'
                      }`}>
                        {(chunk.similarity_score * 100).toFixed(1)}%
                      </span>
                    </div>
                    {chunk.page_num && (
                      <p className="text-xs text-gray-400 mb-1">Page {chunk.page_num}</p>
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
