r"""Playwright E2E test: verify URL exposure fix in RAG streaming responses.

Run with:
    cd d:\GR\src\RAG_v2
    .venv\Scripts\python.exe tests/e2e_test_url_exposure.py
"""

import os
os.environ["PYTHONUTF8"] = "1"

import re
import asyncio
import sys
from playwright.async_api import async_playwright


FRONTEND_URL = "http://localhost:8080"
TEST_QUERY = "biểu mẫu học tập"
# Raw URL pattern — should NOT be visible in chat bubble text
RAW_URL_PATTERN = re.compile(r"https?://\S+")
# Markdown link rendered as plain text (broken rendering)
BROKEN_MARKDOWN_LINK = re.compile(r"\]\(https?://")
TIMEOUT_MS = 120_000  # 2 minutes for full response


async def main() -> None:
    import time
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        # 1. Create a test user via API
        print("[1.1] Creating test user via API ...")
        api_context = await p.request.new_context()
        username = "test_user_" + str(int(time.time()))
        resp = await api_context.post("http://localhost:8000/auth/register", data={
            "username": username,
            "password": "password123",
            "full_name": "E2E Test User",
            "major": "Khoa học máy tính",
            "major_code": "IT1",
            "cohort": "K67"
        })
        print(f"[1.1] ✅ API Registration status: {resp.status}")

        page = await browser.new_page()
        page.on("console", lambda msg: print(f"Browser Console [{msg.type}]: {msg.text}"))
        page.on("pageerror", lambda err: print(f"Browser Error: {err}"))

        # 2. Login via UI
        print(f"[1.2] Logging in at {FRONTEND_URL}/login ...")
        await page.goto(FRONTEND_URL + "/login", wait_until="load")
        await page.fill('input[id="username"]', username)
        await page.fill('input[id="password"]', "password123")
        await page.click('button[type="submit"]')
        
        try:
            await page.wait_for_url("**/chat**", timeout=10000)
            print("[1.2] ✅ Logged in and redirected to Chat")
        except Exception:
            print("⚠️ Timeout waiting for /chat redirect. Checking if we are on page...")
            await page.screenshot(path="d:/GR/src/RAG_v2/tests/login_failed.png")

        # Find the chat input and send a test query
        print(f"[2] Sending query: '{TEST_QUERY}' ...")
        # Try common selectors for the chat input
        input_sel = 'textarea[aria-label="Nhập câu hỏi"]'
        chat_input = page.locator(input_sel).first
        await chat_input.fill(TEST_QUERY)
        await chat_input.press("Enter")
        print("[2] ✅ Query sent")

        # Wait for the bot response to start streaming
        print("[3] Waiting for bot response ...")
        # Wait for a message bubble from assistant (not user)
        # The response should contain text about biểu mẫu
        bot_message = page.locator('.bg-chat-assistant .prose').last
        await bot_message.wait_for(state="visible", timeout=TIMEOUT_MS)

        # Wait for streaming to complete — look for the response to stabilize
        # We wait until no new text is added for 3 seconds
        prev_text = ""
        stable_count = 0
        for _ in range(180):  # max 180 iterations = ~180 seconds
            await asyncio.sleep(1)
            current_text = await bot_message.text_content() or ""
            if current_text == prev_text and len(current_text) > 10:
                stable_count += 1
                if stable_count >= 3:
                    break
            else:
                stable_count = 0
            prev_text = current_text

        response_text = await bot_message.text_content() or ""
        print(f"[3] ✅ Got response ({len(response_text)} chars)")
        print(f"[3] Response preview: {response_text[:200]}...")

        # ── ASSERTIONS ──────────────────────────────────────────────────
        errors: list[str] = []

        # Check 1: No raw URLs visible in the response text
        # We check the VISIBLE text content, not the HTML
        raw_urls = RAW_URL_PATTERN.findall(response_text)
        if raw_urls:
            errors.append(
                f"❌ FAIL: Found {len(raw_urls)} raw URL(s) in response text:\n"
                + "\n".join(f"  - {u}" for u in raw_urls[:5])
            )
        else:
            print("[4] ✅ No raw URLs in response text")

        # Check 2: No broken markdown link syntax visible
        broken = BROKEN_MARKDOWN_LINK.findall(response_text)
        if broken:
            errors.append(
                f"❌ FAIL: Found broken markdown link syntax in response text:\n"
                + "\n".join(f"  - {b}" for b in broken[:5])
            )
        else:
            print("[5] ✅ No broken markdown link syntax")

        # Check 3: Response should contain clickable links (rendered as <a> tags)
        links = await bot_message.locator("a[href]").all()
        link_count = len(links)
        if link_count > 0:
            print(f"[6] ✅ Found {link_count} clickable link(s) in response")
            for link in links[:5]:
                href = await link.get_attribute("href") or ""
                text = await link.text_content() or ""
                print(f"     → [{text}]({href[:60]}...)")
        else:
            print("[6] ⚠️  No clickable links found (may be OK if query doesn't match docs with URLs)")

        # Check 4: If links exist, anchor text should be short (not full document names)
        for link in links[:5]:
            text = (await link.text_content() or "").strip()
            if len(text.split()) > 6:
                errors.append(
                    f"⚠️  WARN: Link anchor text is verbose ({len(text.split())} words): '{text[:50]}...'"
                )

        # Take screenshot for reference
        screenshot_path = "d:/GR/src/RAG_v2/tests/e2e_url_exposure_result.png"
        await page.screenshot(path=screenshot_path, full_page=True)
        print(f"[7] 📸 Screenshot saved: {screenshot_path}")

        await browser.close()

        # ── REPORT ──────────────────────────────────────────────────────
        if errors:
            print("\n" + "=" * 60)
            print("TEST FAILURES:")
            for e in errors:
                print(e)
            print("=" * 60)
            sys.exit(1)
        else:
            print("\n" + "=" * 60)
            print("✅ ALL CHECKS PASSED — No URL exposure in response")
            print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
