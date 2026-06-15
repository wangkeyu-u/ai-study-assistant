import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import Documents from './pages/Documents';
import Chat from './pages/Chat';
import Quiz from './pages/Quiz';
import Dashboard from './pages/Dashboard';
import KnowledgeGraph from './pages/KnowledgeGraph';
import Settings from './pages/Settings';

const NAV_ITEMS = [
  { to: '/', labelKey: 'nav.documents', icon: '▤', end: true },
  { to: '/chat', labelKey: 'nav.chat', icon: '◇' },
  { to: '/quiz', labelKey: 'nav.quiz', icon: '✓' },
  { to: '/dashboard', labelKey: 'nav.dashboard', icon: '⌁' },
  { to: '/knowledge-graph', labelKey: 'nav.knowledgeGraph', icon: '⌘' },
] as const;

function App() {
  const { t, i18n } = useTranslation();

  const toggleLanguage = () => {
    const next = i18n.language === 'en-US' ? 'zh-CN' : 'en-US';
    i18n.changeLanguage(next);
  };

  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `nav-spell ${isActive ? 'is-active' : ''}`;

  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <div className="app-shell flex h-screen">
        {/* Sidebar */}
        <nav className="app-sidebar w-60 flex flex-col">
          <div className="brand-lockup">
            <div className="brand-orbit" aria-hidden="true">
              <span className="brand-core" />
              <span className="brand-satellite brand-satellite-one" />
              <span className="brand-satellite brand-satellite-two" />
            </div>
            <div className="min-w-0">
              <h1 className="text-base font-semibold text-white tracking-tight truncate">
                {t('nav.appTitle')}
              </h1>
              <p className="text-[11px] text-slate-400 mt-0.5 truncate">{t('nav.appSubtitle')}</p>
            </div>
          </div>
          <div className="flex-1 px-3 py-5 space-y-1.5">
            <p className="sidebar-eyebrow">Workspace</p>
            {NAV_ITEMS.map((item) => (
              <NavLink
                key={item.to}
                to={item.to}
                end={'end' in item && item.end}
                className={navLinkClass}
              >
                <span className="nav-glyph" aria-hidden="true">
                  {item.icon}
                </span>
                <span className="truncate">{t(item.labelKey)}</span>
                <span className="nav-spark" aria-hidden="true" />
              </NavLink>
            ))}
          </div>
          <div className="px-3 pb-2">
            <NavLink to="/settings" className={navLinkClass}>
              <span className="nav-glyph" aria-hidden="true">
                ⚙
              </span>
              <span>{t('nav.settings')}</span>
              <span className="nav-spark" aria-hidden="true" />
            </NavLink>
          </div>
          {/* Language switcher */}
          <div className="px-3 pb-4">
            <button onClick={toggleLanguage} className="language-switch">
              <span className={i18n.language === 'zh-CN' ? 'text-white font-medium' : ''}>中</span>
              <span className="text-slate-600">/</span>
              <span className={i18n.language === 'en-US' ? 'text-white font-medium' : ''}>EN</span>
            </button>
          </div>
          <div className="px-4 py-4 border-t border-white/[0.06]">
            <div className="system-status">
              <span className="status-pulse" />
              <span className="text-[11px] text-slate-400">Local workspace</span>
              <span className="ml-auto text-[10px] text-slate-600">v1.0</span>
            </div>
          </div>
        </nav>

        {/* Main content */}
        <main className="app-main flex-1 overflow-hidden">
          <Routes>
            <Route path="/" element={<Documents />} />
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
