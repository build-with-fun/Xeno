import asyncio
import os
import sys
import base64
import json
import logging
import traceback
from pathlib import Path
from urllib.parse import urlparse

from aiohttp import web
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout
from playwright_stealth import Stealth

_PROJECT_ROOT = str(Path(__file__).resolve().parent.parent.parent.parent)

LOG_DIR = Path(os.environ.get("XENO_LOG_DIR", str(Path(_PROJECT_ROOT) / "data" / "logs")))
BROWSER_DAEMON_PORT = int(os.environ.get("XENO_BROWSER_DAEMON_PORT", "9888"))

log_path = LOG_DIR / "daemon.log"
os.makedirs(log_path.parent, exist_ok=True)
logging.basicConfig(filename=str(log_path), level=logging.DEBUG,
                    format='%(asctime)s %(levelname)s %(name)s %(message)s')
logger = logging.getLogger(__name__)

_playwright_instance = None
_browser_context = None
_page = None

AGENT_OUTPUT = str(Path(_PROJECT_ROOT) / "agent_output")
os.makedirs(AGENT_OUTPUT, exist_ok=True)

_console_messages: list = []
_network_entries: list = []
_resource_block_list: list = []
_dialog_behavior: str = "accept"  # "accept", "dismiss", or "ignore"
_storage_state_path: str = os.path.join(AGENT_OUTPUT, "browser_storage.json")
_headless: bool = False  # False = real browser on desktop, True = virtual headless
_screencasting: bool = False
_screencast_clients: list = []  # list of asyncio.Queue for frame distribution
_latest_frame: bytes | None = None  # latest JPEG frame for grab endpoint

async def get_page():
    global _playwright_instance, _browser_context, _page

    if _page is not None:
        try:
            if _page.is_closed():
                _page = None
                _browser_context = None
        except:
            _page = None
            _browser_context = None

    if _page is None:
        if _playwright_instance is None:
            _playwright_instance = await async_playwright().start()

        if _browser_context is None:
            user_data_dir = os.path.join(
                os.environ.get("TEMP", str(LOG_DIR.parent / "temp")),
                "chrome_cdp"
            )
            launch_args = [
                "--no-first-run",
                "--no-default-browser-check",
                "--disable-blink-features=AutomationControlled",
            ]
            if _headless:
                launch_args.extend(["--headless=new", "--window-size=1280,720"])
            _browser_context = await _playwright_instance.chromium.launch_persistent_context(
                user_data_dir,
                headless=_headless,
                args=launch_args,
                viewport={"width": 1280, "height": 720} if _headless else None,
            )

        if _browser_context.pages:
            _page = _browser_context.pages[0]
        else:
            _page = await _browser_context.new_page()

        # Apply stealth evasion
        stealth_inst = Stealth()
        await stealth_inst.apply_stealth_async(_page)

        # Attach console capture
        async def _on_console(msg):
            _console_messages.append({
                "type": msg.type,
                "text": msg.text,
                "location": str(msg.location) if hasattr(msg, "location") and msg.location else "",
            })
            if len(_console_messages) > 500:
                _console_messages[:50] = []

        # Attach network capture
        async def _on_request(req):
            _network_entries.append({
                "url": req.url,
                "method": req.method,
                "resource_type": req.resource_type,
                "type": "request",
            })
            if len(_network_entries) > 200:
                _network_entries[:20] = []

        async def _on_response(resp):
            _network_entries.append({
                "url": resp.url,
                "status": resp.status,
                "status_text": resp.status_text,
                "type": "response",
            })
            if len(_network_entries) > 200:
                _network_entries[:20] = []

        _page.on("console", _on_console)
        _page.on("request", _on_request)
        _page.on("response", _on_response)

        # Attach dialog auto-dismissal
        async def _on_dialog(dialog):
            if _dialog_behavior == "accept":
                await dialog.accept()
                _console_messages.append({"type": "dialog", "text": f"Accepted dialog: {dialog.message}"})
            elif _dialog_behavior == "dismiss":
                await dialog.dismiss()
                _console_messages.append({"type": "dialog", "text": f"Dismissed dialog: {dialog.message}"})
            else:
                _console_messages.append({"type": "dialog", "text": f"Ignored dialog: {dialog.message}"})

        _page.on("dialog", _on_dialog)

        # Attach popup tracking
        async def _on_popup(popup):
            await popup.wait_for_load_state()
            _console_messages.append({
                "type": "popup",
                "text": f"New popup: {popup.url}"
            })

        _page.on("popup", _on_popup)

        # Attach crash auto-recovery
        async def _on_crash():
            global _page
            logger.error("Page crashed — attempting recovery")
            _console_messages.append({"type": "crash", "text": "Page crashed, recovering..."})
            try:
                await _page.close()
            except:
                pass
            _page = None
            new_page = await get_page()
            _console_messages.append({"type": "crash", "text": "Page recovered successfully"})

        _page.on("crash", _on_crash)

        # Attach page error logging
        async def _on_page_error(err):
            _console_messages.append({"type": "pageerror", "text": str(err)})

        _page.on("pageerror", _on_page_error)

        # Apply resource blocking if configured
        if _resource_block_list:
            await _page.route(_resource_block_list, lambda route: route.abort())

        # Restore storage state if available
        if os.path.exists(_storage_state_path):
            try:
                with open(_storage_state_path, "r") as f:
                    state = json.load(f)
                if state.get("cookies"):
                    await _browser_context.add_cookies(state["cookies"])
                if state.get("local_storage") and _page.url != "about:blank":
                    for key, value in state["local_storage"].items():
                        await _page.evaluate(
                            f"window.localStorage.setItem({json.dumps(key)}, {json.dumps(value)})"
                        )
                logger.info(f"Restored storage state ({len(state.get('cookies', []))} cookies, {len(state.get('local_storage', {}))} localStorage entries)")
                _console_messages.append({"type": "storage", "text": "Storage state restored from previous session"})
            except Exception as e:
                logger.warning(f"Failed to restore storage state: {e}")

    return _page

def _make_responder(func):
    async def handler(request):
        try:
            data = await request.json() if request.method == "POST" else {}
            result = await func(request, data)
            return web.json_response({"result": result})
        except PlaywrightTimeout as e:
            return web.json_response({"error": f"Timeout: {str(e)}"}, status=504)
        except Exception as e:
            logger.error(traceback.format_exc())
            return web.json_response({"error": str(e)}, status=500)
    return handler

# --- Core navigation ---

async def handle_status(request, data):
    page = await get_page()
    url = page.url if not page.is_closed() else "No page"
    return {"status": "ok", "url": url}

async def handle_navigate(request, data):
    page = await get_page()
    url = data.get("url")
    timeout = data.get("timeout", 30000)
    wait_until = data.get("wait_until", "domcontentloaded")
    await page.goto(url, wait_until=wait_until, timeout=timeout)
    return f"Successfully navigated to {url}"

async def handle_back(request, data):
    page = await get_page()
    await page.go_back()
    return f"Navigated back to {page.url}"

async def handle_forward(request, data):
    page = await get_page()
    await page.go_forward()
    return f"Navigated forward to {page.url}"

async def handle_refresh(request, data):
    page = await get_page()
    await page.reload()
    return f"Page refreshed: {page.url}"

# --- Page info ---

async def handle_get_url(request, data):
    page = await get_page()
    return page.url

async def handle_get_title(request, data):
    page = await get_page()
    return await page.title()

async def handle_get_page_source(request, data):
    page = await get_page()
    return await page.content()

# --- DOM interaction ---

async def handle_get_dom_tree(request, data):
    page = await get_page()
    js_code = """
    () => {
        let nextId = 1;
        if (!window._mcpNodeMap) window._mcpNodeMap = new Map();
        window._mcpNodeMap.clear();

        const elements = [];

        function isVisible(node) {
            const style = window.getComputedStyle(node);
            if (style.display === 'none' || style.visibility === 'hidden' || style.opacity === '0') return false;
            const rect = node.getBoundingClientRect();
            if (rect.width === 0 || rect.height === 0) return false;
            return true;
        }

        const allNodes = document.querySelectorAll('*');
        for (const node of allNodes) {
            if (!isVisible(node)) continue;

            const tag = node.tagName.toLowerCase();
            const style = window.getComputedStyle(node);
            const isInteractive = ['a', 'button', 'input', 'select', 'textarea'].includes(tag) ||
                                  node.getAttribute('role') === 'button' ||
                                  style.cursor === 'pointer';

            if (isInteractive) {
                const id = nextId++;
                const rect = node.getBoundingClientRect();

                window._mcpNodeMap.set(id, {
                    node: node,
                    x: rect.x + rect.width / 2,
                    y: rect.y + rect.height / 2
                });

                const elData = {
                    id: id,
                    tag: tag,
                    text: (node.innerText || node.value || '').trim().substring(0, 100),
                    attributes: {}
                };

                for (const attr of ['id', 'class', 'href', 'type', 'name', 'placeholder', 'aria-label', 'title']) {
                    if (node.hasAttribute(attr)) elData.attributes[attr] = node.getAttribute(attr);
                }
                elements.push(elData);
            }
        }
        return elements;
    }
    """
    tree = await page.evaluate(js_code)
    return json.dumps(tree)

async def handle_query_selector(request, data):
    page = await get_page()
    selector = data.get("selector")
    timeout = data.get("timeout", 10000)
    try:
        await page.wait_for_selector(selector, timeout=timeout)
        el = await page.query_selector(selector)
        if el:
            text = await el.inner_text() if await el.inner_text() else ""
            attrs = await page.evaluate(f"""() => {{
                const el = document.querySelector({json.dumps(selector)});
                if (!el) return null;
                const attrs = {{}};
                for (const attr of ['id', 'class', 'href', 'src', 'alt', 'title', 'type', 'name', 'placeholder', 'value']) {{
                    if (el.hasAttribute(attr)) attrs[attr] = el.getAttribute(attr);
                }}
                return attrs;
            }}""")
            return json.dumps({"found": True, "text": text.strip()[:200], "attributes": attrs or {}})
        return json.dumps({"found": False})
    except PlaywrightTimeout:
        return json.dumps({"found": False, "error": f"Selector '{selector}' not found within {timeout}ms"})

async def handle_wait_for_selector(request, data):
    page = await get_page()
    selector = data.get("selector")
    timeout = data.get("timeout", 30000)
    state = data.get("state", "visible")
    await page.wait_for_selector(selector, timeout=timeout, state=state)
    return f"Selector '{selector}' is now {state}"

async def handle_get_attribute(request, data):
    page = await get_page()
    selector = data.get("selector")
    attr = data.get("attribute")
    el = await page.query_selector(selector)
    if not el:
        return json.dumps({"error": f"Element '{selector}' not found"})
    val = await el.get_attribute(attr)
    return json.dumps({attr: val})

async def handle_get_text(request, data):
    page = await get_page()
    selector = data.get("selector")
    el = await page.query_selector(selector)
    if not el:
        return json.dumps({"error": f"Element '{selector}' not found"})
    text = await el.inner_text()
    return text

# --- Actions ---

async def handle_click(request, data):
    page = await get_page()
    node_id = data.get("node_id")
    selector = data.get("selector")

    async def _do_click():
        if selector:
            await page.wait_for_selector(selector, timeout=10000)
            await page.click(selector)
            return f"Clicked element with selector '{selector}'"

        js_get_coords = f"""
        () => {{
            const el = window._mcpNodeMap.get({node_id});
            if (!el) return null;
            el.node.scrollIntoView({{behavior: 'instant', block: 'center', inline: 'center'}});
            const rect = el.node.getBoundingClientRect();
            return {{x: rect.x + rect.width / 2, y: rect.y + rect.height / 2}};
        }}
        """
        coords = await page.evaluate(js_get_coords)
        if not coords:
            return json.dumps({"error": f"Element {node_id} not found"})

        x, y = coords['x'], coords['y']
        await page.mouse.move(x, y, steps=10)
        await asyncio.sleep(0.1)
        await page.mouse.down()
        await asyncio.sleep(0.05)
        await page.mouse.up()

        return f"Clicked element with id {node_id} at ({x:.0f},{y:.0f})"

    # Try detecting a download triggered by the click
    try:
        async with page.expect_download(timeout=2000) as download_info:
            result = await _do_click()
        download = await download_info.value
        filename = download.suggested_filename
        filepath = os.path.join(AGENT_OUTPUT, filename)
        await download.save_as(filepath)
        result += f" | Download detected: saved to agent_output/{filename}"
        return result
    except PlaywrightTimeout:
        pass  # No download started within 2s — normal click result

    return await _do_click()

async def handle_double_click(request, data):
    page = await get_page()
    selector = data.get("selector")
    node_id = data.get("node_id")

    async def _do_dblclick():
        if selector:
            await page.wait_for_selector(selector, timeout=10000)
            await page.dblclick(selector)
            return f"Double-clicked '{selector}'"

        if node_id:
            js_coords = f"""
            () => {{
                const el = window._mcpNodeMap.get({node_id});
                if (!el) return null;
                el.node.scrollIntoView({{behavior: 'instant', block: 'center', inline: 'center'}});
                const rect = el.node.getBoundingClientRect();
                return {{x: rect.x + rect.width / 2, y: rect.y + rect.height / 2}};
            }}
            """
            coords = await page.evaluate(js_coords)
            if coords:
                await page.mouse.dblclick(coords['x'], coords['y'])
                return f"Double-clicked element {node_id}"

        return json.dumps({"error": "node_id or selector required"})

    # Try detecting a download triggered by the double-click
    try:
        async with page.expect_download(timeout=2000) as download_info:
            result = await _do_dblclick()
        download = await download_info.value
        filename = download.suggested_filename
        filepath = os.path.join(AGENT_OUTPUT, filename)
        await download.save_as(filepath)
        result += f" | Download detected: saved to agent_output/{filename}"
        return result
    except PlaywrightTimeout:
        pass  # No download started within 2s

    return await _do_dblclick()

async def handle_type(request, data):
    page = await get_page()
    node_id = data.get("node_id")
    selector = data.get("selector")
    text = data.get("text", "")
    wpm = data.get("wpm", 80)
    clear_first = data.get("clear_first", True)

    if selector:
        await page.wait_for_selector(selector, timeout=10000)
        if clear_first:
            await page.fill(selector, "")
        delay = (60.0 / (wpm * 5.0)) * 1000 if wpm > 0 else 10
        await page.keyboard.type(text, delay=delay)
        return f"Typed text into '{selector}'"

    js_get_coords = f"""
    () => {{
        const el = window._mcpNodeMap.get({node_id});
        if (!el) return null;
        el.node.scrollIntoView({{behavior: 'instant', block: 'center', inline: 'center'}});
        const rect = el.node.getBoundingClientRect();
        return {{x: rect.x + rect.width / 2, y: rect.y + rect.height / 2}};
    }}
    """
    coords = await page.evaluate(js_get_coords)
    if not coords:
        return json.dumps({"error": f"Element {node_id} not found"})

    x, y = coords['x'], coords['y']
    await page.mouse.move(x, y, steps=5)
    await page.mouse.click(x, y)

    delay = (60.0 / (wpm * 5.0)) * 1000 if wpm > 0 else 10
    await page.keyboard.type(text, delay=delay)

    return f"Typed text into element {node_id}"

async def handle_fill(request, data):
    page = await get_page()
    selector = data.get("selector")
    value = data.get("value", "")
    timeout = data.get("timeout", 10000)
    await page.wait_for_selector(selector, timeout=timeout)
    await page.fill(selector, value)
    return f"Filled '{selector}' with value"

async def handle_select_option(request, data):
    page = await get_page()
    selector = data.get("selector")
    value = data.get("value")
    label = data.get("label")
    index = data.get("index")
    await page.wait_for_selector(selector, timeout=10000)
    if value:
        await page.select_option(selector, value=value)
    elif label:
        await page.select_option(selector, label=label)
    elif index is not None:
        await page.select_option(selector, index=index)
    return f"Selected option in '{selector}'"

async def handle_hover(request, data):
    page = await get_page()
    selector = data.get("selector")
    node_id = data.get("node_id")

    if selector:
        await page.wait_for_selector(selector, timeout=10000)
        await page.hover(selector)
        return f"Hovered over '{selector}'"

    if node_id:
        js_coords = f"""
        () => {{
            const el = window._mcpNodeMap.get({node_id});
            if (!el) return null;
            el.node.scrollIntoView({{behavior: 'instant', block: 'center', inline: 'center'}});
            const rect = el.node.getBoundingClientRect();
            return {{x: rect.x + rect.width / 2, y: rect.y + rect.height / 2}};
        }}
        """
        coords = await page.evaluate(js_coords)
        if coords:
            await page.mouse.move(coords['x'], coords['y'], steps=10)
            return f"Hovered over element {node_id}"

    return json.dumps({"error": "node_id or selector required"})

async def handle_press_key(request, data):
    page = await get_page()
    key = data.get("key")
    await page.keyboard.press(key)
    return f"Pressed key '{key}'"

async def handle_scroll(request, data):
    page = await get_page()
    amount_x = data.get("amount_x", 0)
    amount_y = data.get("amount_y", 300)
    selector = data.get("selector")

    if selector:
        await page.wait_for_selector(selector, timeout=5000)
        await page.evaluate(f"""
            document.querySelector({json.dumps(selector)}).scrollBy({amount_x}, {amount_y})
        """)
    else:
        await page.evaluate(f"window.scrollBy({amount_x}, {amount_y})")

    return f"Scrolled by ({amount_x}, {amount_y})"

# --- Tabs ---

async def handle_new_tab(request, data):
    global _browser_context, _page
    page = await get_page()
    url = data.get("url", "about:blank")
    new_page = await _browser_context.new_page()
    _page = new_page
    if url and url != "about:blank":
        await new_page.goto(url, wait_until="domcontentloaded")
    return f"Opened new tab: {url}"

async def handle_close_tab(request, data):
    global _page
    page = await get_page()
    await page.close()
    _page = None
    return "Tab closed"

async def handle_switch_tab(request, data):
    global _browser_context, _page
    index = data.get("index")
    if not _browser_context:
        return json.dumps({"error": "No browser context"})
    pages = _browser_context.pages
    if index < 0 or index >= len(pages):
        return json.dumps({"error": f"Tab index {index} out of range. {len(pages)} tabs available."})
    _page = pages[index]
    await _page.bring_to_front()
    return f"Switched to tab {index}: {await _page.title()}"

async def handle_list_tabs(request, data):
    global _browser_context
    if not _browser_context:
        return json.dumps([])
    tabs = []
    for i, p in enumerate(_browser_context.pages):
        try:
            title = await p.title()
            url = p.url
        except:
            title = "<closed>"
            url = ""
        tabs.append({"index": i, "title": title, "url": url})
    return json.dumps(tabs)

# --- Cookies ---

async def handle_get_cookies(request, data):
    page = await get_page()
    context = page.context
    cookies = await context.cookies()
    return json.dumps([{"name": c["name"], "value": c["value"], "domain": c["domain"]} for c in cookies])

async def handle_set_cookies(request, data):
    page = await get_page()
    cookies = data.get("cookies", [])
    context = page.context
    await context.add_cookies(cookies)
    return f"Set {len(cookies)} cookies"

async def handle_clear_cookies(request, data):
    page = await get_page()
    context = page.context
    await context.clear_cookies()
    return "Cookies cleared"

# --- Screenshot & PDF ---

async def handle_screenshot(request, data):
    page = await get_page()
    full_page = data.get("full_page", False)
    screenshot_bytes = await page.screenshot(type="png", full_page=full_page)
    b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
    return b64

async def handle_screenshot_to_file(request, data):
    page = await get_page()
    filename = data.get("filename", f"screenshot_{int(asyncio.get_event_loop().time())}.png")
    full_page = data.get("full_page", False)
    filepath = os.path.join(AGENT_OUTPUT, filename)
    await page.screenshot(path=filepath, full_page=full_page)
    return f"Screenshot saved to {filepath}"

async def handle_pdf(request, data):
    page = await get_page()
    html_content = data.get("html_content")
    filename = data.get("filename", f"output_{int(asyncio.get_event_loop().time())}.pdf")
    output_path = data.get("output_path", os.path.join(AGENT_OUTPUT, filename))

    if html_content:
        await page.set_content(html_content, wait_until="networkidle")

    await page.pdf(
        path=output_path,
        format="A4",
        print_background=True,
        margin={"top": "20px", "bottom": "20px", "left": "20px", "right": "20px"}
    )
    return f"PDF saved to {output_path}"

# --- Downloads ---

async def handle_download(request, data):
    page = await get_page()
    node_id = data.get("node_id")
    selector = data.get("selector")
    download_dir = data.get("download_dir", AGENT_OUTPUT)
    filename = data.get("filename")

    async def _do_download(click_coords=None):
        async with page.expect_download(timeout=60000) as download_info:
            if click_coords:
                x, y = click_coords
                await page.mouse.move(x, y, steps=10)
                await asyncio.sleep(0.1)
                await page.mouse.down()
                await asyncio.sleep(0.05)
                await page.mouse.up()
            elif selector:
                await page.wait_for_selector(selector, timeout=10000)
                await page.click(selector)

        download = await download_info.value
        final_filename = filename if filename else download.suggested_filename
        os.makedirs(download_dir, exist_ok=True)
        final_path = os.path.join(download_dir, final_filename)
        await download.save_as(final_path)
        return f"Downloaded file to {final_path}"

    if selector:
        return await _do_download()

    js_coords = f"""
    () => {{
        const el = window._mcpNodeMap.get({node_id});
        if (!el) return null;
        el.node.scrollIntoView({{behavior: 'instant', block: 'center', inline: 'center'}});
        const rect = el.node.getBoundingClientRect();
        return {{x: rect.x + rect.width / 2, y: rect.y + rect.height / 2}};
    }}
    """
    coords = await page.evaluate(js_coords)
    if not coords:
        return json.dumps({"error": f"Element {node_id} not found"})

    return await _do_download(click_coords=(coords['x'], coords['y']))

async def handle_direct_download(request, data):
    url = data.get("url")
    filename = data.get("filename", os.path.basename(urlparse(url).path) or "download")
    download_dir = data.get("download_dir", AGENT_OUTPUT)
    os.makedirs(download_dir, exist_ok=True)
    filepath = os.path.join(download_dir, filename)

    page = await get_page()
    async with page.expect_download(timeout=120000) as download_info:
        await page.evaluate(f"window.location.href = {json.dumps(url)}")
    download = await download_info.value
    await download.save_as(filepath)
    return f"Downloaded {url} to {filepath}"

# --- Misc ---

async def handle_evaluate(request, data):
    page = await get_page()
    js = data.get("js")
    result = await page.evaluate(js)
    return str(result)

async def handle_wait(request, data):
    ms = data.get("ms", 1000)
    await asyncio.sleep(ms / 1000)
    return f"Waited {ms}ms"

async def handle_set_viewport(request, data):
    page = await get_page()
    width = data.get("width", 1920)
    height = data.get("height", 1080)
    await page.set_viewport_size({"width": width, "height": height})
    return f"Viewport set to {width}x{height}"

# --- Console & Network ---

async def handle_console_logs(request, data):
    clear = data.get("clear", False)
    logs = list(_console_messages)
    if clear:
        _console_messages.clear()
    return json.dumps(logs)

async def handle_network_logs(request, data):
    clear = data.get("clear", False)
    entries = list(_network_entries)
    if clear:
        _network_entries.clear()
    return json.dumps(entries)

# --- Storage ---

async def handle_get_local_storage(request, data):
    page = await get_page()
    result = await page.evaluate("JSON.stringify(window.localStorage)")
    return result

async def handle_set_local_storage(request, data):
    page = await get_page()
    key = data.get("key")
    value = data.get("value", "")
    await page.evaluate(f"window.localStorage.setItem({json.dumps(key)}, {json.dumps(value)})")
    return f"localStorage['{key}'] set"

async def handle_clear_local_storage(request, data):
    page = await get_page()
    await page.evaluate("window.localStorage.clear()")
    return "localStorage cleared"

async def handle_get_session_storage(request, data):
    page = await get_page()
    result = await page.evaluate("JSON.stringify(window.sessionStorage)")
    return result

async def handle_set_session_storage(request, data):
    page = await get_page()
    key = data.get("key")
    value = data.get("value", "")
    await page.evaluate(f"window.sessionStorage.setItem({json.dumps(key)}, {json.dumps(value)})")
    return f"sessionStorage['{key}'] set"

async def handle_clear_session_storage(request, data):
    page = await get_page()
    await page.evaluate("window.sessionStorage.clear()")
    return "sessionStorage cleared"

# --- File Upload ---

async def handle_upload_file(request, data):
    page = await get_page()
    selector = data.get("selector")
    file_path = data.get("file_path")

    if not os.path.exists(file_path):
        return json.dumps({"error": f"File not found: {file_path}"})
    if not selector:
        return json.dumps({"error": "selector required"})

    await page.wait_for_selector(selector, timeout=10000)
    file_input = await page.query_selector(selector)
    if not file_input:
        return json.dumps({"error": f"Element '{selector}' not found"})

    input_type = await file_input.get_attribute("type") or ""
    if input_type.lower() == "file":
        await file_input.set_input_files(file_path)
    else:
        return json.dumps({"error": f"Element '{selector}' is not a file input (type='{input_type}')"})

    return f"Uploaded {file_path} to '{selector}'"

# --- Element Screenshot ---

async def handle_element_screenshot(request, data):
    page = await get_page()
    selector = data.get("selector")
    node_id = data.get("node_id")
    full_page = data.get("full_page", False)

    target_selector = selector
    if node_id and not selector:
        temp_id = f"_mcp_es_{int(asyncio.get_event_loop().time() * 1000)}"
        js = f"""() => {{
            const el = window._mcpNodeMap.get({node_id});
            if (!el) return null;
            el.node.scrollIntoView({{behavior:'instant', block:'center', inline:'center'}});
            el.node.setAttribute('data-mcp-es', '{temp_id}');
            return true;
        }}"""
        ok = await page.evaluate(js)
        if not ok:
            return json.dumps({"error": f"Element {node_id} not found"})
        target_selector = f"[data-mcp-es='{temp_id}']"

    if not target_selector:
        return json.dumps({"error": "selector or node_id required"})

    try:
        screenshot_bytes = await page.locator(target_selector).screenshot(timeout=10000)
        b64 = base64.b64encode(screenshot_bytes).decode('utf-8')
        return b64
    except Exception as e:
        return json.dumps({"error": f"Element screenshot failed: {str(e)}"})

async def handle_element_screenshot_to_file(request, data):
    page = await get_page()
    selector = data.get("selector")
    node_id = data.get("node_id")
    filename = data.get("filename", f"element_{int(asyncio.get_event_loop().time())}.png")

    target_selector = selector
    if node_id and not selector:
        temp_id = f"_mcp_esf_{int(asyncio.get_event_loop().time() * 1000)}"
        js = f"""() => {{
            const el = window._mcpNodeMap.get({node_id});
            if (!el) return null;
            el.node.scrollIntoView({{behavior:'instant', block:'center', inline:'center'}});
            el.node.setAttribute('data-mcp-esf', '{temp_id}');
            return true;
        }}"""
        ok = await page.evaluate(js)
        if not ok:
            return json.dumps({"error": f"Element {node_id} not found"})
        target_selector = f"[data-mcp-esf='{temp_id}']"

    if not target_selector:
        return json.dumps({"error": "selector or node_id required"})

    filepath = os.path.join(AGENT_OUTPUT, filename)
    try:
        await page.locator(target_selector).screenshot(path=filepath, timeout=10000)
        return f"Element screenshot saved to {filepath}"
    except Exception as e:
        return json.dumps({"error": f"Element screenshot failed: {str(e)}"})

# --- Bounding Box ---

async def handle_get_bounding_box(request, data):
    page = await get_page()
    selector = data.get("selector")
    node_id = data.get("node_id")

    js = ""
    if selector:
        js = f"""() => {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) return null;
            const r = el.getBoundingClientRect();
            return {{
                x: r.x, y: r.y, width: r.width, height: r.height,
                top: r.top, bottom: r.bottom, left: r.left, right: r.right,
                visible: !!(r.width && r.height &&
                    window.getComputedStyle(el).display !== 'none' &&
                    window.getComputedStyle(el).visibility !== 'hidden')
            }};
        }}"""
    elif node_id:
        js = f"""() => {{
            const entry = window._mcpNodeMap.get({node_id});
            if (!entry) return null;
            const el = entry.node;
            const r = el.getBoundingClientRect();
            return {{
                x: r.x, y: r.y, width: r.width, height: r.height,
                top: r.top, bottom: r.bottom, left: r.left, right: r.right,
                visible: !!(r.width && r.height &&
                    window.getComputedStyle(el).display !== 'none' &&
                    window.getComputedStyle(el).visibility !== 'hidden'),
                tag: el.tagName.toLowerCase(),
                text: (el.innerText || '').trim().substring(0, 100)
            }};
        }}"""

    if not js:
        return json.dumps({"error": "selector or node_id required"})

    result = await page.evaluate(js)
    return json.dumps(result if result else {"error": "Element not found"})

# --- Highlight ---

async def handle_highlight(request, data):
    page = await get_page()
    selector = data.get("selector")
    node_id = data.get("node_id")
    duration = data.get("duration", 1500)
    color = data.get("color", "red")

    if not selector and not node_id:
        return json.dumps({"error": "selector or node_id required"})

    if selector:
        js = f"""() => {{
            const el = document.querySelector({json.dumps(selector)});
            if (!el) return {{error: 'Element not found'}};
            const orig = {{outline: el.style.outline, bg: el.style.backgroundColor}};
            el.style.outline = '3px solid {color}';
            el.style.backgroundColor = 'rgba(255,0,0,0.1)';
            el.scrollIntoView({{behavior:'instant', block:'center', inline:'center'}});
            setTimeout(() => {{ el.style.outline = orig.outline; el.style.backgroundColor = orig.bg; }}, {duration});
            return {{highlighted: true, tag: el.tagName.toLowerCase(), text: (el.innerText||'').trim().substring(0,80)}};
        }}"""
    elif node_id:
        js = f"""() => {{
            const entry = window._mcpNodeMap.get({node_id});
            if (!entry) return {{error: 'Element {node_id} not found'}};
            const el = entry.node;
            const orig = {{outline: el.style.outline, bg: el.style.backgroundColor}};
            el.style.outline = '3px solid {color}';
            el.style.backgroundColor = 'rgba(255,0,0,0.1)';
            el.scrollIntoView({{behavior:'instant', block:'center', inline:'center'}});
            setTimeout(() => {{ el.style.outline = orig.outline; el.style.backgroundColor = orig.bg; }}, {duration});
            return {{highlighted: true, tag: el.tagName.toLowerCase(), text: (el.innerText||'').trim().substring(0,80)}};
        }}"""

    result = await page.evaluate(js)
    return json.dumps(result)

# --- Wait for Function ---

async def handle_wait_for_function(request, data):
    page = await get_page()
    js_expr = data.get("js")
    timeout = data.get("timeout", 30000)
    poll = data.get("poll", 100)

    if not js_expr:
        return json.dumps({"error": "js expression required"})

    try:
        await page.wait_for_function(js_expr, timeout=timeout, polling=poll)
        return f"Function returned truthy: {js_expr}"
    except PlaywrightTimeout:
        return json.dumps({"error": f"Timeout after {timeout}ms waiting for: {js_expr}"})

# --- Block Resources ---

async def handle_block_resources(request, data):
    global _resource_block_list
    patterns = data.get("patterns", [])
    page = await get_page()

    if patterns:
        _resource_block_list = patterns
        for pat in patterns:
            await page.route(pat, lambda route: route.abort())
        return f"Blocking resources matching: {patterns}"
    else:
        _resource_block_list = []
        await page.unroute()
        return "Resource blocking cleared"

# --- Performance ---

async def handle_get_performance(request, data):
    page = await get_page()
    timing = await page.evaluate("""() => {
        const t = performance.timing || {};
        const n = performance.navigation || {};
        const entries = performance.getEntriesByType('navigation')[0];
        const resources = performance.getEntriesByType('resource').slice(0, 50).map(r => ({
            name: r.name.substring(0, 200),
            duration: Math.round(r.duration),
            initiatorType: r.initiatorType
        }));
        return {
            timing: {
                domContentLoaded: t.domContentLoadedEventEnd - t.navigationStart,
                domComplete: t.domComplete - t.navigationStart,
                loadComplete: t.loadEventEnd - t.navigationStart,
                domInteractive: t.domInteractive - t.navigationStart,
                firstPaint: t.responseStart - t.navigationStart
            },
            navigationType: n.type || (entries ? entries.type : 'unknown'),
            domElements: document.querySelectorAll('*').length,
            resourceCount: resources.length,
            recentResources: resources
        };
    }""")
    return json.dumps(timing)

# --- User Agent ---

async def handle_get_user_agent(request, data):
    page = await get_page()
    ua = await page.evaluate("navigator.userAgent")
    return ua

# --- Focus Element ---

async def handle_focus_element(request, data):
    page = await get_page()
    selector = data.get("selector")
    node_id = data.get("node_id")

    if selector:
        await page.wait_for_selector(selector, timeout=10000)
        await page.focus(selector)
        return f"Focused element '{selector}'"
    elif node_id:
        js = f"""() => {{
            const entry = window._mcpNodeMap.get({node_id});
            if (!entry) return null;
            entry.node.scrollIntoView({{behavior:'instant', block:'center', inline:'center'}});
            entry.node.focus();
            return 'focused';
        }}"""
        result = await page.evaluate(js)
        if not result:
            return json.dumps({"error": f"Element {node_id} not found"})
        return f"Focused element {node_id}"
    return json.dumps({"error": "selector or node_id required"})

# --- Mouse Move ---

async def handle_mouse_move_to_element(request, data):
    page = await get_page()
    selector = data.get("selector")
    node_id = data.get("node_id")

    if selector:
        await page.wait_for_selector(selector, timeout=10000)
        box = await page.locator(selector).bounding_box()
        if not box:
            return json.dumps({"error": f"Element '{selector}' has no bounding box"})
        x, y = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        await page.mouse.move(x, y, steps=15)
        return f"Moved mouse to '{selector}' at ({x:.0f},{y:.0f})"
    elif node_id:
        js = f"""() => {{
            const entry = window._mcpNodeMap.get({node_id});
            if (!entry) return null;
            entry.node.scrollIntoView({{behavior:'instant', block:'center', inline:'center'}});
            const r = entry.node.getBoundingClientRect();
            return {{x: r.x + r.width/2, y: r.y + r.height/2}};
        }}"""
        coords = await page.evaluate(js)
        if not coords:
            return json.dumps({"error": f"Element {node_id} not found"})
        await page.mouse.move(coords["x"], coords["y"], steps=15)
        return f"Moved mouse to element {node_id} at ({coords['x']:.0f},{coords['y']:.0f})"
    return json.dumps({"error": "selector or node_id required"})

# --- Drag Element ---

async def handle_drag_element(request, data):
    page = await get_page()
    source_selector = data.get("source_selector")
    target_selector = data.get("target_selector")
    source_node_id = data.get("source_node_id")
    target_x = data.get("target_x")
    target_y = data.get("target_y")

    async def _get_coords(sel=None, nid=None):
        if sel:
            await page.wait_for_selector(sel, timeout=10000)
            box = await page.locator(sel).bounding_box()
            if box:
                return (box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
        elif nid is not None:
            js = f"""() => {{
                const entry = window._mcpNodeMap.get({nid});
                if (!entry) return null;
                entry.node.scrollIntoView({{behavior:'instant', block:'center', inline:'center'}});
                const r = entry.node.getBoundingClientRect();
                return {{x: r.x + r.width/2, y: r.y + r.height/2}};
            }}"""
            coords = await page.evaluate(js)
            if coords:
                return (coords["x"], coords["y"])
        return None

    src = await _get_coords(sel=source_selector, nid=source_node_id)
    if not src:
        return json.dumps({"error": "Source element not found"})

    if target_selector:
        tgt = await _get_coords(sel=target_selector)
    elif target_x is not None and target_y is not None:
        tgt = (target_x, target_y)
    else:
        tgt = None

    if not tgt:
        return json.dumps({"error": "Target selector or target_x/target_y required"})

    await page.mouse.move(src[0], src[1], steps=10)
    await asyncio.sleep(0.1)
    await page.mouse.down()
    await asyncio.sleep(0.05)
    steps = 20
    for i in range(1, steps + 1):
        cur_x = src[0] + (tgt[0] - src[0]) * (i / steps)
        cur_y = src[1] + (tgt[1] - src[1]) * (i / steps)
        await page.mouse.move(cur_x, cur_y, steps=1)
        await asyncio.sleep(0.008)
    await page.mouse.up()

    return f"Dragged from ({src[0]:.0f},{src[1]:.0f}) to ({tgt[0]:.0f},{tgt[1]:.0f})"

# --- Get Element Count ---

async def handle_get_element_count(request, data):
    page = await get_page()
    selector = data.get("selector")
    if not selector:
        return json.dumps({"error": "selector required"})
    count = await page.evaluate(f"document.querySelectorAll({json.dumps(selector)}).length")
    return json.dumps({"selector": selector, "count": count})

# --- Storage State Persistence ---

async def handle_save_storage_state(request, data):
    """Save current cookies and localStorage to a JSON file for session persistence."""
    page = await get_page()
    context = page.context
    cookies = await context.cookies()
    local_storage = {}
    try:
        local_storage = await page.evaluate("JSON.stringify(window.localStorage)")
        local_storage = json.loads(local_storage) if local_storage != "{}" else {}
    except:
        pass

    state = {"cookies": cookies, "local_storage": local_storage}
    with open(_storage_state_path, "w") as f:
        json.dump(state, f, indent=2)
    return f"Storage state saved ({len(cookies)} cookies, {len(local_storage)} localStorage entries)"

async def handle_get_storage_state(request, data):
    """Get the saved storage state info."""
    if os.path.exists(_storage_state_path):
        with open(_storage_state_path, "r") as f:
            state = json.load(f)
        return json.dumps({
            "saved": True,
            "cookies_count": len(state.get("cookies", [])),
            "local_storage_entries": len(state.get("local_storage", {})),
        })
    return json.dumps({"saved": False})

async def handle_clear_storage_state(request, data):
    """Delete the saved storage state file."""
    if os.path.exists(_storage_state_path):
        os.remove(_storage_state_path)
        return "Storage state cleared"
    return "No storage state to clear"

async def handle_set_dialog_behavior(request, data):
    """Set how browser dialogs (alert, confirm, prompt) are handled."""
    global _dialog_behavior
    action = data.get("action", "accept")
    if action not in ("accept", "dismiss", "ignore"):
        return json.dumps({"error": "action must be 'accept', 'dismiss', or 'ignore'"})
    _dialog_behavior = action
    return f"Dialog behavior set to '{action}'"


# ============================================================
# NEW FEATURES — Content Extraction
# ============================================================

async def handle_get_visible_text(request, data):
    """Get all visible text content from the page."""
    page = await get_page()
    result = await page.evaluate("""() => {
        const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT, null, false);
        const texts = [];
        while (walker.nextNode()) {
            const text = walker.currentNode.textContent.trim();
            if (text) texts.push(text);
        }
        return texts.join('\\n');
    }""")
    return result

async def handle_get_markdown(request, data):
    """Extract page content as simplified markdown."""
    page = await get_page()
    result = await page.evaluate("""() => {
        const lines = [];
        const els = document.body.querySelectorAll('h1, h2, h3, h4, h5, h6, p, li, pre, blockquote, hr, a, img');
        for (const el of els) {
            const tag = el.tagName.toLowerCase();
            const text = el.textContent.trim();
            if (!text && tag !== 'hr' && tag !== 'br' && tag !== 'img') continue;
            if (['h1','h2','h3','h4','h5','h6'].includes(tag)) {
                lines.push('\\n' + '#'.repeat(parseInt(tag[1])) + ' ' + text + '\\n');
            } else if (tag === 'p') lines.push(text + '\\n\\n');
            else if (tag === 'li') {
                const parent = el.parentElement;
                const prefix = parent && parent.tagName === 'OL' ? '1. ' : '- ';
                lines.push(prefix + text);
            } else if (tag === 'a') {
                const href = el.getAttribute('href') || '';
                if (text && href && !href.startsWith('javascript:')) lines.push('[' + text + '](' + href + ')');
            } else if (tag === 'img') {
                const alt = el.getAttribute('alt') || '';
                const src = el.getAttribute('src') || '';
                if (src) lines.push('![' + alt + '](' + src + ')');
            } else if (tag === 'pre' || tag === 'blockquote') lines.push('\\n```\\n' + text + '\\n```\\n');
            else if (tag === 'hr') lines.push('\\n---\\n');
        }
        return lines.join('\\n').replace(/\\n{3,}/g, '\\n\\n').trim();
    }""")
    return result

async def handle_extract_links(request, data):
    """Extract all links from the page."""
    page = await get_page()
    result = await page.evaluate("""() => {
        return Array.from(document.querySelectorAll('a[href]')).map((a, i) => ({
            index: i, text: (a.textContent||'').trim().substring(0,200),
            href: a.getAttribute('href')||'', title: a.getAttribute('title')||''
        }));
    }""")
    return json.dumps(result)

async def handle_extract_images(request, data):
    """Extract all images from the page."""
    page = await get_page()
    result = await page.evaluate("""() => {
        return Array.from(document.querySelectorAll('img')).map((img, i) => ({
            index: i, src: img.getAttribute('src')||'', alt: img.getAttribute('alt')||'',
            width: img.naturalWidth||img.width||null, height: img.naturalHeight||img.height||null
        }));
    }""")
    return json.dumps(result)

async def handle_extract_tables(request, data):
    """Extract all HTML tables as structured data."""
    page = await get_page()
    result = await page.evaluate("""() => {
        return Array.from(document.querySelectorAll('table')).map((table, ti) => {
            const headers = [];
            const hr = table.querySelector('thead tr, tr:first-child');
            if (hr) hr.querySelectorAll('th, td').forEach(c => headers.push((c.textContent||'').trim()));
            const rows = [];
            table.querySelectorAll('tbody tr, tr:not(:first-child)').forEach(row => {
                const cells = [];
                row.querySelectorAll('td, th').forEach(c => cells.push((c.textContent||'').trim()));
                if (cells.length) rows.push(cells);
            });
            return { tableIndex: ti, headers, rows };
        });
    }""")
    return json.dumps(result)

async def handle_get_meta_tags(request, data):
    """Get page metadata (title, description, OG tags)."""
    page = await get_page()
    result = await page.evaluate("""() => {
        const m = {}; m.title = document.title;
        const d = document.querySelector('meta[name="description"]');
        if (d) m.description = d.getAttribute('content');
        document.querySelectorAll('meta[property^="og:"], meta[name^="twitter:"]').forEach(el => {
            m[el.getAttribute('property')||el.getAttribute('name')||''] = el.getAttribute('content')||'';
        });
        const c = document.querySelector('link[rel="canonical"]');
        if (c) m.canonical = c.getAttribute('href');
        m.charset = document.characterSet;
        return m;
    }""")
    return json.dumps(result)


# ============================================================
# NEW FEATURES — CDP Enhancements
# ============================================================

async def handle_get_accessibility_tree(request, data):
    """Get full accessibility tree via Chrome DevTools Protocol."""
    page = await get_page()
    try:
        cdp = await page.context.new_cdp_session(page)
        result = await cdp.send("Accessibility.getFullAXTree", {})
        return json.dumps(result.get("nodes", []))
    except Exception as e:
        return json.dumps({"error": f"CDP AX tree failed: {e}"})

async def handle_query_selector_all(request, data):
    """Get all elements matching a CSS selector."""
    page = await get_page()
    selector = data.get("selector")
    if not selector: return json.dumps({"error": "selector required"})
    result = await page.evaluate(f"""() => {{
        return Array.from(document.querySelectorAll({json.dumps(selector)})).slice(0,100).map((el,i)=>({{
            index:i, tag:el.tagName.toLowerCase(),
            text:(el.textContent||'').trim().substring(0,200),
            visible:!!(el.offsetWidth||el.offsetHeight||el.getClientRects().length)
        }}));
    }}""")
    return json.dumps(result)

async def handle_get_element_by_text(request, data):
    """Find first element containing specific text."""
    page = await get_page()
    text = data.get("text")
    sel = data.get("selector", "*")
    if not text: return json.dumps({"error": "text required"})
    result = await page.evaluate(f"""() => {{
        const q = {json.dumps(text)}.toLowerCase();
        for (const el of document.querySelectorAll({json.dumps(sel)})) {{
            if ((el.textContent||'').toLowerCase().includes(q)) return {{
                tag:el.tagName.toLowerCase(), text:(el.textContent||'').trim().substring(0,200),
                id:el.id||null, visible:!!(el.offsetWidth||el.offsetHeight||el.getClientRects().length)
            }};
        }}
        return null;
    }}""")
    return json.dumps(result if result else {"error": f"No element containing '{text}' found"})

async def handle_wait_for_text(request, data):
    """Wait for specific text to appear."""
    page = await get_page()
    text = data.get("text")
    timeout = data.get("timeout", 30000)
    if not text: return json.dumps({"error": "text required"})
    try:
        await page.wait_for_function(f"() => document.body.innerText.toLowerCase().includes({json.dumps(text.lower())})", timeout=timeout)
        return f"Text '{text}' found"
    except PlaywrightTimeout:
        return json.dumps({"error": f"Timeout waiting for '{text}'"})

async def handle_get_computed_style(request, data):
    """Get computed CSS styles of an element."""
    page = await get_page()
    selector = data.get("selector"); node_id = data.get("node_id")
    props = data.get("properties", ["display","visibility","opacity","position","zIndex","color","backgroundColor","fontSize","fontWeight","cursor","pointerEvents"])
    if selector:
        js = f"""() => {{ const el=document.querySelector({json.dumps(selector)}); if(!el) return null;
            const cs=getComputedStyle(el),r={{}}; {json.dumps(props)}.forEach(p=>r[p]=cs[p]||'');
            r.tag=el.tagName.toLowerCase(); r.rect=el.getBoundingClientRect(); return r; }}"""
    elif node_id:
        js = f"""() => {{ const e=window._mcpNodeMap.get({node_id}); if(!e) return null; const el=e.node;
            const cs=getComputedStyle(el),r={{}}; {json.dumps(props)}.forEach(p=>r[p]=cs[p]||'');
            r.tag=el.tagName.toLowerCase(); r.rect=el.getBoundingClientRect(); return r; }}"""
    else: return json.dumps({"error": "selector or node_id required"})
    r = await page.evaluate(js)
    return json.dumps(r if r else {"error": "Element not found"})

async def handle_is_visible(request, data):
    """Check if an element is visible."""
    page = await get_page()
    selector = data.get("selector"); node_id = data.get("node_id")
    if selector:
        r = await page.evaluate(f"""()=>{{const el=document.querySelector({json.dumps(selector)});
            if(!el) return {{exists:false}}; const rect=el.getBoundingClientRect(),cs=getComputedStyle(el);
            return {{exists:true, visible:!!(rect.width&&rect.height&&cs.display!=='none'&&cs.visibility!=='hidden'&&cs.opacity!=='0'),
            width:rect.width,height:rect.height}};}}""")
    elif node_id:
        r = await page.evaluate(f"""()=>{{const e=window._mcpNodeMap.get({node_id}); if(!e) return {{exists:false}};
            const el=e.node,rect=el.getBoundingClientRect(),cs=getComputedStyle(el);
            return {{exists:true, visible:!!(rect.width&&rect.height&&cs.display!=='none'&&cs.visibility!=='hidden'&&cs.opacity!=='0'),
            width:rect.width,height:rect.height}};}}""")
    else: return json.dumps({"error": "selector or node_id required"})
    return json.dumps(r)

async def handle_is_enabled(request, data):
    """Check if a form element is enabled."""
    page = await get_page()
    selector = data.get("selector"); node_id = data.get("node_id")
    if selector:
        r = await page.evaluate(f"()=>{{const el=document.querySelector({json.dumps(selector)}); if(!el) return {{exists:false}}; return {{exists:true, enabled:!el.disabled, readonly:!!el.readOnly}};}}")
    elif node_id:
        r = await page.evaluate(f"()=>{{const e=window._mcpNodeMap.get({node_id}); if(!e) return {{exists:false}}; return {{exists:true, enabled:!e.node.disabled, readonly:!!e.node.readOnly}};}}")
    else: return json.dumps({"error": "selector or node_id required"})
    return json.dumps(r)

async def handle_get_value(request, data):
    """Get the current value of an input/textarea/select."""
    page = await get_page()
    selector = data.get("selector"); node_id = data.get("node_id")
    if selector:
        r = await page.evaluate(f"""()=>{{const el=document.querySelector({json.dumps(selector)}); if(!el) return null;
            if(el.tagName==='SELECT') return {{value:el.value, selectedValues:Array.from(el.selectedOptions).map(o=>o.value)}};
            return {{value:el.value||el.textContent||''}};}}""")
    elif node_id:
        r = await page.evaluate(f"""()=>{{const e=window._mcpNodeMap.get({node_id}); if(!e) return null; const el=e.node;
            if(el.tagName==='SELECT') return {{value:el.value, selectedValues:Array.from(el.selectedOptions).map(o=>o.value)}};
            return {{value:el.value||el.textContent||''}};}}""")
    else: return json.dumps({"error": "selector or node_id required"})
    return json.dumps(r if r else {"error": "Element not found"})

async def handle_get_html(request, data):
    """Get the outerHTML of an element."""
    page = await get_page()
    selector = data.get("selector"); node_id = data.get("node_id")
    r = None
    if selector: r = await page.evaluate(f"document.querySelector({json.dumps(selector)})?.outerHTML||null")
    elif node_id: r = await page.evaluate(f"()=>{{const e=window._mcpNodeMap.get({node_id}); return e?e.node.outerHTML:null;}}")
    else: return json.dumps({"error": "selector or node_id required"})
    return r if r else json.dumps({"error": "Element not found"})

async def handle_get_selected_options(request, data):
    """Get selected options from a select element."""
    page = await get_page()
    selector = data.get("selector")
    if not selector: return json.dumps({"error": "selector required"})
    r = await page.evaluate(f"""()=>{{const el=document.querySelector({json.dumps(selector)});
        if(!el||el.tagName!=='SELECT') return null;
        return Array.from(el.selectedOptions).map(o=>({{value:o.value,text:o.text,index:o.index}}));}}""")
    return json.dumps(r if r else {"error": "Select not found"})


# ============================================================
# NEW FEATURES — Form Operations
# ============================================================

async def handle_fill_form(request, data):
    """Fill multiple form fields from a JSON object."""
    page = await get_page()
    fields = data.get("fields", {})
    if not fields: return json.dumps({"error": "fields object required"})
    filled = 0
    for sel, val in fields.items():
        try:
            await page.wait_for_selector(sel, timeout=5000)
            await page.fill(sel, str(val))
            filled += 1
        except: pass
    return f"Filled {filled}/{len(fields)} fields"

async def handle_clear_input(request, data):
    """Clear the contents of an input/textarea."""
    page = await get_page()
    selector = data.get("selector"); node_id = data.get("node_id")
    if selector:
        try: await page.wait_for_selector(selector, timeout=5000); await page.fill(selector, ""); return f"Cleared '{selector}'"
        except: return json.dumps({"error": f"Could not clear '{selector}'"})
    elif node_id:
        r = await page.evaluate(f"()=>{{const e=window._mcpNodeMap.get({node_id}); if(!e) return null; e.node.value=''; e.node.dispatchEvent(new Event('input',{{bubbles:true}})); e.node.dispatchEvent(new Event('change',{{bubbles:true}})); return 'ok';}}")
        if not r: return json.dumps({"error": f"Element {node_id} not found"})
        return f"Cleared element {node_id}"
    return json.dumps({"error": "selector or node_id required"})

async def handle_submit_form(request, data):
    """Submit the form containing a given element."""
    page = await get_page()
    selector = data.get("selector"); node_id = data.get("node_id")
    if selector:
        await page.evaluate(f"document.querySelector({json.dumps(selector)})?.closest('form')?.submit()")
        return f"Submitted form containing '{selector}'"
    elif node_id:
        await page.evaluate(f"()=>{{const e=window._mcpNodeMap.get({node_id}); if(!e) return null; const f=e.node.closest('form'); if(f) f.submit(); return f?'submitted':null;}}")
        return f"Submitted form containing element {node_id}"
    return json.dumps({"error": "selector or node_id required"})


# ============================================================
# NEW FEATURES — Device Emulation
# ============================================================

async def handle_set_geolocation(request, data):
    """Set a mock geolocation."""
    page = await get_page()
    lat = data.get("latitude", 37.7749); lon = data.get("longitude", -122.4194); acc = data.get("accuracy", 100)
    await page.context.grant_permissions(["geolocation"])
    await page.set_geolocation({"latitude": lat, "longitude": lon, "accuracy": acc})
    return f"Geolocation set to ({lat}, {lon})"

async def handle_set_timezone(request, data):
    """Set a mock timezone."""
    page = await get_page()
    tz = data.get("timezone_id", "America/New_York")
    cdp = await page.context.new_cdp_session(page)
    await cdp.send("Emulation.setTimezoneOverride", {"timezoneId": tz})
    return f"Timezone set to {tz}"

async def handle_set_device(request, data):
    """Emulate a device (e.g. 'iPhone 14', 'Pixel 7')."""
    page = await get_page()
    name = data.get("device_name", "")
    if not name: return json.dumps({"error": "device_name required"})
    from playwright.async_api import devices
    try:
        d = devices[name]
        cdp = await page.context.new_cdp_session(page)
        if "viewport" in d: await page.set_viewport_size(d["viewport"])
        if "user_agent" in d: await cdp.send("Network.setUserAgentOverride", {"userAgent": d["user_agent"]})
        if d.get("is_mobile"):
            await cdp.send("Emulation.setDeviceMetricsOverride", {
                "width": d["viewport"]["width"], "height": d["viewport"]["height"],
                "deviceScaleFactor": d.get("device_scale_factor", 1), "mobile": True
            })
        return f"Device emulation: {name}"
    except KeyError:
        return json.dumps({"error": f"Device '{name}' not found. Available: iPhone, Pixel, Galaxy, iPad"})

async def handle_set_network_conditions(request, data):
    """Simulate network conditions (offline/latency/throttle)."""
    page = await get_page()
    offline = data.get("offline", False); latency = data.get("latency", 0)
    down = data.get("download_throughput", -1); up = data.get("upload_throughput", -1)
    cdp = await page.context.new_cdp_session(page)
    await cdp.send("Network.emulateNetworkConditions", {
        "offline": offline, "latency": latency,
        "downloadThroughput": 0 if offline else down,
        "uploadThroughput": 0 if offline else up
    })
    if offline: return "Network set to OFFLINE"
    return f"Network: latency={latency}ms, dl={down}B/s, ul={up}B/s"


# ============================================================
# NEW FEATURES — Scrolling & Navigation
# ============================================================

async def handle_scroll_to_element(request, data):
    """Scroll an element into view."""
    page = await get_page()
    sel = data.get("selector"); nid = data.get("node_id")
    b = data.get("block", "center"); i = data.get("inline", "center")
    if sel:
        await page.evaluate(f"document.querySelector({json.dumps(sel)})?.scrollIntoView({{behavior:'smooth',block:'{b}',inline:'{i}'}})")
        return f"Scrolled to '{sel}'"
    elif nid:
        await page.evaluate(f"()=>{{const e=window._mcpNodeMap.get({nid}); if(e) e.node.scrollIntoView({{behavior:'smooth',block:'{b}',inline:'{i}'}});}}")
        return f"Scrolled to element {nid}"
    return json.dumps({"error": "selector or node_id required"})

async def handle_scroll_to_bottom(request, data):
    page = await get_page()
    s = data.get("smooth", True)
    await page.evaluate(f"window.scrollTo({{top:document.body.scrollHeight,behavior:'{'smooth' if s else 'instant'}'}})")
    return f"Scrolled to bottom"

async def handle_scroll_to_top(request, data):
    page = await get_page()
    s = data.get("smooth", True)
    await page.evaluate(f"window.scrollTo({{top:0,behavior:'{'smooth' if s else 'instant'}'}})")
    return "Scrolled to top"

async def handle_wait_for_load_state(request, data):
    """Wait for specific load state (networkidle/load/domcontentloaded)."""
    page = await get_page()
    state = data.get("state", "networkidle"); timeout = data.get("timeout", 30000)
    if state not in ("load","domcontentloaded","networkidle"): return json.dumps({"error": "state must be load/domcontentloaded/networkidle"})
    await page.wait_for_load_state(state, timeout=timeout)
    return f"Load state '{state}' reached"


# ============================================================
# NEW FEATURES — Injection
# ============================================================

async def handle_inject_css(request, data):
    page = await get_page()
    css = data.get("css", "")
    if not css: return json.dumps({"error": "css required"})
    await page.evaluate(f"()=>{{const s=document.createElement('style'); s.textContent={json.dumps(css)}; s.id='_mcp_css'; document.head.appendChild(s);}}")
    return f"Injected CSS ({len(css)} chars)"

async def handle_inject_js(request, data):
    page = await get_page()
    code = data.get("js", ""); url = data.get("url", "")
    if code: await page.evaluate(code); return f"Injected JS ({len(code)} chars)"
    if url:
        await page.evaluate(f"()=>{{const s=document.createElement('script'); s.src={json.dumps(url)}; document.head.appendChild(s);}}")
        return f"Injected JS from {url}"
    return json.dumps({"error": "js or url required"})

async def handle_remove_elements(request, data):
    page = await get_page()
    sel = data.get("selector")
    if not sel: return json.dumps({"error": "selector required"})
    count = await page.evaluate(f"document.querySelectorAll({json.dumps(sel)}).length")
    await page.evaluate(f"document.querySelectorAll({json.dumps(sel)}).forEach(e=>e.remove())")
    return f"Removed {count} elements"


# ============================================================
# NEW FEATURES — Shadow DOM
# ============================================================

async def handle_query_selector_shadow(request, data):
    """Query element inside shadow DOM."""
    page = await get_page()
    host = data.get("host_selector"); shadow = data.get("shadow_selector")
    if not host or not shadow: return json.dumps({"error": "host_selector and shadow_selector required"})
    r = await page.evaluate(f"""()=>{{const h=document.querySelector({json.dumps(host)});
        if(!h||!h.shadowRoot) return null; const el=h.shadowRoot.querySelector({json.dumps(shadow)});
        if(!el) return null;
        return {{tag:el.tagName.toLowerCase(),text:(el.textContent||'').trim().substring(0,200),
            visible:!!(el.offsetWidth||el.offsetHeight||el.getClientRects().length)}};}}""")
    return json.dumps(r if r else {"error": "Shadow element not found"})


# ============================================================
# NEW FEATURES — Mutation Watching
# ============================================================

async def handle_wait_for_mutation(request, data):
    """Wait for element to appear via DOM mutation."""
    page = await get_page()
    container = data.get("container", "body"); selector = data.get("selector"); timeout = data.get("timeout", 30000)
    if not selector: return json.dumps({"error": "selector required"})
    try:
        await page.wait_for_function(f"()=>document.querySelector({json.dumps(container)})?.querySelector({json.dumps(selector)})", timeout=timeout)
        return f"Element '{selector}' appeared"
    except PlaywrightTimeout:
        return json.dumps({"error": f"Timeout waiting for '{selector}'"})

async def handle_wait_for_element_state(request, data):
    """Wait for element to reach visible/hidden/attached/detached state."""
    page = await get_page()
    sel = data.get("selector"); state = data.get("state", "visible"); timeout = data.get("timeout", 30000)
    if not sel: return json.dumps({"error": "selector required"})
    if state not in ("visible","hidden","attached","detached"): return json.dumps({"error": "state must be visible/hidden/attached/detached"})
    try: await page.wait_for_selector(sel, state=state, timeout=timeout); return f"Element '{sel}' is now '{state}'"
    except PlaywrightTimeout: return json.dumps({"error": f"Timeout waiting for '{sel}' to be '{state}'"})


# ============================================================
# NEW FEATURES — Browser Management
# ============================================================

async def handle_get_browser_info(request, data):
    """Get browser info (UA, platform, viewport, etc.)."""
    page = await get_page()
    r = await page.evaluate("""()=>({
        userAgent:navigator.userAgent, platform:navigator.platform, language:navigator.language,
        cookiesEnabled:navigator.cookieEnabled, hardwareConcurrency:navigator.hardwareConcurrency,
        deviceMemory:navigator.deviceMemory, vendor:navigator.vendor,
        viewportWidth:window.innerWidth, viewportHeight:window.innerHeight,
        screenWidth:window.screen.width, screenHeight:window.screen.height,
        colorDepth:window.screen.colorDepth, url:window.location.href, origin:window.location.origin
    })""")
    return json.dumps(r)

async def handle_get_console_errors(request, data):
    """Get only error messages from captured logs."""
    return json.dumps([m for m in _console_messages if m.get("type") in ("error","pageerror","assert")])

async def handle_reset_session(request, data):
    """Clear cookies, storage, logs and navigate to blank page."""
    page = await get_page()
    await page.context.clear_cookies()
    await page.evaluate("window.localStorage.clear(); window.sessionStorage.clear()")
    _console_messages.clear(); _network_entries.clear()
    await page.goto("about:blank")
    return "Session reset: cookies, storage, logs cleared"


# ============================================================
# NEW FEATURES — Cookie Enhancements
# ============================================================

async def handle_export_cookies_netscape(request, data):
    """Export cookies in Netscape format."""
    page = await get_page()
    cookies = await page.context.cookies()
    lines = ["# Netscape HTTP Cookie File","# Generated by MCP Browser Daemon",""]
    for c in cookies:
        lines.append(f"{c.get('domain','')}\t{'TRUE' if c.get('domain','').startswith('.') else 'FALSE'}\t{c.get('path','/')}\t{'TRUE' if c.get('secure',False) else 'FALSE'}\t{int(c.get('expires',0))}\t{c.get('name','')}\t{c.get('value','')}")
    text = "\n".join(lines)
    fp = os.path.join(AGENT_OUTPUT, "cookies_netscape.txt")
    with open(fp, "w") as f: f.write(text)
    return text + f"\n\n(Saved to {fp})"

async def handle_import_cookies_netscape(request, data):
    """Import cookies from Netscape format file."""
    page = await get_page()
    fp = data.get("filepath", os.path.join(AGENT_OUTPUT, "cookies_netscape.txt"))
    if not os.path.exists(fp): return json.dumps({"error": f"File not found: {fp}"})
    with open(fp) as f: content = f.read()
    cookies = []
    for line in content.split("\n"):
        line = line.strip()
        if not line or line.startswith("#"): continue
        parts = line.split("\t")
        if len(parts) >= 7:
            cookies.append({"name": parts[5], "value": parts[6], "domain": parts[0], "path": parts[2], "secure": parts[3]=="TRUE", "httpOnly": False, "sameSite": "Lax"})
    if cookies: await page.context.add_cookies(cookies)
    return f"Imported {len(cookies)} cookies"


# ============================================================
# NEW FEATURES — Enhanced Screenshots
# ============================================================

async def handle_screenshot_region(request, data):
    """Screenshot a specific region."""
    page = await get_page()
    clip = {"x": data.get("x",0), "y": data.get("y",0), "width": data.get("width",800), "height": data.get("height",600)}
    if data.get("to_file"):
        fn = data.get("filename", f"region_{int(asyncio.get_event_loop().time())}.png")
        await page.screenshot(path=os.path.join(AGENT_OUTPUT, fn), clip=clip)
        return f"Region screenshot saved to agent_output/{fn}"
    b64 = base64.b64encode(await page.screenshot(clip=clip)).decode()
    return b64

async def handle_inject_overlay(request, data):
    """Draw an overlay on the page."""
    page = await get_page()
    html = data.get("html", '<div style="position:fixed;top:0;left:0;width:100%;height:100%;background:rgba(255,0,0,0.1);z-index:999999;pointer-events:none;">Overlay</div>')
    await page.evaluate(f"()=>{{const o=document.getElementById('_mcp_overlay'); if(o) o.remove(); const d=document.createElement('div'); d.id='_mcp_overlay'; d.innerHTML={json.dumps(html)}; document.body.appendChild(d);}}")
    return "Overlay injected"

async def handle_remove_overlay(request, data):
    """Remove the overlay."""
    page = await get_page()
    await page.evaluate("document.getElementById('_mcp_overlay')?.remove()")
    return "Overlay removed"


# ── Virtual Browser / Screencast Handlers ──

async def handle_set_headless(request, data):
    """Toggle headless (virtual) mode. Requires daemon restart."""
    global _headless, _page, _browser_context
    new_mode = data.get("headless", False)
    if _headless != new_mode:
        _headless = new_mode
        # Close existing browser to force re-launch with new mode
        if _browser_context:
            try:
                await _browser_context.close()
            except:
                pass
        _browser_context = None
        _page = None
        logger.info(f"Browser mode set to: {'virtual (headless)' if _headless else 'real (desktop)'}")
    return {"headless": _headless, "mode": "virtual" if _headless else "real"}

async def handle_get_headless(request, data):
    """Get current browser mode."""
    return {"headless": _headless, "mode": "virtual" if _headless else "real"}

async def handle_screencast_start(request, data):
    """Start CDP screencast streaming. Returns frames to registered queues."""
    global _screencasting
    page = await get_page()
    if _screencasting:
        return {"status": "already_streaming"}

    try:
        cdp = await page.context.new_cdp_session(page)
        await cdp.send("Page.startScreencast", {
            "format": "jpeg",
            "quality": 70,
            "maxWidth": 1280,
            "maxHeight": 720,
            "everyNthFrame": 1,
        })
        cdp.on("Page.screencastFrame", lambda params: _on_screencast_frame(params, cdp))
        _screencasting = True
        logger.info("Screencast started")
        return {"status": "started", "viewport": {"width": 1280, "height": 720}}
    except Exception as e:
        logger.error(f"Screencast start failed: {e}")
        return {"status": "error", "error": str(e)}

async def handle_screencast_stop(request, data):
    """Stop CDP screencast."""
    global _screencasting
    page = await get_page()
    try:
        cdp = await page.context.new_cdp_session(page)
        await cdp.send("Page.stopScreencast")
    except:
        pass
    _screencasting = False
    logger.info("Screencast stopped")
    return {"status": "stopped"}

def _on_screencast_frame(params, cdp_session):
    """Called by CDP when a new screencast frame arrives. Distribute to clients."""
    global _latest_frame
    try:
        jpeg_b64 = params.get("data", "")
        session_id = params.get("sessionId", 0)
        # Ack the frame (required by CDP)
        asyncio.ensure_future(
            cdp_session.send("Page.screencastFrameAck", {"sessionId": session_id})
        )
        if jpeg_b64:
            jpeg_bytes = base64.b64decode(jpeg_b64)
            _latest_frame = jpeg_bytes
            for q in list(_screencast_clients):
                try:
                    q.put_nowait(jpeg_bytes)
                except asyncio.QueueFull:
                    try:
                        q.get_nowait()  # drop oldest
                    except:
                        pass
                    try:
                        q.put_nowait(jpeg_bytes)
                    except:
                        pass
    except Exception as e:
        logger.error(f"Screencast frame error: {e}")

async def handle_screencast_grab_json(request, data):
    """Return the latest screencast frame info as JSON."""
    global _latest_frame
    has_frame = _latest_frame is not None
    return {"has_frame": has_frame, "size": len(_latest_frame) if has_frame else 0}

async def handle_screencast_grab(request):
    """Raw handler that returns JPEG bytes directly."""
    global _latest_frame
    if _latest_frame is None:
        return web.Response(status=204)
    return web.Response(body=_latest_frame, content_type="image/jpeg")


# --- Routes ---

app = web.Application()
routes = [
    web.post('/status', _make_responder(handle_status)),
    web.post('/navigate', _make_responder(handle_navigate)),
    web.post('/back', _make_responder(handle_back)),
    web.post('/forward', _make_responder(handle_forward)),
    web.post('/refresh', _make_responder(handle_refresh)),
    web.post('/get_url', _make_responder(handle_get_url)),
    web.post('/get_title', _make_responder(handle_get_title)),
    web.post('/get_page_source', _make_responder(handle_get_page_source)),
    web.post('/get_dom_tree', _make_responder(handle_get_dom_tree)),
    web.post('/query_selector', _make_responder(handle_query_selector)),
    web.post('/wait_for_selector', _make_responder(handle_wait_for_selector)),
    web.post('/get_attribute', _make_responder(handle_get_attribute)),
    web.post('/get_text', _make_responder(handle_get_text)),
    web.post('/click', _make_responder(handle_click)),
    web.post('/double_click', _make_responder(handle_double_click)),
    web.post('/type', _make_responder(handle_type)),
    web.post('/fill', _make_responder(handle_fill)),
    web.post('/select_option', _make_responder(handle_select_option)),
    web.post('/hover', _make_responder(handle_hover)),
    web.post('/press_key', _make_responder(handle_press_key)),
    web.post('/scroll', _make_responder(handle_scroll)),
    web.post('/new_tab', _make_responder(handle_new_tab)),
    web.post('/close_tab', _make_responder(handle_close_tab)),
    web.post('/switch_tab', _make_responder(handle_switch_tab)),
    web.post('/list_tabs', _make_responder(handle_list_tabs)),
    web.post('/get_cookies', _make_responder(handle_get_cookies)),
    web.post('/set_cookies', _make_responder(handle_set_cookies)),
    web.post('/clear_cookies', _make_responder(handle_clear_cookies)),
    web.post('/screenshot', _make_responder(handle_screenshot)),
    web.post('/screenshot_to_file', _make_responder(handle_screenshot_to_file)),
    web.post('/pdf', _make_responder(handle_pdf)),
    web.post('/download', _make_responder(handle_download)),
    web.post('/direct_download', _make_responder(handle_direct_download)),
    web.post('/evaluate', _make_responder(handle_evaluate)),
    web.post('/wait', _make_responder(handle_wait)),
    web.post('/set_viewport', _make_responder(handle_set_viewport)),

    # --- Console & Network ---
    web.post('/console_logs', _make_responder(handle_console_logs)),
    web.post('/network_logs', _make_responder(handle_network_logs)),

    # --- Storage ---
    web.post('/get_local_storage', _make_responder(handle_get_local_storage)),
    web.post('/set_local_storage', _make_responder(handle_set_local_storage)),
    web.post('/clear_local_storage', _make_responder(handle_clear_local_storage)),
    web.post('/get_session_storage', _make_responder(handle_get_session_storage)),
    web.post('/set_session_storage', _make_responder(handle_set_session_storage)),
    web.post('/clear_session_storage', _make_responder(handle_clear_session_storage)),

    # --- File Upload ---
    web.post('/upload_file', _make_responder(handle_upload_file)),

    # --- Element Screenshot ---
    web.post('/element_screenshot', _make_responder(handle_element_screenshot)),
    web.post('/element_screenshot_to_file', _make_responder(handle_element_screenshot_to_file)),

    # --- Bounding Box ---
    web.post('/get_bounding_box', _make_responder(handle_get_bounding_box)),

    # --- Highlight ---
    web.post('/highlight', _make_responder(handle_highlight)),

    # --- Wait for Function ---
    web.post('/wait_for_function', _make_responder(handle_wait_for_function)),

    # --- Block Resources ---
    web.post('/block_resources', _make_responder(handle_block_resources)),

    # --- Performance ---
    web.post('/get_performance', _make_responder(handle_get_performance)),

    # --- User Agent ---
    web.post('/get_user_agent', _make_responder(handle_get_user_agent)),

    # --- Focus Element ---
    web.post('/focus_element', _make_responder(handle_focus_element)),

    # --- Mouse Move ---
    web.post('/mouse_move_to_element', _make_responder(handle_mouse_move_to_element)),

    # --- Drag Element ---
    web.post('/drag_element', _make_responder(handle_drag_element)),

    # --- Count Elements ---
    web.post('/get_element_count', _make_responder(handle_get_element_count)),

    # --- Storage State ---
    web.post('/save_storage_state', _make_responder(handle_save_storage_state)),
    web.post('/get_storage_state', _make_responder(handle_get_storage_state)),
    web.post('/clear_storage_state', _make_responder(handle_clear_storage_state)),

    # --- Dialog Behavior ---
    web.post('/set_dialog_behavior', _make_responder(handle_set_dialog_behavior)),

    # ===== NEW FEATURES =====

    # Content Extraction
    web.post('/get_visible_text', _make_responder(handle_get_visible_text)),
    web.post('/get_markdown', _make_responder(handle_get_markdown)),
    web.post('/extract_links', _make_responder(handle_extract_links)),
    web.post('/extract_images', _make_responder(handle_extract_images)),
    web.post('/extract_tables', _make_responder(handle_extract_tables)),
    web.post('/get_meta_tags', _make_responder(handle_get_meta_tags)),

    # CDP Enhancements
    web.post('/get_accessibility_tree', _make_responder(handle_get_accessibility_tree)),
    web.post('/query_selector_all', _make_responder(handle_query_selector_all)),
    web.post('/get_element_by_text', _make_responder(handle_get_element_by_text)),
    web.post('/wait_for_text', _make_responder(handle_wait_for_text)),
    web.post('/get_computed_style', _make_responder(handle_get_computed_style)),
    web.post('/is_visible', _make_responder(handle_is_visible)),
    web.post('/is_enabled', _make_responder(handle_is_enabled)),
    web.post('/get_value', _make_responder(handle_get_value)),
    web.post('/get_html', _make_responder(handle_get_html)),
    web.post('/get_selected_options', _make_responder(handle_get_selected_options)),

    # Form Operations
    web.post('/fill_form', _make_responder(handle_fill_form)),
    web.post('/clear_input', _make_responder(handle_clear_input)),
    web.post('/submit_form', _make_responder(handle_submit_form)),

    # Device Emulation
    web.post('/set_geolocation', _make_responder(handle_set_geolocation)),
    web.post('/set_timezone', _make_responder(handle_set_timezone)),
    web.post('/set_device', _make_responder(handle_set_device)),
    web.post('/set_network_conditions', _make_responder(handle_set_network_conditions)),

    # Scrolling
    web.post('/scroll_to_element', _make_responder(handle_scroll_to_element)),
    web.post('/scroll_to_bottom', _make_responder(handle_scroll_to_bottom)),
    web.post('/scroll_to_top', _make_responder(handle_scroll_to_top)),
    web.post('/wait_for_load_state', _make_responder(handle_wait_for_load_state)),

    # Injection
    web.post('/inject_css', _make_responder(handle_inject_css)),
    web.post('/inject_js', _make_responder(handle_inject_js)),
    web.post('/remove_elements', _make_responder(handle_remove_elements)),

    # Shadow DOM
    web.post('/query_selector_shadow', _make_responder(handle_query_selector_shadow)),

    # Mutation
    web.post('/wait_for_mutation', _make_responder(handle_wait_for_mutation)),
    web.post('/wait_for_element_state', _make_responder(handle_wait_for_element_state)),

    # Browser Management
    web.post('/get_browser_info', _make_responder(handle_get_browser_info)),
    web.post('/get_console_errors', _make_responder(handle_get_console_errors)),
    web.post('/reset_session', _make_responder(handle_reset_session)),

    # Cookie Enhancements
    web.post('/export_cookies_netscape', _make_responder(handle_export_cookies_netscape)),
    web.post('/import_cookies_netscape', _make_responder(handle_import_cookies_netscape)),

    # Enhanced Screenshots
    web.post('/screenshot_region', _make_responder(handle_screenshot_region)),
    web.post('/inject_overlay', _make_responder(handle_inject_overlay)),
    web.post('/remove_overlay', _make_responder(handle_remove_overlay)),

    # ── Virtual Browser / Screencast ──
    web.post('/set_headless', _make_responder(handle_set_headless)),
    web.get('/get_headless', _make_responder(handle_get_headless)),
    web.post('/screencast/start', _make_responder(handle_screencast_start)),
    web.post('/screencast/stop', _make_responder(handle_screencast_stop)),
]

app.add_routes(routes)
# Raw binary route — returns JPEG bytes, not JSON
app.router.add_get('/screencast/grab', handle_screencast_grab)

async def cleanup_browser(app):
    global _browser_context, _playwright_instance

    # Save storage state before closing
    if _browser_context and _page:
        try:
            cookies = await _browser_context.cookies()
            local_storage = {}
            try:
                ls = await _page.evaluate("JSON.stringify(window.localStorage)")
                local_storage = json.loads(ls) if ls != "{}" else {}
            except:
                pass
            state = {"cookies": cookies, "local_storage": local_storage}
            with open(_storage_state_path, "w") as f:
                json.dump(state, f, indent=2)
            logger.info(f"Storage state saved ({len(cookies)} cookies, {len(local_storage)} localStorage entries)")
        except:
            pass

    if _browser_context:
        try:
            await _browser_context.close()
        except:
            pass
    if _playwright_instance:
        try:
            await _playwright_instance.stop()
        except:
            pass

async def init_browser(app):
    """Open the browser eagerly when the daemon starts."""
    try:
        page = await asyncio.wait_for(get_page(), timeout=30)
        url = page.url if not page.is_closed() else "about:blank"
        logger.info(f"Browser opened, current URL: {url}")
    except asyncio.TimeoutError:
        logger.error("Browser launch timed out after 30s")
    except Exception as e:
        logger.error(f"Failed to open browser: {e}")

app.on_startup.append(init_browser)
app.on_cleanup.append(cleanup_browser)

if __name__ == "__main__":
    web.run_app(app, host='127.0.0.1', port=BROWSER_DAEMON_PORT, access_log=None)
