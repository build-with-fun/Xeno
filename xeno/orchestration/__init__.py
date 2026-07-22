"""Multi-agent orchestration patterns.

Core patterns:
- Supervisor: central coordinator delegates to specialists
- Pipeline: sequential agent pipeline for linear workflows
- FanOut: parallel task execution with result aggregation
- Debate: multi-agent debate for verification
- Adaptive: dynamic plan discovery and routing
"""

from xeno.orchestration.supervisor import SupervisorOrchestrator
from xeno.orchestration.pipeline import PipelineOrchestrator
from xeno.orchestration.fanout import FanOutOrchestrator
from xeno.orchestration.debate import DebateOrchestrator
from xeno.orchestration.adaptive import AdaptiveOrchestrator

PatternRegistry = {
    "supervisor": SupervisorOrchestrator,
    "pipeline": PipelineOrchestrator,
    "fanout": FanOutOrchestrator,
    "debate": DebateOrchestrator,
    "adaptive": AdaptiveOrchestrator,
}
