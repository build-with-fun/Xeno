import { create } from 'zustand';
import { subscribeWithSelector } from 'zustand/middleware';

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'system';
  content: string;
  timestamp: Date;
  attachments?: string[];
}

export interface Task {
  id: string;
  title: string;
  status: 'pending' | 'running' | 'completed' | 'failed';
  progress: number;
  agent: string;
  createdAt: Date;
  completedAt?: Date;
}

export interface AgentStatus {
  name: string;
  type: 'main' | 'specialist' | 'worker' | 'monitor';
  status: 'idle' | 'busy' | 'offline';
  currentTask?: string;
  tasksCompleted: number;
}

export interface MemoryStats {
  sensory: number;
  shortTerm: number;
  working: number;
  episodic: number;
  semantic: number;
  procedural: number;
  vector: number;
  knowledgeGraph: number;
  metacognitive: number;
}

interface AppState {
  // Chat
  messages: Message[];
  isTyping: boolean;
  inputValue: string;
  
  // Tasks
  tasks: Task[];
  activeTaskId: string | null;
  
  // Agents
  agents: AgentStatus[];
  
  // Memory
  memoryStats: MemoryStats;
  
  // System
  isConnected: boolean;
  backendLogs: string[];
  systemMetrics: {
    cpu: number;
    memory: number;
    uptime: number;
    tasksPerHour: number;
  };
  
  // Actions
  addMessage: (message: Message) => void;
  setTyping: (typing: boolean) => void;
  setInputValue: (value: string) => void;
  addTask: (task: Task) => void;
  updateTask: (id: string, updates: Partial<Task>) => void;
  setActiveTask: (id: string | null) => void;
  updateAgents: (agents: AgentStatus[]) => void;
  updateMemoryStats: (stats: MemoryStats) => void;
  setConnected: (connected: boolean) => void;
  addBackendLog: (log: string) => void;
  updateSystemMetrics: (metrics: Partial<AppState['systemMetrics']>) => void;
  clearChat: () => void;
}

export const useAppStore = create<AppState>()(
  subscribeWithSelector((set, get) => ({
    // Initial state
    messages: [],
    isTyping: false,
    inputValue: '',
    tasks: [],
    activeTaskId: null,
    agents: [],
    memoryStats: {
      sensory: 0,
      shortTerm: 0,
      working: 0,
      episodic: 0,
      semantic: 0,
      procedural: 0,
      vector: 0,
      knowledgeGraph: 0,
      metacognitive: 0,
    },
    isConnected: false,
    backendLogs: [],
    systemMetrics: {
      cpu: 0,
      memory: 0,
      uptime: 0,
      tasksPerHour: 0,
    },
    
    // Actions
    addMessage: (message) =>
      set((state) => ({ messages: [...state.messages, message] })),
    
    setTyping: (isTyping) => set({ isTyping }),
    
    setInputValue: (inputValue) => set({ inputValue }),
    
    addTask: (task) =>
      set((state) => ({ tasks: [task, ...state.tasks] })),
    
    updateTask: (id, updates) =>
      set((state) => ({
        tasks: state.tasks.map((t) => (t.id === id ? { ...t, ...updates } : t)),
      })),
    
    setActiveTask: (activeTaskId) => set({ activeTaskId }),
    
    updateAgents: (agents) => set({ agents }),
    
    updateMemoryStats: (memoryStats) => set({ memoryStats }),
    
    setConnected: (isConnected) => set({ isConnected }),
    
    addBackendLog: (log) =>
      set((state) => ({
        backendLogs: [...state.backendLogs.slice(-99), log],
      })),
    
    updateSystemMetrics: (metrics) =>
      set((state) => ({
        systemMetrics: { ...state.systemMetrics, ...metrics },
      })),
    
    clearChat: () => set({ messages: [] }),
  }))
);
