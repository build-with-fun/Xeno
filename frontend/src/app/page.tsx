'use client';

import React from 'react';
import { Sidebar } from '@/components/Sidebar/Sidebar';
import { Dashboard } from '@/components/Dashboard/Dashboard';
import { ChatInterface } from '@/components/Chat/ChatInterface';
import { websocketService } from '@/hooks/use-websocket';
import { useEffect, useState } from 'react';

export default function Home() {
  const [activeTab, setActiveTab] = useState('dashboard');
  const [isClient, setIsClient] = useState(false);

  useEffect(() => {
    setIsClient(true);
    
    // Connect to WebSocket on mount
    websocketService.connect();
    
    // Cleanup on unmount
    return () => {
      websocketService.disconnect();
    };
  }, []);

  if (!isClient) {
    return (
      <div className="h-screen w-full bg-background flex items-center justify-center">
        <div className="text-center">
          <div className="w-16 h-16 mx-auto mb-4 relative">
            <div className="absolute inset-0 bg-gradient-to-br from-xenoblue via-xenopurple to-xenogreen rounded-full animate-spin" />
            <div className="absolute inset-2 bg-background rounded-full flex items-center justify-center">
              <div className="w-8 h-8 border-2 border-xenoblue border-t-transparent rounded-full animate-spin" />
            </div>
          </div>
          <p className="text-muted-foreground">Initializing Xeno AI...</p>
        </div>
      </div>
    );
  }

  const renderContent = () => {
    switch (activeTab) {
      case 'dashboard':
        return <Dashboard />;
      case 'chat':
        return <ChatInterface />;
      case 'tasks':
        return (
          <div className="p-6">
            <h2 className="text-2xl font-bold mb-4">Task Manager</h2>
            <p className="text-muted-foreground">Coming soon...</p>
          </div>
        );
      case 'memory':
        return (
          <div className="p-6">
            <h2 className="text-2xl font-bold mb-4">Memory Explorer</h2>
            <p className="text-muted-foreground">Coming soon...</p>
          </div>
        );
      case 'voice':
        return (
          <div className="p-6">
            <h2 className="text-2xl font-bold mb-4">Voice Control</h2>
            <p className="text-muted-foreground">Coming soon...</p>
          </div>
        );
      case 'logs':
        return (
          <div className="p-6">
            <h2 className="text-2xl font-bold mb-4">System Logs</h2>
            <p className="text-muted-foreground">Coming soon...</p>
          </div>
        );
      case 'settings':
        return (
          <div className="p-6">
            <h2 className="text-2xl font-bold mb-4">Settings</h2>
            <p className="text-muted-foreground">Coming soon...</p>
          </div>
        );
      default:
        return <Dashboard />;
    }
  };

  return (
    <div className="h-screen w-full flex bg-background overflow-hidden">
      {/* Sidebar */}
      <Sidebar activeTab={activeTab} setActiveTab={setActiveTab} />
      
      {/* Main Content */}
      <main className="flex-1 overflow-hidden">
        {renderContent()}
      </main>
    </div>
  );
}
