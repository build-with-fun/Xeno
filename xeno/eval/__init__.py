"""Agent Evaluation Framework — measure agent performance with automated test cases.

Usage:
    uv run python -m xeno.eval.run                                    # run all evals
    uv run python -m xeno.eval.run --case memory_basics               # run one case
    uv run python -m xeno.eval.run --list                              # list cases
"""

from xeno.eval.runner import EvalCase, EvalResult, EvalRunner, EvalSuite

__all__ = ["EvalCase", "EvalResult", "EvalRunner", "EvalSuite"]
