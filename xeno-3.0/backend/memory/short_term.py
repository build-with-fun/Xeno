"""Tier 2: Short-Term Memory - Active consciousness (seconds to minutes)"""
from typing import Dict, List, Any, Optional
from datetime import datetime
import structlog

logger = structlog.get_logger()

class ShortTermMemory:
    def __init__(self, capacity: int = 7, duration_minutes: int = 5):
        self.capacity = capacity
        self.duration_minutes = duration_minutes
        self.items: List[Dict] = []
        logger.info("Short-term memory initialized", capacity=capacity)
    
    def store(self, item: Any, priority: float = 1.0) -> str:
        item_id = f"stm_{datetime.utcnow().timestamp()}"
        self.items.append({
            'id': item_id, 'data': item, 'priority': priority,
            'timestamp': datetime.utcnow(), 'rehearsals': 0
        })
        if len(self.items) > self.capacity:
            self._evict_lowest_priority()
        return item_id
    
    def _evict_lowest_priority(self):
        self.items.sort(key=lambda x: x['priority'], reverse=True)
        self.items = self.items[:self.capacity]
    
    def retrieve_all(self) -> List[Dict]:
        return self.items
