"""
Main Agent - Central coordinator and decision maker
"""

from typing import Dict, List, Optional, Any
import structlog
from .base import BaseAgent, AgentCapability

logger = structlog.get_logger()


class MainAgent(BaseAgent):
    """
    Main Agent - The central brain of the HyperAgent system
    
    Responsibilities:
    - Intent classification and task routing
    - Sub-agent creation and management
    - Strategic planning and decomposition
    - Inter-agent coordination
    - Self-improvement decisions
    """
    
    def __init__(self, agent_id: Optional[str] = None, config: Optional[Dict] = None):
        self.sub_agents: Dict[str, BaseAgent] = {}
        self.task_history: List[Dict] = []
        self.learned_patterns: Dict[str, Any] = {}
        super().__init__(agent_id, config)
    
    def _register_capabilities(self):
        """Register main agent capabilities"""
        self.capabilities.update({
            'intent_classification': AgentCapability(
                name='intent_classification',
                description='Classify user intent into predefined categories',
                input_schema={
                    'type': 'object',
                    'properties': {
                        'input': {'type': 'string'},
                        'context': {'type': 'object'}
                    }
                },
                output_schema={
                    'type': 'object',
                    'properties': {
                        'intents': {'type': 'array', 'items': {'type': 'string'}},
                        'confidence': {'type': 'number'}
                    }
                }
            ),
            'task_decomposition': AgentCapability(
                name='task_decomposition',
                description='Break down complex tasks into sub-tasks',
                input_schema={
                    'type': 'object',
                    'properties': {
                        'task': {'type': 'string'},
                        'complexity': {'type': 'string'}
                    }
                },
                output_schema={
                    'type': 'array',
                    'items': {
                        'type': 'object',
                        'properties': {
                            'sub_task': {'type': 'string'},
                            'agent_type': {'type': 'string'},
                            'dependencies': {'type': 'array'}
                        }
                    }
                }
            ),
            'agent_management': AgentCapability(
                name='agent_management',
                description='Create, manage, and destroy sub-agents',
                input_schema={
                    'type': 'object',
                    'properties': {
                        'action': {'type': 'string', 'enum': ['create', 'destroy', 'modify']},
                        'agent_type': {'type': 'string'},
                        'config': {'type': 'object'}
                    }
                },
                output_schema={
                    'type': 'object',
                    'properties': {
                        'success': {'type': 'boolean'},
                        'agent_id': {'type': 'string'}
                    }
                }
            ),
            'strategic_planning': AgentCapability(
                name='strategic_planning',
                description='Create execution strategies for complex goals',
                input_schema={
                    'type': 'object',
                    'properties': {
                        'goal': {'type': 'string'},
                        'constraints': {'type': 'array'},
                        'resources': {'type': 'object'}
                    }
                },
                output_schema={
                    'type': 'object',
                    'properties': {
                        'plan': {'type': 'array'},
                        'timeline': {'type': 'object'},
                        'resource_allocation': {'type': 'object'}
                    }
                }
            ),
            'self_improvement': AgentCapability(
                name='self_improvement',
                description='Analyze performance and initiate self-improvement',
                input_schema={
                    'type': 'object',
                    'properties': {
                        'metrics': {'type': 'object'},
                        'timeframe': {'type': 'string'}
                    }
                },
                output_schema={
                    'type': 'object',
                    'properties': {
                        'improvements': {'type': 'array'},
                        'code_changes': {'type': 'array'},
                        'config_updates': {'type': 'object'}
                    }
                }
            )
        })
    
    async def execute_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a high-level task by coordinating sub-agents"""
        
        logger.info("Main agent executing task", task_name=task.get('name'))
        
        # Step 1: Classify intent
        intents = await self._classify_intent(task)
        
        # Step 2: Decompose task if complex
        sub_tasks = await self._decompose_task(task, intents)
        
        # Step 3: Create strategy
        strategy = await self._create_strategy(task, sub_tasks, intents)
        
        # Step 4: Execute through sub-agents or directly
        if len(sub_tasks) > 1:
            result = await self._execute_distributed(strategy, sub_tasks)
        else:
            result = await self._execute_direct(task, intents)
        
        # Step 5: Learn from execution
        await self._learn_from_execution(task, result)
        
        return result
    
    async def _classify_intent(self, task: Dict[str, Any]) -> List[str]:
        """Classify the intent of a task"""
        # Placeholder for LLM-based intent classification
        description = task.get('description', '')
        
        # Simple keyword-based classification (to be replaced with ML model)
        intent_map = {
            'code': 'code_execution',
            'program': 'code_execution',
            'script': 'code_execution',
            'website': 'web_automation',
            'browser': 'web_automation',
            'scrape': 'web_automation',
            'file': 'desktop_control',
            'folder': 'desktop_control',
            'email': 'communication',
            'message': 'communication',
            'analyze': 'data_analysis',
            'research': 'research',
            'create': 'creation',
            'write': 'creation',
            'modify': 'system_modification',
            'update': 'system_modification',
            'remember': 'memory_operation',
            'learn': 'self_improvement'
        }
        
        detected_intents = []
        description_lower = description.lower()
        
        for keyword, intent in intent_map.items():
            if keyword in description_lower and intent not in detected_intents:
                detected_intents.append(intent)
        
        if not detected_intents:
            detected_intents.append('creation')  # Default intent
        
        logger.debug("Intent classified", intents=detected_intents)
        return detected_intents
    
    async def _decompose_task(self, task: Dict[str, Any], intents: List[str]) -> List[Dict]:
        """Decompose complex task into sub-tasks"""
        # Placeholder for LLM-based task decomposition
        sub_tasks = [{
            'id': f"{task['id']}_1",
            'name': task.get('name', 'main_task'),
            'description': task.get('description', ''),
            'intents': intents,
            'dependencies': []
        }]
        
        logger.debug("Task decomposed", sub_task_count=len(sub_tasks))
        return sub_tasks
    
    async def _create_strategy(self, task: Dict, sub_tasks: List, intents: List[str]) -> Dict:
        """Create execution strategy"""
        return {
            'execution_mode': 'parallel' if len(sub_tasks) > 1 else 'sequential',
            'priority': task.get('priority', 'normal'),
            'resource_allocation': {
                'cpu': 1.0,
                'memory': 512,
                'agents_required': len(set(intents))
            },
            'retry_policy': {
                'max_retries': 3,
                'backoff_multiplier': 2
            }
        }
    
    async def _execute_distributed(self, strategy: Dict, sub_tasks: List[Dict]) -> Dict:
        """Execute tasks through sub-agents"""
        results = []
        
        for sub_task in sub_tasks:
            # Route to appropriate agent based on intents
            agent = await self._route_to_agent(sub_task['intents'])
            
            if agent:
                result = await agent.execute_task(sub_task)
                results.append(result)
            else:
                # Execute directly if no suitable agent
                result = await self._execute_direct(sub_task, sub_task.get('intents', []))
                results.append(result)
        
        return {
            'status': 'completed',
            'results': results,
            'strategy_used': strategy
        }
    
    async def _execute_direct(self, task: Dict, intents: List[str]) -> Dict:
        """Execute task directly without sub-agents"""
        # Placeholder for direct execution logic
        logger.info("Executing task directly", task_name=task.get('name'))
        
        return {
            'status': 'completed',
            'task_id': task.get('id'),
            'result': 'Direct execution completed'
        }
    
    async def _route_to_agent(self, intents: List[str]) -> Optional[BaseAgent]:
        """Route task to appropriate sub-agent"""
        # Priority mapping for agent selection
        intent_agent_map = {
            'code_execution': 'code_specialist',
            'web_automation': 'web_specialist',
            'desktop_control': 'desktop_specialist',
            'data_analysis': 'data_specialist',
            'communication': 'communication_specialist',
            'research': 'research_specialist',
            'creation': 'creation_specialist'
        }
        
        for intent in intents:
            agent_key = intent_agent_map.get(intent)
            if agent_key and agent_key in self.sub_agents:
                return self.sub_agents[agent_key]
        
        return None
    
    async def _learn_from_execution(self, task: Dict, result: Dict):
        """Learn from task execution for future improvements"""
        self.task_history.append({
            'task': task,
            'result': result,
            'timestamp': __import__('datetime').datetime.utcnow().isoformat()
        })
        
        # Keep only last 1000 tasks in memory
        if len(self.task_history) > 1000:
            self.task_history = self.task_history[-1000:]
        
        logger.debug("Learned from execution", task_id=task.get('id'))
    
    def create_sub_agent(self, agent_type: str, config: Optional[Dict] = None) -> str:
        """Create a new sub-agent"""
        from .specialist_agents import (
            CodeSpecialist, WebSpecialist, DesktopSpecialist,
            DataSpecialist, CommunicationSpecialist, ResearchSpecialist,
            CreationSpecialist
        )
        
        agent_classes = {
            'code_specialist': CodeSpecialist,
            'web_specialist': WebSpecialist,
            'desktop_specialist': DesktopSpecialist,
            'data_specialist': DataSpecialist,
            'communication_specialist': CommunicationSpecialist,
            'research_specialist': ResearchSpecialist,
            'creation_specialist': CreationSpecialist
        }
        
        if agent_type not in agent_classes:
            raise ValueError(f"Unknown agent type: {agent_type}")
        
        agent_class = agent_classes[agent_type]
        agent = agent_class(config=config)
        
        self.sub_agents[agent_type] = agent
        logger.info("Sub-agent created", agent_type=agent_type, agent_id=agent.id)
        
        return agent.id
    
    def get_sub_agent(self, agent_type: str) -> Optional[BaseAgent]:
        """Get a sub-agent by type"""
        return self.sub_agents.get(agent_type)
    
    def list_sub_agents(self) -> List[Dict]:
        """List all sub-agents"""
        return [
            {'type': agent_type, 'id': agent.id, 'status': agent.state.status}
            for agent_type, agent in self.sub_agents.items()
        ]
