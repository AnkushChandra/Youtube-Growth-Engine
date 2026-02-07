import { BrowserRouter, Routes, Route } from 'react-router-dom';
import NavMenu from './components/NavMenu';
import { AppProvider, useApp } from './context/AppContext';
import AnalyzePage from './pages/AnalyzePage';
import DataPage from './pages/DataPage';
import HistoryPage from './pages/HistoryPage';
import AgentTracePage from './pages/AgentTracePage';

function AppShell() {
  const { error, toast } = useApp();

  return (
    <div className="app-shell">
      <div className="top-bar">
        <span className="top-bar-brand">YouTube Strategy Lab</span>
        <NavMenu />
      </div>

      {error && (
        <div className="panel" style={{ borderColor: '#ff6b35', margin: '0 0 16px' }}>
          <strong>Heads up:</strong> {error}
        </div>
      )}
      {toast && (
        <div className="panel" style={{ borderColor: 'rgba(0,194,255,0.4)', margin: '0 0 16px' }}>
          {toast}
        </div>
      )}

      <Routes>
        <Route path="/" element={<AnalyzePage />} />
        <Route path="/history" element={<HistoryPage />} />
        <Route path="/data" element={<DataPage />} />
        <Route path="/agent" element={<AgentTracePage />} />
      </Routes>
    </div>
  );
}

function App() {
  return (
    <BrowserRouter>
      <AppProvider>
        <AppShell />
      </AppProvider>
    </BrowserRouter>
  );
}

export default App;
