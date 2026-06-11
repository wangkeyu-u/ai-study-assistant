import { useState, useEffect, useCallback, useRef } from 'react';
import {
  Document,
  Collection,
  listDocuments,
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
} from '../api';

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
  const fileInputRef = useRef<HTMLInputElement>(null);
  const backupInputRef = useRef<HTMLInputElement>(null);

  const fetchDocs = useCallback(async (collId?: string | null) => {
    try {
      setLoading(true);
      let url = '/api/documents';
      if (collId) url += `?collection_id=${encodeURIComponent(collId)}`;
      const res = await fetch(url);
      const data = await res.json();
      setDocs(data.documents);
    } catch {
      setError('加载文档列表失败');
    } finally {
      setLoading(false);
    }
  }, []);

  const fetchCollections = useCallback(async () => {
    try {
      const data = await listCollections();
      setCollections(data);
    } catch { /* ignore */ }
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
    } catch (e: any) {
      setError(e.message || '上传失败');
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  const handleDelete = async (docId: string) => {
    if (!confirm('确认删除该文档？所有相关索引数据也会被清除。')) return;
    try {
      await deleteDocument(docId);
      await fetchDocs();
      if (selectedDoc === docId) {
        setSelectedDoc(null);
        setChunks([]);
      }
    } catch {
      setError('删除失败');
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
      await createNote(noteTitle.trim(), noteContent.trim());
      setShowNoteModal(false);
      setNoteTitle('');
      setNoteContent('');
      await fetchDocs();
    } catch (e: any) {
      setError(e.message || '创建笔记失败');
    }
  };

  const handleAddTag = async (docId: string) => {
    const tag = (tagInput[docId] || '').trim();
    if (!tag) return;
    try {
      await addTag(docId, tag);
      setTagInput({ ...tagInput, [docId]: '' });
      await fetchDocs();
    } catch (e: any) {
      setError(e.message || '添加标签失败');
    }
  };

  const handleRemoveTag = async (docId: string, tagName: string) => {
    try {
      await removeTag(docId, tagName);
      await fetchDocs();
    } catch (e: any) {
      setError(e.message || '删除标签失败');
    }
  };

  const handleGenerateSummary = async (docId: string) => {
    setGeneratingSummary(docId);
    try {
      const summary = await generateSummary(docId);
      setSummaries({ ...summaries, [docId]: summary });
    } catch (e: any) {
      setError(e.message || '摘要生成失败');
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
    } catch (e: any) {
      setError(e.message || '创建分组失败');
    }
  };

  const handleDeleteCollection = async (id: string) => {
    if (!confirm('确认删除此分组？文档不会被删除，只是移除分组关联。')) return;
    try {
      await deleteCollection(id);
      if (selectedCollection === id) setSelectedCollection(null);
      await fetchCollections();
      await fetchDocs(null);
    } catch (e: any) {
      setError(e.message || '删除分组失败');
    }
  };

  const handleAssignCollection = async (docId: string, collId: string | null) => {
    try {
      await assignDocToCollection(docId, collId);
      await fetchDocs(selectedCollection);
      await fetchCollections();
    } catch (e: any) {
      setError(e.message || '分配分组失败');
    }
  };

  const handleExportBackup = async () => {
    setBackupLoading(true);
    try {
      await exportBackup();
    } catch (e: any) {
      setError(e.message || '备份导出失败');
    } finally {
      setBackupLoading(false);
    }
  };

  const handleImportBackup = async (file: File) => {
    if (!confirm('导入将覆盖当前所有数据，确认继续？')) return;
    setBackupLoading(true);
    try {
      const result = await importBackup(file);
      alert(`导入成功！恢复了 ${result.documents_restored} 个文档。页面将刷新。`);
      window.location.reload();
    } catch (e: any) {
      setError(e.message || '导入失败');
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
    <div className="h-full flex flex-col">
      {/* Header */}
      <div className="p-6 border-b border-gray-200 bg-white">
        <h2 className="text-xl font-semibold text-gray-800">文档管理</h2>
        <p className="text-sm text-gray-500 mt-1">上传学习资料，系统自动解析并建立索引</p>

        {/* Collection selector + Backup buttons */}
        <div className="flex items-center gap-2 mt-3">
          <select
            value={selectedCollection || ''}
            onChange={(e) => setSelectedCollection(e.target.value || null)}
            className="text-sm px-3 py-1.5 border border-gray-200 rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500 bg-white"
          >
            <option value="">全部文档</option>
            {collections.map((c) => (
              <option key={c.id} value={c.id}>{c.name} ({c.doc_count})</option>
            ))}
          </select>
          <button
            onClick={() => setShowNewCollectionModal(true)}
            className="text-xs px-3 py-1.5 bg-gray-100 text-gray-700 rounded-lg hover:bg-gray-200 transition-colors"
          >
            + 新建分组
          </button>
          <div className="flex-1" />
          <button
            onClick={handleExportBackup}
            disabled={backupLoading}
            className="text-xs px-3 py-1.5 bg-green-50 text-green-700 rounded-lg hover:bg-green-100 transition-colors disabled:opacity-50 border border-green-100"
            title="导出完整数据备份"
          >
            {backupLoading ? '导出中...' : '备份数据'}
          </button>
          <button
            onClick={() => backupInputRef.current?.click()}
            className="text-xs px-3 py-1.5 bg-yellow-50 text-yellow-700 rounded-lg hover:bg-yellow-100 transition-colors border border-yellow-100"
            title="从备份文件恢复"
          >
            导入备份
          </button>
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
        </div>
      </div>

      {/* Upload area */}
      <div className="p-6 bg-white border-b border-gray-200">
        <div
          onDrop={handleDrop}
          onDragOver={handleDragOver}
          onDragLeave={handleDragLeave}
          className={`border-2 border-dashed rounded-xl p-8 text-center transition-all duration-300 ${
            dragOver
              ? 'border-blue-400 bg-blue-50 scale-[1.01] shadow-lg shadow-blue-100'
              : 'border-gray-200 hover:border-blue-300 hover:bg-gray-50/50'
          }`}
        >
          <div className={`transition-transform duration-300 ${dragOver ? 'scale-110' : ''}`}>
            <div className="w-12 h-12 mx-auto mb-3 bg-gradient-to-br from-blue-100 to-indigo-100 rounded-xl flex items-center justify-center">
              <span className="text-2xl">{dragOver ? '📂' : '📁'}</span>
            </div>
          </div>
          <p className="text-gray-600 mb-1 font-medium">
            {dragOver ? '松开鼠标以上传文件' : '拖拽文件到此处，或点击下方按钮上传'}
          </p>
          <p className="text-xs text-gray-400 mb-4">支持 PDF、TXT、Markdown 格式，单文件最大 50MB</p>
          <div className="flex gap-3 justify-center">
            <button
              onClick={() => fileInputRef.current?.click()}
              disabled={uploading}
              className="px-5 py-2.5 bg-gradient-to-r from-blue-600 to-blue-500 text-white rounded-lg text-sm hover:from-blue-700 hover:to-blue-600 disabled:opacity-50 transition-all duration-200 shadow-sm hover:shadow-md font-medium"
            >
              {uploading ? '上传中...' : '选择文件'}
            </button>
            <button
              onClick={() => setShowNoteModal(true)}
              className="px-5 py-2.5 bg-gray-100 text-gray-700 rounded-lg text-sm hover:bg-gray-200 transition-colors border border-gray-200 font-medium"
            >
              + 新建笔记
            </button>
          </div>
          <input
            ref={fileInputRef}
            type="file"
            multiple
            accept=".pdf,.txt,.md"
            onChange={(e) => handleUpload(e.target.files)}
            className="hidden"
          />
        </div>
        {error && (
          <div className="mt-3 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center gap-2">
            <span className="text-red-400">⚠️</span>
            {error}
          </div>
        )}
      </div>

      {/* Document list */}
      <div className="flex-1 overflow-auto p-6">
        {loading ? (
          <div className="flex items-center justify-center py-16">
            <div className="text-center">
              <div className="w-10 h-10 border-3 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-3"></div>
              <p className="text-gray-400 text-sm">加载中...</p>
            </div>
          </div>
        ) : docs.length === 0 ? (
          <div className="flex items-center justify-center py-16">
            <div className="text-center max-w-sm">
              <div className="w-16 h-16 mx-auto mb-4 bg-gradient-to-br from-gray-100 to-gray-50 rounded-2xl flex items-center justify-center">
                <span className="text-3xl">📚</span>
              </div>
              <p className="text-gray-600 font-medium mb-2">还没有上传任何文档</p>
              <p className="text-sm text-gray-400 leading-relaxed mb-4">
                上传 PDF、TXT 或 Markdown 格式的学习资料，系统会自动解析内容并建立知识索引。
              </p>
              <div className="flex items-center justify-center gap-2">
                <button
                  onClick={() => fileInputRef.current?.click()}
                  className="px-4 py-2 bg-blue-600 text-white rounded-lg text-sm hover:bg-blue-700 transition-colors"
                >
                  上传第一个文档
                </button>
                <button
                  onClick={() => setShowNoteModal(true)}
                  className="px-4 py-2 bg-gray-100 text-gray-600 rounded-lg text-sm hover:bg-gray-200 transition-colors"
                >
                  或新建笔记
                </button>
              </div>
            </div>
          </div>
        ) : (
          <div className="space-y-3">
            {docs.map((doc) => (
              <div key={doc.id} className="bg-white rounded-xl border border-gray-200 overflow-hidden transition-all duration-200 hover:shadow-md hover:border-gray-300">
                <div className="p-4 flex items-center justify-between">
                  <div className="flex items-center gap-3">
                    <div className="w-10 h-10 bg-gradient-to-br from-gray-50 to-gray-100 rounded-lg flex items-center justify-center text-xl">
                      {doc.file_type === 'pdf' ? '📄' : doc.file_type === 'note' ? '📝' : '📃'}
                    </div>
                    <div>
                      <p className="font-medium text-gray-800">{doc.filename}</p>
                      <p className="text-xs text-gray-400 mt-0.5">
                        {formatSize(doc.file_size)} · {doc.chunk_count} 个文本块 · {doc.created_at}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className={`text-xs px-2.5 py-1 rounded-full font-medium ${
                      doc.status === 'ready' ? 'bg-emerald-50 text-emerald-700 border border-emerald-200' :
                      doc.status === 'error' ? 'bg-red-50 text-red-700 border border-red-200' :
                      'bg-amber-50 text-amber-700 border border-amber-200'
                    }`}>
                      {doc.status === 'ready' ? '✓ 就绪' : doc.status === 'error' ? '✕ 失败' : '⏳ 处理中'}
                    </span>
                    {doc.status === 'ready' && (
                      <button
                        onClick={() => handleGenerateSummary(doc.id)}
                        disabled={generatingSummary === doc.id}
                        className="text-xs px-3 py-1.5 text-purple-600 hover:bg-purple-50 rounded-lg transition-colors disabled:opacity-50 border border-purple-100 hover:border-purple-200"
                      >
                        {generatingSummary === doc.id ? '生成中...' : summaries[doc.id] ? '重新总结' : 'AI 总结'}
                      </button>
                    )}
                    <button
                      onClick={() => handleViewChunks(doc.id)}
                      className="text-xs px-3 py-1.5 text-gray-600 hover:bg-gray-100 rounded-lg transition-colors border border-gray-200"
                    >
                      {selectedDoc === doc.id ? '收起' : '查看分块'}
                    </button>
                    <button
                      onClick={() => handleDelete(doc.id)}
                      className="text-xs px-3 py-1.5 text-red-600 hover:bg-red-50 rounded-lg transition-colors border border-red-100 hover:border-red-200"
                    >
                      删除
                    </button>
                  </div>
                </div>

                {/* Tags */}
                <div className="px-4 pb-3 flex items-center gap-2 flex-wrap">
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
                    placeholder="+ 添加标签"
                    value={tagInput[doc.id] || ''}
                    onChange={(e) => setTagInput({ ...tagInput, [doc.id]: e.target.value })}
                    onKeyDown={(e) => e.key === 'Enter' && handleAddTag(doc.id)}
                    className="text-xs px-2.5 py-1 border border-gray-200 rounded-full w-24 focus:outline-none focus:border-blue-400 focus:ring-1 focus:ring-blue-100 transition-all"
                  />
                </div>

                {/* Collection assignment */}
                <div className="px-4 pb-3 flex items-center gap-2">
                  <span className="text-xs text-gray-400">所属分组：</span>
                  <select
                    value={doc.collection_id || ''}
                    onChange={(e) => handleAssignCollection(doc.id, e.target.value || null)}
                    className="text-xs px-2 py-1 border border-gray-200 rounded-lg focus:outline-none focus:border-blue-400 bg-white"
                  >
                    <option value="">未分组</option>
                    {collections.map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                  {doc.collection_name && (
                    <span className="text-xs text-gray-400">({doc.collection_name})</span>
                  )}
                </div>

                {/* Summary */}
                {summaries[doc.id] && (
                  <div className="px-4 pb-3">
                    <div className="bg-gradient-to-br from-purple-50 to-indigo-50 rounded-lg p-4 border border-purple-100">
                      <p className="text-xs font-semibold text-purple-700 mb-2 flex items-center gap-1">
                        <span>📋</span> AI 摘要
                      </p>
                      <p className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed">
                        {summaries[doc.id].summary}
                      </p>
                    </div>
                  </div>
                )}

                {doc.error_message && (
                  <div className="px-4 pb-3">
                    <p className="text-xs text-red-600 bg-red-50 rounded-lg p-2.5 border border-red-100">{doc.error_message}</p>
                  </div>
                )}

                {/* Chunks preview */}
                {selectedDoc === doc.id && chunks.length > 0 && (
                  <div className="border-t border-gray-100 p-4 bg-gradient-to-b from-gray-50 to-white">
                    <p className="text-xs text-gray-500 mb-3 font-medium">共 {chunks.length} 个文本块：</p>
                    <div className="space-y-2 max-h-64 overflow-auto">
                      {chunks.map((chunk) => (
                        <div key={chunk.chunk_id} className="bg-white rounded-lg p-3 border border-gray-200 hover:border-gray-300 transition-colors">
                          <div className="flex items-center gap-2 mb-1">
                            <span className="text-xs bg-gray-100 text-gray-600 px-1.5 py-0.5 rounded font-mono">
                              #{chunk.chunk_index}
                            </span>
                            {chunk.page_num && (
                              <span className="text-xs text-gray-400">第{chunk.page_num}页</span>
                            )}
                            {chunk.heading && (
                              <span className="text-xs text-blue-600 font-medium">{chunk.heading}</span>
                            )}
                          </div>
                          <p className="text-sm text-gray-700 leading-relaxed">{chunk.text_preview}</p>
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
            <h3 className="text-lg font-semibold mb-4">新建笔记</h3>
            <input
              type="text"
              placeholder="笔记标题"
              value={noteTitle}
              onChange={(e) => setNoteTitle(e.target.value)}
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg mb-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <textarea
              placeholder="输入笔记内容..."
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
                取消
              </button>
              <button
                onClick={handleCreateNote}
                disabled={!noteTitle.trim() || !noteContent.trim()}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors font-medium"
              >
                保存
              </button>
            </div>
          </div>
        </div>
      )}

      {/* New Collection Modal */}
      {showNewCollectionModal && (
        <div className="fixed inset-0 bg-black/40 flex items-center justify-center z-50 backdrop-blur-sm">
          <div className="bg-white rounded-2xl shadow-2xl w-[400px] p-6 animate-modal-in">
            <h3 className="text-lg font-semibold mb-4">新建知识库分组</h3>
            <input
              type="text"
              placeholder="分组名称（如：机器学习、前端开发）"
              value={newCollName}
              onChange={(e) => setNewCollName(e.target.value)}
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg mb-3 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <input
              type="text"
              placeholder="描述（可选）"
              value={newCollDesc}
              onChange={(e) => setNewCollDesc(e.target.value)}
              className="w-full px-3 py-2.5 border border-gray-200 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
            />
            <div className="flex justify-end gap-2 mt-4">
              <button
                onClick={() => setShowNewCollectionModal(false)}
                className="px-4 py-2 text-sm text-gray-600 hover:bg-gray-100 rounded-lg transition-colors"
              >
                取消
              </button>
              <button
                onClick={handleCreateCollection}
                disabled={!newCollName.trim()}
                className="px-4 py-2 text-sm bg-blue-600 text-white rounded-lg hover:bg-blue-700 disabled:opacity-50 transition-colors font-medium"
              >
                创建
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
