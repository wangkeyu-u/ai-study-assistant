import { useState, useEffect } from 'react';
import { getApiKeyStatus, updateApiKey, ApiKeyStatus } from '../api';

export default function Settings() {
  const [status, setStatus] = useState<ApiKeyStatus | null>(null);
  const [apiKey, setApiKey] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [showKey, setShowKey] = useState(false);

  useEffect(() => {
    loadStatus();
  }, []);

  const loadStatus = async () => {
    try {
      const s = await getApiKeyStatus();
      setStatus(s);
    } catch {
      setMessage('无法连接后端服务');
    } finally {
      setLoading(false);
    }
  };

  const handleSave = async () => {
    if (!apiKey.trim()) {
      setMessage('请输入 API Key');
      return;
    }
    setSaving(true);
    setMessage('');
    try {
      const result = await updateApiKey(apiKey.trim());
      setMessage(result.message);
      if (result.success) {
        setApiKey('');
        await loadStatus();
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : '保存失败');
    } finally {
      setSaving(false);
    }
  };

  if (loading) {
    return (
      <div className="h-full flex items-center justify-center">
        <div className="w-8 h-8 border-4 border-blue-200 border-t-blue-600 rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="h-full overflow-y-auto bg-gray-50 p-6">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-800 mb-6">设置</h1>

        {/* API Key 配置卡片 */}
        <div className="bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 bg-gradient-to-r from-slate-50 to-white">
            <h2 className="text-lg font-semibold text-gray-800">OpenAI API 配置</h2>
            <p className="text-sm text-gray-500 mt-1">
              配置你的 OpenAI API Key 以启用智能问答、测验生成、知识图谱等功能
            </p>
          </div>

          <div className="p-6 space-y-5">
            {/* 当前状态 */}
            <div className="flex items-center gap-3">
              <div className={`w-3 h-3 rounded-full ${status?.has_key ? 'bg-green-500' : 'bg-red-500'}`} />
              <span className="text-sm text-gray-600">
                当前状态：
                {status?.has_key ? (
                  <span className="text-green-700 font-medium ml-1">
                    已配置（{status.key_preview}）
                  </span>
                ) : (
                  <span className="text-red-600 font-medium ml-1">未配置</span>
                )}
              </span>
            </div>

            {/* 模型信息 */}
            {status && (
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-400 mb-1">LLM 模型</p>
                  <p className="text-sm font-medium text-gray-700">{status.llm_provider} / {status.llm_model}</p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-400 mb-1">Embedding 模型</p>
                  <p className="text-sm font-medium text-gray-700">{status.embedding_provider} / {status.embedding_model}</p>
                </div>
              </div>
            )}

            {/* 输入框 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                OpenAI API Key
              </label>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <input
                    type={showKey ? 'text' : 'password'}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxx"
                    className="w-full px-4 py-2.5 pr-12 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm font-mono transition-shadow"
                    onKeyDown={(e) => e.key === 'Enter' && handleSave()}
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey(!showKey)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-sm"
                  >
                    {showKey ? '隐藏' : '显示'}
                  </button>
                </div>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="px-6 py-2.5 bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:bg-gray-400 text-sm font-medium transition-colors whitespace-nowrap"
                >
                  {saving ? '保存中...' : '保存'}
                </button>
              </div>
              <p className="text-xs text-gray-400 mt-2">
                Key 会写入项目根目录的 .env 文件，仅保存在本地，不会上传到任何服务器。
              </p>
            </div>

            {/* 提示信息 */}
            {message && (
              <div className={`p-3 rounded-lg text-sm ${
                message.includes('已更新') || message.includes('成功')
                  ? 'bg-green-50 text-green-700 border border-green-200'
                  : 'bg-red-50 text-red-700 border border-red-200'
              }`}>
                {message}
              </div>
            )}
          </div>
        </div>

        {/* 使用说明 */}
        <div className="mt-6 bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 bg-gradient-to-r from-amber-50 to-white">
            <h2 className="text-lg font-semibold text-gray-800">使用指南</h2>
          </div>
          <div className="p-6 space-y-3 text-sm text-gray-600">
            <div className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-bold">1</span>
              <p>在 <a href="https://platform.openai.com/api-keys" target="_blank" rel="noopener" className="text-blue-600 hover:underline">OpenAI 平台</a> 获取 API Key</p>
            </div>
            <div className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-bold">2</span>
              <p>将 Key 粘贴到上方输入框并点击保存</p>
            </div>
            <div className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-bold">3</span>
              <p>保存后即可使用文档上传、智能问答、测验生成等全部功能</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
