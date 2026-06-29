import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster } from 'react-hot-toast';
import { Sidebar } from '@/components/layout/Sidebar';

import Dashboard       from '@/pages/Dashboard';
import CorpusPage      from '@/pages/CorpusPage';
import RetrievalPage   from '@/pages/RetrievalPage';
import AgentPage       from '@/pages/AgentPage';
import EvalPage        from '@/pages/EvalPage';
import AdversarialPage from '@/pages/AdversarialPage';
import MetricsPage     from '@/pages/MetricsPage';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: { staleTime: 30_000, retry: 1, refetchOnWindowFocus: false },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <div className="flex min-h-screen">
          <Sidebar />
          <main className="flex-1 ml-64 min-h-screen">
            {/* Ambient scan line */}
            <div className="scan-line" />
            <Routes>
              <Route path="/"            element={<Dashboard />} />
              <Route path="/corpus"      element={<CorpusPage />} />
              <Route path="/retrieve"    element={<RetrievalPage />} />
              <Route path="/agent"       element={<AgentPage />} />
              <Route path="/eval"        element={<EvalPage />} />
              <Route path="/adversarial" element={<AdversarialPage />} />
              <Route path="/metrics"     element={<MetricsPage />} />
              <Route path="/benchmarks"  element={<EvalPage />} />
              <Route path="/docs"        element={<APIDocsPage />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>

      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: '#100C2E',
            color: '#DDD6FE',
            border: '1px solid rgba(124,58,237,0.25)',
            borderRadius: '12px',
            fontSize: '13px',
            boxShadow: '0 8px 32px rgba(0,0,0,0.6), 0 0 20px rgba(124,58,237,0.1)',
          },
          success: { iconTheme: { primary: '#10B981', secondary: '#100C2E' } },
          error:   { iconTheme: { primary: '#EF4444', secondary: '#100C2E' } },
        }}
      />
    </QueryClientProvider>
  );
}

function APIDocsPage() {
  return (
    <div className="flex items-center justify-center h-96">
      <div className="text-center">
        <p className="mb-4" style={{ color: 'rgba(167,139,250,0.6)' }}>
          API documentation available at:
        </p>
        <a href="http://localhost:8000/docs" target="_blank" rel="noopener noreferrer"
          className="btn-primary">
          Open Swagger UI ↗
        </a>
      </div>
    </div>
  );
}
