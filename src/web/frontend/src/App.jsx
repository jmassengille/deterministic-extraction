import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { ReactLenis } from 'lenis/react'
import { Toaster } from 'sonner'
import ErrorBoundary from './components/ErrorBoundary'
import Layout from './components/Layout'
import Landing from './pages/Landing'
import Login from './pages/Login'
import Dashboard from './pages/Dashboard'
import Upload from './pages/Upload'
import Jobs from './pages/Jobs'
import JobDetail from './pages/JobDetail'
import { AuthProvider } from './contexts/AuthContext'
import ProtectedRoute from './components/ProtectedRoute'

// Create React Query client
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      retry: 1,
      staleTime: 30 * 1000, // 30 seconds
    },
  },
})

function LenisWrapper({ children }) {
  return <ReactLenis root>{children}</ReactLenis>
}

function App() {
  return (
    <ErrorBoundary>
      <QueryClientProvider client={queryClient}>
        <AuthProvider>
          <BrowserRouter>
            <LenisWrapper>
              <Routes>
                <Route path="/" element={<Landing />} />
                <Route path="/login" element={<Login />} />
                <Route path="/" element={<Layout />}>
                  <Route
                    path="dashboard"
                    element={
                      <ProtectedRoute>
                        <Dashboard />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="upload"
                    element={
                      <ProtectedRoute>
                        <Upload />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="jobs"
                    element={
                      <ProtectedRoute>
                        <Jobs />
                      </ProtectedRoute>
                    }
                  />
                  <Route
                    path="jobs/:jobId"
                    element={
                      <ProtectedRoute>
                        <JobDetail />
                      </ProtectedRoute>
                    }
                  />
                </Route>
              </Routes>
            </LenisWrapper>
          </BrowserRouter>
        </AuthProvider>
      </QueryClientProvider>
      <Toaster
        position="top-right"
        expand={false}
        richColors
        closeButton
        duration={4000}
      />
    </ErrorBoundary>
  )
}

export default App