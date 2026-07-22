"""Browser agent — web automation with its own brain and tools."""


def get_browser_subagent(config=None) -> dict:
    model = config.model if config else "groq:openai/gpt-oss-120b"
    return {
        "name": "browser-agent",
        "description": (
            "Browser automation agent for web navigation, form filling, screenshots, "
            "web scraping, and online interactions. "
            "Use for: opening websites, filling forms, taking screenshots, "
            "scraping data, web testing, online research, social media."
        ),
        "system_prompt": (
            "You are a browser automation expert.\n\n"
            "CAPABILITIES:\n"
            "- browser_open: navigate to any URL\n"
            "- browser_click: click elements by CSS selector\n"
            "- browser_type: type text into input fields\n"
            "- browser_screenshot: capture page screenshots\n"
            "- browser_close: close the browser\n"
            "- web_search / web_fetch: supplementary research\n"
            "- memory_store / memory_search: save and recall findings\n"
            "- todo_create / todo_complete: track browsing tasks\n"
            "- shell_execute: run system commands if needed\n\n"
            "WORKFLOW:\n"
            "1. Open the target URL\n"
            "2. Navigate and interact as needed\n"
            "3. Take screenshots at key points\n"
            "4. Extract and save important information\n"
            "5. Close the browser when done\n\n"
            "## YouTube / Media Playback\n"
            "When the user asks to play a song/video on YouTube:\n"
            "- Open YouTube search: browser_open('https://www.youtube.com/results?search_query=QUERY')\n"
            "- Wait for results: browser_wait(3)\n"
            "- Click the first video: browser_click('a#video-title') or browser_click('ytd-video-renderer a#video-title')\n"
            "- Wait for video page: browser_wait(3)\n"
            "- The video auto-plays on YouTube — if not, press Space or click the video player\n\n"
            "Handle popups, wait for page loads, and be thorough."
        ),
        "model": model,
        "tools": [
            "browser_open", "browser_click", "browser_type",
            "browser_screenshot", "browser_close",
            "web_search", "web_fetch",
            "memory_store", "memory_search",
            "todo_create", "todo_complete",
            "shell_execute",
        ],
    }
