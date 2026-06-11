import { useState, useEffect, useCallback } from 'react';
import {
  Quiz, QuizResult, WrongAnswer,
  listDocuments, generateQuiz, submitQuiz,
  listWrongAnswers, reviewWrongAnswer, exportAnki,
  Document,
} from '../api';

type Tab = 'generate' | 'wrong' | 'anki';

export default function QuizPage() {
  const [tab, setTab] = useState<Tab>('generate');
  const [docs, setDocs] = useState<Document[]>([]);
  const [selectedDocs, setSelectedDocs] = useState<string[]>([]);
  const [questionCount, setQuestionCount] = useState(5);
  const [quiz, setQuiz] = useState<Quiz | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<QuizResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [wrongAnswers, setWrongAnswers] = useState<WrongAnswer[]>([]);

  const fetchDocs = useCallback(async () => {
    try {
      const data = await listDocuments();
      setDocs(data.filter(d => d.status === 'ready'));
    } catch { /* ignore */ }
  }, []);

  useEffect(() => { fetchDocs(); }, [fetchDocs]);

  const handleGenerate = async () => {
    setLoading(true);
    setError(null);
    setQuiz(null);
    setResult(null);
    setAnswers({});
    try {
      const q = await generateQuiz({
        doc_ids: selectedDocs.length > 0 ? selectedDocs : undefined,
        count: questionCount,
      });
      setQuiz(q);
    } catch (e: any) {
      setError(e.message || '生成测验失败');
    } finally {
      setLoading(false);
    }
  };

  const handleSubmit = async () => {
    if (!quiz) return;
    setLoading(true);
    try {
      const answerList = Object.entries(answers).map(([question_id, user_answer]) => ({
        question_id,
        user_answer,
      }));
      const r = await submitQuiz(quiz.id, answerList);
      setResult(r);
    } catch (e: any) {
      setError(e.message || '提交失败');
    } finally {
      setLoading(false);
    }
  };

  const handleLoadWrong = async () => {
    try {
      const data = await listWrongAnswers();
      setWrongAnswers(data);
    } catch { /* ignore */ }
  };

  useEffect(() => {
    if (tab === 'wrong') handleLoadWrong();
  }, [tab]);

  const handleReview = async (id: string, correct: boolean) => {
    try {
      const res = await reviewWrongAnswer(id, correct);
      if (res.removed) {
        setWrongAnswers(prev => prev.filter(w => w.id !== id));
      } else {
        setWrongAnswers(prev => prev.map(w => w.id === id ? { ...w, mastery_level: res.mastery_level } : w));
      }
    } catch { /* ignore */ }
  };

  const handleExportAnki = async () => {
    try {
      await exportAnki();
    } catch (e: any) {
      setError(e.message || '导出失败');
    }
  };

  const toggleDoc = (id: string) => {
    setSelectedDocs(prev => prev.includes(id) ? prev.filter(d => d !== id) : [...prev, id]);
  };

  const answeredCount = Object.keys(answers).length;
  const progressPercent = quiz ? Math.round((answeredCount / quiz.total_count) * 100) : 0;

  return (
    <div className="h-full flex flex-col">
      <div className="p-6 border-b border-gray-200 bg-white">
        <h2 className="text-xl font-semibold text-gray-800">学习测验</h2>
        <p className="text-sm text-gray-500 mt-1">自动生成测验题，追踪错题，导出到 Anki</p>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-gray-200 bg-white px-6">
        {([['generate', '出题', '✍️'], ['wrong', '错题本', '📕'], ['anki', 'Anki 导出', '📦']] as [Tab, string, string][]).map(([t, label, icon]) => (
          <button
            key={t}
            onClick={() => setTab(t)}
            className={`px-4 py-3 text-sm border-b-2 transition-all duration-200 flex items-center gap-1.5 ${
              tab === t ? 'border-blue-600 text-blue-700 font-medium' : 'border-transparent text-gray-500 hover:text-gray-700'
            }`}
          >
            <span>{icon}</span>
            {label}
            {t === 'wrong' && wrongAnswers.length > 0 && (
              <span className="ml-1 bg-red-100 text-red-600 text-xs px-1.5 py-0.5 rounded-full font-medium">{wrongAnswers.length}</span>
            )}
          </button>
        ))}
      </div>

      <div className="flex-1 overflow-auto p-6">
        {error && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-700 flex items-center gap-2">
            <span>⚠️</span>
            {error}
          </div>
        )}

        {/* Generate Tab */}
        {tab === 'generate' && (
          <div className="space-y-6">
            {/* Config */}
            <div className="bg-white rounded-xl border border-gray-200 p-5">
              <h3 className="font-medium text-gray-800 mb-3">选择出题范围</h3>
              <div className="flex flex-wrap gap-2 mb-4">
                {docs.map(d => (
                  <button
                    key={d.id}
                    onClick={() => toggleDoc(d.id)}
                    className={`text-xs px-3 py-2 rounded-lg border transition-all duration-200 ${
                      selectedDocs.includes(d.id)
                        ? 'bg-blue-50 border-blue-300 text-blue-700 shadow-sm'
                        : 'bg-white border-gray-200 text-gray-600 hover:bg-gray-50 hover:border-gray-300'
                    }`}
                  >
                    {selectedDocs.includes(d.id) && <span className="mr-1">✓</span>}
                    {d.filename}
                  </button>
                ))}
                {docs.length === 0 && <p className="text-xs text-gray-400">暂无就绪文档，请先上传并等待处理完成</p>}
              </div>
              <div className="flex items-center gap-3">
                <label className="text-sm text-gray-600">题目数量：</label>
                <select
                  value={questionCount}
                  onChange={(e) => setQuestionCount(Number(e.target.value))}
                  className="text-sm px-3 py-1.5 border border-gray-200 rounded-lg bg-white focus:outline-none focus:ring-2 focus:ring-blue-500"
                >
                  {[3, 5, 7, 10].map(n => <option key={n} value={n}>{n} 题</option>)}
                </select>
                <button
                  onClick={handleGenerate}
                  disabled={loading || docs.length === 0}
                  className="ml-auto px-5 py-2.5 bg-gradient-to-r from-blue-600 to-blue-500 text-white rounded-lg text-sm hover:from-blue-700 hover:to-blue-600 disabled:opacity-50 transition-all duration-200 shadow-sm hover:shadow-md font-medium"
                >
                  {loading ? '生成中...' : '生成测验'}
                </button>
              </div>
            </div>

            {/* Quiz Questions */}
            {quiz && !result && (
              <div className="space-y-4">
                {/* Progress Bar */}
                <div className="bg-white rounded-xl border border-gray-200 p-4">
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-medium text-gray-800">{quiz.topic} — 共 {quiz.total_count} 题</h3>
                    <span className="text-sm text-gray-500 font-medium">{answeredCount}/{quiz.total_count} 已作答</span>
                  </div>
                  <div className="w-full h-2.5 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-gradient-to-r from-blue-500 to-indigo-500 rounded-full transition-all duration-500 ease-out"
                      style={{ width: `${progressPercent}%` }}
                    />
                  </div>
                </div>

                {quiz.questions.map((q, i) => (
                  <div key={q.id} className="bg-white rounded-xl border border-gray-200 p-5 transition-all duration-200 hover:shadow-sm">
                    <div className="flex items-start gap-2 mb-3">
                      <span className="text-xs bg-gradient-to-br from-gray-100 to-gray-50 text-gray-600 px-2.5 py-1 rounded-lg font-bold border border-gray-200">
                        {i + 1}
                      </span>
                      <span className={`text-xs px-2.5 py-1 rounded-lg font-medium ${
                        q.question_type === 'choice'
                          ? 'bg-blue-50 text-blue-600 border border-blue-100'
                          : 'bg-emerald-50 text-emerald-600 border border-emerald-100'
                      }`}>
                        {q.question_type === 'choice' ? '选择题' : '判断题'}
                      </span>
                      {answers[q.id] && (
                        <span className="text-xs px-2 py-1 rounded-lg bg-green-50 text-green-600 border border-green-100 ml-auto">
                          ✓ 已作答
                        </span>
                      )}
                    </div>
                    <p className="text-sm text-gray-800 mb-4 leading-relaxed">{q.question_text}</p>
                    {q.question_type === 'choice' && q.options ? (
                      <div className="grid gap-2">
                        {q.options.map((opt, j) => {
                          const letter = String.fromCharCode(65 + j);
                          const isSelected = answers[q.id] === letter;
                          return (
                            <button
                              key={j}
                              onClick={() => setAnswers({ ...answers, [q.id]: letter })}
                              className={`flex items-center gap-3 p-3 rounded-lg border text-left text-sm transition-all duration-200 ${
                                isSelected
                                  ? 'bg-blue-50 border-blue-300 text-blue-700 shadow-sm'
                                  : 'bg-white border-gray-200 text-gray-700 hover:bg-gray-50 hover:border-gray-300'
                              }`}
                            >
                              <span className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-bold transition-colors ${
                                isSelected
                                  ? 'bg-blue-600 text-white'
                                  : 'bg-gray-100 text-gray-500'
                              }`}>
                                {letter}
                              </span>
                              <span className="flex-1">{opt}</span>
                              {isSelected && (
                                <span className="text-blue-500">✓</span>
                              )}
                            </button>
                          );
                        })}
                      </div>
                    ) : (
                      <div className="flex gap-3">
                        <button
                          onClick={() => setAnswers({ ...answers, [q.id]: 'true' })}
                          className={`flex-1 px-4 py-3 rounded-lg text-sm border transition-all duration-200 font-medium ${
                            answers[q.id] === 'true'
                              ? 'bg-blue-50 border-blue-300 text-blue-700 shadow-sm'
                              : 'border-gray-200 text-gray-600 hover:bg-gray-50 hover:border-gray-300'
                          }`}
                        >
                          ✓ 正确
                        </button>
                        <button
                          onClick={() => setAnswers({ ...answers, [q.id]: 'false' })}
                          className={`flex-1 px-4 py-3 rounded-lg text-sm border transition-all duration-200 font-medium ${
                            answers[q.id] === 'false'
                              ? 'bg-blue-50 border-blue-300 text-blue-700 shadow-sm'
                              : 'border-gray-200 text-gray-600 hover:bg-gray-50 hover:border-gray-300'
                          }`}
                        >
                          ✕ 错误
                        </button>
                      </div>
                    )}
                  </div>
                ))}
                <button
                  onClick={handleSubmit}
                  disabled={loading || answeredCount < quiz.total_count}
                  className="w-full py-3.5 bg-gradient-to-r from-green-600 to-emerald-500 text-white rounded-xl text-sm hover:from-green-700 hover:to-emerald-600 disabled:opacity-50 font-semibold transition-all duration-200 shadow-sm hover:shadow-md"
                >
                  {loading ? '提交中...' : `提交答案 (${answeredCount}/${quiz.total_count})`}
                </button>
              </div>
            )}

            {/* Results */}
            {result && (
              <div className="space-y-4">
                {/* Score Card */}
                <div className="bg-gradient-to-br from-blue-50 to-indigo-50 rounded-xl border border-blue-100 p-8 text-center">
                  <div className="w-20 h-20 mx-auto mb-4 bg-white rounded-full flex items-center justify-center shadow-sm border border-blue-100">
                    <span className="text-3xl font-bold text-blue-600">
                      {Math.round(result.correct_count / result.total_count * 100)}%
                    </span>
                  </div>
                  <p className="text-2xl font-bold text-gray-800">{result.correct_count}/{result.total_count}</p>
                  <p className="text-sm text-gray-500 mt-1">
                    {result.correct_count === result.total_count ? '满分！太棒了！' :
                     result.correct_count >= result.total_count * 0.8 ? '表现优秀！继续保持！' :
                     result.correct_count >= result.total_count * 0.6 ? '还不错，还有提升空间' :
                     '需要多复习一下哦'}
                  </p>
                  {/* Visual progress ring */}
                  <div className="mt-4 w-full h-3 bg-white/50 rounded-full overflow-hidden max-w-xs mx-auto">
                    <div
                      className={`h-full rounded-full transition-all duration-1000 ease-out ${
                        result.correct_count / result.total_count >= 0.8 ? 'bg-gradient-to-r from-green-400 to-emerald-500' :
                        result.correct_count / result.total_count >= 0.6 ? 'bg-gradient-to-r from-yellow-400 to-amber-500' :
                        'bg-gradient-to-r from-red-400 to-rose-500'
                      }`}
                      style={{ width: `${Math.round(result.correct_count / result.total_count * 100)}%` }}
                    />
                  </div>
                </div>

                {result.results.map((r, i) => (
                  <div key={r.question_id} className={`rounded-xl border p-5 transition-all duration-200 ${
                    r.is_correct
                      ? 'bg-gradient-to-br from-green-50 to-emerald-50 border-green-200'
                      : 'bg-gradient-to-br from-red-50 to-rose-50 border-red-200'
                  }`}>
                    <div className="flex items-center gap-2 mb-3">
                      <span className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-bold ${
                        r.is_correct ? 'bg-green-500 text-white' : 'bg-red-500 text-white'
                      }`}>
                        {r.is_correct ? '✓' : '✕'}
                      </span>
                      <span className="text-xs text-gray-500 font-medium">第 {i + 1} 题</span>
                    </div>
                    <p className="text-sm text-gray-800 mb-3 font-medium">{r.question_text}</p>
                    <div className="flex gap-4 text-xs mb-2">
                      <div className={`px-3 py-1.5 rounded-lg ${
                        r.is_correct ? 'bg-green-100 text-green-700' : 'bg-red-100 text-red-700'
                      }`}>
                        你的答案：{r.user_answer}
                      </div>
                      <div className="px-3 py-1.5 rounded-lg bg-green-100 text-green-700">
                        正确答案：{r.correct_answer}
                      </div>
                    </div>
                    {r.explanation && (
                      <div className="text-xs text-gray-600 mt-3 bg-white/60 rounded-lg p-3 border border-white/80 leading-relaxed">
                        <span className="font-medium text-gray-700">解析：</span>{r.explanation}
                      </div>
                    )}
                  </div>
                ))}
                <button
                  onClick={() => { setQuiz(null); setResult(null); setAnswers({}); }}
                  className="w-full py-3.5 bg-gray-100 text-gray-700 rounded-xl text-sm hover:bg-gray-200 transition-colors font-medium border border-gray-200"
                >
                  再来一轮
                </button>
              </div>
            )}
          </div>
        )}

        {/* Wrong Answers Tab */}
        {tab === 'wrong' && (
          <div className="space-y-3">
            {wrongAnswers.length === 0 ? (
              <div className="flex items-center justify-center py-16">
                <div className="text-center max-w-sm">
                  <div className="w-16 h-16 mx-auto mb-4 bg-gradient-to-br from-green-100 to-emerald-100 rounded-2xl flex items-center justify-center">
                    <span className="text-3xl">🎉</span>
                  </div>
                  <p className="text-gray-600 font-medium mb-2">没有错题，继续保持！</p>
                  <p className="text-sm text-gray-400">完成更多测验来检验学习成果</p>
                </div>
              </div>
            ) : wrongAnswers.map(w => (
              <div key={w.id} className="bg-white rounded-xl border border-gray-200 p-5 transition-all duration-200 hover:shadow-sm">
                <div className="flex items-center gap-2 mb-3">
                  <span className={`text-xs px-2.5 py-1 rounded-full font-medium border ${
                    w.mastery_level >= 3 ? 'bg-green-50 text-green-600 border-green-200' : w.mastery_level >= 1 ? 'bg-yellow-50 text-yellow-600 border-yellow-200' : 'bg-red-50 text-red-600 border-red-200'
                  }`}>
                    掌握度 {w.mastery_level}/5
                  </span>
                  <span className="text-xs text-gray-400">复习 {w.review_count} 次</span>
                  {/* Mastery progress bar */}
                  <div className="flex-1 max-w-[120px] ml-auto">
                    <div className="w-full h-1.5 bg-gray-100 rounded-full overflow-hidden">
                      <div
                        className={`h-full rounded-full transition-all duration-500 ${
                          w.mastery_level >= 3 ? 'bg-green-400' : w.mastery_level >= 1 ? 'bg-yellow-400' : 'bg-red-400'
                        }`}
                        style={{ width: `${(w.mastery_level / 5) * 100}%` }}
                      />
                    </div>
                  </div>
                </div>
                <p className="text-sm text-gray-800 mb-2 font-medium">{w.question_text}</p>
                <div className="flex gap-3 text-xs mb-3">
                  <span className="px-2.5 py-1 rounded-lg bg-red-50 text-red-600 border border-red-100">你的答案：{w.user_answer}</span>
                  <span className="px-2.5 py-1 rounded-lg bg-green-50 text-green-700 border border-green-100">正确答案：{w.correct_answer}</span>
                </div>
                {w.explanation && <p className="text-xs text-gray-500 mb-3 bg-gray-50 rounded-lg p-2.5 leading-relaxed">{w.explanation}</p>}
                <div className="flex gap-2">
                  <button
                    onClick={() => handleReview(w.id, true)}
                    className="text-xs px-4 py-2 bg-gradient-to-r from-green-50 to-emerald-50 text-green-700 rounded-lg hover:from-green-100 hover:to-emerald-100 transition-all duration-200 border border-green-200 font-medium"
                  >
                    ✓ 已掌握
                  </button>
                  <button
                    onClick={() => handleReview(w.id, false)}
                    className="text-xs px-4 py-2 bg-gradient-to-r from-red-50 to-rose-50 text-red-700 rounded-lg hover:from-red-100 hover:to-rose-100 transition-all duration-200 border border-red-200 font-medium"
                  >
                    ✕ 还不熟
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}

        {/* Anki Export Tab */}
        {tab === 'anki' && (
          <div className="bg-white rounded-xl border border-gray-200 p-12 text-center">
            <div className="w-16 h-16 mx-auto mb-4 bg-gradient-to-br from-blue-100 to-indigo-100 rounded-2xl flex items-center justify-center">
              <span className="text-3xl">📦</span>
            </div>
            <h3 className="text-lg font-semibold text-gray-800 mb-2">导出到 Anki</h3>
            <p className="text-sm text-gray-500 mb-6 max-w-sm mx-auto leading-relaxed">将所有测验题导出为 Anki 兼容的 TSV 格式，导入 Anki 进行间隔重复复习</p>
            <button
              onClick={handleExportAnki}
              className="px-6 py-3 bg-gradient-to-r from-blue-600 to-blue-500 text-white rounded-lg text-sm hover:from-blue-700 hover:to-blue-600 transition-all duration-200 shadow-sm hover:shadow-md font-medium"
            >
              导出 Anki 文件
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
