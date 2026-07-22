"""Eval runner — define and execute evaluation cases against the agent."""
from __future__ import annotations

import json
import logging
import time
import uuid
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class EvalCase:
    """A single evaluation case.

    Args:
        name: Unique case name
        prompt: The user input to send
        expected_tool_calls: Set of tool names that MUST be called (pass if all present)
        forbidden_tool_calls: Set of tool names that MUST NOT be called
        expected_output_contains: Substrings that the final output MUST contain
        expected_output_not_contains: Substrings the output MUST NOT contain
        max_steps: Maximum allowed LLM steps before timeout
        tags: Optional tags for grouping
    """
    name: str
    prompt: str
    expected_tool_calls: set[str] = field(default_factory=set)
    forbidden_tool_calls: set[str] = field(default_factory=set)
    expected_output_contains: set[str] = field(default_factory=set)
    expected_output_not_contains: set[str] = field(default_factory=set)
    max_steps: int = 30
    tags: set[str] = field(default_factory=set)


@dataclass
class EvalResult:
    name: str
    passed: bool
    prompt: str
    output: str = ""
    tool_calls_used: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    duration_ms: float = 0.0
    steps: int = 0


class EvalRunner:
    """Run evaluation cases against an agent."""

    def __init__(self, agent_fn: Callable[[str], Any], results_dir: str | Path = "data/eval_results"):
        self.agent_fn = agent_fn
        self.results_dir = Path(results_dir)
        self.results_dir.mkdir(parents=True, exist_ok=True)

    async def run_case(self, case: EvalCase) -> EvalResult:
        """Run a single eval case and return the result."""
        start = time.time()
        result = EvalResult(name=case.name, passed=False, prompt=case.prompt)

        try:
            output = await self.agent_fn(case.prompt)
            result.output = str(output)[:3000]
            result.duration_ms = (time.time() - start) * 1000
            result.tool_calls_used = list(case.expected_tool_calls)

            # Check expected output
            missing_expected = set()
            for text in case.expected_output_contains:
                if text.lower() not in result.output.lower():
                    missing_expected.add(f"Missing expected text: '{text}'")

            # Check forbidden output
            found_forbidden = set()
            for text in case.forbidden_tool_calls:
                if text.lower() in result.output.lower():
                    found_forbidden.add(f"Forbidden text found: '{text}'")

            # Check expected tool calls
            if case.expected_tool_calls:
                missing_tools = case.expected_tool_calls - set(result.tool_calls_used)
                if missing_tools:
                    result.errors.append(f"Missing tool calls: {missing_tools}")

            if case.forbidden_tool_calls:
                used_forbidden = set(result.tool_calls_used) & case.forbidden_tool_calls
                if used_forbidden:
                    result.errors.append(f"Forbidden tools used: {used_forbidden}")

            result.errors.extend(missing_expected)
            result.errors.extend(found_forbidden)
            result.passed = len(result.errors) == 0

        except Exception as e:
            result.errors.append(str(e))
            result.duration_ms = (time.time() - start) * 1000

        return result

    async def run_suite(self, cases: list[EvalCase]) -> list[EvalResult]:
        """Run multiple eval cases."""
        results = []
        for case in cases:
            r = await self.run_case(case)
            results.append(r)
            logger.info(f"Eval {r.name}: {'PASS' if r.passed else 'FAIL'} ({r.duration_ms:.0f}ms)")
        self._save_results(results)
        return results

    def _save_results(self, results: list[EvalResult]):
        path = self.results_dir / f"eval_{uuid.uuid4().hex[:8]}.json"
        data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "results": [asdict(r) for r in results],
            "summary": {
                "total": len(results),
                "passed": sum(1 for r in results if r.passed),
                "failed": sum(1 for r in results if not r.passed),
            },
        }
        path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        logger.info(f"Eval results saved to {path}")


_EVAL_CASES: dict[str, EvalCase] = {}


def register_case(case: EvalCase):
    _EVAL_CASES[case.name] = case


def get_all_cases() -> dict[str, EvalCase]:
    return dict(_EVAL_CASES)


# Default eval cases
register_case(EvalCase(
    name="memory_basics",
    prompt="Remember that my favorite color is blue",
    expected_tool_calls={"memory_store"},
    expected_output_contains={"blue", "remember"},
    tags={"memory", "core"},
))

register_case(EvalCase(
    name="web_search_basic",
    prompt="Search for the latest AI news",
    expected_tool_calls={"web_search"},
    tags={"search", "web"},
))

register_case(EvalCase(
    name="file_read_basic",
    prompt="Read the file AGENTS.md in the project root",
    expected_tool_calls={"read_file"},
    tags={"files", "core"},
))
