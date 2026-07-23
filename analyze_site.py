"""
网站全面分析器 —— 基于抓取 Agent 的 Playwright 渲染 + BeautifulSoup 解析
用法: python analyze_site.py <URL>
"""
import sys, re, json, asyncio
from urllib.parse import urljoin, urlparse
from collections import Counter

sys.path.insert(0, r"C:\Users\24392\.qclaw\workspace-cp1rw4l6s9c7a0e3h")
from crawl_runner import fetch_with_playwright

try:
    from bs4 import BeautifulSoup
    _HAS_BS4 = True
except Exception:
    _HAS_BS4 = False


def analyze(url: str) -> dict:
    r = asyncio.run(fetch_with_playwright(url))
    if not r["success"]:
        return {"success": False, "error": r.get("error")}
    html = r["html"]
    soup = BeautifulSoup(html, "lxml") if _HAS_BS4 else None

    base = {
        "url": url,
        "html_len": len(html),
        "engine": r.get("engine"),
    }

    # 1) 标题 / meta
    title = soup.title.get_text(strip=True) if (soup and soup.title) else ""
    metas = {}
    if soup:
        for m in soup.find_all("meta"):
            k = m.get("name") or m.get("property") or m.get("http-equiv")
            v = m.get("content")
            if k and v:
                metas[k] = v
    base["title"] = title
    base["meta"] = metas
    base["lang"] = soup.get("lang") if soup else ""
    base["charset"] = (soup.meta.get("charset") if (soup and soup.meta and soup.meta.get("charset")) else "")

    # 2) 干净可见文本
    if soup:
        for tag in soup(["script", "style", "noscript"]):
            tag.decompose()
        text = soup.get_text("\n")
        lines = [l.strip() for l in text.splitlines() if l.strip()]
        clean_text = "\n".join(lines)
    else:
        clean_text = ""
    base["visible_text_len"] = len(clean_text)
    base["visible_text_sample"] = clean_text[:1500]

    # 3) 链接分析
    links = []
    domains = Counter()
    if soup:
        for a in soup.find_all("a", href=True):
            href = a["href"].strip()
            full = urljoin(url, href)
            parsed = urlparse(full)
            domains[parsed.netloc] += 1
            links.append({
                "text": a.get_text(strip=True)[:60],
                "href": full if href.startswith(("http", "/")) else href,
                "internal": parsed.netloc in ("", urlparse(url).netloc),
            })
    internal = [l for l in links if l["internal"]]
    external = [l for l in links if not l["internal"]]
    base["links_total"] = len(links)
    base["links_internal"] = len(internal)
    base["links_external"] = len(external)
    base["external_domains"] = dict(domains.most_common(15))
    base["links_sample"] = links[:25]

    # 4) 表单（登录/注册字段）
    forms = []
    if soup:
        for f in soup.find_all("form"):
            fields = []
            for inp in f.find_all(["input", "textarea", "select"]):
                t = inp.get("type", "text")
                name = inp.get("name") or inp.get("id") or ""
                ph = inp.get("placeholder") or ""
                fields.append({"type": t, "name": name, "placeholder": ph})
            forms.append({"action": f.get("action", ""), "method": f.get("method", "get"), "fields": fields})
    base["forms"] = forms

    # 5) 技术栈线索
    tech = {"scripts": [], "stylesheets": [], "images": 0}
    if soup:
        for s in soup.find_all("script", src=True):
            tech["scripts"].append(s["src"])
        for l in soup.find_all("link", rel="stylesheet"):
            if l.get("href"):
                tech["stylesheets"].append(l["href"])
        tech["images"] = len(soup.find_all("img"))
    base["tech"] = tech

    # 6) 标题层级
    headings = []
    if soup:
        for h in soup.find_all(["h1", "h2", "h3"]):
            t = h.get_text(strip=True)
            if t:
                headings.append(f"{h.name}: {t[:80]}")
    base["headings"] = headings[:20]

    return {"success": True, **base}


if __name__ == "__main__":
    target = sys.argv[1] if len(sys.argv) > 1 else "https://h5.haozhuma.com/index.php"
    res = analyze(target)
    print(json.dumps(res, ensure_ascii=False, indent=2))
