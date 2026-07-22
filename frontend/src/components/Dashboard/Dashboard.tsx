'use client';

import React from 'react';
import { useAppStore } from '@/store/app-store';
import { Activity, Cpu, HardDrive, Clock, TrendingUp } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, AreaChart, Area } from 'recharts';

export function Dashboard() {
  const agents = useAppStore((state) => state.agents);
  const memoryStats = useAppStore((state) => state.memoryStats);
  const systemMetrics = useAppStore((state) => state.systemMetrics);
  const tasks = useAppStore((state) => state.tasks);
  const isConnected = useAppStore((state) => state.isConnected);

  // Mock data for charts (will be replaced with real data from backend)
  const activityData = [
    { time: '00:00', tasks: 2, response: 400 },
    { time: '04:00', tasks: 1, response: 350 },
    { time: '08:00', tasks: 5, response: 450 },
    { time: '12:00', tasks: 8, response: 500 },
    { time: '16:00', tasks: 12, response: 480 },
    { time: '20:00', tasks: 6, response: 420 },
  ];

  const getAgentColor = (status: string) => {
    switch (status) {
      case 'busy': return 'text-xenoblue';
      case 'idle': return 'text-xenogreen';
      case 'offline': return 'text-muted-foreground';
      default: return 'text-foreground';
    }
  };

  const getAgentBgColor = (status: string) => {
    switch (status) {
      case 'busy': return 'bg-xenoblue/20 border-xenoblue/50';
      case 'idle': return 'bg-xenogreen/20 border-xenogreen/50';
      case 'offline': return 'bg-muted/20 border-muted/50';
      default: return 'bg-card border-border';
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case 'busy': return '●';
      case 'idle': return '○';
      case 'offline': return '×';
      default: return '?';
    }
  };

  const totalTasks = tasks.length;
  const completedTasks = tasks.filter(t => t.status === 'completed').length;
  const runningTasks = tasks.filter(t => t.status === 'running').length;
  const failedTasks = tasks.filter(t => t.status === 'failed').length;

  return (
    <div className="p-6 space-y-6 overflow-y-auto h-full">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-3xl font-bold gradient-text">Xeno AI Dashboard</h1>
          <p className="text-muted-foreground mt-1">
            Real-time monitoring and control center
          </p>
        </div>
        <div className={`flex items-center gap-2 px-4 py-2 rounded-full ${
          isConnected ? 'bg-xenogreen/20 text-xenogreen' : 'bg-xenored/20 text-xenored'
        }`}>
          <div className={`w-2 h-2 rounded-full ${
            isConnected ? 'bg-xenogreen animate-pulse' : 'bg-xenored'
          }`} />
          <span className="text-sm font-medium">
            {isConnected ? 'Connected' : 'Disconnected'}
          </span>
        </div>
      </div>

      {/* System Metrics Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
        <div className="card-glass">
          <div className="flex items-center gap-3 mb-3">
            <Cpu className="w-5 h-5 text-xenoblue" />
            <span className="text-sm text-muted-foreground">CPU Usage</span>
          </div>
          <div className="text-2xl font-bold">{systemMetrics.cpu.toFixed(1)}%</div>
          <div className="mt-2 h-1 bg-muted rounded-full overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-xenoblue to-xenopurple transition-all duration-500"
              style={{ width: `${systemMetrics.cpu}%` }}
            />
          </div>
        </div>

        <div className="card-glass">
          <div className="flex items-center gap-3 mb-3">
            <HardDrive className="w-5 h-5 text-xenopurple" />
            <span className="text-sm text-muted-foreground">Memory</span>
          </div>
          <div className="text-2xl font-bold">{systemMetrics.memory.toFixed(1)} MB</div>
          <div className="mt-2 h-1 bg-muted rounded-full overflow-hidden">
            <div 
              className="h-full bg-gradient-to-r from-xenopurple to-xenogreen transition-all duration-500"
              style={{ width: `${Math.min(systemMetrics.memory / 100, 100)}%` }}
            />
          </div>
        </div>

        <div className="card-glass">
          <div className="flex items-center gap-3 mb-3">
            <Clock className="w-5 h-5 text-xenogreen" />
            <span className="text-sm text-muted-foreground">Uptime</span>
          </div>
          <div className="text-2xl font-bold">
            {Math.floor(systemMetrics.uptime / 3600)}h {Math.floor((systemMetrics.uptime % 3600) / 60)}m
          </div>
          <div className="text-xs text-muted-foreground mt-2">
            Since last restart
          </div>
        </div>

        <div className="card-glass">
          <div className="flex items-center gap-3 mb-3">
            <TrendingUp className="w-5 h-5 text-xenoorange" />
            <span className="text-sm text-muted-foreground">Tasks/Hour</span>
          </div>
          <div className="text-2xl font-bold">{systemMetrics.tasksPerHour}</div>
          <div className="text-xs text-xenogreen mt-2">
            +12% from last hour
          </div>
        </div>
      </div>

      {/* Task Statistics */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Task Overview */}
        <div className="card-glass">
          <h3 className="text-lg font-semibold mb-4 flex items-center gap-2">
            <Activity className="w-5 h-5 text-xenoblue" />
            Task Overview
          </h3>
          <div className="grid grid-cols-2 gap-4">
            <div className="text-center p-4 bg-muted/30 rounded-xl">
              <div className="text-3xl font-bold text-xenoblue">{totalTasks}</div>
              <div className="text-sm text-muted-foreground mt-1">Total Tasks</div>
            </div>
            <div className="text-center p-4 bg-muted/30 rounded-xl">
              <div className="text-3xl font-bold text-xenogreen">{completedTasks}</div>
              <div className="text-sm text-muted-foreground mt-1">Completed</div>
            </div>
            <div className="text-center p-4 bg-muted/30 rounded-xl">
              <div className="text-3xl font-bold text-xenoorange">{runningTasks}</div>
              <div className="text-sm text-muted-foreground mt-1">Running</div>
            </div>
            <div className="text-center p-4 bg-muted/30 rounded-xl">
              <div className="text-3xl font-bold text-xenored">{failedTasks}</div>
              <div className="text-sm text-muted-foreground mt-1">Failed</div>
            </div>
          </div>
        </div>

        {/* Activity Chart */}
        <div className="card-glass">
          <h3 className="text-lg font-semibold mb-4">Activity Over Time</h3>
          <div className="h-48">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={activityData}>
                <defs>
                  <linearGradient id="colorTasks" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#00f0ff" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#00f0ff" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" stroke="#333" />
                <XAxis dataKey="time" stroke="#666" fontSize={12} />
                <YAxis stroke="#666" fontSize={12} />
                <Tooltip 
                  contentStyle={{ 
                    backgroundColor: '#1a1a2e', 
                    border: '1px solid #333',
                    borderRadius: '8px'
                  }} 
                />
                <Area type="monotone" dataKey="tasks" stroke="#00f0ff" fillOpacity={1} fill="url(#colorTasks)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>

      {/* Agents Status */}
      <div className="card-glass">
        <h3 className="text-lg font-semibold mb-4">Agent Status</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
          {agents.length === 0 ? (
            <div className="col-span-full text-center py-8 text-muted-foreground">
              No agents active. Start a task to activate agents.
            </div>
          ) : (
            agents.map((agent) => (
              <div
                key={agent.name}
                className={`p-4 rounded-xl border transition-all duration-300 ${getAgentBgColor(agent.status)}`}
              >
                <div className="flex items-center justify-between mb-2">
                  <span className="font-medium">{agent.name}</span>
                  <span className={`text-xs ${getAgentColor(agent.status)}`}>
                    {getStatusIcon(agent.status)} {agent.status.toUpperCase()}
                  </span>
                </div>
                <div className="text-xs text-muted-foreground capitalize">
                  Type: {agent.type}
                </div>
                {agent.currentTask && (
                  <div className="text-xs text-xenoblue mt-1 truncate">
                    Task: {agent.currentTask}
                  </div>
                )}
                <div className="text-xs text-muted-foreground mt-1">
                  Completed: {agent.tasksCompleted}
                </div>
              </div>
            ))
          )}
        </div>
      </div>

      {/* Memory Distribution */}
      <div className="card-glass">
        <h3 className="text-lg font-semibold mb-4">Memory Distribution</h3>
        <div className="grid grid-cols-3 md:grid-cols-5 lg:grid-cols-9 gap-2">
          {Object.entries(memoryStats).map(([key, value]) => (
            <div key={key} className="text-center p-3 bg-muted/30 rounded-lg">
              <div className="text-lg font-bold text-xenopurple">{value}</div>
              <div className="text-xs text-muted-foreground capitalize mt-1">
                {key.replace(/([A-Z])/g, ' $1').trim()}
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
