---
name: crawl
description: 网页抓取与精准提取。融合 Crawl4AI（整页渲染+LLM友好输出）和 Scrapling（CSS/XPath/正则精准提取），支持单页/多页/列表→详情抓取，返回 Markdown+JSON 双格式。
color: green
---

# 网页抓取与精准提取技能

## 何时启用
用户发送 URL + 自然语言描述想要什么数据时激活。

## 技术栈
- **Crawl4AI**：整页抓取，JS 渲染，LLM 友好 Markdown 输出，内置去重
- **Scrapling**：CSS / XPath / 正则精准提取，支持模糊匹配与自适应定位
- **BeautifulSoup4 + lxml**：辅助 HTML 解析
- **httpx**：HTTP 请求

## 执行流程

### Step 1：确认需求
- URL 是什么
- 目标数据是什么（自然语言描述）
- 是否需要多页抓取

### Step 2：Crawl4AI 整页抓取
真实可用代码（`crawl_runner.py` 中的 `crawl_page`）：

```python
import asyncio
from crawl4ai import AsyncWebCrawler

async def crawl_page(url: str) -> dict:
    async with AsyncWebCrawler() as crawler:
        result = await crawler.arun(url=url)
    markdown = getattr(result.markdown, "raw", None) or getattr(result.markdown, "fit", None) or str(result.markdown)
    html = getattr(result, "cleaned_html", "") or getattr(result, "html", "")
    return {"success": bool(result.success), "url": url, "markdown": markdown, "html": html}
```

### Step 3：分析页面结构
分析 Markdown，确认：
- 目标数据区域和对应 HTML 标签
- 构造 Scrapling 选择器

### Step 4：Scrapling 精准提取
真实可用代码（Scrapling 的 `Selector` API，见 `crawl_runner.py`）：

```python
from scrapling.parser import Selector

page = Selector(html)
page.css("a.story")            # 选中元素 → 每项是 dict
page.css("title::text")        # 取文本  → 每项是 str
page.xpath("//a/@href")        # 取属性  → 每项是 str
```

**返回值约定（重要，避免踩坑）**：
- 选中**元素**（如 `a`、`div.item`）→ 每项为 `{"tag","text","attrs","html"}` dict
- 选中**属性 / 文本**（如 `//a/@href`、`h2::text`、`text()`）→ 每项为**纯字符串**

所以取链接可以两种写法：
```python
# 写法 A：选元素后取 attrs
[l["attrs"]["href"] for l in extract_with_css(html, "a")]
# 写法 B：直接选属性，拿到字符串列表
extract_with_xpath(html, "//a/@href")     # -> ["https://...", ...]
```

常用选择器：
- CSS：`article h2 a`、`.product-list .item .price`、`title::text`
- XPath：`//div[@class='content']//a/@href`
- 正则：`r'\d{4}-\d{2}-\d{2}'`（日期），可用 `page.re(pattern)` 或 Python `re`

### Step 4.5：中文站编码 & 免浏览器静态兜底（实战补丁）
两个实测踩过的坑，已固化进 `crawl_runner.py`：
- **中文老站编码**：不少站是 GBK/GB2312/GB18030，默认 UTF-8 解码会 `UnicodeDecodeError`。
  用 `fetch_static(url)`（内部 `_decode_bytes` 自动嗅探 `<meta charset>` + 逐个兜底），中文不乱码。
- **免 chromium 静态路径**：`main()` 策略为 **Crawl4AI 优先 → 静态抓取兜底**。
  纯静态页 / chromium 不可用时，走 `fetch_static + html_to_markdown`，无需浏览器即可产出 Markdown+JSON。
  仅当页面需要 JS 渲染时才必须走 Crawl4AI（chromium）。

### Step 5：多页抓取
```python
async def crawl_paginated(base_url: str, max_pages: int = 5):
    urls = []
    for page in range(1, max_pages + 1):
        page_url = f"{base_url}?page={page}"
        urls.append(page_url)
        await asyncio.sleep(2)   # 尊重频率限制
    return urls
```

### Step 6：双格式输出
Markdown（可读）：
```markdown
## 抓取结果
| 标题 | 价格 | 链接 |
```
JSON（程序处理）：
```json
{
  "source": "https://...",
  "extracted_at": "ISO时间戳",
  "total_items": 10,
  "data": [ ... ]
}
```

## 错误处理

| 错误类型 | 返回 |
| --- | --- |
| URL 无效 / 无法访问 | “⚠️ 无法访问该 URL，请确认地址正确且网站可公开访问。” |
| JS 渲染失败 | “⚠️ 需要 JavaScript 渲染但失败。建议确认网站可访问，或尝试提供 Cookie/Header。” |
| 反爬拦截 | “⚠️ 检测到反爬机制（Cloudflare/验证码），无法自动抓取。” |
| 选择器失败 | “⚠️ 内容匹配失败，请描述更多内容特征，我来调整选择器。” |
| 超时 | “⚠️ 请求超时（30s），目标网站响应过慢。” |

## 安全伦理规则
- 同一域名请求间隔 ≥ 2 秒
- 单次最多 50 页
- 不抓取私有 / 付费 / 登录内容
- 不绕过验证码
