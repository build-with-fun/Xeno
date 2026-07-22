"""Tests for the Gateway API."""

import pytest
from xeno.server.gateway import GatewayAPI, GatewayAgentRecord, AgentHealth, RouteStrategy


class TestGatewayAgentRecord:
    def test_create(self):
        r = GatewayAgentRecord(id="a1", name="test", type="local")
        assert r.name == "test"
        assert r.health == AgentHealth.UNKNOWN

    def test_health_string_conversion(self):
        r = GatewayAgentRecord(id="a1", name="test", type="local", health="healthy")
        assert r.health == AgentHealth.HEALTHY

    def test_to_dict(self):
        r = GatewayAgentRecord(id="a1", name="test", type="local")
        d = r.to_dict()
        assert d["name"] == "test"
        assert d["health"] == "unknown"

    def test_success_rate(self):
        r = GatewayAgentRecord(id="a1", name="test", type="local")
        assert r.success_rate == 1.0
        r.total_requests = 10
        r.successful_requests = 7
        assert r.success_rate == 0.7


@pytest.fixture
def gw(tmp_path):
    return GatewayAPI(data_dir=tmp_path / "gateway")


class TestGatewayAPI:
    def test_init(self, gw):
        assert gw.stats()["total_agents"] == 0
        assert gw.stats()["strategy"] == "round_robin"

    def test_register_agent(self, gw):
        aid = gw.register_agent("test-agent", "local", capabilities=["search"], tags=["test"])
        assert aid is not None
        assert gw.stats()["total_agents"] == 1

    def test_get_agent(self, gw):
        aid = gw.register_agent("agent-x", "remote_a2a", url="http://example.com")
        agent = gw.get_agent(aid)
        assert agent is not None
        assert agent.name == "agent-x"

    def test_unregister(self, gw):
        aid = gw.register_agent("temp", "local")
        assert gw.unregister(aid)
        assert gw.get_agent(aid) is None

    def test_health_management(self, gw):
        aid = gw.register_agent("healthy-agent", "local")
        gw.set_health(aid, AgentHealth.HEALTHY)
        assert gw.get_agent(aid).health == AgentHealth.HEALTHY
        gw.set_health(aid, AgentHealth.UNHEALTHY)
        assert gw.get_agent(aid).health == AgentHealth.UNHEALTHY

    def test_list_by_health(self, gw):
        a1 = gw.register_agent("healthy", "local")
        a2 = gw.register_agent("unhealthy", "local")
        gw.set_health(a1, AgentHealth.HEALTHY)
        gw.set_health(a2, AgentHealth.UNHEALTHY)
        healthy = gw.list_agents(health=AgentHealth.HEALTHY)
        assert len(healthy) == 1
        assert healthy[0].name == "healthy"

    def test_list_by_type(self, gw):
        gw.register_agent("local-agent", "local")
        gw.register_agent("remote-agent", "remote_a2a")
        locals_only = gw.list_agents(type_filter="local")
        assert len(locals_only) == 1
        assert locals_only[0].name == "local-agent"

    def test_record_request(self, gw):
        aid = gw.register_agent("tracked", "local")
        gw.record_request(aid, True, 150.0)
        agent = gw.get_agent(aid)
        assert agent.total_requests == 1
        assert agent.successful_requests == 1
        assert agent.avg_response_ms == 150.0
        gw.record_request(aid, False, 200.0)
        assert agent.total_requests == 2
        assert agent.successful_requests == 1

    def test_route_round_robin(self, gw):
        a1 = gw.register_agent("first", "local")
        a2 = gw.register_agent("second", "local")
        gw.set_health(a1, AgentHealth.HEALTHY)
        gw.set_health(a2, AgentHealth.HEALTHY)
        route1 = gw.route()
        route2 = gw.route()
        assert route1 is not None
        assert route2 is not None

    def test_route_by_capability(self, gw):
        gw.register_agent("general", "local")
        aid = gw.register_agent("specialist", "local", capabilities=["search"])
        gw.set_health(aid, AgentHealth.HEALTHY)
        route = gw.route(required_capability="search")
        assert route is not None
        assert "search" in route.capabilities

    def test_route_strategies(self, gw):
        for strategy in RouteStrategy:
            gw.set_strategy(strategy)
            assert gw.stats()["strategy"] == strategy.value

    def test_strategy_default(self, gw):
        assert gw.stats()["strategy"] == "round_robin"

    def test_route_no_agents(self, gw):
        assert gw.route() is None

    def test_route_preferred_agent(self, gw):
        aid = gw.register_agent("preferred", "local")
        gw.set_health(aid, AgentHealth.HEALTHY)
        route = gw.route(preferred_agent=aid)
        assert route is not None
        assert route.name == "preferred"

    def test_route_preferred_unhealthy(self, gw):
        pref = gw.register_agent("preferred", "local")
        other = gw.register_agent("other", "local")
        gw.set_health(pref, AgentHealth.UNHEALTHY)
        gw.set_health(other, AgentHealth.HEALTHY)
        route = gw.route(preferred_agent=pref)
        assert route is not None

    def test_save_and_load(self, tmp_path):
        data_dir = tmp_path / "gateway"
        g1 = GatewayAPI(data_dir=data_dir)
        g1.register_agent("saved", "local", capabilities=["persist"])
        g2 = GatewayAPI(data_dir=data_dir)
        assert g2.stats()["total_agents"] >= 1

    def test_full_lifecycle(self, gw):
        aid = gw.register_agent("worker", "local", capabilities=["code", "search"])
        assert aid
        gw.set_health(aid, AgentHealth.HEALTHY)
        for i in range(5):
            gw.record_request(aid, True, 100 + i * 10)
        route = gw.route(required_capability="code")
        assert route
        assert route.total_requests == 5
        assert route.avg_response_ms == 120.0
        stats = gw.stats()
        assert stats["healthy"] >= 1
