"""Tests for the prompt tiering system."""

import pytest
from xeno.brain.prompt_tiers import PromptTierBuilder


class TestPromptTierBuilder:
    def test_init(self):
        ptb = PromptTierBuilder()
        stats = ptb.cache_stats
        assert not stats["identity_cached"]
        assert not stats["instructions_cached"]
        assert stats["build_count"] == 0

    def test_build_simple_prompt(self):
        ptb = PromptTierBuilder()
        prompt = ptb.build_prompt("Hello, who are you?")
        assert "User message: Hello, who are you?" in prompt
        assert "autonomous AI agent" in prompt

    def test_cache_identity(self):
        ptb = PromptTierBuilder()
        prompt1 = ptb.build_prompt("Hi")
        prompt2 = ptb.build_prompt("Hi again")
        # Identity should be the same both times
        ident1 = ptb._build_identity()
        ident2 = ptb._build_identity()
        assert ident1 == ident2
        assert ptb.cache_stats["identity_cached"]

    def test_cache_instructions(self):
        ptb = PromptTierBuilder()
        ptb.set_tools([{"name": "search", "description": "Web search"}])
        inst1 = ptb._build_instructions()
        inst2 = ptb._build_instructions()
        assert inst1 == inst2
        assert ptb.cache_stats["instructions_cached"]

    def test_invalidate_cache(self):
        ptb = PromptTierBuilder()
        ptb.build_prompt("Test")
        ptb.invalidate()
        stats = ptb.cache_stats
        assert not stats["identity_cached"]
        assert not stats["instructions_cached"]

    def test_instructions_update(self):
        ptb = PromptTierBuilder()
        ptb.set_tools([{"name": "tool_a", "description": "First tool"}])
        inst1 = ptb._build_instructions()
        ptb.set_tools([{"name": "tool_b", "description": "Second tool"}])
        inst2 = ptb._build_instructions()
        assert inst1 != inst2

    def test_skills_in_instructions(self):
        ptb = PromptTierBuilder()
        ptb.set_skills(["Web research", "File management"])
        prompt = ptb.build_prompt("Do something")
        assert "Available skills" in prompt
        assert "Web research" in prompt

    def test_capabilities_in_instructions(self):
        ptb = PromptTierBuilder()
        ptb.set_capabilities(["code_execution", "browser_automation"])
        prompt = ptb.build_prompt("Test")
        assert "Capabilities" in prompt

    def test_metadata_contains_user(self):
        ptb = PromptTierBuilder()
        prompt = ptb.build_prompt("Hi", user_name="Ammar", session_id="sess_123")
        assert "Ammar" in prompt
        assert "sess_123" in prompt

    def test_working_context(self):
        ptb = PromptTierBuilder()
        context = [
            {"role": "user", "content": "Hello"},
            {"role": "assistant", "content": "Hi there"},
        ]
        profile = {"name": "Ammar", "preferences": {"theme": "dark"}}
        prompt = ptb.build_prompt("What's my name?", context=context, profile=profile)
        assert "Ammar" in prompt
        assert "dark" in prompt

    def test_estimate_tokens(self):
        ptb = PromptTierBuilder()
        prompt = "Hello world, this is a test prompt for Xeno."
        tokens = ptb.estimate_tokens(prompt)
        assert tokens > 0
        assert isinstance(tokens, int)

    def test_selective_tiers(self):
        ptb = PromptTierBuilder()
        no_identity = ptb.build_prompt("Hi", include_identity=False)
        no_meta = ptb.build_prompt("Hi", include_metadata=False)
        no_instructions = ptb.build_prompt("Hi", include_instructions=False)
        # All should work without errors
        assert "User message: Hi" in no_identity
        assert "User message: Hi" in no_meta
        assert "User message: Hi" in no_instructions

    def test_configure_identity(self):
        ptb = PromptTierBuilder()
        ptb.configure_identity(name="Xeno-Pro", description="Advanced AI agent")
        prompt = ptb.build_prompt("Who are you?")
        assert "Xeno-Pro" in prompt
        assert "Advanced AI agent" in prompt

    def test_build_count(self):
        ptb = PromptTierBuilder()
        assert ptb.cache_stats["build_count"] == 0
        ptb.build_prompt("First")
        assert ptb.cache_stats["build_count"] == 1
        ptb.build_prompt("Second")
        assert ptb.cache_stats["build_count"] == 2

    def test_tool_registry_reset(self):
        ptb = PromptTierBuilder()
        ptb.set_tools([{"name": "tool", "description": "desc"}])
        ptb.bump_instructions()
        assert ptb._instructions_version > 0

    def test_context_limit(self):
        ptb = PromptTierBuilder()
        many_context = [{"role": "user", "content": f"Message {i}"} for i in range(20)]
        prompt = ptb.build_prompt("Final message", context=many_context)
        # Should only include last 5 context messages
        assert "Message 19" in prompt
        assert "Message 0" not in prompt
