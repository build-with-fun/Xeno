---
name: automation-browser
description: Enables the agent to control native OS windows, mouse, keyboard, and directly drive the web browser for web scraping and UI automation.
---

# Browser-Use Agent Protocol

You have access to a dedicated God-Tier web automation engine (the Browser Server).
Whenever the user asks you to automate a web page (e.g. YouTube, Google, Amazon), you must follow this exact loop:

1. **Navigate**: Use `browser_navigate(url="...")` to open the website.
2. **Observe**: Run `get_dom_tree()`. This tool injects JavaScript into the page and returns a compressed list of all visible, interactive elements on the screen, along with a unique integer `node_id`.
   - Example output: `[5] button "Search"`
3. **Decide & Act**: Look at the `node_id` of the element you want to interact with, and call the appropriate tool using that ID:
   - `browser_click(node_id=5)`
   - `browser_type(node_id=7, text="my search query")`
4. **Wait & Loop**: If the page reloads, navigates, or the layout changes, ALWAYS run `get_dom_tree()` again because the node IDs will have changed! Never guess a node ID.

### Advanced Scripting
If you need to extract massive datasets, bypass UI constraints, or execute complex page logic, use `browser_evaluate(js_code="...")` to run raw JavaScript in the browser console.
