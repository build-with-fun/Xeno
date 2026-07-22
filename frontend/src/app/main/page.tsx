'use client';

import { useState, useEffect, useRef } from 'react';
import { useRouter } from 'next/navigation';

interface LogEntry {
  id: string;
  timestamp: string;
  message: string;
  type: 'info' | 'action' | 'success' | 'error';
}

interface Message {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: string;
}

export default function MainPage() {
  const router = useRouter();
  const [orbState, setOrbState] = useState<'idle' | 'speaking' | 'listening'>('idle');
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [currentTranscript, setCurrentTranscript] = useState('');
  const [isRecording, setIsRecording] = useState(false);
  const [inputValue, setInputValue] = useState('');
  const logsEndRef = useRef<HTMLDivElement>(null);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  // Simulate real-time logs
  useEffect(() => {
    const mockLogs: LogEntry[] = [
      { id: '1', timestamp: new Date().toLocaleTimeString(), message: 'System initialized', type: 'info' },
      { id: '2', timestamp: new Date().toLocaleTimeString(), message: 'Memory systems online', type: 'success' },
      { id: '3', timestamp: new Date().toLocaleTimeString(), message: 'Loading agent modules...', type: 'info' },
      { id: '4', timestamp: new Date().toLocaleTimeString(), message: '9-tier memory hierarchy active', type: 'success' },
      { id: '5', timestamp: new Date().toLocaleTimeString(), message: 'Waiting for user input', type: 'info' },
    ];
    setLogs(mockLogs);
  }, []);

  // Auto-scroll logs
  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [logs]);

  // Auto-scroll messages
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  const handleSendMessage = async () => {
    if (!inputValue.trim()) return;

    const userMessage: Message = {
      id: Date.now().toString(),
      role: 'user',
      content: inputValue,
      timestamp: new Date().toLocaleTimeString(),
    };

    setMessages((prev) => [...prev, userMessage]);
    setInputValue('');
    setOrbState('listening');

    // Add log entry
    const newLog: LogEntry = {
      id: Date.now().toString(),
      timestamp: new Date().toLocaleTimeString(),
      message: `User: ${inputValue.substring(0, 50)}...`,
      type: 'info',
    };
    setLogs((prev) => [...prev, newLog]);

    // Simulate AI response
    setTimeout(() => {
      const aiMessage: Message = {
        id: (Date.now() + 1).toString(),
        role: 'assistant',
        content: "I understand. Let me help you with that. I'm analyzing your request and will provide the best solution.",
        timestamp: new Date().toLocaleTimeString(),
      };
      setMessages((prev) => [...prev, aiMessage]);
      setOrbState('speaking');

      // Add log entries for BEFORE_WORK, DURING, AFTER_WORK
      const workLogs: LogEntry[] = [
        {
          id: (Date.now() + 1).toString(),
          timestamp: new Date().toLocaleTimeString(),
          message: 'BEFORE_WORK: Analyzing intent...',
          type: 'info',
        },
        {
          id: (Date.now() + 2).toString(),
          timestamp: new Date().toLocaleTimeString(),
          message: 'EXECUTING: Processing task...',
          type: 'action',
        },
        {
          id: (Date.now() + 3).toString(),
          timestamp: new Date().toLocaleTimeString(),
          message: 'AFTER_WORK: Task completed successfully',
          type: 'success',
        },
      ];
      setLogs((prev) => [...prev, ...workLogs]);

      // Stop speaking after a while
      setTimeout(() => {
        setOrbState('idle');
      }, 3000);
    }, 1500);
  };

  const toggleRecording = () => {
    if (isRecording) {
      setIsRecording(false);
      setOrbState('idle');
      // Process recorded audio
      if (currentTranscript) {
        setInputValue(currentTranscript);
        setCurrentTranscript('');
      }
    } else {
      setIsRecording(true);
      setOrbState('listening');
      // Simulate transcription
      setCurrentTranscript('Listening...');
    }
  };

  const handleInterrupt = () => {
    setOrbState('listening');
    setIsRecording(true);
    // Clear current AI response
    setCurrentTranscript('Interrupted - listening...');
  };

  return (
    <div className="h-screen flex">
      {/* Left Panel - Logs */}
      <div className="w-80 glass-card m-4 p-4 flex flex-col">
        <h3 className="text-lg font-semibold mb-4 neon-text-cyan">📋 Activity Logs</h3>
        <div className="flex-1 overflow-y-auto space-y-2">
          {logs.map((log) => (
            <div key={log.id} className="text-xs p-2 rounded bg-white bg-opacity-5">
              <span className="text-gray-500">{log.timestamp}</span>
              <div className={`mt-1 ${
                log.type === 'success' ? 'text-green-400' :
                log.type === 'error' ? 'text-red-400' :
                log.type === 'action' ? 'text-purple-400' :
                'text-gray-300'
              }`}>
                {log.message}
              </div>
            </div>
          ))}
          <div ref={logsEndRef} />
        </div>
      </div>

      {/* Center Panel - Orb & Chat */}
      <div className="flex-1 flex flex-col items-center justify-center p-4">
        {/* Orb */}
        <div className="mb-8">
          <div className="orb-container">
            <div 
              className={`orb ${orbState === 'speaking' ? 'speaking' : ''} ${orbState === 'listening' ? 'listening' : ''}`}
            ></div>
          </div>
          <p className="text-center text-gray-400 mt-4">
            {orbState === 'speaking' ? 'Speaking...' :
             orbState === 'listening' ? 'Listening...' :
             'Ready'}
          </p>
        </div>

        {/* Messages */}
        <div className="w-full max-w-2xl glass-card p-4 mb-4 max-h-64 overflow-y-auto">
          {messages.length === 0 ? (
            <p className="text-gray-500 text-center py-8">
              Start a conversation with Xeno...
            </p>
          ) : (
            <div className="space-y-4">
              {messages.map((msg) => (
                <div
                  key={msg.id}
                  className={`p-3 rounded-lg ${
                    msg.role === 'user' 
                      ? 'bg-gradient-to-r from-cyan-600 to-cyan-800 ml-8' 
                      : 'bg-white bg-opacity-10 mr-8'
                  }`}
                >
                  <p className="text-sm">{msg.content}</p>
                  <span className="text-xs text-gray-500 mt-1 block">{msg.timestamp}</span>
                </div>
              ))}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Input */}
        <div className="w-full max-w-2xl flex gap-2">
          <input
            type="text"
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyPress={(e) => e.key === 'Enter' && handleSendMessage()}
            placeholder="Type or speak to Xeno..."
            className="input-neon flex-1"
          />
          <button
            onClick={toggleRecording}
            className={`btn-neon px-6 ${isRecording ? 'animate-pulse bg-red-600' : ''}`}
          >
            {isRecording ? '🔴 Stop' : '🎤'}
          </button>
          <button onClick={handleSendMessage} className="btn-neon px-6">
            Send
          </button>
        </div>

        {/* Interrupt Button */}
        {orbState === 'speaking' && (
          <button
            onClick={handleInterrupt}
            className="mt-4 px-6 py-2 bg-red-600 hover:bg-red-700 rounded-lg transition-colors"
          >
            ⏹️ Interrupt
          </button>
        )}
      </div>

      {/* Right Panel - Transcription & Response */}
      <div className="w-80 glass-card m-4 p-4 flex flex-col">
        <h3 className="text-lg font-semibold mb-4 neon-text-purple">💬 Conversation</h3>
        
        <div className="flex-1 overflow-y-auto space-y-4">
          {/* Current AI Response */}
          {messages.length > 0 && messages[messages.length - 1].role === 'assistant' && (
            <div className="p-3 bg-white bg-opacity-5 rounded-lg">
              <h4 className="text-sm font-semibold text-cyan-400 mb-2">AI Response</h4>
              <p className="text-sm text-gray-300">
                {messages[messages.length - 1].content}
              </p>
            </div>
          )}

          {/* Work Phases */}
          <div className="space-y-2">
            <h4 className="text-sm font-semibold text-purple-400">Task Phases</h4>
            <div className="text-xs space-y-1">
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-green-500"></div>
                <span className="text-gray-400">BEFORE_WORK</span>
              </div>
              <div className="flex items-center gap-2">
                <div className={`w-2 h-2 rounded-full ${orbState === 'speaking' || orbState === 'listening' ? 'bg-yellow-500 animate-pulse' : 'bg-gray-600'}`}></div>
                <span className="text-gray-400">DURING_WORK</span>
              </div>
              <div className="flex items-center gap-2">
                <div className="w-2 h-2 rounded-full bg-gray-600"></div>
                <span className="text-gray-400">AFTER_WORK</span>
              </div>
            </div>
          </div>

          {/* Live Transcription */}
          {isRecording && (
            <div className="p-3 bg-blue-900 bg-opacity-30 rounded-lg border border-blue-500">
              <h4 className="text-sm font-semibold text-blue-400 mb-2">Live Transcription</h4>
              <p className="text-sm text-gray-300 italic">
                {currentTranscript || 'Listening...'}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
