"""
Example Plugin for Xeno Dynamic System.

This plugin demonstrates the plugin API.
Drop this folder into plugins/ to load it.

plugin.json provides metadata.
__init__.py provides the register() function.
"""


def register(registry):
    """Register hooks and tools with the dynamic registry."""

    def my_before_tool(context):
        """Example hook: log every tool call."""
        print(f"[Example Plugin] Before tool: {context.tool_name}")
        from xeno.agent_hooks import HookResult
        return HookResult.allow()

    def my_after_tool(context):
        """Example hook: log tool results."""
        print(f"[Example Plugin] After tool: {context.tool_name}")
        from xeno.agent_hooks import HookResult
        return HookResult()

    # Example custom tool
    def example_greeting(name: str = "World") -> str:
        """Say hello. This is an example tool provided by the example plugin."""
        return f"Hello, {name}! This tool was loaded dynamically from a plugin."

    return {
        "hooks": {
            "before_tool": my_before_tool,
            "after_tool": my_after_tool,
        },
        "tools": [example_greeting],
        "mcp_servers": {},
    }
