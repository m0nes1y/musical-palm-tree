# Web Scraper Pro（精准爬虫师）

## 一、Agent 简介

Web Scraper Pro 是一个自然语言驱动的网页抓取专家。它融合 **Crawl4AI**（整页渲染、JS 执行、LLM 友好的 Markdown 输出、内置去重）与 **Scrapling**（CSS / XPath / 正则精准提取、自适应定位），让使用者只需用一句话描述“想要什么数据”，Agent 便自动完成页面探索、选择器构建、内容抓取，并返回 **Markdown（可读）+ JSON（可程序化处理）** 双格式结果。

## 二、核心功能特点

1. **自然语言驱动**：输入 URL + 一句需求即可，无需手写选择器。
2. **LLM 友好输出**：Crawl4AI 产出干净的 Markdown，可直接喂给大模型或做 RAG。
3. **精准提取**：Scrapling 支持 CSS / XPath / 正则三种提取方式，复杂结构也能拿到字段。
4. **单页 / 多页通吃**：支持翻页、列表 → 详情页等多页场景，自动限速。
5. **双格式交付**：同一份抓取同时给 Markdown 表格与 JSON，人和程序都好用。

## 三、触发词示例

- “帮我抓取这个页面所有文章标题”
- “抓取某电商网站的商品名称和价格”
- “提取这个页面所有图片的 src”
- “爬取这个论坛的所有帖子标题和作者”
- “抓取某新闻网站最近一周的头条新闻”

## 四、使用示例（真实场景）

**场景 1：抓取新闻首页标题与链接**
> 用户：抓取 https://news.ycombinator.com/ 所有帖子的标题和链接
> Agent：Crawl4AI 整页抓取 → Scrapling 提取 `<a>` 标题/链接 → 返回 Markdown 表格 + JSON

**场景 2：电商商品采集**
> 用户：抓取 https://example.com/products 前 3 页的商品名和价格
> Agent：crawl_paginated 翻 3 页（间隔 2s）→ 对每页用 `.product .name` / `.product .price` 提取 → 汇总 JSON

**场景 3：正则抽取日期**
> 用户：从这个页面提取所有发布日期（YYYY-MM-DD）
> Agent：extract_with_regex(html, r'\d{4}-\d{2}-\d{2}') → 返回日期列表 JSON

## 五、技术架构图（文字版）

```
用户自然语言 + URL
        │
        ▼
┌──────────────────────────┐
│  Skill: crawl (CRAWL.md) │  解析需求 / 选选择器 / 限速
└──────────────────────────┘
        │
        ▼
┌──────────────────────────┐
│  Crawl4AI (AsyncWeb-     │  整页抓取 + JS 渲染
│  Crawler)                 │  → LLM 友好 Markdown
└──────────────────────────┘
        │  html
        ▼
┌──────────────────────────┐
│  Scrapling (Selector)    │  CSS / XPath / 正则精准提取
└──────────────────────────┘
        │
        ▼
┌──────────────────────────┐
│  crawl_runner.main()     │  组装双格式输出
│  → Markdown + JSON       │
└──────────────────────────┘
```

## 六、安装依赖列表

```
crawl4ai          # 整页抓取与 Markdown 输出
scrapling[all]    # 精准提取 + 自适应/反爬后端
beautifulsoup4    # 辅助 HTML 解析
lxml              # 高速解析 / CSS 选择器回退
httpx             # HTTP 请求
playwright        # 浏览器渲染引擎（Crawl4AI 依赖）
playwright install chromium   # 安装 Chromium 浏览器
```

或使用自带脚本：`python crawl_runner.py` 前确保已安装上述依赖。

## 七、常见问题 FAQ

**Q1：运行时提示缺少浏览器？**
A：执行 `playwright install chromium` 安装 Chromium。

**Q2：遇到 Cloudflare / 验证码怎么办？**
A：Agent 会明确告知无法自动抓取。可改用 Scrapling 的 StealthyFetcher 后端（需自建抓取服务）或手动提供 Cookie。

**Q3：抓取结果是空？**
A：通常是选择器不匹配。请用更多内容特征描述目标，Agent 会调整选择器。

**Q4：如何提高抓取稳定性？**
A：对反爬/JS 重度站点，建议自托管抓取服务（Crawl4AI Docker + Scrapling），由 Skill 通过 API 调用，避免平台沙箱限制。

**Q5：会高频请求目标站吗？**
A：不会。同一域名间隔 ≥ 2 秒，单次最多 50 页，仅抓取公开内容。
