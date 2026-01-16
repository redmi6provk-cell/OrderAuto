# ⚛️ Frontend Dashboard Documentation

## Overview

This is the Next.js 14 frontend dashboard for the Flipkart Automation System. It provides a modern, responsive web interface for managing automation sessions, addresses, accounts, and system settings.

## 🚀 Tech Stack

- **Framework**: Next.js 14 with App Router
- **Language**: TypeScript
- **Styling**: Tailwind CSS + Tailwind UI
- **UI Components**: Headless UI + Custom components
- **Icons**: Heroicons + Lucide React
- **HTTP Client**: Axios
- **Forms**: React Hook Form
- **Notifications**: React Hot Toast + Sonner
- **Animation**: Framer Motion

## 📁 Project Structure

```
app/
├── dashboard/                 # Main dashboard pages
│   ├── accounts/             # Flipkart account management
│   │   ├── page.tsx         # Accounts listing page
│   │   └── components/      # Account-specific components
│   ├── addresses/           # Address management
│   │   ├── page.tsx        # Addresses CRUD interface
│   │   └── components/     # Address forms & components
│   ├── automation/          # Automation control center
│   │   ├── page.tsx        # Automation dashboard
│   │   └── components/     # Automation forms & status
│   ├── layout.tsx          # Dashboard layout with navigation
│   └── page.tsx            # Dashboard home page
├── login/                   # Authentication pages
│   └── page.tsx            # Login form
├── globals.css             # Global Tailwind styles
└── layout.tsx              # Root application layout
```

## 🎨 UI Components

### Core Components (`/components/ui/`)

#### Button Component
```tsx
// components/ui/button.tsx
interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'destructive'
  size?: 'sm' | 'md' | 'lg'
  children: React.ReactNode
  onClick?: () => void
  disabled?: boolean
}

export const Button: React.FC<ButtonProps> = ({ 
  variant = 'primary', 
  size = 'md', 
  children, 
  ...props 
}) => {
  // Styled with Tailwind CSS variants
}
```

#### Card Component
```tsx
// components/ui/card.tsx
export const Card = ({ children, className, ...props }) => (
  <div 
    className={cn(
      "rounded-lg border bg-card text-card-foreground shadow-sm",
      className
    )}
    {...props}
  >
    {children}
  </div>
)
```

#### Input Component
```tsx
// components/ui/input.tsx
interface InputProps extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string
  error?: string
  helperText?: string
}

export const Input: React.FC<InputProps> = ({
  label,
  error,
  helperText,
  className,
  ...props
}) => {
  // Form input with validation styling
}
```

### Custom Components

#### Toaster (`/components/Toaster.tsx`)
```tsx
// Global notification system integration
import { Toaster as SonnerToaster } from 'sonner'

export function Toaster() {
  return (
    <SonnerToaster
      position="top-right"
      toastOptions={{
        classNames: {
          error: 'border-red-500',
          success: 'border-green-500',
          warning: 'border-yellow-500',
        }
      }}
    />
  )
}
```

## 📄 Pages & Features

### 🏠 Dashboard Home (`/dashboard/page.tsx`)
- **Overview Cards**: System statistics and quick metrics
- **Recent Activity**: Latest automation sessions
- **Quick Actions**: Start automation, add products
- **Status Indicators**: System health and active sessions

```tsx
export default function DashboardPage() {
  const [stats, setStats] = useState(null)
  const [recentSessions, setRecentSessions] = useState([])
  
  useEffect(() => {
    fetchDashboardData()
  }, [])

  return (
    <div className="space-y-6">
      <StatsCards stats={stats} />
      <RecentActivity sessions={recentSessions} />
      <QuickActions />
    </div>
  )
}
```

### 🤖 Automation Control (`/dashboard/automation/page.tsx`)
- **Session Management**: Start, stop, monitor automation sessions
- **Product Configuration**: Add products with quantities
- **Account Selection**: Choose Flipkart account for session
- **Address Selection**: Select delivery address with default fallback
- **Real-time Status**: Live session progress tracking

```tsx
interface AutomationRequest {
  products: Array<{
    url: string
    quantity: number
  }>
  account_id: number
  address_id?: number  // Optional, falls back to default
  enable_checkout?: boolean
}

export default function AutomationPage() {
  const [sessions, setSessions] = useState([])
  const [accounts, setAccounts] = useState([])
  const [addresses, setAddresses] = useState([])
  
  const startAutomation = async (data: AutomationRequest) => {
    try {
      const response = await automationService.startSession(data)
      toast.success('Automation session started!')
      // Poll for status updates
      pollSessionStatus(response.session_id)
    } catch (error) {
      toast.error('Failed to start automation')
    }
  }

  return (
    <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
      <AutomationForm 
        accounts={accounts}
        addresses={addresses}
        onSubmit={startAutomation}
      />
      <SessionMonitor sessions={sessions} />
    </div>
  )
}
```

### 🏠 Address Management (`/dashboard/addresses/page.tsx`)
- **CRUD Operations**: Create, read, update, delete addresses
- **Address Validation**: Form validation with real-time feedback
- **Default Address**: Set and manage default address selection
- **Multi-Address Support**: Manage multiple delivery locations

```tsx
interface Address {
  id?: number
  name: string
  description: string
  address_template: string
  office_no_min: number
  office_no_max: number
  name_postfix: string
  phone_prefix: string
  pincode: string
  is_active: boolean
  is_default: boolean
}

export default function AddressesPage() {
  const [addresses, setAddresses] = useState<Address[]>([])
  const [showForm, setShowForm] = useState(false)
  const [editingAddress, setEditingAddress] = useState<Address | null>(null)

  const handleSave = async (addressData: Address) => {
    try {
      if (editingAddress) {
        await addressesService.update(editingAddress.id!, addressData)
        toast.success('Address updated successfully!')
      } else {
        await addressesService.create(addressData)
        toast.success('Address created successfully!')
      }
      fetchAddresses()
      setShowForm(false)
      setEditingAddress(null)
    } catch (error) {
      toast.error('Failed to save address')
    }
  }

  return (
    <div className="space-y-6">
      <AddressHeader onAdd={() => setShowForm(true)} />
      
      {showForm && (
        <AddressForm
          address={editingAddress}
          onSave={handleSave}
          onCancel={() => {
            setShowForm(false)
            setEditingAddress(null)
          }}
        />
      )}
      
      <AddressList
        addresses={addresses}
        onEdit={(address) => {
          setEditingAddress(address)
          setShowForm(true)
        }}
        onDelete={handleDelete}
        onSetDefault={handleSetDefault}
      />
    </div>
  )
}
```

### 👤 Account Management (`/dashboard/accounts/page.tsx`)
- **Flipkart Accounts**: Manage multiple Flipkart login credentials
- **Account Validation**: Test account credentials
- **Security**: Encrypted password storage
- **Status Tracking**: Active/inactive account management

### 🔧 Settings (`/dashboard/settings/page.tsx`)
- **System Configuration**: General automation settings only
- **Concurrency Limits**: Maximum parallel sessions
- **Timeout Settings**: Order processing timeouts
- **Retry Configuration**: Login attempt limits

Note: Address-related settings have been migrated to the dedicated Addresses page for better organization.

## 🔗 API Integration (`/lib/api.ts`)

### HTTP Client Configuration
```tsx
import axios from 'axios'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'

export const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
})

// Request interceptor for authentication
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('accessToken')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

// Response interceptor for error handling
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Handle unauthorized access
      localStorage.removeItem('accessToken')
      window.location.href = '/login'
    }
    return Promise.reject(error)
  }
)
```

### Service Layer
```tsx
// Authentication Service
export const authService = {
  login: async (credentials: LoginCredentials) => {
    const response = await apiClient.post('/api/auth/login', credentials)
    return response.data
  },
  
  logout: () => {
    localStorage.removeItem('accessToken')
    window.location.href = '/login'
  },
  
  getCurrentUser: async () => {
    const response = await apiClient.get('/api/auth/me')
    return response.data
  }
}

// Addresses Service
export const addressesService = {
  getAll: async (): Promise<Address[]> => {
    const response = await apiClient.get('/api/addresses/')
    return response.data
  },
  
  create: async (address: Omit<Address, 'id'>) => {
    const response = await apiClient.post('/api/addresses/', address)
    return response.data
  },
  
  update: async (id: number, address: Partial<Address>) => {
    const response = await apiClient.put(`/api/addresses/${id}`, address)
    return response.data
  },
  
  delete: async (id: number) => {
    await apiClient.delete(`/api/addresses/${id}`)
  },
  
  setDefault: async (id: number) => {
    const response = await apiClient.post(`/api/addresses/${id}/set-default`)
    return response.data
  }
}

// Automation Service
export const automationService = {
  startSession: async (data: AutomationRequest) => {
    const response = await apiClient.post('/api/automation/start', data)
    return response.data
  },
  
  getSessionStatus: async (sessionId: string) => {
    const response = await apiClient.get(`/api/automation/status/${sessionId}`)
    return response.data
  },
  
  stopSession: async (sessionId: string) => {
    await apiClient.post(`/api/automation/stop/${sessionId}`)
  },
  
  getHistory: async () => {
    const response = await apiClient.get('/api/automation/history')
    return response.data
  }
}
```

## 🎯 State Management

### Local State with React Hooks
```tsx
// Custom hook for automation sessions
export const useAutomationSessions = () => {
  const [sessions, setSessions] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)

  const fetchSessions = useCallback(async () => {
    try {
      setLoading(true)
      const data = await automationService.getHistory()
      setSessions(data)
      setError(null)
    } catch (err) {
      setError('Failed to fetch sessions')
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => {
    fetchSessions()
  }, [fetchSessions])

  return { sessions, loading, error, refetch: fetchSessions }
}
```

### Form State with React Hook Form
```tsx
import { useForm } from 'react-hook-form'

export const AddressForm = ({ address, onSave, onCancel }) => {
  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset
  } = useForm<Address>({
    defaultValues: address || {
      name: '',
      description: '',
      address_template: '',
      office_no_min: 1,
      office_no_max: 999,
      name_postfix: '',
      phone_prefix: '+91',
      pincode: '',
      is_active: true,
      is_default: false
    }
  })

  const onSubmit = async (data: Address) => {
    try {
      await onSave(data)
      reset()
    } catch (error) {
      toast.error('Failed to save address')
    }
  }

  return (
    <form onSubmit={handleSubmit(onSubmit)}>
      {/* Form fields with validation */}
    </form>
  )
}
```

## 🎨 Styling & Theming

### Tailwind Configuration
```js
// tailwind.config.js
module.exports = {
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        primary: {
          50: '#eff6ff',
          500: '#3b82f6',
          600: '#2563eb',
          700: '#1d4ed8',
        },
        gray: {
          50: '#f9fafb',
          100: '#f3f4f6',
          900: '#111827',
        }
      },
      fontFamily: {
        sans: ['Inter', 'sans-serif'],
      },
    },
  },
  plugins: [
    require('@tailwindcss/forms'),
  ],
}
```

### Global Styles
```css
/* app/globals.css */
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  html {
    font-family: 'Inter', sans-serif;
  }
  
  body {
    @apply bg-gray-50 text-gray-900;
  }
}

@layer components {
  .btn-primary {
    @apply bg-blue-600 hover:bg-blue-700 text-white font-medium py-2 px-4 rounded-md transition-colors;
  }
  
  .card {
    @apply bg-white rounded-lg shadow border border-gray-200 p-6;
  }
}
```

## 🔒 Authentication & Route Protection

### Protected Routes
```tsx
// app/dashboard/layout.tsx
import { redirect } from 'next/navigation'
import { getCurrentUser } from '@/lib/auth'

export default async function DashboardLayout({
  children,
}: {
  children: React.ReactNode
}) {
  const user = await getCurrentUser()
  
  if (!user) {
    redirect('/login')
  }

  return (
    <div className="min-h-screen bg-gray-50">
      <Navigation user={user} />
      <main className="py-10">
        <div className="mx-auto max-w-7xl px-4 sm:px-6 lg:px-8">
          {children}
        </div>
      </main>
    </div>
  )
}
```

### Login Form
```tsx
// app/login/page.tsx
export default function LoginPage() {
  const router = useRouter()
  const [loading, setLoading] = useState(false)
  
  const handleLogin = async (credentials: LoginCredentials) => {
    try {
      setLoading(true)
      const { access_token } = await authService.login(credentials)
      localStorage.setItem('accessToken', access_token)
      router.push('/dashboard')
      toast.success('Login successful!')
    } catch (error) {
      toast.error('Invalid credentials')
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-gray-50">
      <LoginForm onSubmit={handleLogin} loading={loading} />
    </div>
  )
}
```

## 📱 Responsive Design

### Mobile-First Approach
```tsx
// Responsive grid layouts
<div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
  {/* Cards adapt to screen size */}
</div>

// Navigation drawer for mobile
<div className="lg:hidden">
  <MobileNavigation />
</div>
<div className="hidden lg:block">
  <DesktopNavigation />
</div>
```

### Breakpoint Strategy
- **Mobile**: `< 768px` - Single column layout, drawer navigation
- **Tablet**: `768px - 1024px` - Two column layout, condensed navigation  
- **Desktop**: `> 1024px` - Multi-column layout, full sidebar navigation

## 🔔 Notifications & Feedback

### Toast Notifications
```tsx
import { toast } from 'sonner'

// Success notifications
toast.success('Address saved successfully!')

// Error notifications  
toast.error('Failed to start automation session')

// Loading notifications
const toastId = toast.loading('Starting automation...')
// Update later
toast.success('Automation started!', { id: toastId })
```

### Loading States
```tsx
const [loading, setLoading] = useState(false)

return (
  <Button disabled={loading}>
    {loading ? (
      <>
        <Spinner className="mr-2 h-4 w-4" />
        Processing...
      </>
    ) : (
      'Start Automation'
    )}
  </Button>
)
```

## 🧪 Testing Strategy

### Component Testing
```tsx
// __tests__/AddressForm.test.tsx
import { render, screen, fireEvent } from '@testing-library/react'
import { AddressForm } from '@/components/AddressForm'

describe('AddressForm', () => {
  it('renders form fields correctly', () => {
    render(<AddressForm onSave={jest.fn()} onCancel={jest.fn()} />)
    
    expect(screen.getByLabelText('Address Name')).toBeInTheDocument()
    expect(screen.getByLabelText('PIN Code')).toBeInTheDocument()
  })
  
  it('validates required fields', async () => {
    const mockSave = jest.fn()
    render(<AddressForm onSave={mockSave} onCancel={jest.fn()} />)
    
    fireEvent.click(screen.getByText('Save Address'))
    
    expect(await screen.findByText('Name is required')).toBeInTheDocument()
    expect(mockSave).not.toHaveBeenCalled()
  })
})
```

## 🚀 Development & Build

### Development Server
```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Open http://localhost:3000
```

### Production Build
```bash
# Build for production
npm run build

# Start production server
npm start

# Lint code
npm run lint
```

### Environment Variables
```env
# .env.local
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_APP_NAME="Flipkart Automation"
```

---

**📝 Last Updated**: January 2024  
**🔄 Framework Version**: Next.js 14  
**👨‍💻 Maintained by**: Frontend Development Team

For development setup and API integration, see the [Backend README](../backend/README.md)
