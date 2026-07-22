'use client';

import Link from 'next/link';
import { usePathname } from 'next/navigation';

const navItems = [
  { href: '/main', label: '🎤 Voice', icon: '🎤' },
  { href: '/workspace', label: 'Workspace', icon: '💼' },
  { href: '/agents', label: 'Agents', icon: '🤖' },
  { href: '/plugins', label: 'Plugins', icon: '🔌' },
  { href: '/memory', label: 'Memory', icon: '🧠' },
  { href: '/settings', label: 'Settings', icon: '⚙️' },
  { href: '/scheduler', label: 'Scheduler', icon: '📅' },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <div className="w-20 glass-card m-4 p-2 flex flex-col items-center">
      {/* Logo */}
      <div className="mb-6">
        <div className="w-12 h-12 rounded-full bg-gradient-to-br from-cyan-500 to-purple-600 flex items-center justify-center text-xl font-bold">
          X
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 space-y-2">
        {navItems.map((item) => (
          <Link
            key={item.href}
            href={item.href}
            className={`block p-3 rounded-xl transition-all group relative ${
              pathname === item.href
                ? 'bg-gradient-to-r from-cyan-600 to-purple-600'
                : 'hover:bg-white hover:bg-opacity-10'
            }`}
          >
            <span className="text-2xl">{item.icon}</span>
            
            {/* Tooltip */}
            <span className="absolute left-full ml-2 px-2 py-1 bg-gray-900 text-white text-sm rounded opacity-0 group-hover:opacity-100 transition-opacity whitespace-nowrap pointer-events-none z-50">
              {item.label}
            </span>
          </Link>
        ))}
      </nav>

      {/* User Profile */}
      <div className="mt-auto pt-4 border-t border-white border-opacity-10">
        <div className="w-10 h-10 rounded-full bg-gradient-to-br from-green-400 to-blue-500 flex items-center justify-center text-sm font-bold cursor-pointer hover:scale-110 transition-transform">
          U
        </div>
      </div>
    </div>
  );
}
