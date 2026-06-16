import { useState, useEffect, useCallback } from 'react';
import { useTranslation, Trans } from 'react-i18next';
import {
  ApiKeyStatus,
  ModelCatalogResponse,
  getApiKeyStatus,
  getModelCatalog,
  updateApiKey,
  updateModelSelection,
} from '../api';

export default function Settings() {
  const { t } = useTranslation();
  const [status, setStatus] = useState<ApiKeyStatus | null>(null);
  const [apiKey, setApiKey] = useState('');
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState('');
  const [messageType, setMessageType] = useState<'success' | 'error'>('error');
  const [showKey, setShowKey] = useState(false);
  const [modelCatalog, setModelCatalog] = useState<ModelCatalogResponse | null>(null);
  const [selectedProvider, setSelectedProvider] = useState('openai');
  const [selectedModel, setSelectedModel] = useState('gpt-4o-mini');
  const [customModel, setCustomModel] = useState('');
  const [baseUrl, setBaseUrl] = useState('');

  const loadStatus = useCallback(async () => {
    try {
      const [s, catalog] = await Promise.all([getApiKeyStatus(), getModelCatalog()]);
      setStatus(s);
      setModelCatalog(catalog);
      setSelectedProvider(catalog.current.llm_provider || s.llm_provider);
      setSelectedModel(catalog.current.llm_model || s.llm_model);
      setBaseUrl(catalog.current.llm_base_url || '');
    } catch {
      setMessage(t('settings.error_connect'));
      setMessageType('error');
    } finally {
      setLoading(false);
    }
  }, [t]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  const handleSave = async () => {
    if (!apiKey.trim()) {
      setMessage(t('settings.pleaseEnterKey'));
      setMessageType('error');
      return;
    }
    setSaving(true);
    setMessage('');
    try {
      const result = await updateApiKey(apiKey.trim());
      setMessage(result.message);
      setMessageType(result.success ? 'success' : 'error');
      if (result.success) {
        setApiKey('');
        await loadStatus();
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : t('settings.error_update'));
      setMessageType('error');
    } finally {
      setSaving(false);
    }
  };

  const currentProvider = modelCatalog?.providers.find((provider) => provider.id === selectedProvider);
  const currentModels = currentProvider?.models || [];
  const resolvedModel = selectedModel === '__custom__' ? customModel.trim() : selectedModel;

  const handleProviderChange = (providerId: string) => {
    const provider = modelCatalog?.providers.find((item) => item.id === providerId);
    setSelectedProvider(providerId);
    setSelectedModel(provider?.models[0]?.id || '__custom__');
    setCustomModel('');
    setBaseUrl(provider?.base_url || '');
  };

  const handleSaveModel = async () => {
    if (!resolvedModel) {
      setMessage(t('settings.pleaseEnterModel'));
      setMessageType('error');
      return;
    }
    setSaving(true);
    setMessage('');
    try {
      const result = await updateModelSelection({
        llm_provider: selectedProvider,
        llm_model: resolvedModel,
        llm_base_url: baseUrl || null,
        api_key: apiKey.trim() || null,
      });
      setMessage(result.message);
      setMessageType(result.success ? 'success' : 'error');
      if (result.success) {
        setApiKey('');
        await loadStatus();
      }
    } catch (err) {
      setMessage(err instanceof Error ? err.message : t('settings.error_update'));
      setMessageType('error');
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
    <div className="spell-page h-full overflow-y-auto bg-transparent p-6">
      <div className="max-w-2xl mx-auto">
        <h1 className="text-2xl font-bold text-gray-800 mb-6">{t('settings.title')}</h1>

        {/* API Key 配置卡片 */}
        <div className="spell-card bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 bg-gradient-to-r from-slate-50 to-white">
            <h2 className="text-lg font-semibold text-gray-800">{t('settings.apiConfig')}</h2>
            <p className="text-sm text-gray-500 mt-1">{t('settings.apiConfigDesc')}</p>
          </div>

          <div className="p-6 space-y-5">
            {/* 当前状态 */}
            <div className="flex items-center gap-3">
              <div
                className={`w-3 h-3 rounded-full ${status?.has_key ? 'bg-green-500' : 'bg-red-500'}`}
              />
              <span className="text-sm text-gray-600">
                {t('settings.status')}
                {status?.has_key ? (
                  <span className="text-green-700 font-medium ml-1">
                    {t('settings.configured')}（{status.key_preview}）
                  </span>
                ) : (
                  <span className="text-red-600 font-medium ml-1">
                    {t('settings.notConfigured')}
                  </span>
                )}
              </span>
            </div>

            {/* 模型信息 */}
            {status && (
              <div className="grid grid-cols-2 gap-4">
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-400 mb-1">{t('settings.llmModel')}</p>
                  <p className="text-sm font-medium text-gray-700">
                    {status.llm_provider} / {status.llm_model}
                  </p>
                </div>
                <div className="bg-gray-50 rounded-lg p-3">
                  <p className="text-xs text-gray-400 mb-1">{t('settings.embeddingModel')}</p>
                  <p className="text-sm font-medium text-gray-700">
                    {status.embedding_provider} / {status.embedding_model}
                  </p>
                </div>
              </div>
            )}

            {/* Model selection */}
            {modelCatalog && (
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    {t('settings.providerLabel')}
                  </label>
                  <select
                    value={selectedProvider}
                    onChange={(event) => handleProviderChange(event.target.value)}
                    className="spell-input w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm bg-white"
                  >
                    {modelCatalog.providers.map((provider) => (
                      <option key={provider.id} value={provider.id}>
                        {provider.label}
                      </option>
                    ))}
                  </select>
                  {currentProvider?.docs_url && (
                    <a
                      href={currentProvider.docs_url}
                      target="_blank"
                      rel="noopener"
                      className="text-xs text-blue-600 hover:underline mt-1 inline-block"
                    >
                      {t('settings.providerDocs')}
                    </a>
                  )}
                </div>

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    {t('settings.modelLabel')}
                  </label>
                  <select
                    value={selectedModel}
                    onChange={(event) => setSelectedModel(event.target.value)}
                    className="spell-input w-full px-3 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm bg-white"
                  >
                    {currentModels.map((model) => (
                      <option key={model.id} value={model.id}>
                        {model.label} ({model.id})
                      </option>
                    ))}
                    <option value="__custom__">{t('settings.customModel')}</option>
                  </select>
                </div>

                {selectedModel === '__custom__' && (
                  <div>
                    <label className="block text-sm font-medium text-gray-700 mb-2">
                      {t('settings.customModelLabel')}
                    </label>
                    <input
                      value={customModel}
                      onChange={(event) => setCustomModel(event.target.value)}
                      placeholder="provider-model-id"
                      className="spell-input w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm font-mono"
                    />
                  </div>
                )}

                <div>
                  <label className="block text-sm font-medium text-gray-700 mb-2">
                    {t('settings.baseUrlLabel')}
                  </label>
                  <input
                    value={baseUrl}
                    onChange={(event) => setBaseUrl(event.target.value)}
                    placeholder={currentProvider?.base_url || 'https://api.example.com/v1'}
                    className="spell-input w-full px-4 py-2.5 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm font-mono"
                  />
                </div>
              </div>
            )}

            {/* 输入框 */}
            <div>
              <label className="block text-sm font-medium text-gray-700 mb-2">
                {currentProvider
                  ? t('settings.providerKeyLabel', { env: currentProvider.api_key_env })
                  : t('settings.apiKeyLabel')}
              </label>
              <div className="flex gap-2">
                <div className="relative flex-1">
                  <input
                    type={showKey ? 'text' : 'password'}
                    value={apiKey}
                    onChange={(e) => setApiKey(e.target.value)}
                    placeholder="sk-xxxxxxxxxxxxxxxxxxxxxxxx"
                    className="spell-input w-full px-4 py-2.5 pr-12 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-blue-500 text-sm font-mono transition-shadow"
                    onKeyDown={(e) => e.key === 'Enter' && handleSave()}
                  />
                  <button
                    type="button"
                    onClick={() => setShowKey(!showKey)}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-400 hover:text-gray-600 text-sm"
                  >
                    {showKey ? t('common.hide') : t('common.show')}
                  </button>
                </div>
                <button
                  onClick={handleSave}
                  disabled={saving}
                  className="spell-button px-6 py-2.5 bg-gradient-to-r from-blue-600 to-indigo-500 text-white rounded-lg hover:from-blue-700 hover:to-indigo-600 disabled:bg-gray-400 text-sm font-medium transition-colors whitespace-nowrap"
                >
                  {saving ? t('common.saving') : t('common.save')}
                </button>
              </div>
              <p className="text-xs text-gray-400 mt-2">{t('settings.securityNote')}</p>
            </div>

            <button
              onClick={handleSaveModel}
              disabled={saving || !modelCatalog}
              className="spell-button w-full px-6 py-2.5 bg-gradient-to-r from-slate-800 to-slate-700 text-white rounded-lg hover:from-slate-900 hover:to-slate-800 disabled:bg-gray-400 text-sm font-medium transition-colors"
            >
              {saving ? t('common.saving') : t('settings.saveModel')}
            </button>

            {/* 提示信息 */}
            {message && (
              <div
                className={`p-3 rounded-lg text-sm ${
                  messageType === 'success'
                    ? 'bg-green-50 text-green-700 border border-green-200'
                    : 'bg-red-50 text-red-700 border border-red-200'
                }`}
              >
                {message}
              </div>
            )}
          </div>
        </div>

        {/* 使用说明 */}
        <div className="spell-card mt-6 bg-white rounded-xl shadow-sm border border-gray-200 overflow-hidden">
          <div className="px-6 py-4 border-b border-gray-100 bg-gradient-to-r from-amber-50 to-white">
            <h2 className="text-lg font-semibold text-gray-800">{t('settings.guide')}</h2>
          </div>
          <div className="p-6 space-y-3 text-sm text-gray-600">
            <div className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-bold">
                1
              </span>
              <p>
                <Trans
                  i18nKey="settings.guide1"
                  components={{
                    a: (
                      <a
                        href="https://platform.openai.com/api-keys"
                        target="_blank"
                        rel="noopener"
                        className="text-blue-600 hover:underline"
                      />
                    ),
                  }}
                />
              </p>
            </div>
            <div className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-bold">
                2
              </span>
              <p>{t('settings.guide2')}</p>
            </div>
            <div className="flex gap-3">
              <span className="flex-shrink-0 w-6 h-6 bg-blue-100 text-blue-600 rounded-full flex items-center justify-center text-xs font-bold">
                3
              </span>
              <p>{t('settings.guide3')}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
