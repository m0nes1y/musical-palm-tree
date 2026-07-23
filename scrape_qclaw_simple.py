"""用 Playwright 自带 chromium (headless) 打开 qclaw 配置页，看是否需要登录。"""
import asyncio
import os
from playwright.async_api import async_playwright

URL = "https://open.qclaw.qq.com/agents/config"
OUT_DIR = r"D:\VS_CODE\agents\scraping_html_to_LLM\qclaw_probe"


async def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
        )
        page = await ctx.new_page()
        print("GOTO", URL, flush=True)
        try:
            resp = await page.goto(URL, wait_until="domcontentloaded", timeout=30000)
            print("STATUS", resp.status if resp else "?", flush=True)
        except Exception as e:
            print("GOTO_FAIL", repr(e), flush=True)
        await page.wait_for_timeout(4000)

        cur = page.url
        title = await page.title()
        print("CUR_URL", cur, flush=True)
        print("TITLE", title, flush=True)

        shot = os.path.join(OUT_DIR, "config_page.png")
        await page.screenshot(path=shot, full_page=True)
        print("SHOT_SAVED", shot, flush=True)

        html = await page.content()
        with open(os.path.join(OUT_DIR, "config_page.html"), "w", encoding="utf-8") as f:
            f.write(html)
        print("HTML_LEN", len(html), flush=True)

        try:
            body_text = await page.inner_text("body")
        except Exception:
            body_text = ""
        with open(os.path.join(OUT_DIR, "config_page.txt"), "w", encoding="utf-8") as f:
            f.write(body_text)
        print("TEXT_LEN", len(body_text), flush=True)
        print("TEXT_PREVIEW", body_text[:500], flush=True)

        await browser.close()
        print("DONE", flush=True)


if __name__ == "__main__":
    asyncio.run(main())
