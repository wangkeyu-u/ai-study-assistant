import { useState, useEffect, useCallback } from 'react';
import { DashboardData, getDashboard } from '../api';

export default function DashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchDashboard = useCallback(async () => {
    try {
      setLoading(true);
      const d = await getDashboard();
      setData(d);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { fetchDashboard(); }, [fetchDashboard]);

  if (loading) return (
    <div className="h-full flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <div className="w-10 h-10 border-3 border-blue-200 border-t-blue-600 rounded-full animate-spin mx-auto mb-3"></div>
        <p className="text-gray-400 text-sm">加载中...</p>
      </div>
    </div>
  );

  if (!data) return (
    <div className="h-full flex items-center justify-center bg-gray-50">
      <div className="text-center">
        <div className="w-16 h-16 mx-auto mb-4 bg-gradient-to-br from-gray-100 to-gray-50 rounded-2xl flex items-center justify-center">
          <span className="text-3xl">📊</span>
        </div>
        <p className="text-gray-500 font-medium">加载失败</p>
        <p className="text-sm text-gray-400 mt-1">请刷新页面重试</p>
      </div>
    </div>
  );

  const accuracy = data.total_quizzes > 0 && data.total_correct_answers > 0
    ? Math.round((data.total_correct_answers / Math.max(data.total_questions_asked, 1)) * 100)
    : 0;

  const maxActivity = Math.max(...data.recent_activity.map(a => a.questions_count), 1);

  return (
    <div className="h-full flex flex-col">
      <div className="p-6 border-b border-gray-200 bg-white">
        <h2 className="text-xl font-semibold text-gray-800">学习看板</h2>
        <p className="text-sm text-gray-500 mt-1">学习进度和知识掌握度概览</p>
      </div>

      <div className="flex-1 overflow-auto p-6 space-y-6">
        {/* Stat Cards */}
        <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: '文档总数', value: data.total_documents, icon: '📄', gradient: 'from-blue-500 to-blue-600', bgLight: 'bg-blue-50' },
            { label: '文本块', value: data.total_chunks, icon: '🧩', gradient: 'from-purple-500 to-purple-600', bgLight: 'bg-purple-50' },
            { label: '提问次数', value: data.total_questions_asked, icon: '💡', gradient: 'from-emerald-500 to-emerald-600', bgLight: 'bg-emerald-50' },
            { label: '测验次数', value: data.total_quizzes, icon: '✍️', gradient: 'from-orange-500 to-orange-600', bgLight: 'bg-orange-50' },
          ].map(({ label, value, icon, gradient, bgLight }) => (
            <div key={label} className={`rounded-xl overflow-hidden shadow-sm border border-gray-100 transition-all duration-200 hover:shadow-md`}>
              <div className={`bg-gradient-to-br ${gradient} p-4`}>
                <div className="flex items-center justify-between">
                  <div>
                    <p className="text-xs text-white/80 font-medium">{label}</p>
                    <p className="text-3xl font-bold text-white mt-1">{value}</p>
                  </div>
                  <div className="w-10 h-10 bg-white/20 rounded-xl flex items-center justify-center backdrop-blur-sm">
                    <span className="text-xl">{icon}</span>
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Quiz Stats */}
        {data.total_quizzes > 0 && (
          <div className="grid grid-cols-3 gap-4">
            <div className="bg-white rounded-xl border border-gray-200 p-5 text-center transition-all duration-200 hover:shadow-sm">
              <div className="w-10 h-10 mx-auto mb-2 bg-green-50 rounded-xl flex items-center justify-center">
                <span className="text-lg">✅</span>
              </div>
              <p className="text-xs text-gray-500 font-medium">答对题数</p>
              <p className="text-2xl font-bold text-green-600 mt-1">{data.total_correct_answers}</p>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-5 text-center transition-all duration-200 hover:shadow-sm">
              <div className="w-10 h-10 mx-auto mb-2 bg-red-50 rounded-xl flex items-center justify-center">
                <span className="text-lg">❌</span>
              </div>
              <p className="text-xs text-gray-500 font-medium">错题数</p>
              <p className="text-2xl font-bold text-red-600 mt-1">{data.wrong_answer_count}</p>
            </div>
            <div className="bg-white rounded-xl border border-gray-200 p-5 text-center transition-all duration-200 hover:shadow-sm">
              <div className="w-10 h-10 mx-auto mb-2 bg-blue-50 rounded-xl flex items-center justify-center">
                <span className="text-lg">🎯</span>
              </div>
              <p className="text-xs text-gray-500 font-medium">正确率</p>
              <p className="text-2xl font-bold text-blue-600 mt-1">{accuracy}%</p>
              <div className="mt-2 w-full h-2 bg-gray-100 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-1000 ${
                    accuracy >= 80 ? 'bg-gradient-to-r from-green-400 to-emerald-500' :
                    accuracy >= 60 ? 'bg-gradient-to-r from-yellow-400 to-amber-500' :
                    'bg-gradient-to-r from-red-400 to-rose-500'
                  }`}
                  style={{ width: `${accuracy}%` }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Tag Stats */}
        {data.tag_stats.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
              <span className="w-1 h-5 bg-blue-500 rounded-full"></span>
              标签统计
            </h3>
            <div className="space-y-3">
              {data.tag_stats.map((t, i) => {
                const maxDoc = Math.max(...data.tag_stats.map(s => s.doc_count), 1);
                const maxQ = Math.max(...data.tag_stats.map(s => s.question_count), 1);
                const colors = [
                  'from-blue-400 to-blue-500',
                  'from-purple-400 to-purple-500',
                  'from-emerald-400 to-emerald-500',
                  'from-amber-400 to-amber-500',
                  'from-rose-400 to-rose-500',
                  'from-cyan-400 to-cyan-500',
                ];
                const barColor = colors[i % colors.length];
                return (
                  <div key={t.tag} className="group">
                    <div className="flex items-center justify-between mb-1">
                      <span className="text-sm text-gray-700 font-medium">{t.tag}</span>
                      <div className="flex gap-3 text-xs text-gray-500">
                        <span className="px-2 py-0.5 bg-gray-50 rounded-full">{t.doc_count} 文档</span>
                        <span className="px-2 py-0.5 bg-gray-50 rounded-full">{t.question_count} 提问</span>
                      </div>
                    </div>
                    <div className="flex gap-1.5">
                      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full bg-gradient-to-r ${barColor} rounded-full transition-all duration-700`}
                          style={{ width: `${(t.doc_count / maxDoc) * 100}%` }}
                        />
                      </div>
                      <div className="flex-1 h-1.5 bg-gray-100 rounded-full overflow-hidden">
                        <div
                          className={`h-full bg-gradient-to-r ${barColor} rounded-full transition-all duration-700 opacity-60`}
                          style={{ width: `${(t.question_count / maxQ) * 100}%` }}
                        />
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </div>
        )}

        {/* Weak Points */}
        {data.weak_points.length > 0 && (
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
              <span className="w-1 h-5 bg-red-500 rounded-full"></span>
              薄弱知识点
            </h3>
            <div className="space-y-4">
              {data.weak_points.map(w => (
                <div key={w.concept} className="group">
                  <div className="flex items-center justify-between mb-1.5">
                    <span className="text-sm text-gray-700 font-medium">{w.concept}</span>
                    <span className={`text-xs font-semibold px-2 py-0.5 rounded-full ${
                      w.mastery_score < 0.3 ? 'bg-red-50 text-red-600' :
                      w.mastery_score < 0.7 ? 'bg-amber-50 text-amber-600' :
                      'bg-green-50 text-green-600'
                    }`}>
                      {Math.round(w.mastery_score * 100)}%
                    </span>
                  </div>
                  <div className="w-full bg-gray-100 rounded-full h-3 overflow-hidden">
                    <div
                      className={`h-3 rounded-full transition-all duration-700 ease-out ${
                        w.mastery_score < 0.3 ? 'bg-gradient-to-r from-red-400 to-red-500' :
                        w.mastery_score < 0.7 ? 'bg-gradient-to-r from-amber-400 to-yellow-500' :
                        'bg-gradient-to-r from-green-400 to-emerald-500'
                      }`}
                      style={{ width: `${w.mastery_score * 100}%` }}
                    />
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Recent Activity */}
        {data.recent_activity.some(a => a.questions_count > 0) && (
          <div className="bg-white rounded-xl border border-gray-200 p-5">
            <h3 className="font-semibold text-gray-800 mb-4 flex items-center gap-2">
              <span className="w-1 h-5 bg-emerald-500 rounded-full"></span>
              近 7 天活动
            </h3>
            <div className="flex items-end gap-3 h-40 px-2">
              {data.recent_activity.map(a => {
                const heightPercent = maxActivity > 0 ? (a.questions_count / maxActivity) * 100 : 0;
                return (
                  <div key={a.date} className="flex-1 flex flex-col items-center gap-2">
                    <span className="text-xs text-gray-500 font-medium">{a.questions_count}</span>
                    <div className="w-full flex items-end justify-center" style={{ height: '100px' }}>
                      <div
                        className="w-full max-w-[36px] bg-gradient-to-t from-blue-500 to-blue-400 rounded-t-lg transition-all duration-500 hover:from-blue-600 hover:to-blue-500"
                        style={{ height: `${Math.max(heightPercent, 3)}%` }}
                      />
                    </div>
                    <span className="text-xs text-gray-400 font-medium">{a.date}</span>
                  </div>
                );
              })}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
