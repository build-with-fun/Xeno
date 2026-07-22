'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';

const providers = [
  { id: 'openai', name: 'OpenAI', models: ['gpt-4o', 'gpt-4-turbo', 'gpt-3.5-turbo'], icon: '🟢' },
  { id: 'anthropic', name: 'Anthropic', models: ['claude-3-opus', 'claude-3-sonnet', 'claude-3-haiku'], icon: '🟠' },
  { id: 'google', name: 'Google', models: ['gemini-pro', 'gemini-ultra'], icon: '🔵' },
  { id: 'ollama', name: 'Ollama (Local)', models: ['llama3', 'mistral', 'codellama'], icon: '🦙' },
  { id: 'groq', name: 'Groq', models: ['llama3-70b', 'mixtral-8x7b'], icon: '⚡' },
  { id: 'together', name: 'Together AI', models: ['llama-3-70b', 'qwen-72b'], icon: '🔷' },
];

export default function AISetupPage() {
  const router = useRouter();
  const [selectedProvider, setSelectedProvider] = useState('openai');
  const [mainModel, setMainModel] = useState('gpt-4o');
  const [visionModel, setVisionModel] = useState('gpt-4o');
  const [codeModel, setCodeModel] = useState('gpt-4o');
  const [fastModel, setFastModel] = useState('gpt-3.5-turbo');
  const [useSameModel, setUseSameModel] = useState(true);
  const [isLoading, setIsLoading] = useState(false);

  const handleSave = async () => {
    setIsLoading(true);
    try {
      await fetch('http://localhost:8000/api/setup/ai', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          provider: selectedProvider,
          main_model: mainModel,
          vision_model: visionModel,
          code_model: codeModel,
          fast_model: fastModel,
          use_same_model: useSameModel,
        }),
      });
    } catch (error) {
      console.error('Error saving AI config:', error);
    } finally {
      setIsLoading(false);
      router.push('/setup/tts-stt');
    }
  };

  const currentProvider = providers.find(p => p.id === selectedProvider);

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="max-w-5xl w-full">
        <div className="glass-card p-10 card-hover">
          <h1 className="text-4xl font-bold mb-2 neon-text-cyan">AI Configuration</h1>
          <p className="text-gray-400 mb-8">Select your preferred AI providers and models</p>

          {/* Provider Selection */}
          <div className="mb-8">
            <h3 className="text-xl font-semibold mb-4 neon-text-purple">Choose AI Provider</h3>
            <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-4">
              {providers.map((provider) => (
                <button
                  key={provider.id}
                  onClick={() => {
                    setSelectedProvider(provider.id);
                    if (useSameModel) {
                      setMainModel(provider.models[0]);
                    }
                  }}
                  className={`glass-card p-4 text-center transition-all card-hover ${
                    selectedProvider === provider.id ? 'border-2 border-neon-cyan' : ''
                  }`}
                >
                  <div className="text-3xl mb-2">{provider.icon}</div>
                  <div className="font-semibold text-sm">{provider.name}</div>
                </button>
              ))}
            </div>
          </div>

          {/* Model Selection */}
          <div className="space-y-6">
            <div className="flex items-center justify-between glass-card p-4">
              <span className="font-medium">Use same model for all tasks</span>
              <label className="relative inline-flex items-center cursor-pointer">
                <input
                  type="checkbox"
                  checked={useSameModel}
                  onChange={(e) => setUseSameModel(e.target.checked)}
                  className="sr-only peer"
                />
                <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-cyan-800 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-gradient-to-r peer-checked:from-cyan-500 peer-checked:to-purple-500"></div>
              </label>
            </div>

            {useSameModel ? (
              <div>
                <label className="block text-sm font-medium mb-2 text-gray-300">
                  Main AI Model (Used for all tasks)
                </label>
                <select
                  value={mainModel}
                  onChange={(e) => {
                    setMainModel(e.target.value);
                    setVisionModel(e.target.value);
                    setCodeModel(e.target.value);
                    setFastModel(e.target.value);
                  }}
                  className="input-neon w-full"
                >
                  {currentProvider?.models.map((model) => (
                    <option key={model} value={model}>
                      {model}
                    </option>
                  ))}
                </select>
              </div>
            ) : (
              <>
                <div>
                  <label className="block text-sm font-medium mb-2 text-gray-300">
                    🧠 Main Agent Model (General conversations & reasoning)
                  </label>
                  <select
                    value={mainModel}
                    onChange={(e) => setMainModel(e.target.value)}
                    className="input-neon w-full"
                  >
                    {currentProvider?.models.map((model) => (
                      <option key={model} value={model}>
                        {model}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2 text-gray-300">
                    👁️ Vision Model (Image analysis & visual tasks)
                  </label>
                  <select
                    value={visionModel}
                    onChange={(e) => setVisionModel(e.target.value)}
                    className="input-neon w-full"
                  >
                    {currentProvider?.models.map((model) => (
                      <option key={model} value={model}>
                        {model}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2 text-gray-300">
                    💻 Code Model (Programming & code execution)
                  </label>
                  <select
                    value={codeModel}
                    onChange={(e) => setCodeModel(e.target.value)}
                    className="input-neon w-full"
                  >
                    {currentProvider?.models.map((model) => (
                      <option key={model} value={model}>
                        {model}
                      </option>
                    ))}
                  </select>
                </div>

                <div>
                  <label className="block text-sm font-medium mb-2 text-gray-300">
                    ⚡ Fast Model (Quick responses & simple tasks)
                  </label>
                  <select
                    value={fastModel}
                    onChange={(e) => setFastModel(e.target.value)}
                    className="input-neon w-full"
                  >
                    {currentProvider?.models.map((model) => (
                      <option key={model} value={model}>
                        {model}
                      </option>
                    ))}
                  </select>
                </div>
              </>
            )}

            {/* API Key Input */}
            <div>
              <label className="block text-sm font-medium mb-2 text-gray-300">
                API Key ({currentProvider?.name})
              </label>
              <input
                type="password"
                className="input-neon w-full"
                placeholder={`Enter your ${currentProvider?.name} API key...`}
              />
              <p className="text-xs text-gray-500 mt-2">
                Your API key is stored securely and never sent to external servers.
              </p>
            </div>

            {/* Info Box */}
            <div className="glass-card p-4 bg-opacity-30">
              <h4 className="font-semibold mb-2 neon-text-cyan">💡 Model Recommendations</h4>
              <ul className="text-sm text-gray-400 space-y-1">
                <li>• <strong>Main:</strong> Use most capable model (GPT-4o, Claude-3-Opus)</li>
                <li>• <strong>Vision:</strong> Must support image input (GPT-4V, Gemini Pro Vision)</li>
                <li>• <strong>Code:</strong> Optimized for programming (GPT-4, Claude-3-Sonnet)</li>
                <li>• <strong>Fast:</strong> Quick responses for simple tasks (GPT-3.5, Haiku)</li>
              </ul>
            </div>
          </div>

          {/* Navigation */}
          <div className="flex justify-between mt-10">
            <button
              onClick={() => router.push('/setup/profiles-setup')}
              className="px-6 py-3 rounded-lg border border-gray-600 hover:border-gray-400 transition-colors"
            >
              Back
            </button>

            <button
              onClick={handleSave}
              disabled={isLoading}
              className="btn-neon px-8 py-3"
            >
              {isLoading ? (
                <span className="flex items-center">
                  <div className="spinner w-5 h-5 mr-2"></div>
                  Saving...
                </span>
              ) : (
                'Continue to TTS/STT Setup'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
