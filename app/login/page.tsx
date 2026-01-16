'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { toast } from 'react-hot-toast'
import { authService } from '@/lib/api'
import { Eye, EyeOff, ShoppingCart, Shield, ArrowRight, CheckCircle2 } from 'lucide-react'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'

export default function LoginPage() {
  const [credentials, setCredentials] = useState({
    username: '',
    password: ''
  })
  const [showPassword, setShowPassword] = useState(false)
  const [isLoading, setIsLoading] = useState(false)
  const router = useRouter()

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)

    try {
      const response = await authService.login(credentials)
      localStorage.setItem('auth_token', response.access_token)
      localStorage.setItem('user', JSON.stringify(response.user))

      toast.success('Welcome back!')
      router.push('/dashboard/automation')
    } catch (error: any) {
      toast.error(error.response?.data?.detail || 'Login failed')
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <div className="min-h-screen flex bg-white text-secondary-900">
      {/* Left Side - Decorative */}
      <div className="hidden lg:flex lg:w-1/2 bg-gradient-to-br from-primary-900 to-primary-800 text-white p-12 flex-col justify-between relative overflow-hidden">
        <div className="absolute inset-0 bg-[url('https://www.transparenttextures.com/patterns/cubes.png')] opacity-10"></div>
        <div className="absolute top-0 right-0 -mt-20 -mr-20 w-96 h-96 bg-primary-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse-slow"></div>
        <div className="absolute bottom-0 left-0 -mb-20 -ml-20 w-96 h-96 bg-secondary-500 rounded-full mix-blend-multiply filter blur-3xl opacity-20 animate-pulse-slow" style={{ animationDelay: '1s' }}></div>

        <div className="relative z-10">
          <div className="flex items-center space-x-3">
            <div className="bg-white/10 p-2 rounded-lg backdrop-blur-sm">
              <ShoppingCart className="h-8 w-8 text-white" />
            </div>
            <span className="text-2xl font-bold tracking-tight">FlipkartBot</span>
          </div>
        </div>

        <div className="relative z-10 max-w-md">
          <h1 className="text-5xl font-bold mb-6 leading-tight">
            Automate your <br />
            <span className="text-primary-200">Flipkart Orders</span>
          </h1>
          <p className="text-primary-100 text-lg mb-8 leading-relaxed">
            Streamline your purchasing workflow with our advanced automation dashboard. Manage multiple accounts, track orders, and optimize your efficiency.
          </p>

          <div className="space-y-4">
            {[
              'Multi-account management',
              'Automated order processing',
              'Real-time status tracking',
              'Secure & reliable execution'
            ].map((feature, i) => (
              <div key={i} className="flex items-center space-x-3 text-primary-50">
                <CheckCircle2 className="h-5 w-5 text-primary-300" />
                <span>{feature}</span>
              </div>
            ))}
          </div>
        </div>

        <div className="relative z-10 text-primary-200 text-sm">
          © {new Date().getFullYear()} Flipkart Automation. All rights reserved.
        </div>
      </div>

      {/* Right Side - Form */}
      <div className="flex-1 flex items-center justify-center p-8 sm:p-12 lg:p-16 bg-secondary-50/30">
        <div className="w-full max-w-md space-y-8 bg-white p-8 rounded-2xl shadow-premium-lg border border-secondary-100">
          <div className="text-center lg:text-left">
            <div className="lg:hidden mx-auto h-12 w-12 bg-primary-600 rounded-xl flex items-center justify-center mb-4 shadow-lg shadow-primary-600/20">
              <ShoppingCart className="h-6 w-6 text-white" />
            </div>
            <h2 className="text-3xl font-bold text-secondary-900 tracking-tight">
              Welcome back
            </h2>
            <p className="mt-2 text-secondary-500">
              Please sign in to your account to continue
            </p>
          </div>

          <form className="space-y-6" onSubmit={handleSubmit}>
            <div className="space-y-2">
              <Label htmlFor="username">Username</Label>
              <Input
                id="username"
                name="username"
                type="text"
                required
                placeholder="Enter your username"
                value={credentials.username}
                onChange={(e) => setCredentials(prev => ({ ...prev, username: e.target.value }))}
                className="h-11"
              />
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">Password</Label>
              <div className="relative">
                <Input
                  id="password"
                  name="password"
                  type={showPassword ? 'text' : 'password'}
                  required
                  placeholder="Enter your password"
                  value={credentials.password}
                  onChange={(e) => setCredentials(prev => ({ ...prev, password: e.target.value }))}
                  className="h-11 pr-10"
                />
                <button
                  type="button"
                  className="absolute inset-y-0 right-0 pr-3 flex items-center text-secondary-400 hover:text-secondary-600 transition-colors"
                  onClick={() => setShowPassword(!showPassword)}
                >
                  {showPassword ? (
                    <EyeOff className="h-5 w-5" />
                  ) : (
                    <Eye className="h-5 w-5" />
                  )}
                </button>
              </div>
            </div>

            <Button
              type="submit"
              disabled={isLoading}
              className="w-full h-11 text-base shadow-premium-md hover:shadow-premium-lg transition-all duration-300"
            >
              {isLoading ? (
                <div className="flex items-center justify-center">
                  <div className="loading-spinner h-5 w-5 border-2 border-white border-t-transparent rounded-full mr-2"></div>
                  Signing in...
                </div>
              ) : (
                <div className="flex items-center justify-center">
                  Sign in
                  <ArrowRight className="ml-2 h-4 w-4" />
                </div>
              )}
            </Button>
          </form>

          <div className="relative">
            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-secondary-200"></div>
            </div>
            <div className="relative flex justify-center text-sm">
              <span className="px-2 bg-white text-secondary-500 flex items-center gap-1">
                <Shield className="h-3 w-3" />
                Secure Access
              </span>
            </div>
          </div>

          <div className="bg-secondary-50 rounded-lg p-4 border border-secondary-100">
            <div className="text-sm text-secondary-600 text-center">
              <p className="font-medium mb-1">Demo Credentials</p>
              <code className="bg-white px-2 py-1 rounded border border-secondary-200 text-primary-700 font-mono text-xs">
                admin / admin123
              </code>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
} 