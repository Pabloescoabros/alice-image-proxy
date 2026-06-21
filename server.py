"""
Alice Yandex Proxy v5.1 — Multi-Session OpenAI-Compatible API
=============================================================
Multi-session management:
  - Separate Alice chats per model type
  - Session rotation with summarization
  - Context aggregation via summaries (not full history injection)

Models:
  alice        — base chat
  alice-pro    — advanced chat (YandexGPT 5 Pro)
  alice-search — deep research agent
  alice-image  — image generation
  alice-vision — image analysis
  alice-code   — coding tasks
"""

import os, sys, json, time, asyncio, base64, logging, hashlib, uuid
from pathlib import Path
from typing import Optional, Dict, List
from dataclasses import dataclass, field
from contextlib import asynccontextmanager
from datetime import datetime

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, StreamingResponse, FileResponse
from pydantic import BaseModel, Field

PROJECT_DIR = Path(__file__).parent
STATE_DIR   = PROJECT_DIR / "state"
COOKIE_FILE = PROJECT_DIR / "cookies.txt"
IMAGE_CACHE = PROJECT_DIR / "cache"
MEDIA_DIR   = PROJECT_DIR / "media"
LOG_FILE    = PROJECT_DIR / "alice_proxy.log"

STATE_DIR.mkdir(exist_ok=True)
IMAGE_CACHE.mkdir(exist_ok=True)
MEDIA_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)],
)
log = logging.getLogger("alice-proxy")

MAX_MESSAGES_PER_SESSION = 50

MODEL_CONFIGS = {
    "alice":        {"url": "https://alice.yandex.ru/", "description": "Base chat"},
    "alice-pro":    {"url": "https://alice.yandex.ru/?model=pro", "description": "Advanced chat (Pro)"},
    "alice-search": {"url": "https://alice.yandex.ru/?model=alice-agents-deep-research", "description": "Deep research"},
    "alice-image":  {"url": "https://alice.yandex.ru/?draw_picture=1", "description": "Image generation"},
    "alice-vision": {"url": "https://alice.yandex.ru/?draw_picture=1", "description": "Image analysis"},
    "alice-code":   {"url": "https://alice.yandex.ru/?model=pro", "description": "Coding tasks"},
    "alice-media":  {"url": "https://alice.yandex.ru/?draw_picture=1", "description": "Unified: generation, editing, vision"},
}


@dataclass
class ChatSession:
    session_id: str
    model: str
    project: str = "default"
    message_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)
    summary: str = ""

    @property
    def key(self) -> str:
        """Unique session key: project:model"""
        return f"{self.project}:{self.model}"

    def needs_rotation(self) -> bool:
        return self.message_count >= MAX_MESSAGES_PER_SESSION

    def touch(self):
        self.message_count += 1
        self.last_active = time.time()

    def first_message(self) -> str:
        """First message sent to Alice to name the chat (project + model)."""
        model_label = self.model.replace("alice-", "").replace("alice", "chat")
        return f"[{self.project}] {model_label}"


class AliceRPC:
    RPC_BASE = "https://rpc.alice.yandex.ru"

    def __init__(self):
        self.cookies: dict = {}
        self.cookie_str: str = ""
        self._load_cookies()

    def _load_cookies(self):
        if COOKIE_FILE.exists():
            self.cookie_str = COOKIE_FILE.read_text(encoding="utf-8").strip()
            if self.cookie_str:
                self.cookies = self._parse_cookie_string(self.cookie_str)

    def _parse_cookie_string(self, s: str) -> dict:
        result = {}
        for part in s.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                result[k.strip()] = v.strip()
        return result

    def set_cookies(self, cookie_str: str):
        self.cookie_str = cookie_str.strip()
        self.cookies = self._parse_cookie_string(self.cookie_str)
        COOKIE_FILE.write_text(self.cookie_str, encoding="utf-8")

    def _get_headers(self) -> dict:
        return {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "Content-Type": "application/json",
            "Origin": "https://alice.yandex.ru",
            "Referer": "https://alice.yandex.ru/",
            "Cookie": self.cookie_str,
            "X-Ya-App-Id": "ru.yandex.webstandalone.desktop",
            "X-Ya-Device-Id": self.cookies.get("yandexuid", "0"),
            "X-Ya-Uuid": self.cookies.get("alice_uuid", str(uuid.uuid4())),
            "X-Ya-Language": "ru",
            "X-Ya-Application": json.dumps({
                "app_id": "ru.yandex.webstandalone.desktop",
                "uuid": self.cookies.get("alice_uuid", ""),
                "device_id": self.cookies.get("yandexuid", "0"),
                "lang": "ru", "timezone": "Asia/Yekaterinburg",
            }),
            "X-Ya-Supported-Features": "background_response_streaming,supports_streaming_response,supports_markdown_response",
            "X-Ya-Experiments": json.dumps(["standalone_alice_2_0", "draw_picture_enable_controls"]),
        }

    async def _post(self, endpoint: str, body: dict) -> dict:
        import httpx
        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(f"{self.RPC_BASE}{endpoint}", headers=self._get_headers(), json=body)
            if resp.status_code != 200:
                raise HTTPException(resp.status_code, f"RPC error: {resp.text[:200]}")
            return resp.json()

    async def health_check(self) -> dict:
        try:
            await self._post("/gproxy/get_user_settings", {})
            return {"status": "ok", "authenticated": True, "login": self.cookies.get("yandex_login", "?")}
        except:
            return {"status": "error", "authenticated": False}


class AliceBrowser:
    def __init__(self):
        self.pw = None
        self.browser = None
        self.context = None
        self.page = None
        self._ready = False
        self._lock = asyncio.Lock()
        self._chrome_proc = None
        self.sessions: Dict[str, ChatSession] = {}
        self.session_pages: Dict[str, object] = {}

    async def ensure_started(self) -> bool:
        if self._ready and self.page and not self.page.is_closed():
            return True

        from playwright.async_api import async_playwright

        if not self.pw:
            self.pw = await async_playwright().start()

        import subprocess
        chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
        user_data = str(STATE_DIR / "chrome_profile")
        debug_port = 9222

        try:
            subprocess.run(["taskkill", "/F", "/IM", "chrome.exe", "/FI", "WINDOWTITLE eq alice-debug"],
                         capture_output=True, timeout=5)
        except:
            pass

        await asyncio.sleep(1)

        chrome_args = [
            chrome_path,
            f"--remote-debugging-port={debug_port}",
            f"--user-data-dir={user_data}",
            "--no-first-run",
            "--disable-features=TranslateUI",
            "--window-size=1280,900",
            "https://alice.yandex.ru/",
        ]

        log.info("Launching Chrome with CDP...")
        self._chrome_proc = subprocess.Popen(chrome_args)
        await asyncio.sleep(5)

        self.browser = await self.pw.chromium.connect_over_cdp(
            f"http://localhost:{debug_port}", timeout=30000,
        )

        contexts = self.browser.contexts
        self.context = contexts[0] if contexts else await self.browser.new_context()

        pages = self.context.pages
        alice_pages = [p for p in pages if "alice.yandex.ru" in p.url]

        if alice_pages:
            self.page = alice_pages[0]
        elif pages:
            self.page = pages[0]
            await self.page.goto("https://alice.yandex.ru/", wait_until="domcontentloaded", timeout=45000)
        else:
            self.page = await self.context.new_page()
            await self.page.goto("https://alice.yandex.ru/", wait_until="domcontentloaded", timeout=45000)

        await asyncio.sleep(5)

        # Inject cookies from cookies.txt into browser context
        if alice_rpc.cookies:
            try:
                cookies_to_inject = []
                for k, v in alice_rpc.cookies.items():
                    cookies_to_inject.append({"name": k, "value": v, "domain": ".yandex.ru", "path": "/"})
                if cookies_to_inject:
                    await self.context.add_cookies(cookies_to_inject)
                    log.info(f"Injected {len(cookies_to_inject)} cookies into browser")
                    await self.page.reload(wait_until="domcontentloaded", timeout=30000)
                    await asyncio.sleep(5)
            except Exception as e:
                log.warning(f"Cookie injection failed: {e}")

        if not await self._check_logged_in():
            log.warning("Not logged in! Waiting for manual login (180s)...")
            for i in range(180):
                await asyncio.sleep(1)
                if await self._check_logged_in():
                    break

        await self._save_cookies()
        self._ready = True
        log.info("Browser ready")
        return True

    async def _check_logged_in(self) -> bool:
        try:
            if "alice.yandex.ru" not in self.page.url:
                return False
            text = await self.page.inner_text("body", timeout=5000)
            indicators = ["Новый чат", "Персонажи", "Спросите", "спросите", "о чём угодно"]
            found = sum(1 for ind in indicators if ind in text)
            cookies = await self.context.cookies()
            has_session = any(c["name"] in ("Session_id", "sessionid2") and c["value"] for c in cookies)
            if (found >= 2 and has_session) or found >= 3:
                return True
            login_btn = self.page.locator('button:has-text("Войти")')
            if await login_btn.count() > 0:
                return False
            if has_session and found >= 1:
                return True
            return False
        except:
            return False

    async def _save_cookies(self):
        try:
            cookies = await self.context.cookies()
            (STATE_DIR / "cookies.json").write_text(json.dumps(cookies, indent=2), encoding="utf-8")
        except Exception as e:
            log.error(f"Save cookies failed: {e}")

    async def _get_page_for_model(self, model: str, project: str = "default") -> object:
        """Get or create a browser page for a project:model session."""
        session_key = f"{project}:{model}"
        # Extract base model for URL config (handle project:model format)
        base_model = model.split(":")[-1] if ":" in model else model

        if session_key in self.session_pages:
            page = self.session_pages[session_key]
            if not page.is_closed():
                try:
                    url = page.url
                    body_len = await page.evaluate("document.body ? document.body.innerText.length : 0")
                    if body_len > 10 and "alice.yandex" in url:
                        return page
                except:
                    pass
                log.warning(f"Page for {session_key} is dead, recreating")
                try:
                    await page.close()
                except:
                    pass

        config = MODEL_CONFIGS.get(base_model, MODEL_CONFIGS["alice"])
        page = await self.context.new_page()

        await page.goto(config["url"], wait_until="domcontentloaded", timeout=45000)
        await asyncio.sleep(5)

        body_len = await page.evaluate("document.body ? document.body.innerText.length : 0")
        if body_len < 50:
            await asyncio.sleep(10)

        await self._start_new_chat(page)
        await asyncio.sleep(2)

        self.session_pages[session_key] = page
        log.info(f"Created isolated page for {session_key}: {config['url']}")
        return page

    async def _start_new_chat(self, page: object):
        try:
            new_btn = page.locator('button:has-text("Новый чат")').first
            if await new_btn.count() > 0:
                await new_btn.click()
                await asyncio.sleep(2)
                log.info("Started new chat")
                return True
        except Exception as e:
            log.warning(f"Could not start new chat: {e}")
        return False

    async def _get_input_field(self, page: object):
        selectors = [
            'textarea[data-testid="inputbase-textarea"]',
            'textarea[placeholder*="Спросите"]',
            'textarea[placeholder*="о чём"]',
            'textarea.AliceInput-Textarea',
            'textarea',
            '[contenteditable="true"]',
            '[role="textbox"]',
        ]
        for sel in selectors:
            el = page.locator(sel).first
            if await el.count() > 0:
                return el
        raise HTTPException(500, "Cannot find chat input field")

    async def _send_message(self, page: object, text: str):
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass
        await asyncio.sleep(1)

        # Clear input field first to prevent text concatenation
        inp = await self._get_input_field(page)
        await inp.click()
        await asyncio.sleep(0.3)
        await page.keyboard.press("Control+a")
        await asyncio.sleep(0.1)
        await page.keyboard.press("Delete")
        await asyncio.sleep(0.3)

        # Verify input is empty
        current_val = await inp.input_value() if hasattr(inp, 'input_value') else ""
        if current_val.strip():
            log.warning(f"Input not empty after clear: {current_val[:50]}, triple-clearing")
            await page.keyboard.press("Control+a")
            await asyncio.sleep(0.1)
            await page.keyboard.press("Backspace")
            await asyncio.sleep(0.3)

        await page.keyboard.type(text, delay=30)
        await asyncio.sleep(0.5)
        await page.keyboard.press("Enter")
        log.info(f"Sent: {text[:80]}")

    async def _check_reauth(self, page: object) -> bool:
        if "passport.yandex" in page.url:
            log.warning("Reauth detected, waiting 120s...")
            for i in range(120):
                await asyncio.sleep(1)
                if "alice.yandex.ru" in page.url:
                    await asyncio.sleep(3)
                    return True
            return False
        return True

    async def _wait_for_response(self, page: object, timeout: int = 120) -> str:
        await asyncio.sleep(2)
        if not await self._check_reauth(page):
            raise HTTPException(401, "Reauth required")

        start = time.time()
        prev_text = ""
        stable_count = 0

        while time.time() - start < timeout:
            await asyncio.sleep(2)

            if not await self._check_reauth(page):
                raise HTTPException(401, "Reauth required")

            try:
                last_msg_text = await page.evaluate("""
                    () => {
                        const selectors = [
                            '[class*="AliceMessage"]',
                            '[class*="message-"]',
                            '[class*="MessageItem"]',
                            '[class*="Bubble"]',
                            '[data-testid*="message"]',
                        ];
                        let msgs = [];
                        for (const sel of selectors) {
                            document.querySelectorAll(sel).forEach(el => {
                                if (el.innerText && el.innerText.trim().length > 1) msgs.push(el);
                            });
                        }
                        const seen = new Set();
                        const unique = [];
                        for (const el of msgs) {
                            const key = el.innerText.trim().substring(0, 100);
                            if (!seen.has(key)) { seen.add(key); unique.push(el); }
                        }
                        const filtered = unique.filter(el => {
                            const t = el.innerText.trim();
                            const c = el.className || '';
                            if (c.includes('user') || c.includes('User') || c.includes('my-')) return false;
                            if (t.includes('Поискать в Яндексе') || t.includes('Поделиться')) return false;
                            if (el.querySelector('button') && !el.querySelector('[class*="markdown"], [class*="text"]')) return false;
                            if (t.length < 3) return false;
                            return true;
                        });
                        if (filtered.length > 0) return filtered[filtered.length - 1].innerText.trim();
                        return '';
                    }
                """)
            except Exception as e:
                log.warning(f"JS error: {e}")
                last_msg_text = ""

            if last_msg_text and len(last_msg_text) > 1:
                if last_msg_text == prev_text:
                    stable_count += 1
                    if stable_count >= 3:
                        return last_msg_text
                else:
                    stable_count = 0
                    prev_text = last_msg_text

            try:
                img_url = await page.evaluate("""
                    () => {
                        const imgs = document.querySelectorAll('img[src*="yaart"], img[src*="s3.yandex"]');
                        if (imgs.length > 0) return imgs[imgs.length - 1].src;
                        return '';
                    }
                """)
                if img_url and ("s3" in img_url or "yaart" in img_url):
                    await asyncio.sleep(5)
                    try:
                        final_text = await page.evaluate("""
                            () => {
                                const els = document.querySelectorAll('[class*="AliceMessage"], [class*="message-"], [class*="Bubble"]');
                                if (els.length > 0) return els[els.length-1].innerText.trim();
                                return '';
                            }
                        """)
                        if final_text and len(final_text) > 5:
                            return final_text
                    except:
                        pass
                    return f"[IMAGE]({img_url})"
            except:
                pass

        if prev_text:
            return prev_text
        raise HTTPException(504, "Response timeout")

    async def _wait_for_image(self, page: object, timeout: int = 120) -> str:
        s3_urls = []

        async def on_response(response):
            url = response.url
            if ("yaart" in url or "s3.yandex" in url) and any(e in url for e in [".jpg", ".png", ".webp"]):
                s3_urls.append(url)

        page.on("response", on_response)
        start = time.time()
        try:
            while time.time() - start < timeout:
                if s3_urls:
                    return s3_urls[-1]
                img = page.locator('img[src*="yaart"], img[src*="s3.yandex"]')
                if await img.count() > 0:
                    src = await img.first.get_attribute("src")
                    if src:
                        return src
                await asyncio.sleep(1)
        finally:
            page.remove_listener("response", on_response)
        raise HTTPException(504, "Image generation timeout")

    async def _close_old_chat(self, page: object):
        """Delete current chat from Alice sidebar."""
        try:
            # Step 1: Expand sidebar if collapsed — click the chat icon
            sidebar_icon = page.locator('[data-testid*="sidebar-toggle"], [aria-label*="Чаты"], [aria-label*="Список чатов"], button:has-text("Чаты")').first
            if await sidebar_icon.count() > 0:
                await sidebar_icon.click()
                await asyncio.sleep(1)
                log.info("Expanded sidebar")

            # Step 2: Find sidebar chat list
            await asyncio.sleep(1)

            # Try to find chat items in expanded sidebar
            chat_items = None
            for sel in [
                '[data-testid*="chat-item"]',
                '[class*="SidebarChatItem"]',
                '[class*="sidebar"] [class*="ChatItem"]',
                '[class*="chat-list"] > div > div',
                '[class*="ChatList"] > div > div',
                'nav a[href*="/chat/"]',
            ]:
                items = page.locator(sel)
                count = await items.count()
                if count > 0:
                    chat_items = items
                    log.info(f"Found {count} chat items via: {sel}")
                    break

            if not chat_items:
                # Fallback: get all clickable divs in sidebar area
                sidebar_area = page.locator('[class*="sidebar"], [class*="Sidebar"], nav').first
                if await sidebar_area.count() > 0:
                    all_divs = sidebar_area.locator('div[class*="item"], div[class*="Item"], div[class*="chat"], a')
                    count = await all_divs.count()
                    if count > 0:
                        chat_items = all_divs
                        log.info(f"Found {count} sidebar items via fallback")

            if not chat_items:
                log.warning("No chat items found in sidebar")
                return False

            # Step 3: Hover on first (most recent) chat item to reveal menu
            item = chat_items.first
            await item.hover()
            await asyncio.sleep(0.8)

            # Step 4: Find and click the 3-dot menu
            menu_found = False
            for msel in [
                'button[aria-label*="Ещё"]',
                'button[aria-label*="Еще"]',
                '[data-testid*="more"]',
                '[data-testid*="menu"]',
                '[class*="MoreButton"]',
                '[class*="more-btn"]',
                'button:has(svg)',
            ]:
                menu = item.locator(msel).first
                if await menu.count() > 0:
                    try:
                        await menu.click(timeout=3000)
                        menu_found = True
                        await asyncio.sleep(1)
                        log.info(f"Clicked menu via: {msel}")
                        break
                    except:
                        continue

            if not menu_found:
                # Try right-click context menu
                await item.click(button="right")
                await asyncio.sleep(1)

            # Step 5: Find delete option
            for dsel in [
                'button:has-text("Удалить")',
                'div:has-text("Удалить")',
                '[data-testid*="delete"]',
                '[class*="delete"]',
            ]:
                del_btn = page.locator(dsel).first
                if await del_btn.count() > 0:
                    try:
                        await del_btn.click(timeout=3000)
                        await asyncio.sleep(1)
                        log.info(f"Clicked delete via: {dsel}")

                        # Confirm if dialog appears
                        for csel in [
                            'button:has-text("Удалить")',
                            'button:has-text("Да")',
                            'button:has-text("Подтвердить")',
                        ]:
                            confirm = page.locator(csel).first
                            if await confirm.count() > 0:
                                try:
                                    await confirm.click(timeout=3000)
                                    await asyncio.sleep(1)
                                except:
                                    pass
                                break

                        log.info("Old chat deleted")
                        return True
                    except:
                        continue

            log.warning("Delete button not found in menu")
            return False
        except Exception as e:
            log.warning(f"Delete old chat failed: {e}")
            return False

    async def _summarize_and_rotate(self, model: str, project: str = "default"):
        """Summarize current chat, delete old, start new with summary."""
        session_key = f"{project}:{model}"
        session = self.sessions.get(session_key)
        if not session:
            return

        page = await self._get_page_for_model(model, project)

        # Ask Alice to summarize
        await self._send_message(page, "Кратко.summarize наш разговор: что обсуждали, какие решения приняты, какие задачи остались? Ответь в 3-5 предложениях.")
        try:
            summary = await self._wait_for_response(page, timeout=60)
            session.summary = summary
            log.info(f"Summary [{session_key}]: {summary[:100]}...")
        except Exception as e:
            log.error(f"Summarize failed [{session_key}]: {e}")
            session.summary = f"Предыдущая сессия ({session.message_count} сообщений)"

        # Delete old chat
        await self._close_old_chat(page)

        # Start new chat
        await self._start_new_chat(page)
        await asyncio.sleep(1)

        # Combine naming + summary into one message (first message = chat name in sidebar)
        if session.summary:
            combined = f"[{project}:{model}] [Context from previous conversation]: {session.summary}"
            await self._send_message(page, combined)
            await asyncio.sleep(3)

        # Reset session counter
        session.session_id = str(uuid.uuid4().hex[:8])
        session.message_count = 0
        log.info(f"Rotated {session_key} → new session {session.session_id}")

    async def chat_with_model(self, model: str, message: str, timeout: int = 120, project: str = "default") -> str:
        """Send message to Alice's chat for this model. Alice handles history natively."""
        async with self._lock:
            await self.ensure_started()

            session_key = f"{project}:{model}"

            # Create session if new
            is_new = session_key not in self.sessions
            if is_new:
                self.sessions[session_key] = ChatSession(
                    session_id=str(uuid.uuid4().hex[:8]),
                    model=model,
                    project=project,
                )

            session = self.sessions[session_key]

            # Rotate if needed BEFORE sending
            if session.needs_rotation():
                log.info(f"Rotating session for {session_key} ({session.message_count} msgs)")
                await self._summarize_and_rotate(model, project)

            page = await self._get_page_for_model(model, project)

            # For new sessions, start a fresh chat
            if is_new:
                await self._start_new_chat(page)
                await asyncio.sleep(1)
                # Prepend project info to first message (becomes chat name in sidebar)
                message = f"[{project}:{model}] {message}"

            # Send message — Alice remembers history natively in this chat
            await self._send_message(page, message)
            session.touch()

            response = await self._wait_for_response(page, timeout)
            log.info(f"[{session_key}] msgs={session.message_count}, response={response[:80]}")
            return response

    def _rewrite_image_prompt(self, raw_prompt: str) -> str:
        """Transform a raw prompt into a high-quality English image generation prompt."""
        import re
        # Common Russian → English translations for art terms
        translations = {
            "кот": "cat", "собака": "dog", "девушка": "beautiful woman", "парень": "young man",
            "закат": "sunset", "восход": "sunrise", "луна": "moon", "море": "ocean",
            "горы": "mountains", "лес": "forest", "город": "cityscape", "небо": "sky",
            "цветы": "flowers", "дерево": "tree", "дождь": "rain", "снег": "snow",
            "космос": "space", "подводный": "underwater", "пейзаж": "landscape",
            "портрет": "portrait", "фантастика": "sci-fi", "фэнтези": "fantasy",
            "реализм": "photorealistic", "абстракция": "abstract",
            "красивый": "stunning", "красивая": "stunning", "огромный": "massive",
            "маленький": "tiny", "тёмный": "dark", "светлый": "bright",
            "яркий": "vibrant", "мягкий": "soft", "жёсткий": "harsh",
            "ночь": "night", "день": "daytime", "вечер": "evening", "утро": "morning",
            "вода": "water", "огонь": "fire", "земля": "earth", "воздух": "air",
            "на луне": "on the moon", "на закате": "at sunset", "в космосе": "in outer space",
            "на море": "at the ocean", "в лесу": "in the forest", "в горах": "in the mountains",
            "на небе": "in the sky", "под водой": "underwater",
        }

        prompt_lower = raw_prompt.lower()
        english_parts = []

        # Translate known words
        for ru, en in translations.items():
            if ru in prompt_lower:
                english_parts.append(en)

        # If we got good translation, use it as base
        if english_parts:
            base = ", ".join(english_parts)
        else:
            base = raw_prompt

        # Build high-quality prompt with style enhancers
        styles = [
            "masterpiece", "best quality", "ultra-detailed",
            "cinematic lighting", "depth of field",
            "professional photography", "8K resolution",
        ]

        quality_boosts = [
            "trending on ArtStation",
            "highly detailed",
            "sharp focus",
            "dramatic lighting",
        ]

        # Pick 2-3 random style elements
        import random
        selected_styles = random.sample(styles, min(3, len(styles)))
        selected_quality = random.sample(quality_boosts, min(2, len(quality_boosts)))

        enhanced = f"{base}, {', '.join(selected_styles)}, {', '.join(selected_quality)}"
        log.info(f"Enhanced prompt: {enhanced}")
        return enhanced

    async def generate_image_with_model(self, model: str, prompt: str, timeout: int = 120, new_chat: bool = True, project: str = "default") -> dict:
        async with self._lock:
            await self.ensure_started()
            page = await self._get_page_for_model(model, project)
            if new_chat:
                await self._start_new_chat(page)
                await asyncio.sleep(1)

            # Enhance prompt locally into high-quality English
            english_prompt = self._rewrite_image_prompt(prompt)

            # Send the draw command
            draw_prompt = f"Нарисуй: {english_prompt}"
            await self._send_message(page, draw_prompt)
            image_url = await self._wait_for_image(page, timeout)

            import httpx
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(image_url, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                img_bytes = resp.content

            if len(img_bytes) < 500:
                raise HTTPException(500, "Downloaded image is too small/corrupted")

            img_hash = hashlib.md5(img_bytes).hexdigest()
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            cache_path = IMAGE_CACHE / f"{img_hash}.jpg"
            media_path = MEDIA_DIR / f"gen_{timestamp}_{img_hash[:8]}.jpg"
            cache_path.write_bytes(img_bytes)
            media_path.write_bytes(img_bytes)
            log.info(f"Image saved: {media_path} ({len(img_bytes)} bytes)")

            return {
                "url": image_url,
                "local_path": str(media_path),
                "cache_path": str(cache_path),
                "b64_json": base64.b64encode(img_bytes).decode("ascii"),
                "revised_prompt": english_prompt,
                "size": len(img_bytes),
            }

    async def send_with_image(self, model: str, message: str, image_b64: str = None, image_path: str = None, timeout: int = 120, new_chat: bool = True, project: str = "default") -> str:
        async with self._lock:
            await self.ensure_started()

            if image_b64:
                img_bytes = base64.b64decode(image_b64)
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                tmp = MEDIA_DIR / f"upload_{timestamp}_{uuid.uuid4().hex[:8]}.jpg"
                tmp.write_bytes(img_bytes)
                image_path = str(tmp)
                log.info(f"Saved upload image: {tmp} ({len(img_bytes)} bytes)")

            page = await self._get_page_for_model(model, project)

            if new_chat:
                await self._start_new_chat(page)
                await asyncio.sleep(2)

            uploaded = False
            if image_path and Path(image_path).exists() and Path(image_path).stat().st_size > 500:
                abs_path = str(Path(image_path).resolve())
                log.info(f"Uploading: {abs_path} ({Path(image_path).stat().st_size} bytes)")

                # Method 1: "+" button + file chooser
                try:
                    plus_btns = page.locator('button:has-text("+"), [data-testid*="attach"], [aria-label*="Добавить"]')
                    count = await plus_btns.count()
                    for i in range(count):
                        btn = plus_btns.nth(i)
                        try:
                            async with page.expect_file_chooser(timeout=8000) as fc_info:
                                await btn.click()
                            file_chooser = await fc_info.value
                            await file_chooser.set_files(abs_path)
                            uploaded = True
                            log.info(f"Uploaded via button #{i}")
                            await asyncio.sleep(4)
                            break
                        except:
                            continue
                except Exception as e:
                    log.warning(f"file_chooser failed: {e}")

                # Method 2: hidden file input
                if not uploaded:
                    try:
                        file_input = page.locator('input[type="file"]').first
                        if await file_input.count() > 0:
                            await file_input.set_input_files(abs_path)
                            uploaded = True
                            log.info("Uploaded via hidden input[type=file]")
                            await asyncio.sleep(4)
                    except Exception as e:
                        log.warning(f"hidden input failed: {e}")

                # Method 3: drag and drop via JS
                if not uploaded:
                    try:
                        import base64 as b64
                        with open(abs_path, "rb") as f:
                            img_data = b64.b64encode(f.read()).decode()
                        mime = "image/jpeg" if abs_path.endswith(".jpg") or abs_path.endswith(".jpeg") else "image/png"
                        await page.evaluate(f"""
                            async () => {{
                                const blob = await (await fetch('data:{mime};base64,{img_data}')).blob();
                                const file = new File([blob], 'image.jpg', {{type: '{mime}'}});
                                const dt = new DataTransfer();
                                dt.items.add(file);
                                const input = document.querySelector('input[type="file"]') || document.querySelector('[contenteditable]');
                                if (input) {{
                                    input.files = dt.files;
                                    input.dispatchEvent(new Event('change', {{bubbles: true}}));
                                }}
                            }}
                        """)
                        uploaded = True
                        log.info("Uploaded via JS DataTransfer")
                        await asyncio.sleep(4)
                    except Exception as e:
                        log.warning(f"JS upload failed: {e}")

                if not uploaded:
                    log.error("All upload methods failed")

            # Wait for upload preview to appear
            await asyncio.sleep(2)

            await self._send_message(page, message)
            return await self._wait_for_response(page, timeout)

    async def _edit_via_button(self, page: object, edit_prompt: str, timeout: int = 120) -> str:
        """Click 'Изменить' button on last generated image and enter edit prompt.
        After editing, waits for a NEW image (edit result), not text."""
        # Collect existing image URLs before edit so we can detect the new one
        existing_images = await page.evaluate("""
            () => {
                const imgs = document.querySelectorAll('img[src*="yaart"], img[src*="s3.yandex"]');
                return Array.from(imgs).map(img => img.src);
            }
        """)
        log.info(f"Pre-edit images: {len(existing_images)}")

        edit_selectors = [
            'button[aria-label*="Изменить"]',
            'button:has-text("Изменить")',
            '[data-testid*="edit"]',
            '[class*="edit"]',
        ]

        for sel in edit_selectors:
            btn = page.locator(sel).last  # last = most recent
            if await btn.count() > 0:
                try:
                    await btn.click(timeout=5000)
                    await asyncio.sleep(2)
                    log.info(f"Clicked edit button: {sel}")

                    await asyncio.sleep(1)
                    inp = await self._get_input_field(page)
                    await inp.click()
                    await asyncio.sleep(0.3)
                    await page.keyboard.press("Control+a")
                    await asyncio.sleep(0.1)
                    await page.keyboard.press("Delete")
                    await asyncio.sleep(0.3)

                    draw_command = f"Измени: {edit_prompt}"
                    await page.keyboard.type(draw_command, delay=30)
                    await asyncio.sleep(0.5)
                    await page.keyboard.press("Enter")
                    log.info(f"Edit prompt sent: {draw_command[:80]}")

                    # Wait for a NEW image that wasn't there before the edit
                    new_image_url = await self._wait_for_new_image(page, existing_images, timeout)
                    return new_image_url
                except Exception as e:
                    log.warning(f"Edit button click failed: {e}")
                    continue

        raise HTTPException(500, "Could not find edit button on generated image")

    async def _wait_for_new_image(self, page: object, existing_urls: list, timeout: int = 120) -> str:
        """Wait for a new image to appear that isn't in existing_urls.
        Handles page navigation gracefully by catching context destruction."""
        existing_set = set(existing_urls)
        start = time.time()

        # Also listen for network responses
        new_s3_urls = []

        async def on_response(response):
            url = response.url
            if ("yaart" in url or "s3.yandex" in url) and any(e in url for e in [".jpg", ".png", ".webp"]):
                if url not in existing_set:
                    new_s3_urls.append(url)

        page.on("response", on_response)
        try:
            while time.time() - start < timeout:
                # Check network-intercepted URLs first
                if new_s3_urls:
                    url = new_s3_urls[-1]
                    log.info(f"New image via network: {url[:100]}")
                    await asyncio.sleep(3)
                    return url

                # Check DOM for new images (handle navigation/context loss)
                try:
                    current_imgs = await page.evaluate("""
                        () => {
                            const imgs = document.querySelectorAll('img[src*="yaart"], img[src*="s3.yandex"]');
                            return Array.from(imgs).map(img => img.src);
                        }
                    """)
                    for url in current_imgs:
                        if url not in existing_set:
                            log.info(f"New image in DOM: {url[:100]}")
                            await asyncio.sleep(3)
                            return url
                except Exception as e:
                    # Page navigation destroyed context — wait for page to stabilize
                    log.warning(f"Page context lost during edit: {str(e)[:80]}, waiting for reload...")
                    try:
                        await page.wait_for_load_state("domcontentloaded", timeout=15000)
                    except:
                        pass
                    await asyncio.sleep(5)
                    # Re-attach listener after navigation
                    try:
                        page.on("response", on_response)
                    except:
                        pass

                await asyncio.sleep(2)
        finally:
            try:
                page.remove_listener("response", on_response)
            except:
                pass

        raise HTTPException(504, "Edited image timeout — no new image appeared after edit")

    async def generate_and_edit(self, model: str, gen_prompt: str, edit_prompt: str, timeout: int = 120, new_chat: bool = True, project: str = "default") -> dict:
        """Generate image, then edit it via the UI edit button. Both prompts enhanced to English."""
        async with self._lock:
            await self.ensure_started()
            page = await self._get_page_for_model(model, project)
            if new_chat:
                await self._start_new_chat(page)
                await asyncio.sleep(1)

            # Enhance generation prompt
            english_gen = self._rewrite_image_prompt(gen_prompt)
            draw_prompt = f"Нарисуй: {english_gen}"
            await self._send_message(page, draw_prompt)
            image_url = await self._wait_for_image(page, timeout)

            # Enhance edit prompt
            english_edit = self._rewrite_image_prompt(edit_prompt)

            # Click edit button and enter prompt — returns new image URL
            edited_image_url = await self._edit_via_button(page, english_edit, timeout)

            # Download edited image to media/
            edited_local = await self._download_image_to_media(edited_image_url, "edited")

            return {
                "gen_prompt": english_gen,
                "edit_prompt": english_edit,
                "original_url": image_url,
                "edited_url": edited_image_url,
                "edited_local_path": edited_local,
            }

    async def _download_image_to_media(self, url: str, prefix: str = "img") -> str:
        """Download image from URL and save to media/ folder."""
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(url, headers={"User-Agent": "Mozilla/5.0"})
                resp.raise_for_status()
                img_bytes = resp.content
            if len(img_bytes) < 500:
                return ""
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            img_hash = hashlib.md5(img_bytes).hexdigest()[:8]
            media_path = MEDIA_DIR / f"{prefix}_{timestamp}_{img_hash}.jpg"
            media_path.write_bytes(img_bytes)
            log.info(f"Downloaded to media: {media_path} ({len(img_bytes)} bytes)")
            return str(media_path)
        except Exception as e:
            log.warning(f"Download to media failed: {e}")
            return ""

    async def take_screenshot(self) -> str:
        if not self.page or self.page.is_closed():
            return ""
        try:
            ss_path = PROJECT_DIR / "debug_screenshot.png"
            await self.page.screenshot(path=str(ss_path))
            return str(ss_path)
        except:
            return ""

    async def get_session_info(self) -> List[Dict]:
        return [{
            "session_id": s.session_id,
            "session_key": m,
            "project": s.project,
            "model": s.model,
            "message_count": s.message_count,
            "created_at": datetime.fromtimestamp(s.created_at).isoformat(),
            "last_active": datetime.fromtimestamp(s.last_active).isoformat(),
            "has_summary": bool(s.summary),
            "needs_rotation": s.needs_rotation(),
        } for m, s in self.sessions.items()]

    async def close(self):
        try:
            if self.browser:
                await self.browser.close()
        except:
            pass
        if self._chrome_proc:
            try:
                self._chrome_proc.terminate()
            except:
                pass
        if self.pw:
            await self.pw.stop()
        self._ready = False


alice_browser = AliceBrowser()
alice_rpc = AliceRPC()


@asynccontextmanager
async def lifespan(app):
    log.info("Alice Proxy v5.1 starting...")
    yield
    await alice_browser.close()
    log.info("Alice Proxy shutdown")

app = FastAPI(
    title="Alice Yandex Proxy",
    description="Multi-session OpenAI-compatible API for Yandex Alice",
    version="5.1.0",
    lifespan=lifespan,
)


class ChatMessage(BaseModel):
    role: str = "user"
    content: str | list = ""

class ChatRequest(BaseModel):
    model: str = "alice"
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 4096
    stream: bool = False
    project: str = "default"

class ChatChoice(BaseModel):
    index: int
    message: dict
    finish_reason: str = "stop"

class ChatUsage(BaseModel):
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0

class ChatResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatChoice]
    usage: ChatUsage

class ImageRequest(BaseModel):
    prompt: str
    n: int = 1
    size: str = "1024x1024"
    response_format: str = "url"
    model: str = "alice-image"

class ImageData(BaseModel):
    url: Optional[str] = None
    b64_json: Optional[str] = None
    revised_prompt: Optional[str] = None

class ImageResponse(BaseModel):
    created: int
    data: list[ImageData]


def extract_text_and_images(content) -> tuple:
    if isinstance(content, str):
        return content, []
    texts, images = [], []
    for block in content:
        if isinstance(block, dict):
            if block.get("type") == "text":
                texts.append(block.get("text", ""))
            elif block.get("type") == "image_url":
                url = block.get("image_url", {}).get("url", "")
                if url.startswith("data:"):
                    b64 = url.split(",", 1)[1] if "," in url else ""
                    if b64:
                        images.append(b64)
                elif url.startswith("http"):
                    try:
                        import httpx
                        resp = httpx.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                        if resp.status_code == 200:
                            images.append(base64.b64encode(resp.content).decode("ascii"))
                    except:
                        pass
    return " ".join(texts), images


async def stream_text(text: str, resp_id: str, model: str):
    for i in range(0, len(text), 10):
        chunk = text[i:i+10]
        yield f"data: {json.dumps({'id':resp_id,'object':'chat.completion.chunk','created':int(time.time()),'model':model,'choices':[{'index':0,'delta':{'content':chunk},'finish_reason':None}]})}\n\n"
        await asyncio.sleep(0.03)
    yield f"data: {json.dumps({'id':resp_id,'object':'chat.completion.chunk','created':int(time.time()),'model':model,'choices':[{'index':0,'delta':{},'finish_reason':'stop'}]})}\n\n"
    yield "data: [DONE]\n\n"


def detect_optimal_model(text: str, has_images: bool = False) -> str:
    text_lower = text.lower()
    if has_images:
        return "alice-vision"
    if any(kw in text_lower for kw in ["нарисуй", "draw", "сгенерир", "generate image", "create image"]):
        return "alice-image"
    if any(kw in text_lower for kw in ["найди", "поищи", "search", "исследуй", "актуальн", "новост"]):
        return "alice-search"
    if any(kw in text_lower for kw in ["код", "code", "функци", "class ", "def ", "import ", "программ", "script", "debug", "error", "баг"]):
        return "alice-code"
    if any(kw in text_lower for kw in ["подробн", "детальн", "развёрнут", "проанализируй", "сравн"]):
        return "alice-pro"
    return "alice"


@app.get("/health")
async def health():
    rpc = await alice_rpc.health_check()
    sessions = await alice_browser.get_session_info()
    return {
        "status": "ok",
        "browser_ready": alice_browser._ready,
        "rpc_authenticated": rpc.get("authenticated", False),
        "login": rpc.get("login", "?"),
        "active_sessions": len(sessions),
        "sessions": sessions,
    }


@app.get("/debug")
async def debug():
    info = {"browser_ready": alice_browser._ready, "sessions": await alice_browser.get_session_info()}
    if alice_browser.page and not alice_browser.page.is_closed():
        info["url"] = alice_browser.page.url
        try:
            info["body_preview"] = (await alice_browser.page.inner_text("body", timeout=3000))[:500]
        except:
            info["body_preview"] = "<error>"
        info["screenshot"] = await alice_browser.take_screenshot()
    return info


@app.get("/v1/models")
@app.post("/v1/models")
async def list_models():
    return {
        "object": "list",
        "data": [
            {"id": mid, "object": "model", "created": 1700000000, "owned_by": "yandex", "description": cfg["description"]}
            for mid, cfg in MODEL_CONFIGS.items()
        ],
    }


@app.get("/v1/sessions")
async def list_sessions():
    return {"sessions": await alice_browser.get_session_info()}


@app.post("/v1/sessions/{session_key}/rotate")
async def rotate_session(session_key: str):
    if session_key not in alice_browser.sessions:
        raise HTTPException(404, f"No session for {session_key}")
    session = alice_browser.sessions[session_key]
    await alice_browser._summarize_and_rotate(session.model, session.project)
    return {"status": "rotated", "new_session_id": session.session_id, "summary": session.summary}


@app.post("/v1/chat/completions")
async def chat_completions(req: ChatRequest):
    last_msg = None
    for msg in reversed(req.messages):
        if msg.role == "user":
            last_msg = msg
            break
    if not last_msg:
        raise HTTPException(400, "No user message found")

    text, images = extract_text_and_images(last_msg.content)
    resp_id = f"chatcmpl-{uuid.uuid4().hex[:12]}"

    is_image_gen = any(kw in text.lower() for kw in ["нарисуй", "draw", "сгенерир", "generate image", "create image", "draw a", "нарисовать"])
    is_vision = bool(images)

    # Determine target model
    if req.model in MODEL_CONFIGS:
        target_model = req.model
    elif is_image_gen and not is_vision:
        target_model = "alice-image"
    elif is_vision:
        target_model = "alice-vision"
    else:
        target_model = detect_optimal_model(text, is_vision)

    try:
        if is_image_gen and not is_vision:
            result = await alice_browser.generate_image_with_model("alice-image", text, project=req.project)
            response_text = f"![Generated image]({result['url']})"
            if req.stream:
                return StreamingResponse(stream_text(response_text, resp_id, req.model), media_type="text/event-stream")
            return ChatResponse(
                id=resp_id, created=int(time.time()), model=req.model,
                choices=[ChatChoice(index=0, message={"role": "assistant", "content": response_text}, finish_reason="stop")],
                usage=ChatUsage(prompt_tokens=len(text), completion_tokens=len(response_text)),
            )

        if is_vision:
            response_text = await alice_browser.send_with_image(
                target_model,
                text or "Что ты видишь на этом изображении?",
                image_b64=images[0] if images else None,
                project=req.project,
            )
            if req.stream:
                return StreamingResponse(stream_text(response_text, resp_id, req.model), media_type="text/event-stream")
            return ChatResponse(
                id=resp_id, created=int(time.time()), model=req.model,
                choices=[ChatChoice(index=0, message={"role": "assistant", "content": response_text}, finish_reason="stop")],
                usage=ChatUsage(prompt_tokens=len(text), completion_tokens=len(response_text)),
            )

        # Regular chat — just send the user's last message
        # Alice handles history natively in her chat session
        response_text = await alice_browser.chat_with_model(target_model, text, project=req.project)

        if req.stream:
            return StreamingResponse(stream_text(response_text, resp_id, req.model), media_type="text/event-stream")
        return ChatResponse(
            id=resp_id, created=int(time.time()), model=req.model,
            choices=[ChatChoice(index=0, message={"role": "assistant", "content": response_text}, finish_reason="stop")],
            usage=ChatUsage(prompt_tokens=len(text), completion_tokens=len(response_text)),
        )

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Chat failed: {e}")
        raise HTTPException(500, str(e))


@app.post("/v1/images/generations", response_model=ImageResponse)
async def generate_images(req: ImageRequest):
    project = req.project if hasattr(req, 'project') else "default"
    try:
        result = await alice_browser.generate_image_with_model(req.model, req.prompt, project=project)
        img_data = ImageData(revised_prompt=result["revised_prompt"])
        if req.response_format == "b64_json":
            img_data.b64_json = result["b64_json"]
        else:
            img_data.url = result["url"]
        return ImageResponse(created=int(time.time()), data=[img_data] * req.n)
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Image gen failed: {e}")
        raise HTTPException(500, str(e))


@app.post("/v1/images/edits")
async def edit_image(req: Request):
    body = await req.json()
    prompt = body.get("prompt", "")
    image_b64 = body.get("image", "")
    image_url = body.get("url", "")
    image_path = body.get("image_path", "")
    model = body.get("model", "alice-pro")
    method = body.get("method", "upload")  # "upload" or "button"
    project = body.get("project", "default")

    # Enhance edit prompt to English
    enhanced_prompt = alice_browser._rewrite_image_prompt(prompt) if prompt else prompt

    if not prompt:
        raise HTTPException(400, "prompt required")

    # Method 2: generate first, then edit via UI button
    if method == "button":
        gen_prompt = body.get("gen_prompt", "")
        if not gen_prompt:
            raise HTTPException(400, "gen_prompt required for button method")
        try:
            result = await alice_browser.generate_and_edit(model, gen_prompt, prompt, project=project)
            return {"edited_url": result["edited_url"], "original_url": result["original_url"], "gen_prompt": result["gen_prompt"], "edit_prompt": result["edit_prompt"]}
        except Exception as e:
            raise HTTPException(500, str(e))

    # Method 1: upload image + message (reliable)
    if image_url and not image_b64:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(image_url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    image_b64 = base64.b64encode(resp.content).decode("ascii")
                else:
                    raise HTTPException(400, f"Failed to download image: HTTP {resp.status_code}")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"Download failed: {e}")

    if not image_b64 and not image_path:
        raise HTTPException(400, "image (base64), url, or image_path required")

    try:
        edit_msg = f"Измени: {enhanced_prompt}"
        response = await alice_browser.send_with_image(
            model, edit_msg,
            image_b64=image_b64 if image_b64 else None,
            image_path=image_path if image_path and not image_b64 else None,
            project=project,
        )
        return {"response": response, "enhanced_prompt": enhanced_prompt}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/v1/vision/analyze")
async def vision_analyze(req: Request):
    body = await req.json()
    image_b64 = body.get("image", "")
    image_url = body.get("url", "")
    model = body.get("model", "alice-vision")
    project = body.get("project", "default")
    prompt = body.get("prompt", "Опиши это изображение подробно: что видишь, цвета, композиция, настроение, стиль и любые заметные элементы.")

    if image_url and not image_b64:
        import httpx
        try:
            async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                resp = await client.get(image_url, headers={"User-Agent": "Mozilla/5.0"})
                if resp.status_code == 200:
                    image_b64 = base64.b64encode(resp.content).decode("ascii")
                else:
                    raise HTTPException(400, f"Failed to download image: HTTP {resp.status_code}")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(400, f"Failed to download image: {e}")

    if not image_b64:
        raise HTTPException(400, "image (base64) or url required")

    try:
        response = await alice_browser.send_with_image(
            model,
            prompt,
            image_b64=image_b64,
            project=project,
        )
        return {"description": response}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/v1/media/generate")
async def media_generate(req: Request):
    """Unified media endpoint: generate, edit, and analyze images in ONE chat session.
    All operations share the same alice-media page for context continuity."""
    body = await req.json()
    action = body.get("action", "generate")  # generate, edit_button, edit_upload, vision
    prompt = body.get("prompt", "")
    project = body.get("project", "default")
    model = "alice-media"

    # Ensure project session exists and create page if new
    session_key = f"{project}:{model}"
    is_new_media_session = session_key not in alice_browser.sessions
    if is_new_media_session:
        alice_browser.sessions[session_key] = ChatSession(
            session_id=str(uuid.uuid4().hex[:8]),
            model=model,
            project=project,
        )
        # Create page and start new chat (no naming message — prefix goes into first action)
        async with alice_browser._lock:
            await alice_browser.ensure_started()
            page = await alice_browser._get_page_for_model(model, project)
            await alice_browser._start_new_chat(page)
            await asyncio.sleep(1)
            log.info(f"Media session created: {session_key}")

    # Prefix for first message (becomes chat name in sidebar)
    naming_prefix = f"[{project}:{model}] " if is_new_media_session else ""

    if action == "generate":
        if not prompt:
            raise HTTPException(400, "prompt required")
        try:
            # Prepend naming prefix so first message becomes chat name
            full_prompt = f"{naming_prefix}{prompt}" if naming_prefix else prompt
            result = await alice_browser.generate_image_with_model(model, full_prompt, new_chat=False, project=project)
            return {
                "action": "generate",
                "url": result["url"],
                "local_path": result["local_path"],
                "b64_json": result["b64_json"],
                "revised_prompt": result["revised_prompt"],
            }
        except Exception as e:
            raise HTTPException(500, str(e))

    elif action == "edit_button":
        edit_prompt = body.get("edit_prompt", prompt)
        if not edit_prompt:
            raise HTTPException(400, "edit_prompt required")
        try:
            # Use the existing page (no new chat) — edit the last generated image
            english_edit = alice_browser._rewrite_image_prompt(edit_prompt)
            async with alice_browser._lock:
                await alice_browser.ensure_started()
                page = await alice_browser._get_page_for_model(model, project)
                edited_url = await alice_browser._edit_via_button(page, english_edit)
                edited_local = await alice_browser._download_image_to_media(edited_url, "edited")
            return {
                "action": "edit_button",
                "edited_url": edited_url,
                "edited_local_path": edited_local,
                "edit_prompt": english_edit,
            }
        except Exception as e:
            raise HTTPException(500, str(e))

    elif action == "edit_upload":
        image_b64 = body.get("image", "")
        image_url = body.get("url", "")
        edit_prompt = body.get("edit_prompt", prompt)
        if not edit_prompt:
            raise HTTPException(400, "edit_prompt required")
        if not image_b64 and not image_url:
            raise HTTPException(400, "image (base64) or url required")

        if image_url and not image_b64:
            import httpx
            try:
                async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                    resp = await client.get(image_url, headers={"User-Agent": "Mozilla/5.0"})
                    if resp.status_code == 200:
                        image_b64 = base64.b64encode(resp.content).decode("ascii")
                    else:
                        raise HTTPException(400, f"Failed to download image: HTTP {resp.status_code}")
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(400, f"Download failed: {e}")

        enhanced = alice_browser._rewrite_image_prompt(edit_prompt)
        try:
            edit_msg = f"{naming_prefix}Измени: {enhanced}"
            response = await alice_browser.send_with_image(
                model, edit_msg, image_b64=image_b64, new_chat=False, project=project,
            )
            return {"action": "edit_upload", "response": response, "edit_prompt": enhanced}
        except Exception as e:
            raise HTTPException(500, str(e))

    elif action == "vision":
        image_b64 = body.get("image", "")
        image_url = body.get("url", "")
        vision_prompt = body.get("vision_prompt", prompt or "Опиши это изображение подробно.")
        # Ensure Russian prefix for vision
        if not vision_prompt.startswith(("Опиши", "Посмотри", "Что")):
            vision_prompt = f"Опиши: {vision_prompt}"

        if image_url and not image_b64:
            import httpx
            try:
                async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
                    resp = await client.get(image_url, headers={"User-Agent": "Mozilla/5.0"})
                    if resp.status_code == 200:
                        image_b64 = base64.b64encode(resp.content).decode("ascii")
                    else:
                        raise HTTPException(400, f"Failed to download image: HTTP {resp.status_code}")
            except HTTPException:
                raise
            except Exception as e:
                raise HTTPException(400, f"Download failed: {e}")

        if not image_b64:
            raise HTTPException(400, "image (base64) or url required")

        try:
            vision_prompt = f"{naming_prefix}{vision_prompt}" if naming_prefix else vision_prompt
            response = await alice_browser.send_with_image(
                model, vision_prompt, image_b64=image_b64, new_chat=False, project=project,
            )
            return {"action": "vision", "description": response}
        except Exception as e:
            raise HTTPException(500, str(e))

    else:
        raise HTTPException(400, f"Unknown action: {action}. Use: generate, edit_button, edit_upload, vision")


@app.get("/v1/media/list")
async def media_list():
    """List all files in the media/ folder."""
    files = []
    for f in sorted(MEDIA_DIR.glob("*")):
        if f.is_file():
            files.append({
                "name": f.name,
                "size": f.stat().st_size,
                "created": datetime.fromtimestamp(f.stat().st_ctime).isoformat(),
            })
    return {"media_dir": str(MEDIA_DIR), "count": len(files), "files": files}


@app.delete("/v1/media/{filename}")
async def media_delete(filename: str):
    """Delete a file from media/ folder."""
    target = MEDIA_DIR / filename
    if not target.exists() or not target.is_file():
        raise HTTPException(404, f"File not found: {filename}")
    # Prevent path traversal
    if ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(400, "Invalid filename")
    target.unlink()
    return {"status": "deleted", "file": filename}


PROJECTS_FILE = STATE_DIR / "projects.json"

def load_projects() -> dict:
    if PROJECTS_FILE.exists():
        try:
            return json.loads(PROJECTS_FILE.read_text(encoding="utf-8"))
        except:
            pass
    return {}

def save_projects(projects: dict):
    PROJECTS_FILE.write_text(json.dumps(projects, indent=2, ensure_ascii=False), encoding="utf-8")


@app.get("/v1/projects")
async def list_projects():
    """List all known projects and their sessions."""
    projects = load_projects()
    active_sessions = await alice_browser.get_session_info()
    # Group sessions by project
    for s in active_sessions:
        proj = s["project"]
        if proj not in projects:
            projects[proj] = {"created": datetime.now().isoformat(), "models": []}
        if s["model"] not in projects[proj]["models"]:
            projects[proj]["models"].append(s["model"])
    return {"projects": projects, "active_sessions": active_sessions}


@app.post("/v1/projects/{project}")
async def create_project(project: str, req: Request = None):
    """Register a new project. Body optional: {"description": "..."}"""
    projects = load_projects()
    desc = ""
    if req:
        try:
            body = await req.json()
            desc = body.get("description", "")
        except:
            pass
    projects[project] = {
        "created": datetime.now().isoformat(),
        "description": desc,
        "models": [],
    }
    save_projects(projects)
    return {"status": "created", "project": project}


@app.delete("/v1/projects/{project}")
async def delete_project(project: str):
    """Remove a project registration and close its sessions."""
    projects = load_projects()
    if project not in projects:
        raise HTTPException(404, f"Project not found: {project}")
    del projects[project]
    save_projects(projects)
    # Close all sessions for this project
    keys_to_remove = [k for k, s in alice_browser.sessions.items() if s.project == project]
    for k in keys_to_remove:
        page_key = k
        if page_key in alice_browser.session_pages:
            try:
                await alice_browser.session_pages[page_key].close()
            except:
                pass
            del alice_browser.session_pages[page_key]
        del alice_browser.sessions[k]
    return {"status": "deleted", "project": project, "sessions_closed": len(keys_to_remove)}


@app.post("/v1/projects/{project}/sessions")
async def create_project_session(project: str, req: Request):
    """Create sessions for a project. Body: {"models": ["alice", "alice-code", ...]}"""
    body = await req.json()
    models = body.get("models", ["alice"])
    projects = load_projects()
    if project not in projects:
        projects[project] = {"created": datetime.now().isoformat(), "description": "", "models": []}

    created = []
    for m in models:
        session_key = f"{project}:{m}"
        if session_key not in alice_browser.sessions:
            alice_browser.sessions[session_key] = ChatSession(
                session_id=str(uuid.uuid4().hex[:8]),
                model=m,
                project=project,
            )
            if m not in projects[project].get("models", []):
                projects[project].setdefault("models", []).append(m)
            created.append(session_key)

    save_projects(projects)
    return {"status": "ok", "created": created, "project": project}


@app.post("/cookies")
async def set_cookies(req: Request):
    body = await req.json()
    cookie_str = body.get("cookie", "")
    if not cookie_str:
        raise HTTPException(400, "cookie string required")
    alice_rpc.set_cookies(cookie_str)
    if alice_browser.context:
        cookies = []
        for part in cookie_str.split(";"):
            part = part.strip()
            if "=" in part:
                k, v = part.split("=", 1)
                cookies.append({"name": k.strip(), "value": v.strip(), "domain": ".yandex.ru", "path": "/"})
        if cookies:
            await alice_browser.context.add_cookies(cookies)
    return {"status": "ok", "cookies_set": len(alice_rpc.cookies)}


@app.get("/cookies/status")
async def cookie_status():
    return await alice_rpc.health_check()


@app.post("/v1/files/write")
async def write_file_endpoint(req: Request):
    body = await req.json()
    path = body.get("path", "")
    content = body.get("content", "")
    if not path:
        raise HTTPException(400, "path required")
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"status": "ok", "path": str(p), "size": len(content)}
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/v1/files/read")
async def read_file_endpoint(req: Request):
    body = await req.json()
    path = body.get("path", "")
    if not path:
        raise HTTPException(400, "path required")
    try:
        p = Path(path)
        if not p.exists():
            raise HTTPException(404, f"File not found: {path}")
        content = p.read_text(encoding="utf-8")
        return {"status": "ok", "path": str(p), "content": content, "size": len(content)}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/v1/files/list")
async def list_files_endpoint(req: Request):
    body = await req.json()
    path = body.get("path", ".")
    pattern = body.get("pattern", "*")
    try:
        p = Path(path)
        if not p.exists():
            raise HTTPException(404, f"Directory not found: {path}")
        files = [{"name": f.name, "size": f.stat().st_size if f.is_file() else 0, "is_dir": f.is_dir()}
                 for f in sorted(p.glob(pattern))[:100]]
        return {"status": "ok", "path": str(p), "files": files}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(500, str(e))


@app.post("/v1/execute")
async def execute_command(req: Request):
    import subprocess
    body = await req.json()
    command = body.get("command", "")
    timeout = body.get("timeout", 30)
    if not command:
        raise HTTPException(400, "command required")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=timeout)
        return {
            "status": "ok" if result.returncode == 0 else "error",
            "exit_code": result.returncode,
            "stdout": result.stdout[:5000],
            "stderr": result.stderr[:2000],
        }
    except subprocess.TimeoutExpired:
        raise HTTPException(408, "Command timeout")
    except Exception as e:
        raise HTTPException(500, str(e))


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", "8976"))
    uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
