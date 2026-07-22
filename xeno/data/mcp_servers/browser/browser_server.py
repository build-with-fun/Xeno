import os
import json
import urllib.request
import urllib.error
from pathlib import Path
from fastmcp import FastMCP
from mcp.types import ImageContent

mcp = FastMCP("Browser Automation Server")

DAEMON_URL = os.environ.get("XENO_BROWSER_DAEMON_URL", "http://127.0.0.1:9888")
AGENT_OUTPUT = str(Path(__file__).resolve().parent.parent.parent.parent / "agent_output")
os.makedirs(AGENT_OUTPUT, exist_ok=True)

DAEMON_HINT = (
    "Browser daemon is not running. "
    "Start it with: python xeno/data/mcp_servers/automation/browser_daemon.py"
)

def _post(endpoint: str, data: dict = None, timeout: int = 30) -> str:
    payload = json.dumps(data or {}).encode('utf-8')
    req = urllib.request.Request(
        f"{DAEMON_URL}/{endpoint}",
        data=payload,
        headers={'Content-Type': 'application/json'}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            res = json.loads(response.read().decode('utf-8'))
            if "error" in res:
                return f"Error: {res['error']}"
            result = res.get("result", "Success")
            return json.dumps(result) if not isinstance(result, str) else result
    except urllib.error.URLError:
        return f"CRITICAL Error: {DAEMON_HINT}"
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode('utf-8'))
            return f"Error: {err.get('error', str(e))}"
        except:
            return f"HTTP Error: {str(e)}"
    except Exception as e:
        return f"Request Error: {str(e)}"


# --- Navigation ---

@mcp.tool()
def browser_status() -> str:
    """Check if the browser daemon is running and get current URL."""
    return _post("status")

@mcp.tool()
def browser_navigate(url: str, wait_until: str = "domcontentloaded") -> str:
    """
    Navigate the browser to a URL and wait for it to load.
    url: The full URL to navigate to (e.g. https://google.com)
    wait_until: 'load', 'domcontentloaded', 'networkidle' (default: domcontentloaded)
    """
    return _post("navigate", {"url": url, "wait_until": wait_until, "timeout": 30000})

@mcp.tool()
def browser_back() -> str:
    """Go back to the previous page in history."""
    return _post("back")

@mcp.tool()
def browser_forward() -> str:
    """Go forward to the next page in history."""
    return _post("forward")

@mcp.tool()
def browser_refresh() -> str:
    """Reload the current page."""
    return _post("refresh")


# --- Page info ---

@mcp.tool()
def browser_get_url() -> str:
    """Get the current page URL."""
    return _post("get_url")

@mcp.tool()
def browser_get_title() -> str:
    """Get the current page title."""
    return _post("get_title")

@mcp.tool()
def browser_get_page_source() -> str:
    """Get the full HTML source of the current page."""
    return _post("get_page_source")


# --- DOM queries ---

@mcp.tool()
def get_dom_tree() -> str:
    """
    Extract simplified DOM tree of visible interactive elements.
    Each element has a unique 'id' you MUST use for clicking/typing via node_id.
    """
    return _post("get_dom_tree")

@mcp.tool()
def browser_query_selector(selector: str) -> str:
    """
    Check if a CSS selector exists on the page and return its text + attributes.
    selector: CSS selector (e.g. '#search', 'button.submit', 'input[name="q"]')
    """
    return _post("query_selector", {"selector": selector})

@mcp.tool()
def browser_wait_for_selector(selector: str, timeout: int = 30000, state: str = "visible") -> str:
    """
    Wait for a CSS selector to appear on the page.
    selector: CSS selector to wait for
    timeout: Max wait time in ms (default 30000)
    state: 'visible', 'attached', 'hidden' (default: visible)
    """
    return _post("wait_for_selector", {"selector": selector, "timeout": timeout, "state": state})

@mcp.tool()
def browser_get_attribute(selector: str, attribute: str) -> str:
    """Get an attribute value from an element matched by CSS selector."""
    return _post("get_attribute", {"selector": selector, "attribute": attribute})

@mcp.tool()
def browser_get_text(selector: str) -> str:
    """Get the inner text of an element matched by CSS selector."""
    return _post("get_text", {"selector": selector})


# --- Browser actions ---

@mcp.tool()
def browser_click(node_id: int = None, selector: str = None) -> str:
    """
    Click an element by its DOM node ID (from get_dom_tree) or CSS selector.
    Provide either node_id or selector.
    """
    return _post("click", {"node_id": node_id, "selector": selector})

@mcp.tool()
def browser_double_click(node_id: int = None, selector: str = None) -> str:
    """Double-click an element by DOM node ID or CSS selector."""
    return _post("double_click", {"node_id": node_id, "selector": selector})

@mcp.tool()
def browser_type(node_id: int = None, selector: str = None, text: str = "", wpm: int = 80, clear_first: bool = True) -> str:
    """
    Type text into an input field by DOM node ID or CSS selector.
    node_id: DOM node ID from get_dom_tree()
    selector: CSS selector (alternative to node_id)
    text: The text to type
    wpm: Typing speed in words per minute (default 80)
    clear_first: Clear the field before typing (default True)
    """
    return _post("type", {"node_id": node_id, "selector": selector, "text": text, "wpm": wpm, "clear_first": clear_first})

@mcp.tool()
def browser_fill(selector: str, value: str) -> str:
    """
    Fill an input field with a value instantly (faster than typing).
    selector: CSS selector for the input field
    value: The value to fill
    """
    return _post("fill", {"selector": selector, "value": value})

@mcp.tool()
def browser_select_option(selector: str, value: str = None, label: str = None, index: int = None) -> str:
    """
    Select an option in a dropdown/select element.
    selector: CSS selector for the select element
    value: Select by value attribute
    label: Select by visible text label
    index: Select by option index (0-based)
    """
    return _post("select_option", {"selector": selector, "value": value, "label": label, "index": index})

@mcp.tool()
def browser_hover(node_id: int = None, selector: str = None) -> str:
    """Hover the mouse over an element by DOM node ID or CSS selector."""
    return _post("hover", {"node_id": node_id, "selector": selector})

@mcp.tool()
def browser_press_key(key: str) -> str:
    """
    Press a keyboard key in the browser.
    key: Key name (e.g. 'Enter', 'Escape', 'Tab', 'ArrowDown', 'Control+a')
    """
    return _post("press_key", {"key": key})

@mcp.tool()
def browser_scroll(amount_y: int = 300, amount_x: int = 0) -> str:
    """
    Scroll the page by a number of pixels.
    amount_y: Positive = scroll down, negative = scroll up (default 300)
    amount_x: Horizontal scroll (default 0)
    """
    return _post("scroll", {"amount_y": amount_y, "amount_x": amount_x})


# --- Tabs ---

@mcp.tool()
def browser_new_tab(url: str = "about:blank") -> str:
    """Open a new browser tab and optionally navigate to a URL."""
    return _post("new_tab", {"url": url})

@mcp.tool()
def browser_close_tab() -> str:
    """Close the current browser tab."""
    return _post("close_tab")

@mcp.tool()
def browser_switch_tab(index: int) -> str:
    """
    Switch to a specific browser tab by index.
    index: Tab index (0 = first tab)
    """
    return _post("switch_tab", {"index": index})

@mcp.tool()
def browser_list_tabs() -> str:
    """List all open browser tabs with their titles and URLs."""
    return _post("list_tabs")


# --- Cookies ---

@mcp.tool()
def browser_get_cookies() -> str:
    """Get all cookies from the browser context."""
    return _post("get_cookies")

@mcp.tool()
def browser_set_cookies(cookies_json: str) -> str:
    """
    Set cookies in the browser context.
    cookies_json: JSON string of cookies array, e.g. [{"name":"session","value":"abc","domain":".example.com"}]
    """
    try:
        cookies = json.loads(cookies_json)
        return _post("set_cookies", {"cookies": cookies})
    except json.JSONDecodeError as e:
        return f"Invalid cookies JSON: {e}"

@mcp.tool()
def browser_clear_cookies() -> str:
    """Clear all browser cookies."""
    return _post("clear_cookies")


# --- Screenshot & PDF ---

@mcp.tool()
def browser_screenshot() -> list:
    """
    Take a screenshot of the current browser page.
    Returns the image so you can visually confirm the page state.
    """
    res = _post("screenshot", {})
    if res.startswith("Error:") or res.startswith("CRITICAL Error:"):
        raise Exception(res)
    return [ImageContent(type="image", data=res, mimeType="image/png")]

@mcp.tool()
def browser_screenshot_to_file(filename: str = None, full_page: bool = False) -> str:
    """
    Save a browser screenshot to agent_output/ directory.
    filename: Custom filename (default: auto-generated)
    full_page: Capture full scrollable page (default: False)
    """
    return _post("screenshot_to_file", {"filename": filename, "full_page": full_page})

@mcp.tool()
def browser_html_to_pdf(html_content: str = None, filename: str = None) -> str:
    """
    Generate a PDF from the current page or from raw HTML.
    html_content: Optional raw HTML string to render. If omitted, uses current page.
    filename: Optional filename for the PDF (saved to agent_output/)
    """
    return _post("pdf", {"html_content": html_content, "filename": filename})


# --- Downloads ---

@mcp.tool()
def browser_download_file(node_id: int = None, selector: str = None, filename: str = None) -> str:
    """
    Click an element that triggers a file download and save it to agent_output/.
    node_id: DOM node ID from get_dom_tree() representing the download link/button
    selector: CSS selector (alternative to node_id)
    filename: Optional custom filename (default: uses the server-suggested filename)
    """
    return _post("download", {
        "node_id": node_id,
        "selector": selector,
        "filename": filename,
        "download_dir": AGENT_OUTPUT,
    })

@mcp.tool()
def browser_direct_download(url: str, filename: str = None) -> str:
    """
    Download a file directly via HTTP GET and save to agent_output/.
    url: Direct URL to the file
    filename: Optional custom filename (default: extracted from URL)
    """
    return _post("direct_download", {"url": url, "filename": filename})


# --- Misc ---

@mcp.tool()
def browser_evaluate(js_code: str) -> str:
    """
    Execute raw JavaScript on the current page and return the result.
    js_code: JavaScript code to execute (e.g. "document.title" or "() => { return 1+1 }")
    """
    return _post("evaluate", {"js": js_code})

@mcp.tool()
def browser_wait(ms: int = 1000) -> str:
    """Wait for a specified time in milliseconds."""
    return _post("wait", {"ms": ms})

@mcp.tool()
def browser_set_viewport(width: int = 1920, height: int = 1080) -> str:
    """Set the browser viewport size."""
    return _post("set_viewport", {"width": width, "height": height})

# --- Console & Network ---

@mcp.tool()
def browser_console_logs(clear: bool = False) -> str:
    """
    Get recent browser console logs (log, warn, error, debug messages).
    clear: Clear logs after reading if True (default False)
    """
    return _post("console_logs", {"clear": clear})

@mcp.tool()
def browser_network_logs(clear: bool = False) -> str:
    """
    Get recent network requests and responses captured by the browser.
    clear: Clear captured entries after reading if True (default False)
    """
    return _post("network_logs", {"clear": clear})


# --- Storage ---

@mcp.tool()
def browser_get_local_storage() -> str:
    """Get all localStorage key-value pairs from the current page."""
    return _post("get_local_storage")

@mcp.tool()
def browser_set_local_storage(key: str, value: str = "") -> str:
    """
    Set a localStorage key-value pair on the current page.
    key: localStorage key
    value: Value to set (default empty string)
    """
    return _post("set_local_storage", {"key": key, "value": value})

@mcp.tool()
def browser_clear_local_storage() -> str:
    """Clear all localStorage data for the current domain."""
    return _post("clear_local_storage")

@mcp.tool()
def browser_get_session_storage() -> str:
    """Get all sessionStorage key-value pairs from the current page."""
    return _post("get_session_storage")

@mcp.tool()
def browser_set_session_storage(key: str, value: str = "") -> str:
    """
    Set a sessionStorage key-value pair on the current page.
    key: sessionStorage key
    value: Value to set (default empty string)
    """
    return _post("set_session_storage", {"key": key, "value": value})

@mcp.tool()
def browser_clear_session_storage() -> str:
    """Clear all sessionStorage data for the current domain."""
    return _post("clear_session_storage")


# --- File Upload ---

@mcp.tool()
def browser_upload_file(selector: str, file_path: str) -> str:
    """
    Upload a file to a file input element on the page.
    selector: CSS selector for the <input type="file"> element
    file_path: Absolute path to the file to upload
    """
    return _post("upload_file", {"selector": selector, "file_path": file_path})


# --- Element Screenshot ---

@mcp.tool()
def browser_element_screenshot(selector: str = None, node_id: int = None) -> list:
    """
    Take a screenshot of a specific DOM element on the page.
    selector: CSS selector for the element
    node_id: DOM node ID from get_dom_tree (alternative to selector)
    Returns the element image so you can visually confirm.
    """
    res = _post("element_screenshot", {"selector": selector, "node_id": node_id})
    if res.startswith("Error:") or res.startswith("CRITICAL Error:"):
        raise Exception(res)
    return [ImageContent(type="image", data=res, mimeType="image/png")]

@mcp.tool()
def browser_element_screenshot_to_file(selector: str = None, node_id: int = None, filename: str = None) -> str:
    """
    Save a screenshot of a specific DOM element to agent_output/.
    selector: CSS selector for the element
    node_id: DOM node ID from get_dom_tree (alternative to selector)
    filename: Custom filename (default: auto-generated)
    """
    return _post("element_screenshot_to_file", {
        "selector": selector, "node_id": node_id, "filename": filename
    })


# --- Bounding Box ---

@mcp.tool()
def browser_get_bounding_box(selector: str = None, node_id: int = None) -> str:
    """
    Get the bounding box (position and size) of an element.
    Returns x, y, width, height, visibility status.
    selector: CSS selector for the element
    node_id: DOM node ID from get_dom_tree (alternative to selector)
    """
    return _post("get_bounding_box", {"selector": selector, "node_id": node_id})


# --- Highlight ---

@mcp.tool()
def browser_highlight(selector: str = None, node_id: int = None, duration: int = 1500, color: str = "red") -> str:
    """
    Temporarily highlight an element on the page with a colored outline.
    Useful for visually confirming which element will be interacted with.
    selector: CSS selector for the element
    node_id: DOM node ID from get_dom_tree (alternative to selector)
    duration: Highlight duration in milliseconds (default 1500)
    color: Outline color name or hex (e.g. 'red', '#00ff00', default 'red')
    """
    return _post("highlight", {"selector": selector, "node_id": node_id, "duration": duration, "color": color})


# --- Wait for Function ---

@mcp.tool()
def browser_wait_for_function(js: str, timeout: int = 30000, poll: int = 100) -> str:
    """
    Wait until a JavaScript expression returns a truthy value.
    js: JavaScript expression to evaluate (e.g. "document.querySelector('.loaded') !== null")
    timeout: Max wait time in ms (default 30000)
    poll: Polling interval in ms (default 100)
    """
    return _post("wait_for_function", {"js": js, "timeout": timeout, "poll": poll})


# --- Block Resources ---

@mcp.tool()
def browser_block_resources(patterns: list = None) -> str:
    """
    Block network requests matching URL patterns to speed up page loading.
    patterns: List of URL patterns to block (e.g. ["*.png", "*.jpg", "*.css", "analytics.js"]).
              Pass empty list or omit to clear all blocking.
    """
    return _post("block_resources", {"patterns": patterns or []})


# --- Performance ---

@mcp.tool()
def browser_get_performance() -> str:
    """
    Get page performance metrics: timing, DOM size, resource count.
    Returns DOM content loaded, load complete times, number of elements, recent network resources.
    """
    return _post("get_performance")


# --- User Agent ---

@mcp.tool()
def browser_get_user_agent() -> str:
    """Get the browser's current user agent string."""
    return _post("get_user_agent")


# --- Focus ---

@mcp.tool()
def browser_focus_element(selector: str = None, node_id: int = None) -> str:
    """
    Focus on a specific element on the page.
    selector: CSS selector for the element
    node_id: DOM node ID from get_dom_tree (alternative to selector)
    """
    return _post("focus_element", {"selector": selector, "node_id": node_id})


# --- Mouse Move (hover without click) ---

@mcp.tool()
def browser_mouse_move_to_element(selector: str = None, node_id: int = None) -> str:
    """
    Move the mouse cursor to hover over an element without clicking.
    Useful for triggering hover menus and tooltips.
    selector: CSS selector for the element
    node_id: DOM node ID from get_dom_tree (alternative to selector)
    """
    return _post("mouse_move_to_element", {"selector": selector, "node_id": node_id})


# --- Drag & Drop ---

@mcp.tool()
def browser_drag_element(source_selector: str = None, target_selector: str = None,
                        source_node_id: int = None, target_x: int = None, target_y: int = None) -> str:
    """
    Drag and drop an element to a target position on the page.
    source_selector: CSS selector for the element to drag
    target_selector: CSS selector for the drop target element
    source_node_id: DOM node ID from get_dom_tree (alternative to source_selector)
    target_x: Absolute X coordinate to drop at (used when no target_selector)
    target_y: Absolute Y coordinate to drop at (used when no target_selector)
    """
    return _post("drag_element", {
        "source_selector": source_selector,
        "target_selector": target_selector,
        "source_node_id": source_node_id,
        "target_x": target_x,
        "target_y": target_y,
    })


# --- Count Elements ---

@mcp.tool()
def browser_get_element_count(selector: str) -> str:
    """
    Count how many elements match a CSS selector on the page.
    selector: CSS selector to count (e.g. 'button', 'div.item', 'a[href*="pdf"]')
    """
    return _post("get_element_count", {"selector": selector})


# --- Storage State Persistence ---

@mcp.tool()
def browser_save_storage_state() -> str:
    """
    Save current cookies and localStorage to agent_output/browser_storage.json.
    State is restored automatically on daemon restart — use this to persist sessions.
    """
    return _post("save_storage_state")

@mcp.tool()
def browser_get_storage_state() -> str:
    """Check if a saved storage state exists and how many cookies/entries it has."""
    return _post("get_storage_state")

@mcp.tool()
def browser_clear_storage_state() -> str:
    """Delete the saved storage state file."""
    return _post("clear_storage_state")


# --- Dialog Behavior ---

@mcp.tool()
def browser_set_dialog_behavior(action: str = "accept") -> str:
    """
    Set how browser dialogs (alert, confirm, prompt) are handled automatically.
    action: 'accept' (default) — click OK/Yes, 'dismiss' — click Cancel/No, 'ignore' — leave open
    """
    return _post("set_dialog_behavior", {"action": action})


# ============================================================
# NEW FEATURES — Content Extraction
# ============================================================

@mcp.tool()
def browser_get_visible_text() -> str:
    """Get all visible text content from the current page (stripped of HTML tags)."""
    return _post("get_visible_text")

@mcp.tool()
def browser_get_markdown() -> str:
    """
    Extract page content as simplified markdown.
    Converts headings, paragraphs, links, images, lists, code blocks to markdown format.
    """
    return _post("get_markdown")

@mcp.tool()
def browser_extract_links() -> str:
    """
    Extract all links from the page as a JSON array.
    Each link includes: index, text, href, title.
    """
    return _post("extract_links")

@mcp.tool()
def browser_extract_images() -> str:
    """
    Extract all images from the page as a JSON array.
    Each image includes: index, src, alt, width, height.
    """
    return _post("extract_images")

@mcp.tool()
def browser_extract_tables() -> str:
    """
    Extract all HTML tables as structured JSON data.
    Each table includes headers array and rows array.
    """
    return _post("extract_tables")

@mcp.tool()
def browser_get_meta_tags() -> str:
    """Get page metadata as JSON: title, description, OG tags, canonical URL, charset."""
    return _post("get_meta_tags")


# ============================================================
# NEW FEATURES — CDP/Advanced DOM
# ============================================================

@mcp.tool()
def browser_get_accessibility_tree() -> str:
    """
    Get the full accessibility tree via Chrome DevTools Protocol.
    Returns AX nodes with roles, names, properties for all elements.
    """
    return _post("get_accessibility_tree")

@mcp.tool()
def browser_query_selector_all(selector: str) -> str:
    """
    Get ALL elements matching a CSS selector (up to 100), not just the first.
    Each result includes index, tag, text, visibility status.
    selector: CSS selector (e.g. 'button', 'div.card', 'a[href*="pdf"]')
    """
    return _post("query_selector_all", {"selector": selector})

@mcp.tool()
def browser_get_element_by_text(text: str, selector: str = "*") -> str:
    """
    Find the first element containing specific text on the page.
    text: Text to search for (case-insensitive)
    selector: Optional CSS selector to narrow the search (default: all elements)
    """
    return _post("get_element_by_text", {"text": text, "selector": selector})

@mcp.tool()
def browser_wait_for_text(text: str, timeout: int = 30000) -> str:
    """
    Wait for specific text to appear anywhere on the page.
    text: The text to wait for (case-insensitive)
    timeout: Max wait time in ms (default 30000)
    """
    return _post("wait_for_text", {"text": text, "timeout": timeout})

@mcp.tool()
def browser_get_computed_style(selector: str = None, node_id: int = None, properties: list = None) -> str:
    """
    Get computed CSS styles of an element.
    selector: CSS selector for the element
    node_id: DOM node ID from get_dom_tree (alternative to selector)
    properties: List of CSS properties to retrieve (default: display, visibility, opacity, position, zIndex, color, etc.)
    """
    return _post("get_computed_style", {"selector": selector, "node_id": node_id, "properties": properties})

@mcp.tool()
def browser_is_visible(selector: str = None, node_id: int = None) -> str:
    """
    Check if an element is visible on the page (has size, display != none, visibility != hidden, opacity != 0).
    selector: CSS selector for the element
    node_id: DOM node ID from get_dom_tree (alternative to selector)
    """
    return _post("is_visible", {"selector": selector, "node_id": node_id})

@mcp.tool()
def browser_is_enabled(selector: str = None, node_id: int = None) -> str:
    """
    Check if a form element is enabled (not disabled, not read-only).
    selector: CSS selector for the element
    node_id: DOM node ID from get_dom_tree (alternative to selector)
    """
    return _post("is_enabled", {"selector": selector, "node_id": node_id})

@mcp.tool()
def browser_get_value(selector: str = None, node_id: int = None) -> str:
    """
    Get the current value of an input, textarea, or select element.
    For select elements, returns both value and selected option texts.
    selector: CSS selector for the element
    node_id: DOM node ID from get_dom_tree (alternative to selector)
    """
    return _post("get_value", {"selector": selector, "node_id": node_id})

@mcp.tool()
def browser_get_html(selector: str = None, node_id: int = None) -> str:
    """
    Get the outerHTML of an element.
    selector: CSS selector for the element
    node_id: DOM node ID from get_dom_tree (alternative to selector)
    """
    return _post("get_html", {"selector": selector, "node_id": node_id})

@mcp.tool()
def browser_get_selected_options(selector: str) -> str:
    """
    Get the selected options from a select (dropdown) element.
    Returns each option's value, text, and index.
    selector: CSS selector for the select element
    """
    return _post("get_selected_options", {"selector": selector})


# ============================================================
# NEW FEATURES — Form Operations
# ============================================================

@mcp.tool()
def browser_fill_form(fields: str, form_selector: str = "form") -> str:
    """
    Fill multiple form fields at once from a JSON object.
    fields: JSON string mapping CSS selectors to values, e.g. '{"#name":"John","input[name=email]":"a@b.com"}'
    form_selector: CSS selector for the form container (default: 'form')
    """
    try:
        fields_dict = json.loads(fields) if isinstance(fields, str) else fields
        return _post("fill_form", {"fields": fields_dict, "form_selector": form_selector})
    except json.JSONDecodeError as e:
        return f"Invalid fields JSON: {e}"

@mcp.tool()
def browser_clear_input(selector: str = None, node_id: int = None) -> str:
    """
    Clear the contents of an input or textarea element.
    selector: CSS selector for the element
    node_id: DOM node ID from get_dom_tree (alternative to selector)
    """
    return _post("clear_input", {"selector": selector, "node_id": node_id})

@mcp.tool()
def browser_submit_form(selector: str = None, node_id: int = None) -> str:
    """
    Submit the form that contains a given element.
    selector: CSS selector for any element inside the target form
    node_id: DOM node ID from get_dom_tree (alternative to selector)
    """
    return _post("submit_form", {"selector": selector, "node_id": node_id})


# ============================================================
# NEW FEATURES — Device Emulation
# ============================================================

@mcp.tool()
def browser_set_geolocation(latitude: float = 37.7749, longitude: float = -122.4194, accuracy: int = 100) -> str:
    """
    Set a mock geolocation for the browser.
    latitude: Latitude (default: 37.7749 = San Francisco)
    longitude: Longitude (default: -122.4194 = San Francisco)
    accuracy: Accuracy in meters (default: 100)
    """
    return _post("set_geolocation", {"latitude": latitude, "longitude": longitude, "accuracy": accuracy})

@mcp.tool()
def browser_set_timezone(timezone_id: str = "America/New_York") -> str:
    """
    Set a mock timezone for the browser page.
    timezone_id: IANA timezone string (default: 'America/New_York')
    """
    return _post("set_timezone", {"timezone_id": timezone_id})

@mcp.tool()
def browser_set_device(device_name: str) -> str:
    """
    Emulate a specific device by name.
    device_name: Device name from Playwright's device list (e.g. 'iPhone 14', 'Pixel 7', 'iPad Pro 11', 'Galaxy S24')
    """
    return _post("set_device", {"device_name": device_name})

@mcp.tool()
def browser_set_network_conditions(offline: bool = False, latency: int = 0, download_throughput: int = -1, upload_throughput: int = -1) -> str:
    """
    Simulate network conditions for the browser.
    offline: Go offline if True (default: False)
    latency: Minimum latency in ms (default: 0)
    download_throughput: Max download bytes/sec (-1 = unlimited, default: -1)
    upload_throughput: Max upload bytes/sec (-1 = unlimited, default: -1)
    """
    return _post("set_network_conditions", {
        "offline": offline, "latency": latency,
        "download_throughput": download_throughput, "upload_throughput": upload_throughput
    })


# ============================================================
# NEW FEATURES — Scroll & Navigation
# ============================================================

@mcp.tool()
def browser_scroll_to_element(selector: str = None, node_id: int = None, block: str = "center", inline: str = "center") -> str:
    """
    Scroll an element into view.
    selector: CSS selector for the element
    node_id: DOM node ID from get_dom_tree (alternative to selector)
    block: Vertical alignment ('start', 'center', 'end', 'nearest') (default: 'center')
    inline: Horizontal alignment ('start', 'center', 'end', 'nearest') (default: 'center')
    """
    return _post("scroll_to_element", {"selector": selector, "node_id": node_id, "block": block, "inline": inline})

@mcp.tool()
def browser_scroll_to_bottom(smooth: bool = True) -> str:
    """Scroll to the bottom of the page. smooth: Use smooth scrolling (default: True)."""
    return _post("scroll_to_bottom", {"smooth": smooth})

@mcp.tool()
def browser_scroll_to_top(smooth: bool = True) -> str:
    """Scroll to the top of the page. smooth: Use smooth scrolling (default: True)."""
    return _post("scroll_to_top", {"smooth": smooth})

@mcp.tool()
def browser_wait_for_load_state(state: str = "networkidle", timeout: int = 30000) -> str:
    """
    Wait for a specific page load state.
    state: 'networkidle' (default) — no network activity for 500ms, 'load' — load event fired, 'domcontentloaded' — DOM parsed
    timeout: Max wait time in ms (default: 30000)
    """
    return _post("wait_for_load_state", {"state": state, "timeout": timeout})


# ============================================================
# NEW FEATURES — Injection
# ============================================================

@mcp.tool()
def browser_inject_css(css: str) -> str:
    """
    Inject custom CSS into the page.
    css: CSS rules to inject (e.g. 'body { background: red; }')
    """
    return _post("inject_css", {"css": css})

@mcp.tool()
def browser_inject_js(js: str = None, url: str = None) -> str:
    """
    Inject a JavaScript code snippet or external script URL into the page.
    js: JavaScript code to execute inline
    url: URL of an external JS file to load (alternative to js)
    """
    payload = {}
    if js: payload["js"] = js
    if url: payload["url"] = url
    return _post("inject_js", payload)

@mcp.tool()
def browser_remove_elements(selector: str) -> str:
    """
    Remove all elements matching a CSS selector from the DOM.
    selector: CSS selector for elements to remove (e.g. '.ad-banner', '#cookie-banner')
    """
    return _post("remove_elements", {"selector": selector})


# ============================================================
# NEW FEATURES — Shadow DOM
# ============================================================

@mcp.tool()
def browser_query_selector_shadow(host_selector: str, shadow_selector: str) -> str:
    """
    Query an element inside a shadow DOM tree.
    host_selector: CSS selector for the shadow host element
    shadow_selector: CSS selector for the element inside the shadow root
    """
    return _post("query_selector_shadow", {"host_selector": host_selector, "shadow_selector": shadow_selector})


# ============================================================
# NEW FEATURES — Mutation Watching
# ============================================================

@mcp.tool()
def browser_wait_for_mutation(container: str = "body", selector: str = None, timeout: int = 30000) -> str:
    """
    Wait for an element matching a selector to appear via DOM mutation.
    container: CSS selector for the container to observe (default: 'body')
    selector: CSS selector for the element to wait for
    timeout: Max wait time in ms (default: 30000)
    """
    return _post("wait_for_mutation", {"container": container, "selector": selector, "timeout": timeout})

@mcp.tool()
def browser_wait_for_element_state(selector: str, state: str = "visible", timeout: int = 30000) -> str:
    """
    Wait for an element to reach a specific state.
    selector: CSS selector for the element
    state: 'visible' (default), 'hidden', 'attached', or 'detached'
    timeout: Max wait time in ms (default: 30000)
    """
    return _post("wait_for_element_state", {"selector": selector, "state": state, "timeout": timeout})


# ============================================================
# NEW FEATURES — Browser Management
# ============================================================

@mcp.tool()
def browser_get_browser_info() -> str:
    """
    Get detailed browser information as JSON.
    Returns: userAgent, platform, language, viewport size, screen size, cookiesEnabled, hardwareConcurrency, current URL, origin
    """
    return _post("get_browser_info")

@mcp.tool()
def browser_get_console_errors() -> str:
    """Get only error-level messages from the captured console logs (errors, page errors, assertions)."""
    return _post("get_console_errors")

@mcp.tool()
def browser_reset_session() -> str:
    """
    Reset the browser session completely:
    - Clears all cookies
    - Clears localStorage and sessionStorage
    - Clears console and network logs
    - Navigates to about:blank
    """
    return _post("reset_session")


# ============================================================
# NEW FEATURES — Cookie Enhancements
# ============================================================

@mcp.tool()
def browser_export_cookies_netscape() -> str:
    """
    Export all cookies in Netscape HTTP Cookie File format.
    Also saved to agent_output/cookies_netscape.txt for later import.
    """
    return _post("export_cookies_netscape")

@mcp.tool()
def browser_import_cookies_netscape(filepath: str = None) -> str:
    """
    Import cookies from a Netscape format cookie file.
    filepath: Path to the Netscape cookie file (default: agent_output/cookies_netscape.txt)
    """
    return _post("import_cookies_netscape", {"filepath": filepath})


# ============================================================
# NEW FEATURES — Enhanced Screenshots
# ============================================================

@mcp.tool()
def browser_screenshot_region(x: int = 0, y: int = 0, width: int = 800, height: int = 600, to_file: bool = False, filename: str = None) -> str:
    """
    Take a screenshot of a specific region of the viewport.
    x: X coordinate of the top-left corner (default: 0)
    y: Y coordinate of the top-left corner (default: 0)
    width: Width of the region in pixels (default: 800)
    height: Height of the region in pixels (default: 600)
    to_file: Save to agent_output/ instead of returning base64 (default: False)
    filename: Custom filename for file output (default: auto-generated)
    """
    return _post("screenshot_region", {"x": x, "y": y, "width": width, "height": height, "to_file": to_file, "filename": filename})

@mcp.tool()
def browser_inject_overlay(html: str = None) -> str:
    """
    Draw a visual overlay on the page (e.g. a semi-transparent highlight).
    html: HTML string for the overlay content (default: full-page red tint)
    """
    return _post("inject_overlay", {"html": html})

@mcp.tool()
def browser_remove_overlay() -> str:
    """Remove a previously injected overlay from the page."""
    return _post("remove_overlay")


if __name__ == "__main__":
    mcp.run(transport="stdio")
