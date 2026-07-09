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
            <Routes>
              <Route path="/"            element={<Dashboard />} />
              <Route path="/corpus"      element={<CorpusPage />} />
              <Route path="/retrieve"    element={<RetrievalPage />} />
              <Route path="/agent"       element={<AgentPage />} />
              <Route path="/eval"        element={<EvalPage />} />
              <Route path="/adversarial" element={<AdversarialPage />} />
              <Route path="/metrics"     element={<MetricsPage />} />
              <Route path="/docs"        element={<APIDocsPage />} />
            </Routes>
          </main>
        </div>
      </BrowserRouter>

      <Toaster
        position="bottom-right"
        toastOptions={{
          style: {
            background: '#151517',
            color: '#F5F5F5',
            border: '1px solid rgba(255,255,255,0.08)',
            borderRadius: '3px',
            fontSize: '13px',
          },
          success: { iconTheme: { primary: '#22C55E', secondary: '#151517' } },
          error:   { iconTheme: { primary: '#EF4444', secondary: '#151517' } },
        }}
      />
    </QueryClientProvider>
  );
}

function APIDocsPage() {
  return (
    <div className="flex items-center justify-center h-96">
      <div className="text-center">
        <p className="mb-4 text-text-secondary">
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
