<<<<<<< HEAD
import { BrowserRouter, Navigate, Route, Routes } from 'react-router-dom'

import { RequireAuth } from './components/RequireAuth'
import { AuthProvider } from './context/AuthProvider'
import { DashboardLayout } from './layouts/DashboardLayout'
import { LoginPage } from './pages/LoginPage'
import { NewAssetPage } from './pages/NewAssetPage'
import { PortfolioPage } from './pages/PortfolioPage'

export default function App() {
  return (
    <AuthProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/login" element={<LoginPage />} />

          <Route element={<RequireAuth />}>
            <Route element={<DashboardLayout />}>
              <Route index element={<PortfolioPage />} />

              <Route element={<RequireAuth roles={['NIT']} />}>
                <Route path="ativos/novo" element={<NewAssetPage />} />
              </Route>
            </Route>
          </Route>

          <Route path="*" element={<Navigate to="/" replace />} />
        </Routes>
      </BrowserRouter>
    </AuthProvider>
=======
// Placeholder da Etapa 1: confirma que React + Tailwind estão funcionando.
// As rotas (login, painel, cadastro) entram na Etapa 4.
export default function App() {
  return (
    <main className="flex min-h-screen items-center justify-center p-6">
      <div className="max-w-md rounded-xl border border-line bg-white p-8 text-center">
        <p className="text-xs font-semibold tracking-wide text-teal uppercase">
          Sistema de Acompanhamento de PI
        </p>
        <h1 className="mt-2 font-serif text-2xl font-semibold text-navy-dark">
          Setup concluído
        </h1>
        <p className="mt-2 text-sm text-subink">
          Frontend React + Vite + Tailwind CSS pronto para a próxima etapa.
        </p>
      </div>
    </main>
>>>>>>> b6b47a4fd75e03c2aa8d187258382a1dc8411da4
  )
}
