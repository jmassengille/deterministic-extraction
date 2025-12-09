import { Outlet, NavLink, useLocation, useNavigate } from 'react-router-dom'
import { AnimatePresence } from 'framer-motion'
import {
  LayoutDashboard,
  Upload,
  List,
  Activity,
  FileText,
  LogOut
} from 'lucide-react'
import PageTransition from './PageTransition'
import { useAuth } from '../contexts/AuthContext'

const navigation = [
  { name: 'Dashboard', href: '/dashboard', icon: LayoutDashboard },
  { name: 'Upload', href: '/upload', icon: Upload },
  { name: 'Jobs', href: '/jobs', icon: List }
]

export default function Layout() {
  const location = useLocation()
  const navigate = useNavigate()
  const { logout } = useAuth()

  const handleLogout = () => {
    logout()
    navigate('/')
  }

  return (
    <div className="flex h-screen bg-slate-100">
      {/* Sidebar */}
      <div className="w-64 bg-slate-900 flex-shrink-0 shadow-xl">
        <div className="flex h-full flex-col">
          {/* Logo */}
          <div className="flex h-16 items-center px-6 border-b border-slate-700 bg-slate-900">
            <FileText className="h-7 w-7 text-accent-400 mr-3" />
            <div>
              <h1 className="text-white font-bold text-lg">
                DocProcessor
              </h1>
              <p className="text-slate-400 text-xs font-medium">
                PDF Processing
              </p>
            </div>
          </div>

          {/* Navigation */}
          <nav className="flex-1 px-4 py-6">
            {navigation.map((item) => {
              const Icon = item.icon
              return (
                <NavLink
                  key={item.name}
                  to={item.href}
                  className={({ isActive }) =>
                    `group flex items-center px-4 py-3 mb-2 text-sm font-medium rounded-lg transition-all duration-200 ${
                      isActive
                        ? 'bg-slate-700 text-white shadow-lg'
                        : 'text-slate-300 hover:bg-slate-700 hover:text-white hover:shadow-md'
                    }`
                  }
                >
                  <Icon className="mr-3 h-5 w-5 flex-shrink-0" />
                  <span>{item.name}</span>
                </NavLink>
              )
            })}
          </nav>

          {/* Footer */}
          <div className="flex-shrink-0 border-t border-slate-700 px-4 py-4 bg-slate-900 space-y-2">
            <div className="flex items-center px-2">
              <Activity className="w-4 h-4 text-green-400 mr-2" />
              <span className="text-sm text-slate-300 font-medium">System Online</span>
            </div>
            <button
              onClick={handleLogout}
              className="w-full flex items-center px-4 py-2 text-sm font-medium text-slate-300 hover:bg-slate-700 hover:text-white rounded-lg transition-all duration-200 cursor-pointer"
            >
              <LogOut className="w-4 h-4 mr-3" />
              <span>Logout</span>
            </button>
          </div>
        </div>
      </div>

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden">
        {/* Top bar */}
        <header className="bg-white border-b border-gray-200 h-16 flex items-center shadow-sm">
          <div className="px-8">
            <h2 className="text-base font-semibold text-gray-900">
              PDF Processing Pipeline
            </h2>
            <p className="text-xs text-gray-500 mt-0.5">
              Document conversion and processing
            </p>
          </div>
        </header>

        {/* Page content */}
        <main className="flex-1 overflow-y-auto p-6 lg:p-8" data-lenis-prevent>
          <AnimatePresence mode="wait">
            <PageTransition key={location.pathname}>
              <Outlet />
            </PageTransition>
          </AnimatePresence>
        </main>
      </div>
    </div>
  )
}
