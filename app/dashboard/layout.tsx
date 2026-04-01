'use client'

import { useState, useEffect } from 'react'
import { useRouter, usePathname } from 'next/navigation'
import Link from 'next/link'
import {
  ShoppingCart,
  Users,
  Settings,
  Play,
  BarChart3,
  LogOut,
  Menu,
  X,
  Package,
  MapPin,
  ChevronRight
} from 'lucide-react'
import { cn } from '@/lib/utils'

interface NavigationItem {
  name: string
  href: string
  icon: any
  adminOnly?: boolean
}

const navigation: NavigationItem[] = [
  { name: 'Products', href: '/dashboard/products', icon: Package },
  { name: 'Flipkart Accounts', href: '/dashboard/accounts', icon: Users },
  { name: 'Addresses', href: '/dashboard/addresses', icon: MapPin },
  { name: 'Automation', href: '/dashboard/automation', icon: Play },
  { name: 'Settings', href: '/dashboard/settings', icon: Settings },
]

const adminNavigation: NavigationItem[] = []

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const [user, setUser] = useState<any>(null)
  const router = useRouter()
  const pathname = usePathname()

  useEffect(() => {
    const token = localStorage.getItem('auth_token')
    const userData = localStorage.getItem('user')

    if (!token) {
      router.push('/login')
    } else if (userData) {
      setUser(JSON.parse(userData))
    }
  }, [router])

  const handleLogout = () => {
    localStorage.removeItem('auth_token')
    localStorage.removeItem('user')
    router.push('/login')
  }

  if (!user) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-secondary-50">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary-600"></div>
      </div>
    )
  }

  const allNavigation = [
    ...navigation,
    ...(user.is_admin ? adminNavigation : [])
  ]

  const NavItem = ({ item, mobile = false }: { item: NavigationItem, mobile?: boolean }) => {
    const isActive = pathname === item.href
    return (
      <Link
        href={item.href}
        onClick={() => mobile && setSidebarOpen(false)}
        className={cn(
          "group flex items-center px-3 py-2.5 text-sm font-medium rounded-lg transition-all duration-200 mb-1",
          isActive
            ? "bg-primary-50 text-primary-700 shadow-sm"
            : "text-secondary-600 hover:bg-secondary-50 hover:text-secondary-900",
          item.adminOnly && "border-l-2 border-warning-500"
        )}
      >
        <item.icon className={cn(
          "mr-3 h-5 w-5 transition-colors",
          isActive ? "text-primary-600" : "text-secondary-400 group-hover:text-secondary-600"
        )} />
        {item.name}
        {item.adminOnly && (
          <span className="ml-auto text-[10px] font-bold bg-warning-100 text-warning-800 px-1.5 py-0.5 rounded uppercase tracking-wider">
            Admin
          </span>
        )}
        {isActive && (
          <ChevronRight className="ml-auto h-4 w-4 text-primary-400" />
        )}
      </Link>
    )
  }

  return (
    <div className="h-screen flex overflow-hidden bg-secondary-50">
      {/* Sidebar */}
      <div className={`fixed inset-y-0 left-0 z-50 w-72 bg-white transform ${sidebarOpen ? 'translate-x-0' : '-translate-x-full'
        } transition-transform duration-300 ease-in-out lg:translate-x-0 lg:static lg:inset-0 border-r border-secondary-300 shadow-sm`}>

        {/* Sidebar Header */}
        <div className="flex items-center justify-between h-16 px-6 border-b border-secondary-200 bg-white">
          <div className="flex items-center space-x-3">
            <div className="bg-primary-600 p-1.5 rounded-lg shadow-lg shadow-primary-600/20">
              <ShoppingCart className="h-5 w-5 text-white" />
            </div>
            <span className="text-lg font-bold text-secondary-900 tracking-tight">FlipkartBot</span>
          </div>
          <button
            className="lg:hidden text-secondary-500 hover:text-secondary-700"
            onClick={() => setSidebarOpen(false)}
          >
            <X className="h-6 w-6" />
          </button>
        </div>

        {/* Navigation */}
        <nav className="flex-1 px-4 py-6 space-y-1 overflow-y-auto">
          <div className="text-xs font-semibold text-secondary-400 uppercase tracking-wider mb-4 px-2">
            Main Menu
          </div>
          {allNavigation.map((item) => (
            <NavItem key={item.name} item={item} mobile />
          ))}
        </nav>

        {/* User Profile */}
        <div className="p-4 border-t border-secondary-200 bg-secondary-50/50">
          <div className="flex items-center justify-between">
            <div className="flex items-center min-w-0">
              <div className="flex-shrink-0">
                <div className="h-10 w-10 rounded-full bg-gradient-to-br from-primary-500 to-primary-600 flex items-center justify-center shadow-md text-white font-semibold text-sm">
                  {user.username?.[0]?.toUpperCase()}
                </div>
              </div>
              <div className="ml-3 min-w-0">
                <p className="text-sm font-medium text-secondary-900 truncate">{user.username}</p>
                <p className="text-xs text-secondary-500 truncate">
                  {user.is_admin ? 'Administrator' : 'User'}
                </p>
              </div>
            </div>
            <button
              onClick={handleLogout}
              className="p-2 text-secondary-400 hover:text-danger-600 hover:bg-danger-50 rounded-full transition-colors"
              title="Logout"
            >
              <LogOut className="h-5 w-5" />
            </button>
          </div>
        </div>
      </div>

      {/* Mobile sidebar overlay */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div className="fixed inset-0 bg-secondary-900/50 backdrop-blur-sm transition-opacity" onClick={() => setSidebarOpen(false)} />
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col overflow-hidden bg-secondary-50/50">
        {/* Desktop Header */}
        <header className="hidden lg:flex items-center justify-between h-16 px-8 bg-white border-b border-secondary-300">
          <div className="flex items-center space-x-4">
             <h2 className="text-sm font-semibold text-secondary-500 uppercase tracking-wider">
               {pathname.split('/').pop()?.replace('_', ' ')}
             </h2>
          </div>
          <div className="flex items-center space-x-4">
            <div className="h-8 w-px bg-secondary-200 mx-2" />
            <span className="text-sm font-medium text-secondary-600">{user.username}</span>
          </div>
        </header>

        {/* Mobile Header */}
        <div className="lg:hidden flex items-center justify-between h-16 px-4 bg-white border-b border-secondary-300 shadow-sm">
          <button
            className="text-secondary-500 hover:text-secondary-700 p-2 -ml-2"
            onClick={() => setSidebarOpen(true)}
          >
            <Menu className="h-6 w-6" />
          </button>
          <h1 className="text-lg font-semibold text-secondary-900">Dashboard</h1>
          <div className="w-6"></div> {/* Spacer for centering */}
        </div>

        <main className="flex-1 relative z-0 overflow-y-auto focus:outline-none">
          <div className="py-8">
            <div className="max-w-7xl mx-auto px-4 sm:px-6 md:px-8">
              {children}
            </div>
          </div>
        </main>
      </div>
    </div>
  )
} 