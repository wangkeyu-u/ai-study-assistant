import { FormEvent, useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { ChatSession, Document, listDocuments, listSessions } from '../api';
import Icon from '../components/Icon';

export default function Home() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [question, setQuestion] = useState('');
  const [documents, setDocuments] = useState<Document[]>([]);
  const [sessions, setSessions] = useState<ChatSession[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    Promise.all([listDocuments(), listSessions()])
      .then(([nextDocuments, nextSessions]) => {
        setDocuments(nextDocuments);
        setSessions(nextSessions);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  const ask = (event: FormEvent) => {
    event.preventDefault();
    const value = question.trim();
    if (!value) return;
    navigate(`/chat?q=${encodeURIComponent(value)}`);
  };

  const readyDocuments = documents.filter((document) => document.status === 'ready');

  return (
    <div className="workspace-home h-full overflow-auto">
      <div className="mx-auto max-w-6xl px-7 py-10 lg:px-12 lg:py-14">
        <header className="home-intro">
          <p className="workspace-kicker">{t('home.kicker')}</p>
          <h1>{t('home.title')}</h1>
          <p>{t('home.subtitle')}</p>
        </header>

        <form onSubmit={ask} className="ask-surface mt-8">
          <div className="flex items-start gap-4">
            <div className="ask-mark">
              <Icon name="sparkles" size={19} />
            </div>
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === 'Enter' && !event.shiftKey) {
                  event.preventDefault();
                  event.currentTarget.form?.requestSubmit();
                }
              }}
              rows={2}
              aria-label={t('home.askPlaceholder')}
              placeholder={t('home.askPlaceholder')}
              className="min-h-[68px] flex-1 resize-none bg-transparent text-[17px] leading-7 text-zinc-900 outline-none placeholder:text-zinc-400"
            />
          </div>
          <div className="mt-4 flex items-center justify-between border-t border-zinc-100 pt-3">
            <span className="text-xs text-zinc-400">{t('home.askHint')}</span>
            <button type="submit" disabled={!question.trim()} className="primary-action">
              {t('home.askAction')} <Icon name="arrow" size={16} />
            </button>
          </div>
        </form>

        <div className="mt-10 grid gap-8 lg:grid-cols-[1.35fr_0.85fr]">
          <section>
            <div className="section-heading">
              <div>
                <p>{t('home.recentDocuments')}</p>
                <span>{t('home.recentDocumentsHint')}</span>
              </div>
              <button onClick={() => navigate('/documents')}>
                {t('home.viewLibrary')} <Icon name="arrow" size={14} />
              </button>
            </div>
            <div className="quiet-panel mt-3">
              {loading ? (
                <div className="home-skeleton" />
              ) : readyDocuments.length === 0 ? (
                <button className="empty-home-action" onClick={() => navigate('/documents')}>
                  <span>
                    <Icon name="upload" size={20} />
                  </span>
                  <div>
                    <strong>{t('home.addFirstDocument')}</strong>
                    <small>{t('home.addFirstDocumentHint')}</small>
                  </div>
                  <Icon name="arrow" size={16} />
                </button>
              ) : (
                readyDocuments.slice(0, 5).map((document) => (
                  <button
                    key={document.id}
                    className="home-row"
                    onClick={() =>
                      navigate(
                        `/chat?documents=${encodeURIComponent(document.id)}&names=${encodeURIComponent(document.filename)}`
                      )
                    }
                  >
                    <span className="home-row-icon">
                      <Icon name={document.file_type === 'note' ? 'note' : 'file'} size={18} />
                    </span>
                    <span className="min-w-0 flex-1 text-left">
                      <strong>{document.filename}</strong>
                      <small>{t('home.documentMeta', { chunks: document.chunk_count })}</small>
                    </span>
                    <span className="row-action">
                      {t('home.askThis')} <Icon name="arrow" size={14} />
                    </span>
                  </button>
                ))
              )}
            </div>
          </section>

          <section>
            <div className="section-heading">
              <div>
                <p>{t('home.continueWork')}</p>
                <span>{t('home.continueWorkHint')}</span>
              </div>
            </div>
            <div className="quiet-panel mt-3">
              {!loading && sessions.length === 0 ? (
                <div className="home-empty">
                  <Icon name="chat" size={20} />
                  <p>{t('home.noRecentChats')}</p>
                </div>
              ) : (
                sessions.slice(0, 5).map((session) => (
                  <button
                    key={session.id}
                    className="home-row"
                    onClick={() => navigate(`/chat?session=${encodeURIComponent(session.id)}`)}
                  >
                    <span className="home-row-icon">
                      <Icon name="clock" size={17} />
                    </span>
                    <span className="min-w-0 flex-1 text-left">
                      <strong>{session.title}</strong>
                      <small>{t('home.messageCount', { count: session.message_count })}</small>
                    </span>
                    <Icon name="arrow" size={14} className="text-zinc-400" />
                  </button>
                ))
              )}
            </div>
          </section>
        </div>

        <section className="mt-10 grid gap-3 md:grid-cols-3">
          <button className="quick-card" onClick={() => navigate('/documents')}>
            <Icon name="upload" />
            <span>
              <strong>{t('home.upload')}</strong>
              <small>{t('home.uploadHint')}</small>
            </span>
          </button>
          <button className="quick-card" onClick={() => navigate('/documents')}>
            <Icon name="layers" />
            <span>
              <strong>{t('home.compare')}</strong>
              <small>{t('home.compareHint')}</small>
            </span>
          </button>
          <button className="quick-card" onClick={() => navigate('/quiz')}>
            <Icon name="quiz" />
            <span>
              <strong>{t('home.review')}</strong>
              <small>{t('home.reviewHint')}</small>
            </span>
          </button>
        </section>
      </div>
    </div>
  );
}
