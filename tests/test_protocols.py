"""Tests for the 4 protocol clients — MCP 2025, A2A, AGNTCY, UMP."""

import asyncio
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest

from xeno.protocols import (
    MCP2025Client,
    MCPServerCard,
    A2AClient,
    A2AAgentCard,
    AGNTCYClient,
    AGNTCYAgentRecord,
    UMPClient,
    UMPAccessController,
    UMPPermission,
)


class TestMCP2025Client:
    def test_init(self):
        client = MCP2025Client()
        assert client.list_servers() == []

    def test_add_server(self):
        client = MCP2025Client()
        asyncio.run(client.add_server("test", "local", command=["python", "-m"]))
        servers = client.list_servers()
        assert len(servers) == 1
        assert servers[0].name == "test"

    def test_multiple_servers(self):
        client = MCP2025Client()
        asyncio.run(client.add_server("s1", "local", command=["python"]))
        asyncio.run(client.add_server("s2", "remote_sse", url="http://localhost:8080"))
        assert len(client.list_servers()) == 2

    def test_remove_server(self):
        client = MCP2025Client()
        asyncio.run(client.add_server("test", "local", command=["python"]))
        asyncio.run(client.remove_server("test"))
        assert client.list_servers() == []


class TestA2AClient:
    def test_init(self):
        card = A2AAgentCard(name="xeno", description="Test", version="1.0", url="http://localhost:8000")
        client = A2AClient(my_card=card)
        assert client.my_card.name == "xeno"
        assert client.list_discovered() == []

    def test_agent_card_serialization(self):
        card = A2AAgentCard(name="xeno", description="Test agent", version="2.0",
                            capabilities={"tools": True}, skills=["research"])
        d = card.to_dict()
        assert d["name"] == "xeno"
        assert d["version"] == "2.0"
        card2 = A2AAgentCard.from_dict(d)
        assert card2.name == "xeno"
        assert card2.version == "2.0"

    def test_publish_my_card(self):
        card = A2AAgentCard(name="xeno", description="Test", url="http://localhost:8000")
        client = A2AClient(my_card=card)
        d = client.publish_my_card()
        assert d["name"] == "xeno"

    def test_no_card(self):
        client = A2AClient()
        assert client.publish_my_card() == {}


class TestAGNTCYClient:
    def test_init(self):
        client = AGNTCYClient()
        assert client.list_cached() == []

    def test_register_and_cache(self, tmp_path):
        cache = tmp_path / "agntcy_cache.json"
        client = AGNTCYClient(local_cache=cache)
        record = AGNTCYAgentRecord(
            id="agent_1",
            name="test-agent",
            description="A test agent",
            version="1.0",
            capabilities=["search", "code"],
        )
        asyncio.run(client.register(record))
        cached = client.list_cached()
        assert len(cached) == 1
        assert cached[0].name == "test-agent"

    def test_agent_record_roundtrip(self):
        record = AGNTCYAgentRecord(
            id="a1", name="agent1", description="desc",
            organization="org", endpoints=["http://localhost"],
            capabilities=["cap1"],
        )
        d = record.to_dict()
        assert d["name"] == "agent1"
        record2 = AGNTCYAgentRecord.from_dict(d)
        assert record2.id == "a1"


class TestUMP:
    def test_access_controller(self, tmp_path):
        grants_file = tmp_path / "grants.json"
        ctrl = UMPAccessController("xeno", grants_file=grants_file)
        g = ctrl.grant("agent_b", UMPPermission.READ, tier_scope=["semantic"])
        assert g.grantor == "xeno"
        assert g.grantee == "agent_b"
        ok, gid = ctrl.check_access("agent_b", UMPPermission.READ)
        assert ok

    def test_access_denied(self):
        ctrl = UMPAccessController("xeno")
        ok, reason = ctrl.check_access("unknown", UMPPermission.READ)
        assert not ok
        assert reason == "no grant"

    def test_revoke_grant(self):
        ctrl = UMPAccessController("xeno")
        g = ctrl.grant("b", UMPPermission.WRITE)
        assert ctrl.revoke(g.id)
        ok, _ = ctrl.check_access("b", UMPPermission.WRITE)
        assert not ok

    def test_read_write_grants_both_access(self):
        ctrl = UMPAccessController("xeno")
        ctrl.grant("b", UMPPermission.READ_WRITE, tier_scope=["semantic", "episodic"])
        ok, _ = ctrl.check_access("b", UMPPermission.READ, "semantic")
        assert ok
        ok, _ = ctrl.check_access("b", UMPPermission.WRITE, "episodic")
        assert ok
        # But READ-only should not grant WRITE
        ctrl2 = UMPAccessController("xeno")
        ctrl2.grant("c", UMPPermission.READ)
        ok2, _ = ctrl2.check_access("c", UMPPermission.WRITE, "semantic")
        assert not ok2

    def test_ump_client_init(self):
        client = UMPClient("xeno")
        assert client.my_id == "xeno"


class TestProtocolImports:
    def test_all_exported(self):
        from xeno.protocols import __all__
        expected = {
            "MCP2025Client", "MCPServerCard",
            "A2AClient", "A2AAgentCard",
            "AGNTCYClient",
            "UMPClient", "UMPAccessController", "UMPPermission",
        }
        assert expected.issubset(set(__all__))
