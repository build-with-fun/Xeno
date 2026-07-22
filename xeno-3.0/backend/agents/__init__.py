"""
HyperAgent Controller - Advanced Multi-Agent System
"""

from .base import BaseAgent
from .main_agent import MainAgent
from .specialist_agents import (
    CodeSpecialist,
    WebSpecialist,
    DesktopSpecialist,
    DataSpecialist,
    CommunicationSpecialist,
    ResearchSpecialist,
    CreationSpecialist
)
from .critic_agents import (
    QualityCritic,
    SecurityCritic,
    PerformanceCritic,
    EthicsCritic,
    ConsistencyCritic
)
from .worker_agent import WorkerAgent
from .monitor_agent import MonitorAgent

__all__ = [
    'BaseAgent',
    'MainAgent',
    'CodeSpecialist',
    'WebSpecialist',
    'DesktopSpecialist',
    'DataSpecialist',
    'CommunicationSpecialist',
    'ResearchSpecialist',
    'CreationSpecialist',
    'QualityCritic',
    'SecurityCritic',
    'PerformanceCritic',
    'EthicsCritic',
    'ConsistencyCritic',
    'WorkerAgent',
    'MonitorAgent'
]
