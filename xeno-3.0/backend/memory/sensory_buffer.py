"""
Tier 1: Sensory Buffer - Immediate perception storage
Ultra-short-term memory for raw sensory input (milliseconds to seconds)
"""

from typing import Dict, List, Any, Optional
from collections import deque
from datetime import datetime
import structlog

logger = structlog.get_logger()


class SensoryBuffer:
    """
    Sensory Buffer - First tier of Omni-Memory System
    
    Stores raw sensory data for immediate processing:
    - Visual input (screen captures, images)
    - Audio input (voice, sounds)
    - Keyboard/mouse events
    - System events
    
    Characteristics:
    - Capacity: ~1000 items
    - Duration: 100ms - 5 seconds
    - Access: O(1) direct access
    - Decay: Automatic FIFO eviction
    """
    
    def __init__(self, max_size: int = 1000, ttl_seconds: float = 5.0):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self.buffer: deque = deque(maxlen=max_size)
        self.timestamps: deque = deque(maxlen=max_size)
        self.modalities = {
            'visual': [],
            'audio': [],
            'haptic': [],
            'system': []
        }
        logger.info("Sensory buffer initialized", max_size=max_size, ttl=ttl_seconds)
    
    def store(self, data: Any, modality: str, metadata: Optional[Dict] = None) -> str:
        """Store sensory data in buffer"""
        timestamp = datetime.utcnow()
        item_id = f"{modality}_{timestamp.timestamp()}_{len(self.buffer)}"
        
        item = {
            'id': item_id,
            'data': data,
            'modality': modality,
            'metadata': metadata or {},
            'timestamp': timestamp
        }
        
        self.buffer.append(item)
        self.timestamps.append(timestamp)
        
        if modality in self.modalities:
            self.modalities[modality].append(item_id)
        
        # Clean expired items
        self._cleanup()
        
        logger.debug("Sensory data stored", item_id=item_id, modality=modality)
        return item_id
    
    def retrieve(self, item_id: str) -> Optional[Dict]:
        """Retrieve specific item by ID"""
        for item in self.buffer:
            if item['id'] == item_id:
                if not self._is_expired(item['timestamp']):
                    return item
        return None
    
    def get_recent(self, modality: Optional[str] = None, count: int = 10) -> List[Dict]:
        """Get most recent items, optionally filtered by modality"""
        items = list(self.buffer)[-count:]
        
        if modality:
            items = [item for item in items if item['modality'] == modality]
        
        return items
    
    def get_all_current(self) -> List[Dict]:
        """Get all non-expired items"""
        self._cleanup()
        return list(self.buffer)
    
    def _is_expired(self, timestamp: datetime) -> bool:
        """Check if item has exceeded TTL"""
        age = (datetime.utcnow() - timestamp).total_seconds()
        return age > self.ttl_seconds
    
    def _cleanup(self):
        """Remove expired items"""
        while self.timestamps and self._is_expired(self.timestamps[0]):
            old_item = self.buffer.popleft()
            self.timestamps.popleft()
            
            modality = old_item['modality']
            if modality in self.modalities and old_item['id'] in self.modalities[modality]:
                self.modalities[modality].remove(old_item['id'])
        
        logger.debug("Sensory buffer cleanup completed", remaining=len(self.buffer))
    
    def clear(self, modality: Optional[str] = None):
        """Clear buffer, optionally for specific modality"""
        if modality:
            self.buffer = deque([item for item in self.buffer if item['modality'] != modality], maxlen=self.max_size)
        else:
            self.buffer.clear()
            self.timestamps.clear()
            for key in self.modalities:
                self.modalities[key] = []
        
        logger.info("Sensory buffer cleared", modality=modality)
    
    def stats(self) -> Dict:
        """Get buffer statistics"""
        return {
            'size': len(self.buffer),
            'max_size': self.max_size,
            'utilization': len(self.buffer) / self.max_size,
            'by_modality': {k: len(v) for k, v in self.modalities.items()},
            'oldest_age_seconds': (datetime.utcnow() - self.timestamps[0]).total_seconds() if self.timestamps else 0
        }
