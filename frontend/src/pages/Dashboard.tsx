import { useCallback, useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { DashboardData, RagReadiness, getDashboard, getRagReadiness } from '../api';
import Icon, { IconName } from '../components/Icon';

export default function DashboardPage() {
  const { t } = useTranslation();
  const [data, setData] = useState<DashboardData | null>(null);
  const [ragReadiness, setRagReadiness] = useState<RagReadiness | null>(null);
  const [loading, setLoading] = useState(true);

  const fetchDashboard = useCallback(async () => {
    try {
      setLoading(true);
      const [nextDashboard, nextReadiness] = await Promise.all([
        getDashboard(),
        getRagReadiness().catch(() => null),
      ]);
      setData(nextDashboard);
      setRagReadiness(nextReadiness);
    } catch {
      setData(null);
      setRagReadiness(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchDashboard();
  }, [fetchDashboard]);

  if (loading) {
    return (
      <div className="product-state" aria-live="polite">
        <div className="product-state-skeleton" />
        <div className="product-state-skeleton is-short" />
        <span>{t('common.loading')}</span>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="product-state">
        <span className="product-state-icon is-warning">
          <Icon name="offline" size={22} />
        </span>
        <h1>{t('dashboard.loadFailed')}</h1>
        <p>{t('dashboard.loadFailedHint')}</p>
        <button className="secondary-action" onClick={fetchDashboard}>
          {t('common.refresh')}
        </button>
      </div>
    );
  }

  const accuracy =
    data.total_quizzes > 0
      ? Math.round((data.total_correct_answers / Math.max(data.total_questions_asked, 1)) * 100)
      : 0;
  const maxActivity = Math.max(...data.recent_activity.map((item) => item.questions_count), 1);
  const metrics: { label: string; value: number; icon: IconName }[] = [
    { label: t('dashboard.totalDocs'), value: data.total_documents, icon: 'file' },
    { label: t('dashboard.totalChunks'), value: data.total_chunks, icon: 'layers' },
    { label: t('dashboard.totalQuestions'), value: data.total_questions_asked, icon: 'chat' },
    { label: t('dashboard.totalQuizzes'), value: data.total_quizzes, icon: 'quiz' },
  ];
  const moduleIcons: Record<string, IconName> = {
    ingestion: 'upload',
    retrieval: 'search',
    planning: 'graph',
    context: 'layers',
    generation: 'sparkles',
    observability: 'chart',
  };

  return (
    <div className="product-page h-full overflow-auto">
      <header className="product-page-header">
        <h1>{t('dashboard.title')}</h1>
        <p>{t('dashboard.subtitle')}</p>
      </header>

      <div className="product-page-content dashboard-layout">
        <section className="dashboard-metrics" aria-label={t('dashboard.title')}>
          {metrics.map((metric) => (
            <div className="dashboard-metric" key={metric.label}>
              <span>
                <Icon name={metric.icon} size={18} />
              </span>
              <p>{metric.label}</p>
              <strong>{metric.value}</strong>
            </div>
          ))}
        </section>

        {ragReadiness && (
          <section className="rag-readiness-panel product-section">
            <div className="rag-readiness-hero">
              <div>
                <span className="rag-readiness-kicker">{t('dashboard.ragReadinessKicker')}</span>
                <h2>{t('dashboard.ragReadinessTitle')}</h2>
                <p>{t('dashboard.ragReadinessHint')}</p>
              </div>
              <div className="rag-score-card">
                <span>{t('dashboard.ragReadinessScore')}</span>
                <strong>{Math.round(ragReadiness.readiness_score * 100)}%</strong>
                <small>
                  {ragReadiness.runtime.llm_provider} / {ragReadiness.runtime.llm_model}
                </small>
              </div>
            </div>

            <div className="rag-runtime-grid">
              <div>
                <span>{t('dashboard.ragVectors')}</span>
                <strong>{ragReadiness.data.vectors}</strong>
              </div>
              <div>
                <span>{t('dashboard.ragCitations')}</span>
                <strong>{ragReadiness.data.citations}</strong>
              </div>
              <div>
                <span>{t('dashboard.ragEmbedding')}</span>
                <strong>{ragReadiness.runtime.embedding_model}</strong>
              </div>
              <div>
                <span>{t('dashboard.ragHealth')}</span>
                <strong>
                  {ragReadiness.runtime.vector_store_healthy
                    ? t('dashboard.ragHealthy')
                    : t('dashboard.ragNeedsAttention')}
                </strong>
              </div>
            </div>

            <div className="rag-module-grid">
              {ragReadiness.modules.map((module) => (
                <article key={module.id} className="rag-module-card">
                  <div>
                    <span className="rag-module-icon">
                      <Icon name={moduleIcons[module.id] || 'database'} size={17} />
                    </span>
                    <span
                      className={`rag-module-status ${
                        module.status === 'enabled' ? 'is-enabled' : ''
                      }`}
                    >
                      {module.status}
                    </span>
                  </div>
                  <h3>{module.label}</h3>
                  <p>{module.summary}</p>
                  <ul>
                    {module.talking_points.slice(0, 2).map((point) => (
                      <li key={point}>{point}</li>
                    ))}
                  </ul>
                </article>
              ))}
            </div>

            <div className="rag-demo-row">
              <div>
                <h3>{t('dashboard.ragQualityGates')}</h3>
                <div className="rag-gate-list">
                  {ragReadiness.quality_gates.map((gate) => (
                    <div key={gate.name}>
                      <Icon name={gate.enabled ? 'check' : 'offline'} size={15} />
                      <span>
                        <strong>{gate.name}</strong>
                        <small>{gate.description}</small>
                      </span>
                    </div>
                  ))}
                </div>
              </div>
              <div>
                <h3>{t('dashboard.ragDemoScript')}</h3>
                <div className="rag-demo-list">
                  {ragReadiness.demo_script.map((step) => (
                    <div key={step.title}>
                      <strong>{step.title}</strong>
                      <p>{step.prompt}</p>
                      <small>{step.what_to_show}</small>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </section>
        )}

        {data.total_quizzes > 0 && (
          <section className="dashboard-summary">
            <div>
              <span>{t('dashboard.correctCount')}</span>
              <strong>{data.total_correct_answers}</strong>
            </div>
            <div>
              <span>{t('dashboard.wrongCount')}</span>
              <strong>{data.wrong_answer_count}</strong>
            </div>
            <div className="is-accent">
              <span>{t('dashboard.accuracy')}</span>
              <strong>{accuracy}%</strong>
            </div>
          </section>
        )}

        <div className="dashboard-columns">
          {data.tag_stats.length > 0 && (
            <section className="product-section">
              <div className="product-section-heading">
                <h2>{t('dashboard.tagStats')}</h2>
              </div>
              <div className="dashboard-list">
                {data.tag_stats.map((item) => (
                  <div className="dashboard-list-row" key={item.tag}>
                    <strong>{item.tag}</strong>
                    <span>
                      {item.doc_count} {t('dashboard.documents_unit')}
                    </span>
                    <span>
                      {item.question_count} {t('dashboard.questions_unit')}
                    </span>
                  </div>
                ))}
              </div>
            </section>
          )}

          {data.weak_points.length > 0 && (
            <section className="product-section">
              <div className="product-section-heading">
                <h2>{t('dashboard.weakPoints')}</h2>
              </div>
              <div className="dashboard-list">
                {data.weak_points.map((item) => (
                  <div className="dashboard-list-row is-weak" key={item.concept}>
                    <strong>{item.concept}</strong>
                    <span>{Math.round(item.mastery_score * 100)}%</span>
                  </div>
                ))}
              </div>
            </section>
          )}
        </div>

        {data.recent_activity.some((item) => item.questions_count > 0) && (
          <section className="product-section">
            <div className="product-section-heading">
              <h2>{t('dashboard.recentActivity')}</h2>
            </div>
            <div className="dashboard-activity">
              {data.recent_activity.map((item) => (
                <div key={item.date}>
                  <span>{item.questions_count}</span>
                  <i
                    style={{
                      height: `${Math.max((item.questions_count / maxActivity) * 100, 3)}%`,
                    }}
                  />
                  <small>{item.date}</small>
                </div>
              ))}
            </div>
          </section>
        )}
      </div>
    </div>
  );
}
