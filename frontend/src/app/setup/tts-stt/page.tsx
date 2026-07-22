'use client';

import { useState, useEffect } from 'react';
import { useRouter } from 'next/navigation';

const geminiTTSModels = [
  { id: 'gemini-tts-fast', name: 'Gemini TTS Fast', latency: '~200ms', quality: 'Good' },
  { id: 'gemini-tts-standard', name: 'Gemini TTS Standard', latency: '~400ms', quality: 'Better' },
  { id: 'gemini-tts-premium', name: 'Gemini TTS Premium', latency: '~600ms', quality: 'Best' },
];

const voices = [
  { id: 'en-US-1', name: 'Emma (Female)', language: 'English US', gender: 'Female' },
  { id: 'en-US-2', name: 'James (Male)', language: 'English US', gender: 'Male' },
  { id: 'en-GB-1', name: 'Oliver (Male)', language: 'English UK', gender: 'Male' },
  { id: 'en-GB-2', name: 'Sophie (Female)', language: 'English UK', gender: 'Female' },
  { id: 'es-ES-1', name: 'Lucia (Female)', language: 'Spanish', gender: 'Female' },
  { id: 'fr-FR-1', name: 'Pierre (Male)', language: 'French', gender: 'Male' },
  { id: 'de-DE-1', name: 'Hans (Male)', language: 'German', gender: 'Male' },
  { id: 'ja-JP-1', name: 'Sakura (Female)', language: 'Japanese', gender: 'Female' },
  { id: 'zh-CN-1', name: 'Li Wei (Male)', language: 'Chinese', gender: 'Male' },
  { id: 'hi-IN-1', name: 'Priya (Female)', language: 'Hindi', gender: 'Female' },
];

export default function TTSSetupPage() {
  const router = useRouter();
  const [selectedModel, setSelectedModel] = useState('gemini-tts-standard');
  const [selectedVoice, setSelectedVoice] = useState('en-US-1');
  const [sttProvider, setSttProvider] = useState('gemini');
  const [keyRotation, setKeyRotation] = useState(true);
  const [isLoading, setIsLoading] = useState(false);
  const [isPlaying, setIsPlaying] = useState(false);

  const handleTestVoice = () => {
    setIsPlaying(true);
    // Simulate voice playback
    setTimeout(() => setIsPlaying(false), 2000);
  };

  const handleSave = async () => {
    setIsLoading(true);
    try {
      await fetch('http://localhost:8000/api/setup/tts-stt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          tts_model: selectedModel,
          tts_voice: selectedVoice,
          stt_provider: sttProvider,
          key_rotation: keyRotation,
        }),
      });
    } catch (error) {
      console.error('Error saving TTS/STT config:', error);
    } finally {
      setIsLoading(false);
      router.push('/setup/system-setup');
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center p-4">
      <div className="max-w-5xl w-full">
        <div className="glass-card p-10 card-hover">
          <h1 className="text-4xl font-bold mb-2 neon-text-cyan">Voice Configuration</h1>
          <p className="text-gray-400 mb-8">Set up Text-to-Speech and Speech-to-Text</p>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
            {/* TTS Settings */}
            <div className="space-y-6">
              <h3 className="text-xl font-semibold neon-text-purple">🔊 Text-to-Speech</h3>
              
              <div>
                <label className="block text-sm font-medium mb-2 text-gray-300">
                  TTS Model (Gemini Default)
                </label>
                <select
                  value={selectedModel}
                  onChange={(e) => setSelectedModel(e.target.value)}
                  className="input-neon w-full"
                >
                  {geminiTTSModels.map((model) => (
                    <option key={model.id} value={model.id}>
                      {model.name} - {model.quality} ({model.latency})
                    </option>
                  ))}
                </select>
              </div>

              <div>
                <label className="block text-sm font-medium mb-2 text-gray-300">
                  Select Voice
                </label>
                <select
                  value={selectedVoice}
                  onChange={(e) => setSelectedVoice(e.target.value)}
                  className="input-neon w-full mb-4"
                >
                  {voices.map((voice) => (
                    <option key={voice.id} value={voice.id}>
                      {voice.name} - {voice.language}
                    </option>
                  ))}
                </select>

                <button
                  onClick={handleTestVoice}
                  disabled={isPlaying}
                  className="btn-neon w-full flex items-center justify-center"
                >
                  {isPlaying ? (
                    <>
                      <div className="spinner w-5 h-5 mr-2"></div>
                      Playing...
                    </>
                  ) : (
                    <>
                      ▶️ Test Voice
                    </>
                  )}
                </button>
              </div>

              <div className="glass-card p-4 bg-opacity-30">
                <h4 className="font-semibold mb-2 neon-text-cyan">✨ Key Rotation</h4>
                <div className="flex items-center justify-between mb-3">
                  <span className="text-sm text-gray-400">Automatically rotate API keys</span>
                  <label className="relative inline-flex items-center cursor-pointer">
                    <input
                      type="checkbox"
                      checked={keyRotation}
                      onChange={(e) => setKeyRotation(e.target.checked)}
                      className="sr-only peer"
                    />
                    <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-gradient-to-r peer-checked:from-cyan-500 peer-checked:to-purple-500"></div>
                  </label>
                </div>
                <p className="text-xs text-gray-500">
                  Automatically extract and rotate Gemini TTS models for optimal performance
                </p>
              </div>
            </div>

            {/* STT Settings */}
            <div className="space-y-6">
              <h3 className="text-xl font-semibold neon-text-blue">🎤 Speech-to-Text</h3>
              
              <div>
                <label className="block text-sm font-medium mb-2 text-gray-300">
                  STT Provider
                </label>
                <select
                  value={sttProvider}
                  onChange={(e) => setSttProvider(e.target.value)}
                  className="input-neon w-full"
                >
                  <option value="gemini">Gemini Speech-to-Text</option>
                  <option value="whisper">OpenAI Whisper</option>
                  <option value="google">Google Cloud Speech</option>
                  <option value="azure">Azure Speech Services</option>
                </select>
              </div>

              <div className="glass-card p-6 text-center">
                <div className="text-6xl mb-4">🎙️</div>
                <p className="text-gray-300 mb-4">
                  Test your microphone setup
                </p>
                <button className="btn-neon w-full">
                  🎤 Test Microphone
                </button>
              </div>

              <div className="glass-card p-4 bg-opacity-30">
                <h4 className="font-semibold mb-2 neon-text-purple">⚡ Real-time Transcription</h4>
                <ul className="text-sm text-gray-400 space-y-1">
                  <li>• Low-latency streaming transcription</li>
                  <li>• Multi-language support (50+ languages)</li>
                  <li>• Automatic punctuation</li>
                  <li>• Speaker diarization</li>
                </ul>
              </div>
            </div>
          </div>

          {/* Navigation */}
          <div className="flex justify-between mt-10">
            <button
              onClick={() => router.push('/setup/ai-setup')}
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
                'Continue to System Setup'
              )}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}
