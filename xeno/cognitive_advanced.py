"""Advanced cognitive reasoning patterns for Xeno.

Implements additional reasoning scaffolds from the deepagents guide:
- Chain of Verification (CoVe)
- Graph of Thoughts (GoT) with merge/loop/transform
- Self-Consistency (majority voting)
- Self-Ask (question decomposition)
- Plan-and-Solve (upfront planning)

These complement the base patterns in cognitive.py.
"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Callable, Optional


class AdvancedPattern(str, Enum):
    CHAIN_OF_VERIFICATION = "chain_of_verification"
    GRAPH_OF_THOUGHTS = "graph_of_thoughts"
    SELF_CONSISTENCY = "self_consistency"
    SELF_ASK = "self_ask"
    PLAN_AND_SOLVE = "plan_and_solve"


class GoTTransform(str, Enum):
    GENERATE = "generate"
    AGGREGATE = "aggregate"
    REFINE = "refine"
    SCORE = "score"
    LOOP = "loop"
    MERGE = "merge"
    SPLIT = "split"


# --- Prompts ---

COVE_SYSTEM_PROMPT = """You are a Chain of Verification (CoVe) agent.
Given a question or task:
1. Generate an initial answer
2. Break the answer into verifiable claims
3. For each claim, write a verification question
4. Answer each verification question independently
5. Revise the original answer based on verified/unverified claims
6. Output a final, verified answer

Format:
INITIAL_ANSWER: [first draft]
CLAIMS:
- claim 1
- claim 2
VERIFICATIONS:
- Q: [verification question for claim 1] -> A: [answer]
- Q: [verification question for claim 2] -> A: [answer]
REVISED_ANSWER: [improved answer]
CONFIDENCE: [0.0-1.0]"""

SELF_ASK_SYSTEM_PROMPT = """You are a Self-Ask agent that decomposes complex questions.
1. Given the original question, ask yourself follow-up questions
2. Answer each follow-up independently
3. Compose the final answer from sub-answers

Format:
ORIGINAL: [the question]
FOLLOW_UP_1: [sub-question] -> ANSWER_1: [answer]
FOLLOW_UP_2: [sub-question] -> ANSWER_2: [answer]
...
FINAL_ANSWER: [composed answer]"""

PLAN_AND_SOLVE_SYSTEM_PROMPT = """You are a Plan-and-Solve agent.
1. Analyze the problem
2. Create a step-by-step plan
3. Execute each step, tracking results
4. Handle errors and adjust the plan
5. Produce the final answer

Format:
ANALYSIS: [understanding of the problem]
PLAN:
1. [step 1]
2. [step 2]
...
EXECUTION:
Step 1: [result]
Step 2: [result]
...
FINAL_ANSWER: [answer]"""

GOT_SYSTEM_PROMPT = """You are a Graph of Thoughts agent that manages a network of reasoning nodes.
1. Generate multiple thought branches (initial nodes)
2. Evaluate and score each branch
3. Merge related branches to form stronger combined thoughts
4. Refine weak branches
5. Loop until convergence
6. Select the best final thought

Output a JSON array of operations:
[
  {"op": "generate", "thoughts": ["thought1", "thought2"]},
  {"op": "score", "thoughts": ["thought1"], "scores": [8]},
  {"op": "merge", "thoughts": ["thought1", "thought2"], "result": "merged"},
  {"op": "refine", "thoughts": ["merged"], "result": "refined"},
  {"op": "final", "thought": "best result"}
]"""

SELF_CONSISTENCY_SYSTEM_PROMPT = """You are a Self-Consistency agent.
Generate multiple independent solutions to the problem, then vote on the most consistent answer.

SOLUTION_1: [independent solution 1]
SOLUTION_2: [independent solution 2]
SOLUTION_3: [independent solution 3]
VOTE: [answer with majority support]
CONFIDENCE: [fraction of solutions agreeing]"""


# --- Data structures ---

@dataclass
class GoTNode:
    id: str
    content: str
    score: float = 0.0
    parent_ids: list[str] = field(default_factory=list)
    children_ids: list[str] = field(default_factory=list)
    iteration: int = 0
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "id": self.id, "content": self.content, "score": self.score,
            "parent_ids": self.parent_ids, "children_ids": self.children_ids,
            "iteration": self.iteration,
        }


@dataclass
class GoTGraph:
    nodes: dict[str, GoTNode] = field(default_factory=dict)
    operations: list[dict] = field(default_factory=list)
    final_node_id: Optional[str] = None

    def add_node(self, content: str, parent_ids: Optional[list[str]] = None,
                 score: float = 0.0, iteration: int = 0) -> GoTNode:
        node_id = f"got_{uuid.uuid4().hex[:8]}"
        node = GoTNode(
            id=node_id, content=content, score=score,
            parent_ids=parent_ids or [], iteration=iteration,
        )
        self.nodes[node_id] = node
        if parent_ids:
            for pid in parent_ids:
                if pid in self.nodes:
                    self.nodes[pid].children_ids.append(node_id)
        return node

    def get_top_nodes(self, k: int = 1) -> list[GoTNode]:
        sorted_nodes = sorted(self.nodes.values(), key=lambda n: n.score, reverse=True)
        return sorted_nodes[:k]

    def merge_nodes(self, node_ids: list[str], merged_content: str) -> GoTNode:
        return self.add_node(merged_content, parent_ids=node_ids)

    def to_dict(self) -> dict:
        return {
            "nodes": {nid: n.to_dict() for nid, n in self.nodes.items()},
            "operations": self.operations,
            "final_node_id": self.final_node_id,
        }


@dataclass
class VerificationClaim:
    claim: str
    verification_question: str
    verification_answer: Optional[str] = None
    verified: Optional[bool] = None


@dataclass
class CoVeTrace:
    initial_answer: str
    claims: list[VerificationClaim] = field(default_factory=list)
    revised_answer: Optional[str] = None
    confidence: float = 0.0
    verified_count: int = 0
    unverified_count: int = 0

    def to_dict(self) -> dict:
        return {
            "initial_answer": self.initial_answer,
            "claims": [
                {"claim": c.claim, "question": c.verification_question,
                 "answer": c.verification_answer, "verified": c.verified}
                for c in self.claims
            ],
            "revised_answer": self.revised_answer,
            "confidence": self.confidence,
            "verified": self.verified_count,
            "unverified": self.unverified_count,
        }


@dataclass
class ConsistencyVote:
    solution: str
    answer: str
    reasoning: str = ""


class AdvancedCognitiveEngine:
    """Extended cognitive engine with CoVe, GoT, Self-Consistency, Self-Ask, Plan-and-Solve."""

    def __init__(self, model: str = "deepseek:deepseek-chat"):
        self.model = model
        self.cove_traces: list[CoVeTrace] = []
        self.got_graphs: list[GoTGraph] = []
        self.consistency_runs: list[list[ConsistencyVote]] = []

    def get_system_prompt(self, pattern: AdvancedPattern) -> str:
        return {
            AdvancedPattern.CHAIN_OF_VERIFICATION: COVE_SYSTEM_PROMPT,
            AdvancedPattern.GRAPH_OF_THOUGHTS: GOT_SYSTEM_PROMPT,
            AdvancedPattern.SELF_CONSISTENCY: SELF_CONSISTENCY_SYSTEM_PROMPT,
            AdvancedPattern.SELF_ASK: SELF_ASK_SYSTEM_PROMPT,
            AdvancedPattern.PLAN_AND_SOLVE: PLAN_AND_SOLVE_SYSTEM_PROMPT,
        }[pattern]

    # --- Chain of Verification ---

    def create_cove_trace(self, initial_answer: str) -> CoVeTrace:
        trace = CoVeTrace(initial_answer=initial_answer)
        self.cove_traces.append(trace)
        return trace

    def add_claim(self, trace: CoVeTrace, claim: str, verification_question: str) -> VerificationClaim:
        vc = VerificationClaim(claim=claim, verification_question=verification_question)
        trace.claims.append(vc)
        return vc

    def verify_claim(self, trace: CoVeTrace, claim_index: int, answer: str, verified: bool) -> None:
        if 0 <= claim_index < len(trace.claims):
            trace.claims[claim_index].verification_answer = answer
            trace.claims[claim_index].verified = verified
            if verified:
                trace.verified_count += 1
            else:
                trace.unverified_count += 1

    def revise_answer(self, trace: CoVeTrace, revised: str, confidence: float = 0.85) -> CoVeTrace:
        trace.revised_answer = revised
        trace.confidence = confidence
        return trace

    def parse_cove_response(self, text: str) -> dict:
        """Parse CoVe-formatted LLM response into structured data."""
        result = {"claims": [], "initial": "", "revised": ""}
        lines = text.strip().split("\n")
        section = None
        for line in lines:
            line_stripped = line.strip()
            if line_stripped.startswith("INITIAL_ANSWER:"):
                result["initial"] = line_stripped.split(":", 1)[1].strip()
            elif line_stripped.startswith("REVISED_ANSWER:"):
                result["revised"] = line_stripped.split(":", 1)[1].strip()
            elif line_stripped.startswith("CONFIDENCE:"):
                try:
                    result["confidence"] = float(line_stripped.split(":", 1)[1].strip())
                except ValueError:
                    result["confidence"] = 0.5
            elif line_stripped.startswith("- ") or line_stripped.startswith("Q:"):
                result["claims"].append(line_stripped.lstrip("- "))
        return result

    # --- Graph of Thoughts ---

    def create_got_graph(self) -> GoTGraph:
        graph = GoTGraph()
        self.got_graphs.append(graph)
        return graph

    def got_generate(self, graph: GoTGraph, thoughts: list[str], iteration: int = 0) -> list[GoTNode]:
        nodes = [graph.add_node(t, iteration=iteration) for t in thoughts]
        graph.operations.append({"op": "generate", "count": len(thoughts), "iteration": iteration})
        return nodes

    def got_score(self, graph: GoTGraph, node_ids: list[str], scores: list[float]) -> None:
        for nid, score in zip(node_ids, scores):
            if nid in graph.nodes:
                graph.nodes[nid].score = score
        graph.operations.append({"op": "score", "nodes": node_ids, "scores": scores})

    def got_merge(self, graph: GoTGraph, node_ids: list[str], merged_content: str) -> GoTNode:
        node = graph.merge_nodes(node_ids, merged_content)
        graph.operations.append({"op": "merge", "from": node_ids, "to": node.id})
        return node

    def got_refine(self, graph: GoTGraph, node_id: str, refined_content: str, new_score: float = 0.0) -> GoTNode:
        node = graph.add_node(refined_content, parent_ids=[node_id], score=new_score)
        graph.operations.append({"op": "refine", "from": node_id, "to": node.id})
        return node

    def got_loop(self, graph: GoTGraph, iteration: int, thoughts: list[str]) -> list[GoTNode]:
        """Continue the graph with new generation at a given iteration."""
        return self.got_generate(graph, thoughts, iteration=iteration)

    def got_finalize(self, graph: GoTGraph) -> Optional[GoTNode]:
        top = graph.get_top_nodes(k=1)
        if top:
            graph.final_node_id = top[0].id
            graph.operations.append({"op": "final", "node": top[0].id})
            return top[0]
        return None

    # --- Self-Consistency ---

    def create_consistency_run(self) -> list[ConsistencyVote]:
        run: list[ConsistencyVote] = []
        self.consistency_runs.append(run)
        return run

    def add_solution(self, run: list[ConsistencyVote], solution: str, answer: str, reasoning: str = "") -> ConsistencyVote:
        vote = ConsistencyVote(solution=solution, answer=answer, reasoning=reasoning)
        run.append(vote)
        return vote

    def tally_votes(self, run: list[ConsistencyVote]) -> dict[str, Any]:
        counts: dict[str, int] = {}
        for v in run:
            counts[v.answer] = counts.get(v.answer, 0) + 1
        if not counts:
            return {"winner": "", "confidence": 0.0, "counts": {}}
        winner = max(counts, key=counts.get)
        confidence = counts[winner] / len(run) if run else 0.0
        return {"winner": winner, "confidence": confidence, "counts": counts, "total_solutions": len(run)}

    # --- Self-Ask ---

    def parse_self_ask(self, text: str) -> dict:
        """Parse Self-Ask formatted response."""
        result = {"original": "", "follow_ups": [], "final": ""}
        lines = text.strip().split("\n")
        for line in lines:
            line_s = line.strip()
            if line_s.startswith("ORIGINAL:"):
                result["original"] = line_s.split(":", 1)[1].strip()
            elif line_s.startswith("FOLLOW_UP"):
                parts = line_s.split("->")
                if len(parts) == 2:
                    q = parts[0].split(":", 1)[1].strip() if ":" in parts[0] else parts[0].strip()
                    a = parts[1].split(":", 1)[1].strip() if ":" in parts[1] else parts[1].strip()
                    result["follow_ups"].append({"question": q, "answer": a})
            elif line_s.startswith("FINAL_ANSWER:"):
                result["final"] = line_s.split(":", 1)[1].strip()
        return result

    # --- Plan-and-Solve ---

    def parse_plan_and_solve(self, text: str) -> dict:
        """Parse Plan-and-Solve formatted response."""
        result = {"plan": [], "execution": [], "final": "", "analysis": ""}
        lines = text.strip().split("\n")
        section = None
        for line in lines:
            line_s = line.strip()
            if line_s.startswith("ANALYSIS:"):
                result["analysis"] = line_s.split(":", 1)[1].strip()
                section = None
            elif line_s == "PLAN:":
                section = "plan"
            elif line_s.startswith("EXECUTION:"):
                section = "exec"
            elif line_s.startswith("FINAL_ANSWER:"):
                result["final"] = line_s.split(":", 1)[1].strip()
                section = None
            elif section == "plan" and line_s and line_s[0].isdigit():
                result["plan"].append(line_s.split(".", 1)[1].strip() if "." in line_s else line_s)
            elif section == "exec" and line_s.lower().startswith("step"):
                result["execution"].append(line_s)
        return result
