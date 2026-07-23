"""
用真实 Edge 配置(登录态)打开 qclaw 配置页, 抓取表单结构 + 截图 + 全文。
运行前请完全关闭 Edge (所有窗口), 否则 profile 被锁无法启动。
"""
import asyncio
import json
import os

from playwright.async_api import async_playwright

USER_DATA = r"C:\Users\24392\AppData\Local\Microsoft\Edge\User Data"
URL = "https://open.qclaw.qq.com/agents/config"
OUT_DIR = r"D:\VS_CODE\agents\scraping_html_to_LLM\qclaw_probe"


async def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    async with async_playwright() as p:
        ctx = await p.chromium.launch_persistent_context(
            USER_DATA,
            channel="msedge",
            headless=True,
            args=["--disable-blink-features=AutomationControlled"],
        )
        page = ctx.pages[0] if ctx.pages else await ctx.new_page()
        print("GOTO", URL, flush=True)
        try:
            await page.goto(URL, wait_until="domcontentloaded", timeout=45000)
        except Exception as e:
            print("GOTO_FAIL", repr(e), flush=True)
        await page.wait_for_timeout(4000)
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except Exception as e:
            print("networkidle timeout (ok):", e, flush=True)

        cur = page.url
        title = await page.title()
        print("CUR_URL", cur)
        print("TITLE", title)

        # 整页截图
        shot = os.path.join(OUT_DIR, "config_page.png")
        try:
            await page.screenshot(path=shot, full_page=True)
            print("SHOT_SAVED", shot)
        except Exception as e:
            print("SHOT_FAIL", repr(e))

        # 保存整页 HTML
        html = await page.content()
        with open(os.path.join(OUT_DIR, "config_page.html"), "w", encoding="utf-8") as f:
            f.write(html)
        print("HTML_LEN", len(html))

        # 提取可见文本
        try:
            body_text = await page.inner_text("body")
        except Exception:
            body_text = ""
        with open(os.path.join(OUT_DIR, "config_page.txt"), "w", encoding="utf-8") as f:
            f.write(body_text)
        print("TEXT_LEN", len(body_text))

        # 提取表单控件结构 (label / input / textarea / select / button)
        fields = await page.evaluate(
            """() => {
                const pick = (el) => ({
                    tag: el.tagName.toLowerCase(),
                    type: el.getAttribute('type') || '',
                    name: el.getAttribute('name') || '',
                    id: el.id || '',
                    placeholder: el.getAttribute('placeholder') || '',
                    ariaLabel: el.getAttribute('aria-label') || '',
                    value: (el.value || '').slice(0, 120),
                    text: (el.innerText || el.textContent || '').trim().slice(0, 120),
                });
                const out = {inputs: [], textareas: [], selects: [], buttons: [], labels: [], headings: []};
                document.querySelectorAll('input').forEach(e => out.inputs.push(pick(e)));
                document.querySelectorAll('textarea').forEach(e => out.textareas.push(pick(e)));
                document.querySelectorAll('select').forEach(e => out.selects.push(pick(e)));
                document.querySelectorAll('button,[role=button]').forEach(e => out.buttons.push(pick(e)));
                document.querySelectorAll('label').forEach(e => out.labels.push((e.innerText||'').trim()));
                document.querySelectorAll('h1,h2,h3,h4').forEach(e => out.headings.push((e.innerText||'').trim()));
                return out;
            }"""
        )
        with open(os.path.join(OUT_DIR, "config_form.json"), "w", encoding="utf-8") as f:
            json.dump({"url": cur, "title": title, "fields": fields}, f, ensure_ascii=False, indent=2)

        print("=== HEADINGS ===")
        for h in fields["headings"]:
            if h:
                print(" H:", h)
        print("=== LABELS ===")
        for l in fields["labels"]:
            if l:
                print(" L:", l)
        print("=== INPUTS ===", len(fields["inputs"]))
        for i in fields["inputs"]:
            print("  IN:", i["type"], "| name=", i["name"], "| ph=", i["placeholder"], "| aria=", i["ariaLabel"])
        print("=== TEXTAREAS ===", len(fields["textareas"]))
        for t in fields["textareas"]:
            print("  TA: ph=", t["placeholder"], "| aria=", t["ariaLabel"], "| val=", t["value"][:60])
        print("=== BUTTONS ===")
        for b in fields["buttons"]:
            if b["text"]:
                print("  BTN:", b["text"])

        # 保持窗口开一会, 便于你肉眼确认
        await page.wait_for_timeout(3000)
        await ctx.close()
        print("DONE")


if __name__ == "__main__":
    asyncio.run(main())
