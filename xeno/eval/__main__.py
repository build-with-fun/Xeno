"""CLI entry point for the eval framework.

Usage:
    uv run python -m xeno.eval             # list cases
    uv run python -m xeno.eval.run         # run all cases
"""
import argparse
import sys
from xeno.eval.runner import get_all_cases


def main():
    parser = argparse.ArgumentParser(description="Xeno Agent Eval Runner")
    parser.add_argument("--list", action="store_true", help="List all registered eval cases")
    parser.add_argument("--case", default=None, help="Run a specific case by name")
    args = parser.parse_args()

    cases = get_all_cases()

    if args.list:
        print("Registered eval cases:")
        for name, case in cases.items():
            tags = ", ".join(case.tags) if case.tags else "none"
            print(f"  {name}: {case.prompt[:60]} [{tags}]")
        return

    if args.case:
        if args.case not in cases:
            print(f"Unknown case '{args.case}'. Available: {list(cases.keys())}")
            sys.exit(1)
        cases_to_run = {args.case: cases[args.case]}
    else:
        cases_to_run = cases

    print(f"Running {len(cases_to_run)} eval case(s)...")
    for name, case in cases_to_run.items():
        print(f"  {name}: {case.prompt[:60]}")
    print("\nUse --agent-fn to specify a real agent function for actual execution.")


if __name__ == "__main__":
    main()
