import './globals.css'
import { Inter } from 'next/font/google'
import Toaster from '@/components/Toaster'

const inter = Inter({ subsets: ['latin'] })

export const metadata = {
  title: 'Flipkart Automation Dashboard',
  description: 'Automated Flipkart ordering system with multi-account management',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={inter.className}>
        <div className="min-h-screen bg-gradient-to-br from-secondary-50 to-primary-50">
          {children}
        </div>
        <Toaster />
      </body>
    </html>
  )
} 