import axios from 'axios'

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL
      
// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
    'Accept': 'application/json',
  },
  withCredentials: true,
  timeout: 10000, // 10 second timeout
})

// Add auth token to requests
api.interceptors.request.use(
  (config) => {
    const token = localStorage.getItem('auth_token')
    if (token) {
      config.headers.Authorization = `Bearer ${token}`
    }
    return config
  },
  (error) => {
    return Promise.reject(error)
  }
)

// Add response interceptor for error handling
api.interceptors.response.use(
  (response) => {
    return response
  },
  (error) => {
    if (error.response?.status === 401) {
      // Clear auth token on 401 Unauthorized
      localStorage.removeItem('auth_token')
      // Redirect to login if not already on login page
      if (typeof window !== 'undefined' && !window.location.pathname.includes('/login')) {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

// Export the api instance for direct use
export { api }

// Auth service
export const authService = {
  login: async (credentials: { username: string; password: string }) => {
    const response = await api.post('/auth/login', credentials)
    return response.data
  },
  
  me: async () => {
    const response = await api.get('/auth/me')
    return response.data
  },
  
  refresh: async () => {
    const response = await api.post('/auth/refresh')
    return response.data
  }
}

// Products service
export const productsService = {
  getAll: async (params?: { skip?: number; limit?: number; active_only?: boolean }) => {
    const response = await api.get('/products', { params })
    return response.data
  },
  
  create: async (product: any) => {
    const response = await api.post('/products', product)
    return response.data
  },
  
  update: async (id: number, product: any) => {
    const response = await api.put(`/products/${id}`, product)
    return response.data
  },
  
  delete: async (id: number) => {
    const response = await api.delete(`/products/${id}`)
    return response.data
  },
  
}

// Orders service
export const ordersService = {
  getAll: async (params?: any) => {
    const response = await api.get('/orders', { params })
    return response.data
  },
  
}

// Flipkart users service
export const flipkartUsersService = {
  getAll: async (params?: { skip?: number; limit?: number }) => {
    const response = await api.get('/users/flipkart', { params })
    return response.data
  },
  
  create: async (user: any) => {
    const response = await api.post('/users/flipkart', user)
    return response.data
  },
  
  update: async (id: number, user: any) => {
    const response = await api.put(`/users/flipkart/${id}`, user)
    return response.data
  },
  
  delete: async (id: number) => {
    const response = await api.delete(`/users/flipkart/${id}`)
    return response.data
  },
  
  testLogin: async (id: number) => {
    const response = await api.post(`/users/flipkart/${id}/test-login`)
    return response.data
  }
}

// Automation service
export const automationService = {
  getSessions: async (params?: any) => {
    const response = await api.get('/automation/sessions', { params })
    return response.data
  },
  
  createSession: async (session: any) => {
    const response = await api.post('/automation/sessions', session)
    return response.data
  },
  
  stopSession: async (id: number) => {
    const response = await api.post(`/automation/sessions/${id}/stop`)
    return response.data
  },
  

  startAutomation: async (config: {
    batch_size: number;
    account_range_start: number;
    account_range_end: number;
    automation_type: string;
    view_mode: string;
  }) => {
    const response = await api.post('/automation/start-automation', config)
    return response.data
  },

  getJobStatus: async (jobId: number) => {
    const response = await api.get(`/automation/jobs/${jobId}/status`)
    return response.data
  },

  getJobLogs: async (jobId: number) => {
    const response = await api.get(`/automation/jobs/${jobId}/logs`)
    return response.data
  },

  getSessionJobs: async (sessionId: number) => {
    const response = await api.get(`/automation/sessions/${sessionId}/jobs`)
    return response.data
  }
}

// Settings service
export const settingsService = {
  getAll: async () => {
    const response = await api.get('/settings/')
    return response.data
  },
  
  update: async (settings: Record<string, string>) => {
    const response = await api.put('/settings/', settings)
    return response.data
  },
  
  getNames: async () => {
    const response = await api.get('/settings/names')
    return response.data
  },
  
  updateNames: async (names: string[]) => {
    const response = await api.put('/settings/names', { names })
    return response.data
  },
  
  clearNames: async () => {
    const response = await api.delete('/settings/names')
    return response.data
  }
}

// Addresses service
export const addressesService = {
  getAddresses: async () => {
    const response = await api.get('/addresses/')
    return response.data
  },
  
  createAddress: async (address: {
    name: string;
    description?: string;
    address_template: string;
    office_no_min: number;
    office_no_max: number;
    name_postfix: string;
    phone_prefix: string;
    pincode: string;
  }) => {
    const response = await api.post('/addresses/', address)
    return response.data
  },
  
  updateAddress: async (id: number, address: any) => {
    const response = await api.put(`/addresses/${id}`, address)
    return response.data
  },
  
  deleteAddress: async (id: number) => {
    const response = await api.delete(`/addresses/${id}`)
    return response.data
  },
  
  setDefaultAddress: async (id: number) => {
    const response = await api.post(`/addresses/${id}/set-default`)
    return response.data
  }
} 