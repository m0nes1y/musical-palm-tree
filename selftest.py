"""
selftest.py — 静态自检（不依赖浏览器 / 网络）
验证 crawl_runner.py 的提取逻辑（Scrapling CSS/XPath + 正则）是否正确。
依赖安装完成后运行:
    python selftest.py
"""
import json
from crawl_runner import (
    extract_with_css,
    extract_with_xpath,
    extract_with_regex,
)

SAMPLE = """
<html><body>
  <a class="story" href="https://news.ycombinator.com/item?id=1">First post title</a>
  <a class="story" href="https://news.ycombinator.com/item?id=2">Second post title</a>
  <span class="score">123 points</span>
  <span class="score">45 points</span>
  <p>Published on 2026-07-21 and updated 2026-07-22.</p>
</body></html>
"""


def run_static():
    print("== CSS 提取 a.story 标签 ==")
    links = extract_with_css(SAMPLE, "a.story")
    for l in links:
        print(l)

    print("\n== XPath 提取 @href ==")
    hrefs = extract_with_xpath(SAMPLE, "//a[@class='story']/@href")
    print(hrefs)

    print("\n== 正则提取日期 (YYYY-MM-DD) ==")
    dates = extract_with_regex(SAMPLE, r"\d{4}-\d{2}-\d{2}")
    print(dates)

    print("\n== 组合：标题 + 链接 ==")
    items = [{"title": l["text"], "url": l["attrs"].get("href")} for l in links]
    print(json.dumps(items, ensure_ascii=False, indent=2))

    # 简单断言，确保核心路径可用
    assert len(links) == 2, "CSS 提取数量不对"
    assert all(isinstance(h, str) and h.startswith("https") for h in hrefs), "XPath href 异常"
    assert len(dates) == 2, "日期正则数量不对"
    print("\n✅ 静态自检通过")


if __name__ == "__main__":
    run_static()
