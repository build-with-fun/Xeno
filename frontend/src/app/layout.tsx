import type { Metadata } from 'next'
import { Inter } from 'next/font/google'
import './globals.css'

const inter = Inter({ subsets: ['latin'] })

export const metadata: Metadata = {
  title: 'Xeno AI - Super Advanced Agent System',
  description: 'The most advanced AI agent system capable of doing anything',
}

export default function RootLayout({
  children,
}: {
  children: React.ReactNode
}) {
  return (
    <html lang="en">
      <body className={`${inter.className} animated-gradient grid-pattern`} suppressHydrationWarning>
        {children}
      </body>
    </html>
  )
}
