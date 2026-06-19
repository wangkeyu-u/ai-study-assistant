import { useState, useEffect, useCallback, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { useNavigate } from 'react-router-dom';
import Icon from '../components/Icon';
import {
  Document,
  Collection,
  uploadDocument,
  deleteDocument,
  createNote,
  getChunks,
  addTag,
  removeTag,
  generateSummary,
  listCollections,
  createCollection,
  deleteCollection,
  assignDocToCollection,
  exportBackup,
  importBackup,
  ChunkInfo,
  Summary,
  getErrorMessage,
} from '../api';
import {
  DEMO_DOCUMENT_CONTENT,
  DEMO_DOCUMENT_FILENAME,
  DEMO_DOCUMENT_TITLE,
  DEMO_QUESTIONS,
} from '../demo';

const TAG_COLORS = [
  'bg-blue-50 text-blue-700 border-blue-200',
  'bg-emerald-50 text-emerald-700 border-emerald-200',
  'bg-purple-50 text-purple-700 border-purple-200',
  'bg-amber-50 text-amber-700 border-amber-200',
  'bg-rose-50 text-rose-700 border-rose-200',
  'bg-cyan-50 text-cyan-700 border-cyan-200',
  'bg-indigo-50 text-indigo-700 border-indigo-200',
  'bg-orange-50 text-orange-700 border-orange-200',
];

function getTagColor(tag: string) {
  let hash = 0;
  for (let i = 0; i < tag.length; i++) {
    hash = tag.charCodeAt(i) + ((hash << 5) - hash);
  }
  return TAG_COLORS[Math.abs(hash) % TAG_COLORS.length];
}

export default function Documents() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [docs, setDocs] = useState<Document[]>([]);
  const [loading, setLoading] = useState(false);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedDoc, setSelectedDoc] = useState<string | null>(null);
  const [chunks, setChunks] = useState<ChunkInfo[]>([]);
  const [showNoteModal, setShowNoteModal] = useState(false);
  const [noteTitle, setNoteTitle] = useState('');
  const [noteContent, setNoteContent] = useState('');
  const [tagInput, setTagInput] = useState<{ [docId: string]: string }>({});
  const [summaries, setSummaries] = useState<{ [docId: string]: Summary }>({});
  const [generatingSummary, setGeneratingSummary] = useState<string | null>(null);
  const [collections, setCollections] = useState<Collection[]>([]);
  const [selectedCollection, setSelectedCollection] = useState<string | null>(null);
  const [showNewCollectionModal, setShowNewCollectionModal] = useState(false);
  const [newCollName, setNewCollName] = useState('');
  const [newCollDesc, setNewCollDesc] = useState('');
  const [backupLoading, setBackupLoading] = useState(false);
  const [dragOver, setDragOver] = useState(false);
  const [demoLoading, setDemoLoading] = useState(false);
  const [compareDocumentIds, setCompareDocumentIds] = useState<string[]>([]);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const backupInputRef = useRef<HTMLInputElement>(null);

  const fetchDocs = useCallback(
    async (collId?: string | null) => {
      try {
        setLoading(true);
        let url = '/api/documents';
        if (collId) url += `?collection_id=${encodeURIComponent(collId)}`;
        const res = await fetch(url);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data = await res.json();
        setDocs(data.documents);
      } catch {
        setError(t('documents.error_loadDocs'));
      } finally {
        setLoading(false);
      }
    },
    [t]
  );

  const fetchCollections = useCallback(async () => {
    try {
      const data = await listCollections();
      setCollections(data);
    } catch {
      /* ignore */
    }
  }, []);

  useEffect(() => {
    fetchDocs(selectedCollection);
  }, [fetchDocs, selectedCollection]);

  useEffect(() => {
    fetchCollections();
  }, [fetchCollections]);

  const handleUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    setUploading(true);
    setError(null);

    try {
      for (const file of Array.from(files)) {
        await uploadDocument(file, selectedCollection || undefined);
      }
      await fetchDocs(selectedCollection);
    } catch (error: unknown) {
      setError(getErrorMessage(error, t('documents.error_upload')));
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDelete = async (docId: string) => {
    if (!confirm(t('documents.confirmDeleteDoc'))) return;
    try {
      await deleteDocument(docId);
      await fetchDocs(selectedCollection);
      if (selectedDoc === docId) {
        setSelectedDoc(null);
        setChunks([]);
      }
    } catch {
      setError(t('documents.error_delete'));
    }
  };

  const handleViewChunks = async (docId: string) => {
    if (selectedDoc === docId) {
      setSelectedDoc(null);
      setChunks([]);
      return;
    }
    setSelectedDoc(docId);
    try {
      const data = await getChunks(docId);
      setChunks(data);
    } catch {
      setChunks([]);
    }
  };

  const handleCreateNote = async () => {
    if (!noteTitle.trim() || !noteContent.trim()) return;
    try {
      await createNote(noteTitle.trim(), noteContent.trim(), selectedCollection || undefined);
      setShowNoteModal(false);
      setNoteTitle('');
      setNoteContent('');
      await fetchDocs(selectedCollection);
    } catch (error: unknown) {
      setError(getErrorMessage(error, t('documents.error_createNote')));
    }
  };

  const handleLoadDemo = async () => {
    setDemoLoading(true);
    setError(null);
    try {
      if (!docs.some((doc) => doc.filename === DEMO_DOCUMENT_FILENAME)) {
        await createNote(
          DEMO_DOCUMENT_TITLE,
          DEMO_DOCUMENT_CONTENT,
          selectedCollection || undefined
        );
        await fetchDocs(selectedCollection);
      }
    } catch (error: unknown) {
      setError(getErrorMessage(error, t('documents.error_demo')));
    } finally {
      setDemoLoading(false);
    }
  };

  const openQuestion = (question: string) => {
    navigate(`/chat?q=${encodeURIComponent(question)}`);
  };

  const askAboutDocument = (doc: Document) => {
    navigate(
      `/chat?documents=${encodeURIComponent(doc.id)}&names=${encodeURIComponent(doc.filename)}&q=${encodeURIComponent(
        t('documents.askDocumentPrompt', { filename: doc.filename })
      )}`
    );
  };

  const toggleCompareDocument = (docId: string) => {
    setCompareDocumentIds((current) =>
      current.includes(docId)
        ? current.filter((id) => id !== docId)
        : current.length < 5
          ? [...current, docId]
          : current
    );
  };

  const startComparison = () => {
    const selected = docs.filter((doc) => compareDocumentIds.includes(doc.id));
    if (selected.length < 2) return;
    navigate(
      `/chat?documents=${encodeURIComponent(selected.map((doc) => doc.id).join(','))}` +
        `&names=${encodeURIComponent(selected.map((doc) => doc.filename).join('|'))}` +
        `&q=${encodeURIComponent(
          t('documents.comparePrompt', {
            names: selected.map((doc) => doc.filename).join('、'),
          })
        )}`
    );
  };

  const handleAddTag = async (docId: string) => {
    const tag = (tagInput[docId] || '').trim();
    if (!tag) return;
    try {
      await addTag(docId, tag);
      setTagInput({ ...tagInput, [docId]: '' });
      await fetchDocs(selectedCollection);
    } catch (error: unknown) {
      setError(getErrorMessage(error, t('documents.error_addTag')));
    }
  };

  const handleRemoveTag = async (docId: string, tagName: string) => {
    try {
      await removeTag(docId, tagName);
      await fetchDocs(selectedCollection);
    } catch (error: unknown) {
      setError(getErrorMessage(error, t('documents.error_removeTag')));
    }
  };

  const handleGenerateSummary = async (docId: string) => {
    setGeneratingSummary(docId);
    try {
      const summary = await generateSummary(docId);
      setSummaries({ ...summaries, [docId]: summary });
    } catch (error: unknown) {
      setError(getErrorMessage(error, t('documents.error_summary')));
    } finally {
      setGeneratingSummary(null);
    }
  };

  const handleCreateCollection = async () => {
    if (!newCollName.trim()) return;
    try {
      await createCollection(newCollName.trim(), newCollDesc.trim() || undefined);
      setShowNewCollectionModal(false);
      setNewCollName('');
      setNewCollDesc('');
      await fetchCollections();
    } catch (error: unknown) {
      setError(getErrorMessage(error, t('documents.error_createCollection')));
    }
  };

  const handleDeleteCollection = async (id: string) => {
    if (!confirm(t('documents.confirmDeleteCol'))) return;
    try {
      await deleteCollection(id);
      if (selectedCollection === id) setSelectedCollection(null);
      await fetchCollections();
      await fetchDocs(null);
    } catch (error: unknown) {
      setError(getErrorMessage(error, t('documents.error_deleteCollection')));
    }
  };

  const handleAssignCollection = async (docId: string, collId: string | null) => {
    try {
      await assignDocToCollection(docId, collId);
      await fetchDocs(selectedCollection);
      await fetchCollections();
    } catch (error: unknown) {
      setError(getErrorMessage(error, t('documents.error_assignCollection')));
    }
  };

  const handleExportBackup = async () => {
    setBackupLoading(true);
    try {
      await exportBackup();
    } catch (error: unknown) {
      setError(getErrorMessage(error, t('documents.error_exportBackup')));
    } finally {
      setBackupLoading(false);
    }
  };

  const handleImportBackup = async (file: File) => {
    if (!confirm(t('documents.confirmImport'))) return;
    setBackupLoading(true);
    try {
      const result = await importBackup(file);
      alert(t('documents.importSuccess', { count: result.documents_restored }));
      window.location.reload();
    } catch (error: unknown) {
      setError(getErrorMessage(error, t('documents.error_import')));
    } finally {
      setBackupLoading(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handleUpload(e.dataTransfer.files);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = () => {
    setDragOver(false);
  };

  const formatSize = (bytes: number) => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
  };

  return (
    <div className="spell-page h-full flex flex-col">
      {/* Header */}
      <div className="page-header library-header border-b border-zinc-200 bg-white px-7 py-5">
        <div className="flex items-center justify-between gap-5">
          <div>
            <h1 className="text-xl font-semibold tracking-tight text-zinc-900">
              {t('documents.title')}
            </h1>
            <p className="mt-1 text-sm text-zinc-500">{t('documents.subtitle')}</p>
          </div>
          <div className="flex items-center gap-2">
            <button onClick={() => setShowNoteModal(true)} className="secondary-action">
              <Icon name="note" size={16} /> {t('documents.newNote')}
            </button>
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="primary-action"
            >
              <Icon name="upload" size={16} />
              {uploading ? t('common.uploading') : t('documents.selectFile')}
            </button>
          </div>
        </div>

        <div className="mt-4 flex items-center gap-2">
          <select
            value={selectedCollection || ''}
            onChange={(e) => setSelectedCollection(e.target.value || null)}
            className="quiet-select"
          >
            <option value="">{t('documents.allDocuments')}</option>
            {collections.map((c) => (
              <option key={c.id} value={c.id}>
                {c.name} ({c.doc_count})
              </option>
            ))}
          </select>
          <button onClick={() => setShowNewCollectionModal(true)} className="quiet-button">
            {t('documents.newCollection')}
          </button>
          {selectedCollection && (
            <button
              onClick={() => handleDeleteCollection(selectedCollection)}
              className="text-xs px-3 py-1.5 bg-red-50 text-red-700 rounded-lg hover:bg-red-100 transition-colors border border-red-100"
            >
              {t('common.delete')}
            </button>
          )}
          <div className="flex-1" />
          <details className="context-menu">
            <summary aria-label={t('documents.moreActions')}>
              <Icon name="more" size={18} />
            </summary>
            <div className="context-menu-popover">
              <button onClick={handleLoadDemo} disabled={demoLoading}>
                <Icon name="sparkles" size={15} />
                {demoLoading ? t('documents.loadingDemo') : t('documents.loadDemo')}
              </button>
              <button onClick={handleExportBackup} disabled={backupLoading}>
                <Icon name="database" size={15} />
                {backupLoading ? t('common.exporting') : t('documents.backupData')}
              </button>
              <button onClick={() => backupInputRef.current?.click()}>
                <Icon name="upload" size={15} /> {t('documents.importBackup')}
              </button>
            </div>
          </details>
          <input
            ref={backupInputRef}
            type="file"
            accept=".zip"
            onChange={(e) => {
              if (e.target.files?.[0]) handleImportBackup(e.target.files[0]);
              e.target.value = '';
            }}
            className="hidden"
          />
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.txt,.md"
            onChange={(e) => handleUpload(e.target.files)}
            className="hidden"
          />
        </div>
      </div>

      {/* Upload area */}
      <div className="border-b border-zinc-200 bg-white px-7 py-3">
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          className={`library-drop-row ${dragOver ? 'is-dragging' : ''} ${
            dragOver ? 'border-blue-400 bg-blue-50' : 'border-zinc-200 hover:border-zinc-300'
          }`}
        >
          <Icon name="upload" size={17} />
          <p className="text-sm font-medium text-zinc-600">
            {dragOver ? t('documents.dropHint') : t('documents.dragHint')}
          </p>
          <span className="ml-auto text-xs text-zinc-400">{t('documents.formatHint')}</span>
        </div>
        {error && docs.length > 0 && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center gap-2">
            <span className="text-red-400">⚠️</span>
            {error}
          </div>
        )}
      </div>

      {/* Document list */}
      <div className="flex-1 overflow-auto p-6">
        {compareDocumentIds.length > 0 && (
          <div className="mb-4 flex items-center gap-3 rounded-xl border border-blue-200 bg-blue-50 px-4 py-3 text-sm text-blue-900">
            <span className="font-medium">
              {t('documents.selectedForCompare', { count: compareDocumentIds.length })}
            </span>
            <span className="text-xs text-blue-600">{t('documents.compareLimit')}</span>
            <div className="flex-1" />
            <button
              onClick={() => setCompareDocumentIds([])}
              className="px-3 py-1.5 text-xs text-blue-600 hover:bg-blue-100 rounded-lg"
            >
              {t('common.cancel')}
            </button>
            <button
              onClick={startComparison}
              disabled={compareDocumentIds.length < 2}
              className="rounded-lg bg-blue-600 px-4 py-1.5 text-xs font-medium text-white hover:bg-blue-700 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {t('documents.compareNow')}
            </button>
          </div>
        )}
        {docs.some((doc) => doc.filename === DEMO_DOCUMENT_FILENAME) && (
          <div className="mb-5 rounded-2xl border border-indigo-200 bg-gradient-to-r from-indigo-50 via-white to-cyan-50 p-5 shadow-sm">
            <div className="flex items-start justify-between gap-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.18em] text-indigo-600">
                  {t('documents.interviewDemo')}
                </p>
                <h3 className="mt-1 text-base font-semibold text-slate-800">
                  {t('documents.demoReady')}
                </h3>
                <p className="mt-1 text-sm text-slate-500">{t('documents.demoHint')}</p>
              </div>
              <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-medium text-emerald-700">
                {t('documents.readyToAsk')}
              </span>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-3">
              {DEMO_QUESTIONS.map((item, index) => (
                <button
                  key={item.kind}
                  onClick={() => openQuestion(t(item.questionKey))}
                  className="group rounded-xl border border-white bg-white/90 p-3 text-left shadow-sm transition-all hover:-translate-y-0.5 hover:border-indigo-200 hover:shadow-md"
                >
                  <span className="text-[11px] font-medium text-indigo-500">
                    {t(`documents.demoQuestion${index + 1}`)}
                  </span>
                  <p className="mt-1 text-sm leading-relaxed text-slate-700 group-hover:text-indigo-700">
                    {t(item.questionKey)}
                  </p>
                </button>
              ))}
            </div>
          </div>
        )}
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="text-center">
              <div className="w-10 h-10 border-3 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-3"></div>
              <p className="text-gray-400 text-sm">{t('common.loading')}</p>
            </div>
          </div>
        ) : error && docs.length === 0 ? (
          <div className="flex items-center justify-center py-20">
            <div className="max-w-sm text-center">
              <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-xl border border-amber-200 bg-amber-50 text-amber-700">
                <Icon name="offline" size={21} />
              </div>
              <p className="font-medium text-zinc-800">{t('documents.libraryUnavailable')}</p>
              <p className="mt-2 text-sm leading-relaxed text-zinc-500">{error}</p>
              <button
                onClick={() => fetchDocs(selectedCollection)}
                className="secondary-action mt-5"
              >
                {t('common.refresh')}
              </button>
            </div>
          </div>
        ) : docs.length === 0 ? (
          <div className="flex items-center justify-center py-16">
            <div className="text-center max-w-sm">
              <div className="mx-auto mb-4 grid h-14 w-14 place-items-center rounded-xl border border-zinc-200 bg-white text-zinc-500">
                <Icon name="library" size={24} />
              </div>
              <p className="text-gray-600 font-medium mb-2">{t('documents.noDocuments')}</p>
              <p className="text-sm text-gray-400 leading-relaxed mb-4">
                {t('documents.noDocumentsHint')}
              </p>
              <div className="flex items-center justify-center gap-2">
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors"
                >
                  {t('documents.uploadFirst')}
                </button>
                <button
                  onClick={() => setShowNoteModal(true)}
                  className="px-4 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm hover:bg-gray-200 transition-colors"
                >
                  {t('documents.orCreateNote')}
                </button>
                <button
                  onClick={handleLoadDemo}
                  disabled={demoLoading}
                  className="px-4 py-2 bg-amber-50 text-amber-700 rounded-lg text-sm hover:bg-amber-100 transition-colors border border-amber-200 disabled:opacity-50"
                >
                  {demoLoading ? t('documents.loadingDemo') : t('documents.loadDemo')}
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {docs.map((doc) => (
              <div
                key={doc.id}
                className="library-document-card overflow-visible rounded-xl border border-zinc-200 bg-white"
              >
                <div className="p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    {doc.status === 'ready' && (
                      <input
                        type="checkbox"
                        checked={compareDocumentIds.includes(doc.id)}
                        onChange={() => toggleCompareDocument(doc.id)}
                        aria-label={t('documents.selectForCompare', { filename: doc.filename })}
                        className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500"
                      />
                    )}
                    <div className="grid h-10 w-10 place-items-center rounded-lg border border-zinc-200 bg-zinc-50 text-zinc-600">
                      <Icon name={doc.file_type === 'note' ? 'note' : 'file'} size={18} />
                    </div>
                    <div>
                      <p className="font-medium text-gray-800">{doc.filename}</p>
                      <p className="text-xs text-gray-400 mt-0.5">
                        {t('documents.docMeta', {
                          size: formatSize(doc.file_size),
                          chunks: doc.chunk_count,
                          date: doc.created_at,
                        })}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                        doc.status === 'ready'
                          ? 'bg-emerald-50 text-emerald-700 border border-emerald-200'
                          : doc.status === 'error'
                            ? 'bg-red-50 text-red-700 border border-red-200'
                            : 'bg-amber-50 text-amber-700 border border-amber-200'
                      }`}
                    >
                      {doc.status === 'ready'
                        ? t('documents.status_ready')
                        : doc.status === 'error'
                          ? t('documents.status_error')
                          : t('documents.status_processing')}
                    </span>
                    {doc.status === 'ready' && (
                      <button onClick={() => askAboutDocument(doc)} className="document-ask-action">
                        <Icon name="chat" size={14} /> {t('documents.askDocument')}
                      </button>
                    )}
                    <details className="context-menu document-menu">
                      <summary aria-label={t('documents.moreActions')}>
                        <Icon name="more" size={18} />
                      </summary>
                      <div className="context-menu-popover">
                        {doc.status === 'ready' && (
                          <button
                            onClick={() => handleGenerateSummary(doc.id)}
                            disabled={generatingSummary === doc.id}
                          >
                            <Icon name="sparkles" size={15} />
                            {generatingSummary === doc.id
                              ? t('common.generating')
                              : summaries[doc.id]
                                ? t('documents.reSummarize')
                                : t('documents.aiSummary')}
                          </button>
                        )}
                        <button onClick={() => handleViewChunks(doc.id)}>
                          <Icon name="layers" size={15} />
                          {selectedDoc === doc.id
                            ? t('documents.collapse')
                            : t('documents.viewChunks')}
                        </button>
                        <button className="danger" onClick={() => handleDelete(doc.id)}>
                          <Icon name="trash" size={15} /> {t('common.delete')}
                        </button>
                      </div>
                    </details>
                  </div>
                </div>

                <details className="document-metadata border-t border-zinc-100 px-4 py-2.5">
                  <summary>
                    {t('documents.organizeDocument')} <Icon name="chevron" size={14} />
                  </summary>
                  {/* Tags */}
                  <div className="mt-3 flex items-center gap-2 flex-wrap">
                    {doc.tags.map((tag) => (
                      <span
                        key={tag}
                        className={`inline-flex items-center gap-1 text-xs px-2.5 py-1 rounded-full border transition-colors ${getTagColor(tag)}`}
                      >
                        {tag}
                        <button
                          onClick={() => handleRemoveTag(doc.id, tag)}
                          className="opacity-60 hover:opacity-100 transition-opacity"
                        >
                          ×
                        </button>
                      </span>
                    ))}
                    <input
                      type="text"
                      placeholder={t('documents.addTag')}
                      value={tagInput[doc.id] || ''}
                      onChange={(e) => setTagInput({ ...tagInput, [doc.id]: e.target.value })}
                      onKeyDown={(e) => e.key === 'Enter' && handleAddTag(doc.id)}
                      className="text-xs px-2.5 py-1 border border-gray-200 rounded-full w-24 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100 transition-all"
                    />
                  </div>

                  {/* Collection assignment */}
                  <div className="mt-3 flex items-center gap-2 pb-1">
                    <span className="text-xs text-gray-400">{t('documents.collection')}</span>
                    <select
                      value={doc.collection_id || ''}
                      onChange={(e) => handleAssignCollection(doc.id, e.target.value || null)}
                      className="text-xs px-2 py-1 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-400 bg-white"
                    >
                      <option value="">{t('documents.ungrouped')}</option>
                      {collections.map((c) => (
                        <option key={c.id} value={c.id}>
                          {c.name}
                        </option>
                      ))}
                    </select>
                    {doc.collection_name && (
                      <span className="text-xs text-gray-400">({doc.collection_name})</span>
                    )}
                  </div>
                </details>

                {/* Summary */}
                {summaries[doc.id] && (
                  <div className="px-4 pb-3">
                    <div className="rounded-lg border border-blue-100 bg-blue-50/50 p-4">
                      <p className="mb-2 flex items-center gap-1.5 text-xs font-semibold text-blue-700">
                        <Icon name="sparkles" size={14} /> {t('documents.aiSummaryTitle')}
                      </p>
                      <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                        {summaries[doc.id].summary}
                      </p>
                    </div>
                  </div>
                )}

                {doc.error_message && (
                  <div className="px-4 pb-3">
                    <p className="text-xs text-red-600 bg-red-50 rounded-lg p-2.5 border border-red-100">
                      {doc.error_message}
                    </p>
                  </div>
                )}

                {/* Chunks preview */}
                {selectedDoc === doc.id && chunks.length > 0 && (
                  <div className="border-t border-gray-100 p-4 bg-gradient-to-b from-gray-50 to-white">
                    <p className="text-xs text-gray-500 mb-3 font-medium">
                      {t('documents.chunksCount', { count: chunks.length })}
                    </p>
                    <div className="space-y-2 max-h-64 overflow-auto">
                      {chunks.map((chunk) => (
                        <div
                          key={chunk.chunk_id}
                          className="bg-white rounded-lg p-3 border border-gray-200 hover:border-gray-300 transition-colors"
                        >
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded font-mono">
                              #{chunk.chunk_index}
                            </span>
                            {chunk.page_num && (
                              <span className="text-xs text-gray-400">
                                {t('chat.page', { page: chunk.page_num })}
                              </span>
                            )}
                            {chunk.heading && (
                              <span className="text-xs text-blue-600 font-medium">
                                {chunk.heading}
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-gray-700 leading-relaxed">
                            {chunk.text_preview}
                          </p>
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Note Modal */}
      {showNoteModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-[500px] p-6 animate-modal-in">
            <h3 className="text-lg font-semibold mb-4">{t('documents.noteTitle')}</h3>
            <input
              type="text"
              placeholder={t('documents.noteTitlePlaceholder')}
              value={noteTitle}
              onChange={(e) => setNoteTitle(e.target.value)}
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg mb-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <textarea
              placeholder={t('documents.noteContentPlaceholder')}
              value={noteContent}
              onChange={(e) => setNoteContent(e.target.value)}
              rows={8}
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500 resize-none"
            />
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => setShowNoteModal(false)}
                className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={handleCreateNote}
                disabled={!noteTitle.trim() || !noteContent.trim()}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors font-medium"
              >
                {t('common.save')}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* New Collection Modal */}
      {showNewCollectionModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-[400px] p-6 animate-modal-in">
            <h3 className="text-lg font-semibold mb-4">{t('documents.newCollectionTitle')}</h3>
            <input
              type="text"
              placeholder={t('documents.collectionNamePlaceholder')}
              value={newCollName}
              onChange={(e) => setNewCollName(e.target.value)}
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg mb-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <input
              type="text"
              placeholder={t('documents.collectionDescPlaceholder')}
              value={newCollDesc}
              onChange={(e) => setNewCollDesc(e.target.value)}
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => setShowNewCollectionModal(false)}
                className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
              >
                {t('common.cancel')}
              </button>
              <button
                onClick={handleCreateCollection}
                disabled={!newCollName.trim()}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors font-medium"
              >
                {t('common.create')}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
