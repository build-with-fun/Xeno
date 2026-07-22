"""
Base Agent - Foundation for all agent types
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Optional, Any, Callable
from dataclasses import dataclass, field
from datetime import datetime
import uuid
import asyncio
import structlog

logger = structlog.get_logger()


@dataclass
class AgentState:
    """Represents the current state of an agent"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    status: str = "idle"  # idle, busy, paused, error
    current_task: Optional[str] = None
    completed_tasks: int = 0
    failed_tasks: int = 0
    created_at: datetime = field(default_factory=datetime.utcnow)
    last_active: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentCapability:
    """Defines a capability of an agent"""
    name: str
    description: str
    input_schema: Dict[str, Any]
    output_schema: Dict[str, Any]
    async_executable: bool = True


class BaseAgent(ABC):
    """
    Abstract base class for all agents in the HyperAgent system
    
    Provides:
    - State management
    - Capability registration
    - Task execution framework
    - Inter-agent communication
    - Self-monitoring
    """
    
    def __init__(self, agent_id: Optional[str] = None, config: Optional[Dict] = None):
        self.id = agent_id or str(uuid.uuid4())
        self.config = config or {}
        self.state = AgentState(id=self.id)
        self.capabilities: Dict[str, AgentCapability] = {}
        self.tools: Dict[str, Callable] = {}
        self.message_queue: asyncio.Queue = asyncio.Queue()
        self._running = False
        self._current_task = None
        
        self._register_capabilities()
        logger.info("Agent initialized", agent_id=self.id, type=self.__class__.__name__)
    
    @abstractmethod
    def _register_capabilities(self):
        """Register agent-specific capabilities"""
        pass
    
    @abstractmethod
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a task - to be implemented by subclasses"""
        pass
    
    async def start(self):
        """Start the agent's main loop"""
        self._running = True
        self.state.status = "idle"
        logger.info("Agent started", agent_id=self.id)
        
        while self._running:
            try:
                # Process messages with timeout
                try:
                    message = await asyncio.wait_for(
                        self.message_queue.get(),
                        timeout=1.0
                    )
                    await self._process_message(message)
                except asyncio.TimeoutError:
                    # No messages, continue loop
                    pass
            
            except Exception as e:
                logger.error("Agent loop error", agent_id=self.id, error=str(e))
                self.state.status = "error"
                await asyncio.sleep(1)
    
    async def stop(self):
        """Stop the agent gracefully"""
        self._running = False
        self.state.status = "idle"
        logger.info("Agent stopped", agent_id=self.id)
    
    async def submit_task(self, task: Dict[str, Any]):
        """Submit a task to the agent"""
        await self.message_queue.put({
            'type': 'task',
            'payload': task,
            'timestamp': datetime.utcnow()
        })
        logger.debug("Task submitted to agent", agent_id=self.id, task=task.get('name'))
    
    async def _process_message(self, message: Dict[str, Any]):
        """Process incoming messages"""
        msg_type = message.get('type')
        
        if msg_type == 'task':
            await self._handle_task(message['payload'])
        elif msg_type == 'command':
            await self._handle_command(message['payload'])
        elif msg_type == 'query':
            await self._handle_query(message['payload'])
    
    async def _handle_task(self, task: Dict[str, Any]):
        """Handle a task execution request"""
        self.state.status = "busy"
        self.state.current_task = task.get('id')
        self._current_task = task
        
        logger.info("Executing task", agent_id=self.id, task_name=task.get('name'))
        
        try:
            result = await self.execute_task(task)
            self.state.completed_tasks += 1
            
            # Send result back (implementation depends on communication layer)
            await self._send_result(task.get('id'), result, success=True)
            
        except Exception as e:
            self.state.failed_tasks += 1
            logger.error("Task failed", agent_id=self.id, task_name=task.get('name'), error=str(e))
            await self._send_result(task.get('id'), {'error': str(e)}, success=False)
        
        finally:
            self.state.status = "idle"
            self.state.current_task = None
            self.state.last_active = datetime.utcnow()
            self._current_task = None
    
    async def _handle_command(self, command: Dict[str, Any]):
        """Handle a command (start, stop, pause, etc.)"""
        cmd_type = command.get('type')
        
        if cmd_type == 'stop':
            await self.stop()
        elif cmd_type == 'pause':
            self.state.status = "paused"
        elif cmd_type == 'resume':
            self.state.status = "idle"
    
    async def _handle_query(self, query: Dict[str, Any]):
        """Handle a status/capability query"""
        query_type = query.get('type')
        
        if query_type == 'status':
            await self._send_status()
        elif query_type == 'capabilities':
            await self._send_capabilities()
    
    async def _send_result(self, task_id: str, result: Any, success: bool):
        """Send task result (to be overridden by subclasses)"""
        logger.debug("Task result", agent_id=self.id, task_id=task_id, success=success)
    
    async def _send_status(self):
        """Send current agent status"""
        status = {
            'agent_id': self.id,
            'type': self.__class__.__name__,
            'status': self.state.status,
            'current_task': self.state.current_task,
            'completed_tasks': self.state.completed_tasks,
            'failed_tasks': self.state.failed_tasks,
            'capabilities': list(self.capabilities.keys()),
            'last_active': self.state.last_active.isoformat()
        }
        logger.debug("Agent status", **status)
    
    async def _send_capabilities(self):
        """Send agent capabilities"""
        caps = {
            'agent_id': self.id,
            'capabilities': {
                name: {
                    'description': cap.description,
                    'input_schema': cap.input_schema,
                    'output_schema': cap.output_schema
                }
                for name, cap in self.capabilities.items()
            }
        }
        logger.debug("Agent capabilities", **caps)
    
    def register_tool(self, name: str, tool: Callable):
        """Register a tool function"""
        self.tools[name] = tool
        logger.debug("Tool registered", agent_id=self.id, tool_name=name)
    
    def get_capability(self, name: str) -> Optional[AgentCapability]:
        """Get a specific capability"""
        return self.capabilities.get(name)
    
    def has_capability(self, name: str) -> bool:
        """Check if agent has a capability"""
        return name in self.capabilities
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert agent state to dictionary"""
        return {
            'id': self.id,
            'type': self.__class__.__name__,
            'status': self.state.status,
            'capabilities': list(self.capabilities.keys()),
            'completed_tasks': self.state.completed_tasks,
            'failed_tasks': self.state.failed_tasks,
            'config': self.config
        }
