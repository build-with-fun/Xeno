"""Tier 3: Working Memory - Active manipulation and reasoning"""
from typing import Dict, List, Any, Optional
from datetime import datetime
import structlog

logger = structlog.get_logger()

class WorkingMemory:
    def __init__(self):
        self.central_executive = {}
        self.phonological_loop = []
        self.visuospatial_sketchpad = []
        self.episodic_buffer = []
        logger.info("Working memory initialized")
    
    def focus(self, item_id: str) -> Optional[Any]:
        return self.central_executive.get(item_id)
    
    def store(self, data: Any, component: str = 'central_executive') -> str:
        item_id = f"wm_{datetime.utcnow().timestamp()}"
        if component == 'phonological_loop':
            self.phonological_loop.append({'id': item_id, 'data': data})
        elif component == 'visuospatial_sketchpad':
            self.visuospatial_sketchpad.append({'id': item_id, 'data': data})
        else:
            self.central_executive[item_id] = data
        return item_id
