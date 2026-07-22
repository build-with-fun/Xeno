"""Memory-as-MCP-server — exposes all memory tiers through MCP protocol.

The Main Agent accesses memory through MCP tools instead of direct imports.
This standardizes memory access and makes it available to ALL agents in the pool.
"""

from __future__ import annotations

import logging
from typing import Optional

from xeno.mcp.adapter import ToolMCPServer, mcp_tool
from xeno.memory.temporal import get_temporal_kg, TemporalKnowledgeGraph
from xeno.config import XenoConfig

logger = logging.getLogger(__name__)


class MemoryMCPServer(ToolMCPServer):
    """MCP server that exposes memory operations as tools.

    Integrates with:
    - TemporalKnowledgeGraph (temporal fact storage)
    - Legacy MemoryManager (context + vector)
    - Mem0Manager (AUDN cycle)
    """

    def __init__(self, config: Optional[XenoConfig] = None):
        self.config = config or XenoConfig.from_env()
        self.temporal_kg: TemporalKnowledgeGraph = get_temporal_kg("main")
        self._legacy_memory = None
        self._mem0 = None

        tools = [
            self._store_fact,
            self._get_fact,
            self._query_facts,
            self._search_memory,
            self._get_entity_summary,
            self._get_context,
            self._get_history,
        ]
        super().__init__("memory", tools)

    async def _store_fact(self, subject: str, predicate: str, object: str,
                          confidence: float = 1.0, source: str = "",
                          namespace: str = "main") -> str:
        kg = get_temporal_kg(namespace)
        fact = kg.add_fact(subject, predicate, object, confidence=confidence, source=source)
        kg._save()
        return f"Stored: {subject} {predicate} {object} (id={fact.id})"

    async def _get_fact(self, subject: str, predicate: str,
                        namespace: str = "main") -> str:
        kg = get_temporal_kg(namespace)
        value = kg.get_current(subject, predicate)
        if value:
            return f"{subject} {predicate} {value}"
        history = kg.get_history(subject, predicate)
        if history:
            latest = history[-1]
            return f"{subject} {predicate} was '{latest.object}' (but no longer valid as of {latest.valid_to})"
        return f"No fact found for {subject} {predicate}"

    async def _query_facts(self, subject: str = "", predicate: str = "",
                           namespace: str = "main") -> str:
        kg = get_temporal_kg(namespace)
        facts = kg.query(subject, predicate) if subject else kg.get_all_facts(namespace)
        if not facts:
            return "No matching facts found."
        lines = [f"Facts ({len(facts)}):"]
        for f in facts[:20]:
            lines.append(f"  • {f.subject} — {f.predicate}: {f.object}")
        return "\n".join(lines)

    async def _search_memory(self, query: str, namespace: str = "main") -> str:
        kg = get_temporal_kg(namespace)
        results = kg.search(query)
        if not results:
            return "No results found."
        lines = [f"Memory search results for '{query}':"]
        for r in results[:10]:
            lines.append(f"  • {r.subject} {r.predicate} {r.object}")
        return "\n".join(lines)

    async def _get_entity_summary(self, subject: str, namespace: str = "main") -> str:
        kg = get_temporal_kg(namespace)
        return kg.get_entity_summary(subject)

    async def _get_context(self, subjects: str = "", limit: int = 20,
                           namespace: str = "main") -> str:
        kg = get_temporal_kg(namespace)
        subject_list = [s.strip() for s in subjects.split(",")] if subjects else None
        return kg.export_context(subject_list, limit=limit)

    async def _get_history(self, subject: str, predicate: str,
                           namespace: str = "main") -> str:
        kg = get_temporal_kg(namespace)
        history = kg.get_history(subject, predicate)
        if not history:
            return f"No history for {subject} {predicate}"
        lines = [f"History of {subject} {predicate}:"]
        for f in history:
            valid_str = f"valid: {f.valid_from} → {f.valid_to if f.valid_to != float('inf') else 'present'}"
            lines.append(f"  • '{f.object}' (conf={f.confidence}, {valid_str})")
        return "\n".join(lines)


def create_memory_mcp_server(config=None) -> MemoryMCPServer:
    """Create and register the memory MCP server."""
    server = MemoryMCPServer(config)
    from xeno.mcp.adapter import register_server
    register_server(server)
    return server
