"""Built-in governance hooks."""
from __future__ import annotations
import logging
from xeno.hooks.registry import HookRegistry, HookEvent, HookAction, HookContext, HookDecision
from xeno.hooks.risk import RiskClassifier, BashAllowlist, RiskLevel
from xeno.hooks.audit import AuditLog
logger = logging.getLogger(__name__)

def register_governance_hooks(registry, classifier, audit, bash_allowlist=None, workspace_root=None):
    bash = bash_allowlist or BashAllowlist()
    async def pre_tool_use(ctx):
        assessment = classifier.classify(ctx.tool_name, ctx.tool_args, workspace_root)
        if ctx.tool_name in ("shell_execute","shell_run_python"):
            command = ctx.tool_args.get("command", ctx.tool_args.get("code",""))
            allowed, reason = bash.check(command)
            if not allowed:
                return HookDecision(action=HookAction.BLOCK, block_reason=reason)
        if assessment.auto_approve:
            return HookDecision(action=HookAction.ALLOW, metadata={"risk": assessment.level.value})
        if assessment.level == RiskLevel.DESTRUCTIVE:
            return HookDecision(action=HookAction.BLOCK,
                block_reason=f"DESTRUCTIVE: {assessment.reason}")
        if assessment.requires_confirmation:
            return HookDecision(action=HookAction.DELAY,
                delay_prompt=f"Approve {ctx.tool_name}? Risk: {assessment.level.value}")
        return HookDecision(action=HookAction.ALLOW)
    async def post_tool_use(ctx):
        audit.log_tool_call(ctx.tool_name, ctx.tool_args, ctx.tool_result,
                           risk_level=ctx.metadata.get("risk_level",""),
                           session_id=ctx.session_id,
                           success=ctx.metadata.get("success",True),
                           error=ctx.metadata.get("error",""))
        return HookDecision(action=HookAction.ALLOW)
    registry.register(HookEvent.PRE_TOOL_USE, pre_tool_use, name="governance_pre", priority=10)
    registry.register(HookEvent.POST_TOOL_USE, post_tool_use, name="governance_post", priority=10)
