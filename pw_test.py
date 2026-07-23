"""最小 Playwright 测试"""
import sys
print("py ok", flush=True)
from playwright.sync_api import sync_playwright
print("import ok", flush=True)
with sync_playwright() as p:
    print("launching chromium...", flush=True)
    b = p.chromium.launch(headless=True)
    print("launched", flush=True)
    pg = b.new_page()
    print("new_page ok", flush=True)
    pg.goto("https://example.com", timeout=15000)
    print("goto ok, title=", pg.title(), flush=True)
    b.close()
    print("done", flush=True)
