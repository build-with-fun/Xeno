'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function GetStartedPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(false);

  const handleStart = () => {
    setIsLoading(true);
    setTimeout(() => {
      router.push('/setup/user-setup');
    }, 500);
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="max-w-2xl w-full">
        <div className="glass-card p-12 text-center card-hover">
          {/* Logo/Icon */}
          <div className="orb-container mx-auto mb-8">
            <div className="orb"></div>
          </div>

          <h1 className="text-5xl font-bold mb-6 neon-text-cyan">
            Welcome to Xeno AI
          </h1>
          
          <p className="text-xl text-gray-300 mb-8 leading-relaxed">
            The most advanced AI agent system ever created. 
            Capable of doing anything you ask - from controlling your computer 
            to managing your entire digital life.
          </p>

          <div className="grid grid-cols-1 md:grid-cols-3 gap-6 mb-10">
            <div className="glass-card p-6 card-hover">
              <div className="text-4xl mb-3">🚀</div>
              <h3 className="font-semibold text-lg mb-2 neon-text-purple">Super Fast</h3>
              <p className="text-sm text-gray-400">Lightning-fast response times with intelligent task routing</p>
            </div>
            
            <div className="glass-card p-6 card-hover">
              <div className="text-4xl mb-3">🧠</div>
              <h3 className="font-semibold text-lg mb-2 neon-text-cyan">9-Tier Memory</h3>
              <p className="text-sm text-gray-400">Advanced memory system from sensory to metacognitive</p>
            </div>
            
            <div className="glass-card p-6 card-hover">
              <div className="text-4xl mb-3">⚡</div>
              <h3 className="font-semibold text-lg mb-2 neon-text-purple">Self-Improving</h3>
              <p className="text-sm text-gray-400">Automatically rewrites and enhances its own code</p>
            </div>
          </div>

          <div className="space-y-4">
            <button 
              onClick={handleStart}
              disabled={isLoading}
              className="btn-neon w-full md:w-auto px-12 py-4 text-lg"
            >
              {isLoading ? (
                <span className="flex items-center justify-center">
                  <div className="spinner w-5 h-5 mr-3"></div>
                  Starting...
                </span>
              ) : (
                'Get Started'
              )}
            </button>
            
            <p className="text-sm text-gray-500 mt-6">
              This setup will only take a few minutes. Let's configure your super advanced AI agent.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
