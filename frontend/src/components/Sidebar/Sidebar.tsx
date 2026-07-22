'use client';

import React from 'react';
import { useAppStore } from '@/store/app-store';
import { 
  LayoutDashboard, 
  MessageSquare, 
  CheckSquare, 
  Brain, 
  Settings, 
  Terminal,
  Mic,
  User,
  Zap,
  FolderOpen,
  Bot
} from 'lucide-react';

interface NavItemProps {
  icon: React.ReactNode;
  label: string;
  active?: boolean;
  onClick?: () => void;
}

function NavItem({ icon, label, active, onClick }: NavItemProps) {
  return (
    <button
      onClick={onClick}
      className={`w-full flex items-center gap-3 px-4 py-3 rounded-xl transition-all duration-300 ${
        active
          ? 'bg-gradient-to-r from-xenoblue/20 to-xenopurple/20 text-white border border-xenoblue/50'
          : 'text-muted-foreground hover:text-foreground hover:bg-muted/50'
      }`}
    >
      {icon}
      <span className="font-medium">{label}</span>
      {active && (
        <div className="ml-auto w-1.5 h-1.5 rounded-full bg-xenoblue glow-blue" />
      )}
    </button>
  );
}

interface SidebarProps {
  activeTab: string;
  setActiveTab: (tab: string) => void;
}

export function Sidebar({ activeTab, setActiveTab }: SidebarProps) {
  const agents = useAppStore((state) => state.agents);
  const tasks = useAppStore((state) => state.tasks);
  
  const runningTasks = tasks.filter(t => t.status === 'running').length;

  const navItems = [
    { id: 'dashboard', icon: <LayoutDashboard className="w-5 h-5" />, label: 'Dashboard' },
    { id: 'chat', icon: <MessageSquare className="w-5 h-5" />, label: 'Chat' },
    { id: 'tasks', icon: <CheckSquare className="w-5 h-5" />, label: 'Tasks', badge: runningTasks > 0 ? runningTasks : undefined },
    { id: 'memory', icon: <Brain className="w-5 h-5" />, label: 'Memory Explorer' },
    { id: 'voice', icon: <Mic className="w-5 h-5" />, label: 'Voice Control' },
    { id: 'logs', icon: <Terminal className="w-5 h-5" />, label: 'System Logs' },
    { id: 'settings', icon: <Settings className="w-5 h-5" />, label: 'Settings' },
  ];

  return (
    <div className="w-72 h-full flex flex-col glass border-r border-border">
      {/* Logo */}
      <div className="p-6 border-b border-border">
        <div className="flex items-center gap-3">
          <div className="relative w-12 h-12">
            <div className="absolute inset-0 bg-gradient-to-br from-xenoblue via-xenopurple to-xenogreen rounded-xl animate-gradient" />
            <div className="absolute inset-1 bg-background rounded-lg flex items-center justify-center">
              <Bot className="w-6 h-6 text-foreground" />
            </div>
          </div>
          <div>
            <h1 className="text-xl font-bold gradient-text">XENO AI</h1>
            <p className="text-xs text-muted-foreground">v3.0 Super Advanced</p>
          </div>
        </div>
      </div>

      {/* Quick Stats */}
      <div className="p-4 border-b border-border">
        <div className="grid grid-cols-2 gap-2">
          <div className="text-center p-3 bg-muted/30 rounded-lg">
            <Zap className="w-4 h-4 mx-auto text-xenoblue mb-1" />
            <div className="text-lg font-bold">{agents.length}</div>
            <div className="text-xs text-muted-foreground">Agents</div>
          </div>
          <div className="text-center p-3 bg-muted/30 rounded-lg">
            <FolderOpen className="w-4 h-4 mx-auto text-xenogreen mb-1" />
            <div className="text-lg font-bold">{tasks.length}</div>
            <div className="text-xs text-muted-foreground">Tasks</div>
          </div>
        </div>
      </div>

      {/* Navigation */}
      <nav className="flex-1 p-4 space-y-2 overflow-y-auto">
        {navItems.map((item) => (
          <div key={item.id} className="relative">
            <NavItem
              icon={item.icon}
              label={item.label}
              active={activeTab === item.id}
              onClick={() => setActiveTab(item.id)}
            />
            {item.badge && item.badge > 0 && (
              <span className="absolute right-4 top-3 px-2 py-0.5 text-xs font-bold bg-xenored text-white rounded-full">
                {item.badge}
              </span>
            )}
          </div>
        ))}
      </nav>

      {/* User Profile */}
      <div className="p-4 border-t border-border">
        <div className="flex items-center gap-3 p-3 rounded-xl bg-muted/30 hover:bg-muted/50 transition-colors cursor-pointer">
          <div className="w-10 h-10 rounded-full bg-gradient-to-br from-xenoblue to-xenopurple flex items-center justify-center">
            <User className="w-5 h-5 text-white" />
          </div>
          <div className="flex-1">
            <div className="font-medium text-sm">Admin User</div>
            <div className="text-xs text-muted-foreground">Full Access</div>
          </div>
        </div>
      </div>
    </div>
  );
}
