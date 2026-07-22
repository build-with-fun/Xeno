'use client';

import { useState } from 'react';
import Sidebar from '@/components/Sidebar';

const agents = [
  { id: 1, name: 'Main Agent', type: 'main', status: 'active', model: 'GPT-4o', skills: 24 },
  { id: 2, name: 'Code Specialist', type: 'specialist', status: 'active', model: 'GPT-4o', skills: 18 },
  { id: 3, name: 'Web Specialist', type: 'specialist', status: 'idle', model: 'GPT-4o', skills: 12 },
  { id: 4, name: 'Desktop Specialist', type: 'specialist', status: 'active', model: 'GPT-4o', skills: 15 },
  { id: 5, name: 'Research Specialist', type: 'specialist', status: 'idle', model: 'Claude-3-Opus', skills: 10 },
];

const skills = [
  { id: 1, name: 'Python Code Execution', category: 'code' },
  { id: 2, name: 'Web Scraping', category: 'web' },
  { id: 3, name: 'File Management', category: 'desktop' },
  { id: 4, name: 'Email Automation', category: 'communication' },
  { id: 5, name: 'Data Analysis', category: 'data' },
];

export default function AgentsPage() {
  const [selectedAgent, setSelectedAgent] = useState(agents[0]);
  const [showAddSkill, setShowAddSkill] = useState(false);
  const [customPrompt, setCustomPrompt] = useState('');

  return (
    <div className="h-screen flex">
      <Sidebar />
      
      <div className="flex-1 p-8 overflow-y-auto">
        <div className="max-w-7xl mx-auto">
          <h1 className="text-4xl font-bold mb-2 neon-text-cyan">🤖 Agents Management</h1>
          <p className="text-gray-400 mb-8">Configure agents, add skills, and customize behavior</p>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-8">
            {/* Agents List */}
            <div className="lg:col-span-1 space-y-4">
              {agents.map((agent) => (
                <div
                  key={agent.id}
                  onClick={() => setSelectedAgent(agent)}
                  className={`glass-card p-4 card-hover cursor-pointer transition-all ${
                    selectedAgent?.id === agent.id ? 'border-2 border-neon-cyan' : ''
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <h3 className="font-semibold text-lg">{agent.name}</h3>
                    <span className={`px-2 py-1 rounded text-xs ${
                      agent.status === 'active' 
                        ? 'bg-green-600 text-white' 
                        : 'bg-gray-600 text-white'
                    }`}>
                      {agent.status}
                    </span>
                  </div>
                  <div className="text-sm text-gray-400 mb-2">Type: {agent.type}</div>
                  <div className="text-sm text-gray-400 mb-2">Model: {agent.model}</div>
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-purple-400">{agent.skills} Skills</span>
                    <button className="text-xs px-3 py-1 bg-cyan-600 hover:bg-cyan-700 rounded">
                      Configure
                    </button>
                  </div>
                </div>
              ))}

              <button className="w-full glass-card p-4 card-hover text-center border-2 border-dashed border-gray-600 hover:border-neon-cyan transition-colors">
                <span className="text-2xl">➕</span>
                <div className="mt-2 font-semibold">Add New Agent</div>
              </button>
            </div>

            {/* Agent Details */}
            <div className="lg:col-span-2 space-y-6">
              {selectedAgent && (
                <>
                  {/* Agent Info */}
                  <div className="glass-card p-6">
                    <div className="flex items-center justify-between mb-6">
                      <div>
                        <h2 className="text-3xl font-bold neon-text-purple">{selectedAgent.name}</h2>
                        <p className="text-gray-400 mt-1">
                          {selectedAgent.type} agent powered by {selectedAgent.model}
                        </p>
                      </div>
                      <div className="text-right">
                        <div className="text-4xl mb-2">🤖</div>
                        <span className={`px-3 py-1 rounded-full text-sm ${
                          selectedAgent.status === 'active' 
                            ? 'bg-green-600' 
                            : 'bg-gray-600'
                        }`}>
                          {selectedAgent.status.toUpperCase()}
                        </span>
                      </div>
                    </div>

                    {/* Stats */}
                    <div className="grid grid-cols-3 gap-4 mb-6">
                      <div className="text-center p-4 bg-white bg-opacity-5 rounded-lg">
                        <div className="text-2xl font-bold neon-text-cyan">{selectedAgent.skills}</div>
                        <div className="text-sm text-gray-400">Skills</div>
                      </div>
                      <div className="text-center p-4 bg-white bg-opacity-5 rounded-lg">
                        <div className="text-2xl font-bold neon-text-purple">156</div>
                        <div className="text-sm text-gray-400">Tasks Done</div>
                      </div>
                      <div className="text-center p-4 bg-white bg-opacity-5 rounded-lg">
                        <div className="text-2xl font-bold neon-text-blue">98%</div>
                        <div className="text-sm text-gray-400">Success Rate</div>
                      </div>
                    </div>
                  </div>

                  {/* Skills */}
                  <div className="glass-card p-6">
                    <div className="flex items-center justify-between mb-4">
                      <h3 className="text-xl font-semibold neon-text-cyan">⚡ Skills</h3>
                      <button
                        onClick={() => setShowAddSkill(!showAddSkill)}
                        className="btn-neon px-4 py-2 text-sm"
                      >
                        {showAddSkill ? 'Cancel' : '+ Add Skill'}
                      </button>
                    </div>

                    {showAddSkill && (
                      <div className="mb-6 p-4 bg-white bg-opacity-5 rounded-lg">
                        <h4 className="font-semibold mb-3">Add New Skill</h4>
                        <div className="space-y-3">
                          <select className="input-neon w-full">
                            <option>Select a skill...</option>
                            {skills.map((skill) => (
                              <option key={skill.id} value={skill.id}>
                                {skill.name} ({skill.category})
                              </option>
                            ))}
                          </select>
                          <button className="btn-neon w-full">Add Skill</button>
                        </div>
                      </div>
                    )}

                    <div className="flex flex-wrap gap-2">
                      {skills.slice(0, selectedAgent.skills).map((skill) => (
                        <span
                          key={skill.id}
                          className="px-3 py-2 bg-gradient-to-r from-cyan-600 to-purple-600 rounded-lg text-sm"
                        >
                          {skill.name}
                        </span>
                      ))}
                    </div>
                  </div>

                  {/* Custom Prompt */}
                  <div className="glass-card p-6">
                    <h3 className="text-xl font-semibold neon-text-purple mb-4">📝 Custom System Prompt</h3>
                    <textarea
                      value={customPrompt}
                      onChange={(e) => setCustomPrompt(e.target.value)}
                      className="input-neon w-full h-40 font-mono text-sm"
                      placeholder="Enter custom system prompt to override default behavior..."
                    />
                    <div className="flex justify-end mt-4">
                      <button className="btn-neon px-6 py-2">Save Prompt</button>
                    </div>
                  </div>

                  {/* MCP Servers */}
                  <div className="glass-card p-6">
                    <h3 className="text-xl font-semibold neon-text-blue mb-4">🔌 MCP Servers</h3>
                    <div className="space-y-3">
                      <div className="flex items-center justify-between p-3 bg-white bg-opacity-5 rounded-lg">
                        <div>
                          <div className="font-semibold">Filesystem MCP</div>
                          <div className="text-sm text-gray-400">Access local files securely</div>
                        </div>
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input type="checkbox" className="sr-only peer" defaultChecked />
                          <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-gradient-to-r peer-checked:from-cyan-500 peer-checked:to-purple-500"></div>
                        </label>
                      </div>
                      <div className="flex items-center justify-between p-3 bg-white bg-opacity-5 rounded-lg">
                        <div>
                          <div className="font-semibold">Database MCP</div>
                          <div className="text-sm text-gray-400">PostgreSQL connection</div>
                        </div>
                        <label className="relative inline-flex items-center cursor-pointer">
                          <input type="checkbox" className="sr-only peer" />
                          <div className="w-11 h-6 bg-gray-700 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-gradient-to-r peer-checked:from-cyan-500 peer-checked:to-purple-500"></div>
                        </label>
                      </div>
                    </div>
                  </div>
                </>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
