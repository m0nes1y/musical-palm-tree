"""
crawl_runner.py — Web Scraper Pro 执行脚本
融合 Crawl4AI (整页渲染 + LLM 友好 Markdown) 与 Scrapling (CSS/XPath/正则精准提取)
所有函数完整可运行，可独立执行: python crawl_runner.py
"""
import asyncio
import re
import json
from datetime import datetime, timezone

# ---------- Crawl4AI（可选：无 chromium 时也能靠静态路径工作）----------
try:
    from crawl4ai import AsyncWebCrawler
    _HAS_CRAWL4AI = True
except Exception:
    AsyncWebCrawler = None
    _HAS_CRAWL4AI = False

# ---------- Scrapling ----------
from scrapling.parser import Selector as ScraplingSelector
try:
    from scrapling.fetchers import Fetcher as _ScraplingFetcher
except Exception:
    _ScraplingFetcher = None

# ---------- 辅助 ----------
from bs4 import BeautifulSoup


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _decode_bytes(raw: bytes) -> str:
    """中文站常见 GBK/GB2312/GB18030，UTF-8 直接解码会崩。按优先级探测编码。"""
    if not isinstance(raw, (bytes, bytearray)):
        return str(raw)
    raw = bytes(raw)
    # 1) 从 <meta charset> 里嗅探
    head = raw[:2048].lower()
    for token, enc in ((b"gb2312", "gb18030"), (b"gbk", "gb18030"),
                       (b"gb18030", "gb18030"), (b"big5", "big5"),
                       (b"utf-8", "utf-8"), (b"utf8", "utf-8")):
        if token in head:
            try:
                return raw.decode(enc)
            except Exception:
                pass
    # 2) 逐个兜底
    for enc in ("utf-8", "gb18030", "gbk", "big5", "latin-1"):
        try:
            return raw.decode(enc)
        except Exception:
            continue
    return raw.decode("utf-8", errors="replace")


def fetch_static(url: str, timeout: int = 25) -> dict:
    """
    Scrapling 静态抓取（curl_cffi，免浏览器），带编码自适应。
    返回 {success, url, html, status, error}。适合静态页 / 中文 GBK 站。
    """
    if _ScraplingFetcher is None:
        return {"success": False, "url": url, "html": "", "status": None,
                "error": "Scrapling Fetcher 不可用"}
    try:
        page = _ScraplingFetcher.get(url, timeout=timeout)
        status = getattr(page, "status", None)
        raw = None
        for attr in ("body", "_raw_body"):
            if hasattr(page, attr):
                v = getattr(page, attr)
                if isinstance(v, (bytes, bytearray)):
                    raw = bytes(v)
                    break
        if raw is not None:
            html = _decode_bytes(raw)
        else:
            # 没有原始字节就退回其 html_content（可能已是 str）
            html = getattr(page, "html_content", "") or ""
        return {"success": bool(html), "url": url, "html": html,
                "status": status, "error": "" if html else "空响应"}
    except Exception as e:
        return {"success": False, "url": url, "html": "", "status": None,
                "error": f"{type(e).__name__}: {e}"}


def html_to_markdown(html: str) -> str:
    """把 HTML 转成简洁 Markdown（正文文本）。用于静态路径的 LLM 可读输出。"""
    if not html:
        return ""
    try:
        from markdownify import markdownify as _md
        return _md(html, heading_style="ATX", strip=["script", "style"])
    except Exception:
        soup = BeautifulSoup(html, "lxml")
        for tag in soup(["script", "style"]):
            tag.decompose()
        return soup.get_text("\n", strip=True)


def _is_text_node(el) -> bool:
    """判断是否为属性/文本节点（xpath @attr、text()，css ::text 会命中）。"""
    if isinstance(el, str):
        return True
    tag = getattr(el, "tag", None)
    return tag in ("#text", None)


def _normalize_node(el):
    """
    归一化 Scrapling / lxml 节点：
    - 属性/文本节点 -> 返回纯字符串（如 //a/@href、title::text）
    - 普通元素     -> 返回 {tag, text, attrs, html} dict
    """
    if _is_text_node(el):
        if isinstance(el, str):
            return str(el).strip()
        # Scrapling 文本节点：优先 .text，退回 str()
        val = getattr(el, "text", None)
        return (str(val) if val is not None else str(el)).strip()
    return _element_to_dict(el)


def _element_to_dict(el):
    """把一个 Scrapling / lxml 元素归一化成 dict。兼容 xpath 返回的属性字符串。"""
    if isinstance(el, str):
        return {"value": el}
    try:
        text = el.text or ""
    except Exception:
        text = ""
    try:
        attrs = dict(el.attrib) if hasattr(el, "attrib") else {}
    except Exception:
        attrs = {}
    try:
        html = el.html or ""
    except Exception:
        html = ""
    return {"tag": getattr(el, "tag", ""), "text": text.strip(), "attrs": attrs, "html": html}


def _lxml_to_dict(el):
    from lxml import html as lxml_html
    return {
        "tag": el.tag,
        "text": (el.text_content() or "").strip(),
        "attrs": dict(el.attrib),
    }


# 1. 单页抓取
async def crawl_page(url: str) -> dict:
    """
    用 Crawl4AI 整页抓取，返回 LLM 友好 Markdown + 清洗后 HTML。
    针对重型 JS 站（MSN 等）做了全方位 stealth + 渲染等待配置。
    """
    try:
        async with AsyncWebCrawler() as crawler:
            result = await crawler.arun(
                url=url,

                # ---- stealth 反爬 ----
                magic=True,                         # 反爬绕过（stealth 浏览器指纹）
                simulate_user=True,                 # 模拟真人交互（鼠标移动/滚动）
                override_navigator=True,            # 覆盖 navigator.webdriver 等检测属性

                # ---- 弹窗 / Cookie 同意 ----
                remove_overlay_elements=True,       # 自动关弹窗/遮罩层
                remove_consent_popups=True,         # ✅ 专门处理 Cookie 同意弹窗（独立于 overlay）

                # ---- Shadow DOM / iframe ----
                flatten_shadow_dom=True,            # ✅ 扁平化 shadow DOM，让内容可提取
                process_iframes=True,               # 处理 iframe 内嵌内容

                # ---- JS 渲染等待 ----
                delay_before_return_html=10.0,      # 等 JS 完整渲染（重型站给足 10 秒）
                wait_for="article, main, p, h1, h2",# 等到正文标签出现才返回
                wait_for_timeout=15000,             # wait_for 最长等 15 秒
                page_timeout=60000,                 # 页面加载超时 60 秒

                # ---- 滚动触发懒加载 ----
                scan_full_page=True,                # 扫描整页（非仅首屏）
                scroll_delay=1.0,                   # 滚动间隔 1 秒，触发懒加载
                max_scroll_steps=10,                # 最多滚 10 步

                # ---- 避免误判空壳 ----
                ignore_body_visibility=True,        # 不因 body 初始隐藏就判空

                # ---- 请求头伪装 ----
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                user_agent_mode="random",           # 每次随机切换 UA

                # ---- JS 预处理（点 Cookie 同意 + 关弹窗） ----
                js_code=[
                    # 点所有包含"接受/同意/allow"的按钮（含 shadow DOM 穿透）
                    "document.querySelectorAll('button, a, [role=button]').forEach(b=>{"
                    "  const t=(b.textContent||b.innerText||'').toLowerCase();"
                    "  if(/accept|agree|同意|接受|allow|ok|yes|got it|continue/i.test(t))b.click();"
                    "})",
                    # 关闭常见的 newsletter / 订阅弹窗
                    "document.querySelectorAll('[aria-label=close], .close, .dismiss, [data-dismiss]').forEach(e=>e.click())",
                ],
                js_code_before_wait=[               # 在等待渲染之前先点一轮
                    "document.querySelectorAll('button, a, [role=button]').forEach(b=>{"
                    "  const t=(b.textContent||b.innerText||'').toLowerCase();"
                    "  if(/accept|agree|同意|接受|allow|ok|yes/i.test(t))b.click();"
                    "})",
                ],

                # ---- 其他 ----
                cache_mode="bypass",                # 不走缓存，拿最新内容
            )
        if result is None:
            return {"success": False, "url": url, "error": "Crawl4AI 返回空结果", "markdown": "", "html": ""}
        success = bool(getattr(result, "success", True))
        if not success:
            return {
                "success": False,
                "url": url,
                "error": getattr(result, "error_message", "抓取失败"),
                "markdown": "",
                "html": "",
            }
        md = getattr(result, "markdown", None)
        markdown = ""
        if md is not None:
            markdown = getattr(md, "raw", None) or getattr(md, "fit", None) or str(md)
        html = getattr(result, "cleaned_html", "") or getattr(result, "html", "")
        return {"success": True, "url": url, "markdown": markdown, "html": html, "error": ""}
    except Exception as e:
        return {"success": False, "url": url, "error": f"{type(e).__name__}: {e}", "markdown": "", "html": ""}


# 2. CSS 选择器提取
def extract_with_css(html: str, selector: str) -> list:
    if not html:
        return []
    try:
        page = ScraplingSelector(html)
        elements = page.css(selector)
        return [_normalize_node(el) for el in elements]
    except Exception:
        # 回退: lxml + cssselect
        from lxml import html as lxml_html
        from lxml.cssselect import CSSSelector
        tree = lxml_html.fromstring(html)
        return [_lxml_to_dict(e) for e in CSSSelector(selector)(tree)]


# 3. XPath 提取
def extract_with_xpath(html: str, xpath: str) -> list:
    if not html:
        return []
    try:
        page = ScraplingSelector(html)
        elements = page.xpath(xpath)
        return [_normalize_node(el) for el in elements]
    except Exception:
        from lxml import html as lxml_html
        tree = lxml_html.fromstring(html)
        out = tree.xpath(xpath)
        return [str(o).strip() if isinstance(o, str) else _lxml_to_dict(o) for o in out]


# 4. 正则提取
def extract_with_regex(text: str, pattern: str) -> list:
    if not text:
        return []
    try:
        return re.findall(pattern, text)
    except re.error as e:
        return [f"正则错误: {e}"]


# 5. 多页抓取
async def crawl_paginated(base_url: str, max_pages: int = 5) -> list:
    results = []
    for page in range(1, max_pages + 1):
        page_url = f"{base_url}?page={page}"
        r = await crawl_page(page_url)
        results.append(r)
        if page < max_pages:
            await asyncio.sleep(2)  # 尊重频率限制
    return results


# 6. 主入口（接收 URL + 自然语言描述，输出双格式）
async def main(url: str, user_description: str = "") -> dict:
    # 策略：有 Crawl4AI+chromium 优先用它（能渲染 JS）；失败/无浏览器则回退 Scrapling 静态抓取。
    html, markdown, engine, err = "", "", "", ""
    if _HAS_CRAWL4AI:
        crawl = await crawl_page(url)
        if crawl["success"] and crawl.get("html"):
            html, markdown, engine = crawl["html"], crawl["markdown"], "crawl4ai"
        else:
            err = crawl.get("error", "")
    if not html:
        # 静态兜底（免 chromium，带编码自适应）
        st = fetch_static(url)
        if st["success"]:
            html = st["html"]
            markdown = html_to_markdown(html)
            engine = "scrapling-static"
        else:
            return {
                "markdown": "",
                "json": {
                    "source": url,
                    "user_description": user_description,
                    "extracted_at": _now_iso(),
                    "success": False,
                    "engine": "failed",
                    "error": err or st["error"],
                    "data": [],
                },
            }

    # 通用提取: 所有带文字的链接（足以覆盖 HN 等“标题+链接”场景）
    links = extract_with_css(html, "a")
    items = []
    for l in links:
        href = l.get("attrs", {}).get("href", "")
        text = l.get("text", "")
        if text and href:
            items.append({"title": text, "url": href})

    # 去重
    seen, uniq = set(), []
    for it in items:
        key = (it["title"], it["url"])
        if key not in seen:
            seen.add(key)
            uniq.append(it)

    json_out = {
        "source": url,
        "user_description": user_description,
        "extracted_at": _now_iso(),
        "success": True,
        "engine": engine,
        "total_items": len(uniq),
        "data": uniq[:50],
    }
    return {"markdown": markdown, "json": json_out}


if __name__ == "__main__":
    test_url = "https://news.ycombinator.com/"
    desc = "抓取所有帖子的标题、链接和分数"
    res = asyncio.run(main(test_url, desc))
    print("===== MARKDOWN (前 2000 字) =====")
    print((res["markdown"] or "")[:2000])
    print("\n===== JSON (前 3000 字) =====")
    print(json.dumps(res["json"], ensure_ascii=False, indent=2)[:3000])
