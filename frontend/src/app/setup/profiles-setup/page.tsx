'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

export default function ProfilesSetupPage() {
  const router = useRouter();
  const [activeTab, setActiveTab] = useState<'whatsapp' | 'chrome'>('whatsapp');
  const [isLoading, setIsLoading] = useState(false);
  const [whatsappConfigured, setWhatsappConfigured] = useState(false);
  const [chromeConfigured, setChromeConfigured] = useState(false);

  const handleConfigureWhatsApp = async () => {
    setIsLoading(true);
    // Simulate WhatsApp profile configuration
    setTimeout(() => {
      setWhatsappConfigured(true);
      setIsLoading(false);
    }, 2000);
  };

  const handleConfigureChrome = async () => {
    setIsLoading(true);
    // Simulate Chrome profile configuration
    setTimeout(() => {
      setChromeConfigured(true);
      setIsLoading(false);
    }, 2000);
  };

  const handleContinue = () => {
    router.push('/setup/ai-setup');
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="max-w-4xl w-full">
        <div className="glass-card p-10 card-hover">
          <h1 className="text-4xl font-bold mb-2 neon-text-cyan">Profiles Setup</h1>
          <p className="text-gray-400 mb-8">Configure your communication and browsing profiles</p>

          {/* Tabs */}
          <div className="flex gap-4 mb-8 border-b border-gray-700 pb-2">
            <button
              onClick={() => setActiveTab('whatsapp')}
              className={`px-6 py-3 rounded-lg transition-all ${
                activeTab === 'whatsapp'
                  ? 'bg-gradient-to-r from-green-500 to-green-600 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              📱 WhatsApp Profile
            </button>
            <button
              onClick={() => setActiveTab('chrome')}
              className={`px-6 py-3 rounded-lg transition-all ${
                activeTab === 'chrome'
                  ? 'bg-gradient-to-r from-blue-500 to-blue-600 text-white'
                  : 'text-gray-400 hover:text-white'
              }`}
            >
              🌐 Chrome Profile
            </button>
          </div>

          {activeTab === 'whatsapp' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="glass-card p-6">
                  <h3 className="text-xl font-semibold mb-4 neon-text-purple">WhatsApp Configuration</h3>
                  <p className="text-gray-400 mb-4">
                    Connect your WhatsApp account to let Xeno send and receive messages on your behalf.
                  </p>
                  
                  {!whatsappConfigured ? (
                    <button
                      onClick={handleConfigureWhatsApp}
                      disabled={isLoading}
                      className="btn-neon w-full"
                    >
                      {isLoading ? (
                        <span className="flex items-center justify-center">
                          <div className="spinner w-5 h-5 mr-2"></div>
                          Connecting...
                        </span>
                      ) : (
                        'Connect WhatsApp'
                      )}
                    </button>
                  ) : (
                    <div className="text-center p-4 bg-green-900 bg-opacity-30 rounded-lg border border-green-500">
                      <div className="text-3xl mb-2">✅</div>
                      <p className="text-green-400 font-semibold">WhatsApp Connected Successfully!</p>
                    </div>
                  )}
                </div>

                <div className="glass-card p-6">
                  <h3 className="text-xl font-semibold mb-4 neon-text-cyan">How It Works</h3>
                  <ul className="space-y-3 text-gray-400">
                    <li className="flex items-start">
                      <span className="mr-2">1.</span>
                      <span>Xeno will open WhatsApp Web in a controlled browser session</span>
                    </li>
                    <li className="flex items-start">
                      <span className="mr-2">2.</span>
                      <span>You'll scan the QR code with your phone</span>
                    </li>
                    <li className="flex items-start">
                      <span className="mr-2">3.</span>
                      <span>Xeno saves the session securely for future use</span>
                    </li>
                    <li className="flex items-start">
                      <span className="mr-2">4.</span>
                      <span>Send/receive messages through voice or text commands</span>
                    </li>
                  </ul>
                </div>
              </div>

              <div className="glass-card p-6 bg-opacity-30">
                <h4 className="font-semibold mb-3 neon-text-purple">🔒 Privacy & Security</h4>
                <p className="text-sm text-gray-400">
                  Your WhatsApp session is encrypted and stored locally. Xeno never sends your messages 
                  to external servers. All data remains on your device.
                </p>
              </div>
            </div>
          )}

          {activeTab === 'chrome' && (
            <div className="space-y-6">
              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                <div className="glass-card p-6">
                  <h3 className="text-xl font-semibold mb-4 neon-text-blue">Chrome Configuration</h3>
                  <p className="text-gray-400 mb-4">
                    Set up Chrome profile for web automation, browsing, and data extraction.
                  </p>
                  
                  {!chromeConfigured ? (
                    <button
                      onClick={handleConfigureChrome}
                      disabled={isLoading}
                      className="btn-neon w-full"
                    >
                      {isLoading ? (
                        <span className="flex items-center justify-center">
                          <div className="spinner w-5 h-5 mr-2"></div>
                          Setting Up...
                        </span>
                      ) : (
                        'Configure Chrome'
                      )}
                    </button>
                  ) : (
                    <div className="text-center p-4 bg-blue-900 bg-opacity-30 rounded-lg border border-blue-500">
                      <div className="text-3xl mb-2">✅</div>
                      <p className="text-blue-400 font-semibold">Chrome Profile Configured!</p>
                    </div>
                  )}
                </div>

                <div className="glass-card p-6">
                  <h3 className="text-xl font-semibold mb-4 neon-text-cyan">Capabilities</h3>
                  <ul className="space-y-3 text-gray-400">
                    <li className="flex items-start">
                      <span className="mr-2">•</span>
                      <span>Automated web browsing and form filling</span>
                    </li>
                    <li className="flex items-start">
                      <span className="mr-2">•</span>
                      <span>Web scraping and data extraction</span>
                    </li>
                    <li className="flex items-start">
                      <span className="mr-2">•</span>
                      <span>Screenshot capture and visual analysis</span>
                    </li>
                    <li className="flex items-start">
                      <span className="mr-2">•</span>
                      <span>Cookie and session management</span>
                    </li>
                    <li className="flex items-start">
                      <span className="mr-2">•</span>
                      <span>Multi-tab management and navigation</span>
                    </li>
                  </ul>
                </div>
              </div>

              <div className="glass-card p-6 bg-opacity-30">
                <h4 className="font-semibold mb-3 neon-text-blue">⚙️ Advanced Settings</h4>
                <div className="space-y-3 text-sm text-gray-400">
                  <div className="flex items-center justify-between">
                    <span>Headless Mode</span>
                    <input type="checkbox" className="toggle-neon" />
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Block Images</span>
                    <input type="checkbox" className="toggle-neon" />
                  </div>
                  <div className="flex items-center justify-between">
                    <span>Disable JavaScript</span>
                    <input type="checkbox" className="toggle-neon" />
                  </div>
                </div>
              </div>
            </div>
          )}

          {/* Navigation */}
          <div className="flex justify-between mt-10">
            <button
              onClick={() => router.push('/setup/user-setup')}
              className="px-6 py-3 rounded-lg border border-gray-600 hover:border-gray-400 transition-colors"
            >
              Back
            </button>

            <button
              onClick={handleContinue}
              className="btn-neon px-8 py-3"
            >
              Continue to AI Setup
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
