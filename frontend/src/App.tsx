import { useEffect, useState } from 'react';
import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Home from './pages/Home';
import Documents from './pages/Documents';
import Chat from './pages/Chat';
import Quiz from './pages/Quiz';
import Dashboard from './pages/Dashboard';
import KnowledgeGraph from './pages/KnowledgeGraph';
import Settings from './pages/Settings';
import Icon, { IconName } from './components/Icon';

const PRIMARY_NAV: { to: string; labelKey: string; icon: IconName; end?: boolean }[] = [
  { to: '/', labelKey: 'nav.home', icon: 'home', end: true },
  { to: '/documents', labelKey: 'nav.documents', icon: 'library' },
  { to: '/chat', labelKey: 'nav.chat', icon: 'chat' },
];

const LEARNING_NAV: { to: string; labelKey: string; icon: IconName }[] = [
  { to: '/quiz', labelKey: 'nav.quiz', icon: 'quiz' },
  { to: '/dashboard', labelKey: 'nav.dashboard', icon: 'chart' },
  { to: '/knowledge-graph', labelKey: 'nav.knowledgeGraph', icon: 'graph' },
];

function App() {
  const { t, i18n } = useTranslation();
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let active = true;
    const checkHealth = () => {
      fetch('/api/health')
        .then((response) => {
          if (!response.ok) throw new Error('offline');
          if (active) setOnline(true);
        })
        .catch(() => active && setOnline(false));
    };
    checkHealth();
    const timer = window.setInterval(checkHealth, 30_000);
    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  const toggleLanguage = () => {
    i18n.changeLanguage(i18n.language === 'en-US' ? 'zh-CN' : 'en-US');
  };

  const navClass = ({ isActive }: { isActive: boolean }) =>
    `workspace-nav-link ${isActive ? 'is-active' : ''}`;

  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <a href="#workspace-main" className="skip-link">
        {t('nav.skipContent')}
      </a>
      <div className="app-shell flex h-screen">
        <nav className="workspace-sidebar" aria-label={t('nav.primary')}>
          <NavLink to="/" className="workspace-brand" aria-label={t('nav.home')}>
            <span className="workspace-brand-mark">K</span>
            <span className="sidebar-copy">
              <strong>{t('nav.appTitle')}</strong>
              <small>{t('nav.appSubtitle')}</small>
            </span>
          </NavLink>

          <div className="workspace-nav-section">
            {PRIMARY_NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={item.end}
                className={navClass}
                aria-label={t(item.labelKey)}
              >
                <Icon name={item.icon} size={18} />
                <span className="sidebar-copy">{t(item.labelKey)}</span>
              </NavLink>
            ))}
          </div>

          <div className="workspace-nav-section workspace-tools">
            <p className="sidebar-label sidebar-copy">{t('nav.learningTools')}</p>
            {LEARNING_NAV.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                className={navClass}
                aria-label={t(item.labelKey)}
              >
                <Icon name={item.icon} size={18} />
                <span className="sidebar-copy">{t(item.labelKey)}</span>
              </NavLink>
            ))}
          </div>

          <div className="mt-auto">
            <NavLink to="/settings" className={navClass} aria-label={t('nav.settings')}>
              <Icon name="settings" size={18} />
              <span className="sidebar-copy">{t('nav.settings')}</span>
            </NavLink>
            <button
              onClick={toggleLanguage}
              className="workspace-language"
              aria-label={t('nav.switchLanguage')}
            >
              <span>{i18n.language === 'en-US' ? 'EN' : '中'}</span>
              <span className="sidebar-copy">
                {i18n.language === 'en-US' ? 'English' : '简体中文'}
              </span>
            </button>
            <div className={`workspace-status ${online === false ? 'is-offline' : ''}`}>
              <Icon name={online === false ? 'offline' : 'database'} size={15} />
              <span className="sidebar-copy">
                {online === null
                  ? t('nav.connecting')
                  : online
                    ? t('nav.connected')
                    : t('nav.disconnected')}
              </span>
              <span className="status-dot" />
            </div>
          </div>
        </nav>

        <main id="workspace-main" className="app-main flex-1 overflow-hidden">
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/documents" element={<Documents />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/quiz" element={<Quiz />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/knowledge-graph" element={<KnowledgeGraph />} />
            <Route path="/settings" element={<Settings />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
