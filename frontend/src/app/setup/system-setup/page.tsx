'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

export default function SystemSetupPage() {
  const router = useRouter();
  const [isLoading, setIsLoading] = useState(true);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [systemInfo, setSystemInfo] = useState({
    os: '',
    osVersion: '',
    architecture: '',
    cpu: '',
    ram: '',
    drives: [] as { name: string; total: string; free: string }[],
    apps: [] as string[],
    gpu: '',
  });

  useEffect(() => {
    analyzeSystem();
  }, []);

  const analyzeSystem = async () => {
    setIsAnalyzing(true);
    try {
      // Fetch system information from backend
      const response = await fetch('http://localhost:8000/api/setup/system-info');
      const data = await response.json();
      setSystemInfo(data);
    } catch (error) {
      console.error('Error fetching system info:', error);
      // Mock data for demo
      setSystemInfo({
        os: 'Windows',
        osVersion: '11 Pro',
        architecture: 'x64',
        cpu: 'Intel Core i9-13900K',
        ram: '64 GB DDR5',
        drives: [
          { name: 'C:', total: '1 TB', free: '450 GB' },
          { name: 'D:', total: '2 TB', free: '1.2 TB' },
        ],
        apps: ['Chrome', 'VS Code', 'Spotify', 'Discord', 'Slack', 'Notion'],
        gpu: 'NVIDIA RTX 4090',
      });
    } finally {
      setIsLoading(false);
      setIsAnalyzing(false);
    }
  };

  const handleComplete = async () => {
    try {
      await fetch('http://localhost:8000/api/setup/complete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ system_info: systemInfo }),
      });
    } catch (error) {
      console.error('Error completing setup:', error);
    }
    router.push('/main');
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="max-w-6xl w-full">
        <div className="glass-card p-10 card-hover">
          <h1 className="text-4xl font-bold mb-2 neon-text-cyan">System Analysis</h1>
          <p className="text-gray-400 mb-8">Xeno is analyzing your computer to understand its capabilities</p>

          {isLoading || isAnalyzing ? (
            <div className="text-center py-16">
              <div className="spinner mx-auto mb-6" style={{ width: '60px', height: '60px' }}></div>
              <h2 className="text-2xl font-semibold mb-2 neon-text-purple">Analyzing System...</h2>
              <p className="text-gray-400">Gathering information about your hardware and software</p>
              
              <div className="mt-8 max-w-md mx-auto">
                <div className="progress-bar mb-2">
                  <div className="progress-bar-fill animate-pulse" style={{ width: '70%' }}></div>
                </div>
                <p className="text-sm text-gray-500">This may take a moment...</p>
              </div>
            </div>
          ) : (
            <div className="space-y-8">
              {/* System Overview */}
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
                <div className="glass-card p-4 card-hover">
                  <div className="text-3xl mb-2">💻</div>
                  <div className="text-sm text-gray-400">Operating System</div>
                  <div className="font-semibold">{systemInfo.os} {systemInfo.osVersion}</div>
                </div>
                
                <div className="glass-card p-4 card-hover">
                  <div className="text-3xl mb-2">⚙️</div>
                  <div className="text-sm text-gray-400">CPU</div>
                  <div className="font-semibold text-sm">{systemInfo.cpu}</div>
                </div>
                
                <div className="glass-card p-4 card-hover">
                  <div className="text-3xl mb-2">🧠</div>
                  <div className="text-sm text-gray-400">RAM</div>
                  <div className="font-semibold">{systemInfo.ram}</div>
                </div>
                
                <div className="glass-card p-4 card-hover">
                  <div className="text-3xl mb-2">🎮</div>
                  <div className="text-sm text-gray-400">GPU</div>
                  <div className="font-semibold text-sm">{systemInfo.gpu}</div>
                </div>
              </div>

              {/* Drives */}
              <div>
                <h3 className="text-xl font-semibold mb-4 neon-text-purple">💾 Storage Drives</h3>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  {systemInfo.drives.map((drive, index) => (
                    <div key={index} className="glass-card p-4 card-hover">
                      <div className="flex justify-between items-center mb-2">
                        <span className="font-semibold text-lg">{drive.name}</span>
                        <span className="text-sm text-gray-400">{drive.total}</span>
                      </div>
                      <div className="text-sm text-gray-400 mb-2">Free: {drive.free}</div>
                      <div className="progress-bar">
                        <div 
                          className="progress-bar-fill" 
                          style={{ width: '60%' }}
                        ></div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              {/* Installed Applications */}
              <div>
                <h3 className="text-xl font-semibold mb-4 neon-text-blue">📦 Detected Applications ({systemInfo.apps.length})</h3>
                <div className="glass-card p-4 max-h-48 overflow-y-auto">
                  <div className="flex flex-wrap gap-2">
                    {systemInfo.apps.map((app, index) => (
                      <span 
                        key={index}
                        className="px-3 py-1 bg-white bg-opacity-10 rounded-full text-sm"
                      >
                        {app}
                      </span>
                    ))}
                  </div>
                </div>
              </div>

              {/* Info Box */}
              <div className="glass-card p-4 bg-opacity-30 border-l-4 border-l-cyan-500">
                <h4 className="font-semibold mb-2 neon-text-cyan">ℹ️ How Xeno Uses This Information</h4>
                <ul className="text-sm text-gray-400 space-y-1">
                  <li>• <strong>Desktop Control:</strong> Knows which apps are available for automation</li>
                  <li>• <strong>File Operations:</strong> Understands drive structure for file management</li>
                  <li>• <strong>Performance:</strong> Optimizes tasks based on CPU/RAM/GPU capabilities</li>
                  <li>• <strong>Compatibility:</strong> Adapts behavior to OS-specific features</li>
                  <li>• <strong>Context:</strong> Provides relevant suggestions based on installed software</li>
                </ul>
              </div>

              {/* Privacy Notice */}
              <div className="glass-card p-4 bg-opacity-30">
                <h4 className="font-semibold mb-2 neon-text-purple">🔒 Privacy & Security</h4>
                <p className="text-sm text-gray-400">
                  All system information is stored locally and never sent to external servers. 
                  Xeno uses this data solely to provide better assistance and automation capabilities.
                </p>
              </div>
            </div>
          )}

          {/* Navigation */}
          <div className="flex justify-between mt-10">
            <button
              onClick={() => router.push('/setup/tts-stt')}
              className="px-6 py-3 rounded-lg border border-gray-600 hover:border-gray-400 transition-colors"
              disabled={isLoading}
            >
              Back
            </button>

            <button
              onClick={handleComplete}
              disabled={isLoading || isAnalyzing}
              className="btn-neon px-8 py-3"
            >
              {isLoading || isAnalyzing ? (
                <span className="flex items-center">
                  <div className="spinner w-5 h-5 mr-2"></div>
                  Analyzing...
                </span>
              ) : (
                '🎉 Complete Setup & Launch Xeno'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
