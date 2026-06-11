import { BrowserRouter, Routes, Route, NavLink } from 'react-router-dom';
import Documents from './pages/Documents';
import Chat from './pages/Chat';
import Quiz from './pages/Quiz';
import Dashboard from './pages/Dashboard';
import KnowledgeGraph from './pages/KnowledgeGraph';

function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen bg-gray-50">
        {/* Sidebar */}
        <nav className="w-56 bg-gradient-to-b from-slate-900 via-slate-800 to-slate-900 flex flex-col shadow-xl">
          <div className="p-5 border-b border-slate-700/50">
            <h1 className="text-lg font-bold text-white tracking-tight">AI Study Assistant</h1>
            <p className="text-xs text-slate-400 mt-1">RAG-Powered Learning Tool</p>
          </div>
          <div className="flex-1 p-3 space-y-1">
            <NavLink
              to="/"
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-200 ${
                  isActive
                    ? 'bg-white/10 text-white font-medium shadow-sm backdrop-blur-sm'
                    : 'text-slate-400 hover:text-white hover:bg-white/5'
                }`
              }
            >
              <span className="text-base w-6 text-center">📄</span> 文档管理
            </NavLink>
            <NavLink
              to="/chat"
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-200 ${
                  isActive
                    ? 'bg-white/10 text-white font-medium shadow-sm backdrop-blur-sm'
                    : 'text-slate-400 hover:text-white hover:bg-white/5'
                }`
              }
            >
              <span className="text-base w-6 text-center">💬</span> 智能问答
            </NavLink>
            <NavLink
              to="/quiz"
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-200 ${
                  isActive
                    ? 'bg-white/10 text-white font-medium shadow-sm backdrop-blur-sm'
                    : 'text-slate-400 hover:text-white hover:bg-white/5'
                }`
              }
            >
              <span className="text-base w-6 text-center">✍️</span> 学习测验
            </NavLink>
            <NavLink
              to="/dashboard"
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-200 ${
                  isActive
                    ? 'bg-white/10 text-white font-medium shadow-sm backdrop-blur-sm'
                    : 'text-slate-400 hover:text-white hover:bg-white/5'
                }`
              }
            >
              <span className="text-base w-6 text-center">📊</span> 学习看板
            </NavLink>
            <NavLink
              to="/knowledge-graph"
              className={({ isActive }) =>
                `flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm transition-all duration-200 ${
                  isActive
                    ? 'bg-white/10 text-white font-medium shadow-sm backdrop-blur-sm'
                    : 'text-slate-400 hover:text-white hover:bg-white/5'
                }`
              }
            >
              <span className="text-base w-6 text-center">🔗</span> 知识图谱
            </NavLink>
          </div>
          <div className="p-4 border-t border-slate-700/50">
            <div className="flex items-center justify-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
              <p className="text-xs text-slate-500">v1.0.0</p>
            </div>
          </div>
        </nav>

        {/* Main content */}
        <main className="flex-1 overflow-hidden">
          <Routes>
            <Route path="/" element={<Documents />} />
            <Route path="/chat" element={<Chat />} />
            <Route path="/quiz" element={<Quiz />} />
            <Route path="/dashboard" element={<Dashboard />} />
            <Route path="/knowledge-graph" element={<KnowledgeGraph />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}

export default App;
