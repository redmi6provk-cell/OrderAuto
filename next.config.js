/** @type {import('next').NextConfig} */
const isDev = process.env.NODE_ENV !== 'production'

// Optionally allow configuring backend base via env var. Example:
// API_BASE_URL=http://147.93.31.160:8000
const API_BASE_URL = process.env.API_BASE_URL || 'http://localhost:8000'

const nextConfig = {
  async rewrites() {
    // Only add a rewrite when running the Next.js dev server or when explicitly configured.
    // In production, clients should call the API directly using NEXT_PUBLIC_API_URL.
    if (isDev) {
      return [
        {
          source: '/api/:path*',
          destination: `${API_BASE_URL}/api/:path*`,
        },
      ]
    }
    return []
  },
}

module.exports = nextConfig