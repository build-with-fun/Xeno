import { io, Socket } from 'socket.io-client';
import { useAppStore } from '@/store/app-store';

const API_URL = process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000';

class WebSocketService {
  private socket: Socket | null = null;
  private reconnectAttempts = 0;
  private maxReconnectAttempts = 5;

  connect() {
    if (this.socket?.connected) return;

    this.socket = io(API_URL, {
      transports: ['websocket', 'polling'],
      reconnection: true,
      reconnectionDelay: 1000,
      reconnectionDelayMax: 5000,
      reconnectionAttempts: this.maxReconnectAttempts,
    });

    this.socket.on('connect', () => {
      console.log('[WebSocket] Connected to Xeno backend');
      useAppStore.getState().setConnected(true);
      this.reconnectAttempts = 0;
    });

    this.socket.on('disconnect', () => {
      console.log('[WebSocket] Disconnected from Xeno backend');
      useAppStore.getState().setConnected(false);
    });

    this.socket.on('connect_error', (error) => {
      console.error('[WebSocket] Connection error:', error);
      this.reconnectAttempts++;
      if (this.reconnectAttempts >= this.maxReconnectAttempts) {
        console.error('[WebSocket] Max reconnection attempts reached');
      }
    });

    // Message events
    this.socket.on('message', (data: { role: string; content: string; id?: string }) => {
      useAppStore.getState().addMessage({
        id: data.id || Date.now().toString(),
        role: data.role as 'user' | 'assistant' | 'system',
        content: data.content,
        timestamp: new Date(),
      });
      useAppStore.getState().setTyping(false);
    });

    // Task events
    this.socket.on('task_created', (task) => {
      useAppStore.getState().addTask({
        ...task,
        createdAt: new Date(task.createdAt),
        completedAt: task.completedAt ? new Date(task.completedAt) : undefined,
      });
    });

    this.socket.on('task_updated', (task) => {
      useAppStore.getState().updateTask(task.id, {
        ...task,
        progress: task.progress,
        status: task.status,
        completedAt: task.completedAt ? new Date(task.completedAt) : undefined,
      });
    });

    // Agent status updates
    this.socket.on('agents_update', (agents) => {
      useAppStore.getState().updateAgents(agents);
    });

    // Memory stats
    this.socket.on('memory_stats', (stats) => {
      useAppStore.getState().updateMemoryStats(stats);
    });

    // System metrics
    this.socket.on('system_metrics', (metrics) => {
      useAppStore.getState().updateSystemMetrics(metrics);
    });

    // Typing indicator
    this.socket.on('typing_start', () => {
      useAppStore.getState().setTyping(true);
    });

    this.socket.on('typing_end', () => {
      useAppStore.getState().setTyping(false);
    });

    // Error handling
    this.socket.on('error', (error) => {
      console.error('[WebSocket] Error:', error);
      useAppStore.getState().addBackendLog(`Error: ${error.message}`);
    });
  }

  disconnect() {
    if (this.socket) {
      this.socket.disconnect();
      this.socket = null;
    }
  }

  sendMessage(content: string, attachments?: string[]) {
    if (!this.socket?.connected) {
      console.error('[WebSocket] Not connected');
      return;
    }

    const message = {
      id: Date.now().toString(),
      role: 'user' as const,
      content,
      timestamp: new Date(),
      attachments,
    };

    useAppStore.getState().addMessage(message);
    useAppStore.getState().setInputValue('');
    useAppStore.getState().setTyping(true);

    this.socket.emit('user_message', { content, attachments });
  }

  cancelTask(taskId: string) {
    this.socket?.emit('cancel_task', { taskId });
  }

  requestAgentStatus() {
    this.socket?.emit('request_agents');
  }

  requestMemoryStats() {
    this.socket?.emit('request_memory_stats');
  }
}

export const websocketService = new WebSocketService();
