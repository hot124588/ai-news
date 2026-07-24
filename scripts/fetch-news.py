#!/usr/bin/env python3
"""
AI News Daily — 每日AI新闻抓取 & HTML生成脚本
零成本方案：使用免费公开API，无需任何API Key
运行环境：GitHub Actions (Ubuntu)
"""

import json
import os
import re
import urllib.request
import urllib.error
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from html import escape

OUTPUT_DIR = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "docs")
os.makedirs(OUTPUT_DIR, exist_ok=True)

# 中国时区
CST = timezone(timedelta(hours=8))
TODAY = datetime.now(CST).strftime("%Y-%m-%d")
TODAY_DISPLAY = datetime.now(CST).strftime("%Y年%m月%d日")

# AI相关关键词（中英文）
AI_KEYWORDS = [
    "ai", "artificial intelligence", "machine learning", "deep learning",
    "llm", "large language model", "gpt", "openai", "claude", "anthropic",
    "gemini", "google ai", "meta ai", "mistral", "deepseek", "通义",
    "千问", "大模型", "人工智能", "智能体", "agent", "rag",
    "stable diffusion", "sora", "video generation", "多模态",
    "neural network", "transformer", "fine-tuning", "量化",
    "langchain", "llamaindex", "hugging face", "pytorch",
    "tensorflow", "ai芯片", "gpu", "nvidia", "算力",
    "open source ai", "开源模型", "embeddings", "vector database",
    "ai coding", "cursor", "copilot", "codex",
]


def fetch_json(url, timeout=15):
    """获取JSON数据"""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; AINewsBot/1.0)"
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = resp.read().decode("utf-8", errors="replace")
            return json.loads(data)
    except Exception as e:
        print(f"[WARN] 请求失败: {url} -> {e}")
        return None


def fetch_text(url, timeout=15):
    """获取文本数据"""
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (compatible; AINewsBot/1.0)"
    })
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"[WARN] 请求失败: {url} -> {e}")
        return None


def is_ai_related(title, text=""):
    """判断是否跟AI相关"""
    combined = (title + " " + text).lower()
    for kw in AI_KEYWORDS:
        if kw.lower() in combined:
            return True
    return False


# ============================================================
# 数据源 1: HackerNews — 获取Top新闻，筛选AI相关
# ============================================================
def fetch_hackernews_ai(max_items=20):
    """从HackerNews获取AI相关新闻"""
    items = []
    try:
        top_ids = fetch_json("https://hacker-news.firebaseio.com/v0/topstories.json")
        if not top_ids:
            return items
        for item_id in top_ids[:60]:
            item = fetch_json(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json")
            if item and item.get("title") and is_ai_related(item.get("title", ""), item.get("text", "")):
                items.append({
                    "title": item["title"][:120],
                    "url": item.get("url", f"https://news.ycombinator.com/item?id={item_id}"),
                    "source": "HackerNews",
                    "desc": f"👍 {item.get('score', 0)} 分 · {item.get('by', 'anonymous')}"
                })
                if len(items) >= max_items:
                    break
    except Exception as e:
        print(f"[WARN] HackerNews: {e}")
    return items


# ============================================================
# 数据源 2: GitHub Trending (通过 gh-trending API)
# ============================================================
def fetch_github_trending_ai(max_items=10):
    """获取GitHub Trending AI项目"""
    items = []
    # 尝试多个API源，哪个能通用哪个
    trending_apis = [
        "https://trending.repo.ved/top/ai?since=daily&limit=20",
        "https://api.githunt.com/v2/repos?language=&since=daily",
        "https://gh-trending-api.herokuapp.com/repositories?language=&since=daily",
    ]
    data = None
    for api_url in trending_apis:
        data = fetch_json(api_url)
        if data:
            print(f"   ✅ GitHub Trending 使用: {api_url}")
            break

    if not data:
        # 终极方案：直接解析 GitHub Trending 页面
        try:
            html = fetch_text("https://github.com/trending?since=daily")
            if html:
                # 找到所有文章卡片
                blocks = re.findall(r'<article[^>]*class="[^"]*Box-row[^"]*"[^>]*>(.*?)</article>', html, re.DOTALL)
                for block in blocks[:30]:
                    # 提取仓库名
                    name_match = re.search(r'href="/([^"/]+/[^"/"]+)"', block)
                    if not name_match:
                        continue
                    name = name_match.group(1)
                    # 提取描述
                    desc_match = re.search(r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>\s*([^<]+)', block)
                    desc = desc_match.group(1).strip() if desc_match else ""
                    if is_ai_related(name + " " + desc):
                        items.append({
                            "title": name,
                            "url": f"https://github.com/{name}",
                            "source": "GitHub Trending",
                            "desc": (desc[:150] + "..." if len(desc) > 150 else desc) if desc else ""
                        })
                        if len(items) >= max_items:
                            break
                return items
        except Exception as e2:
            print(f"   [WARN] GitHub Trending 页面解析: {e2}")
        return items

    # 处理API返回的数据（兼容多种格式）
    if isinstance(data, list):
        for repo in data[:30]:
            name = repo.get("full_name", repo.get("name", ""))
            topics = repo.get("topics", []) or []
            desc = repo.get("description", repo.get("desc", "")) or ""
            stars = repo.get("stars", repo.get("currentPeriodStars", 0))
            if is_ai_related(name + " " + " ".join(topics) + " " + desc):
                items.append({
                    "title": name,
                    "url": f"https://github.com/{name}",
                    "source": "GitHub Trending",
                    "desc": (desc[:150] + "..." if len(desc) > 150 else desc) if desc else f"⭐ {stars} stars"
                })
                if len(items) >= max_items:
                    break
    return items


# ============================================================
# 数据源 3: 机器之心 (jiqizhixin) — 中文AI专业媒体
# ============================================================
def fetch_jiqizhixin_ai(max_items=10):
    """获取机器之心AI新闻"""
    items = []
    try:
        html = fetch_text("https://www.jiqizhixin.com/")
        if html:
            # 提取文章标题和链接
            pattern = r'<a[^>]*href="(/article/[^"]+)"[^>]*>([^<]+)</a>'
            matches = re.findall(pattern, html)
            seen = set()
            for path, title in matches:
                title = title.strip()
                if not title or title in seen:
                    continue
                seen.add(title)
                if is_ai_related(title):
                    full_url = f"https://www.jiqizhixin.com{path}" if path.startswith("/") else path
                    items.append({
                        "title": title[:120],
                        "url": full_url,
                        "source": "机器之心",
                        "desc": ""
                    })
                    if len(items) >= max_items:
                        break
    except Exception as e:
        print(f"[WARN] 机器之心: {e}")
    return items


# ============================================================
# 数据源 4: IT之家 AI频道
# ============================================================
def fetch_ithome_ai(max_items=10):
    """获取IT之家AI相关新闻"""
    items = []
    try:
        html = fetch_text("https://www.ithome.com/block/ai.html")
        if not html:
            html = fetch_text("https://www.ithome.com/")
        if html:
            pattern = r'<a[^>]*href="(/[^"]*)"[^>]*title="([^"]+)"'
            matches = re.findall(pattern, html)
            seen = set()
            for path, title in matches:
                if title in seen or len(title) < 5:
                    continue
                seen.add(title)
                if is_ai_related(title):
                    full_url = f"https://www.ithome.com{path}" if path.startswith("/") else path
                    items.append({
                        "title": title[:120],
                        "url": full_url,
                        "source": "IT之家",
                        "desc": ""
                    })
                    if len(items) >= max_items:
                        break
    except Exception as e:
        print(f"[WARN] IT之家: {e}")
    return items


# ============================================================
# 数据源 5: AI相关RSS聚合
# ============================================================
def fetch_rss_ai(max_items=10):
    """从RSS feed获取AI新闻"""
    items = []
    rss_feeds = [
        "https://rsshub.app/hackernews/best/20",
    ]
    for feed_url in rss_feeds:
        try:
            xml_data = fetch_text(feed_url)
            if xml_data:
                root = ET.fromstring(xml_data)
                for entry in root.iter("item") if root.tag == "rss" else root.iter("entry"):
                    title = entry.findtext("title", "")
                    link = entry.findtext("link", "") or entry.findtext("link", "")
                    desc = entry.findtext("description", "") or entry.findtext("summary", "")
                    if title and is_ai_related(title, desc):
                        items.append({
                            "title": title[:120],
                            "url": link,
                            "source": "RSS",
                            "desc": desc[:150] if desc else ""
                        })
                        if len(items) >= max_items:
                            break
        except Exception as e:
            print(f"[WARN] RSS源 {feed_url}: {e}")
    return items


# ============================================================
# 数据源 5: HackerNews "Show HN" AI项目
# ============================================================
def fetch_show_hn_ai(max_items=10):
    """从Show HN获取AI相关项目"""
    items = []
    try:
        show_ids = fetch_json("https://hacker-news.firebaseio.com/v0/showstories.json")
        if not show_ids:
            return items
        for item_id in show_ids[:40]:
            item = fetch_json(f"https://hacker-news.firebaseio.com/v0/item/{item_id}.json")
            if item and item.get("title") and is_ai_related(item.get("title", "")):
                items.append({
                    "title": item["title"][:120],
                    "url": item.get("url", f"https://news.ycombinator.com/item?id={item_id}"),
                    "source": "Show HN",
                    "desc": f"👤 {item.get('by', 'anonymous')}"
                })
                if len(items) >= max_items:
                    break
    except Exception as e:
        print(f"[WARN] Show HN: {e}")
    return items


# ============================================================
# HTML生成
# ============================================================
def build_html(all_news):
    """生成美观的日报HTML"""
    # 按来源分组
    grouped = {}
    for item in all_news:
        src = item["source"]
        if src not in grouped:
            grouped[src] = []
        grouped[src].append(item)

    source_icons = {
        "HackerNews": "📰",
        "Show HN": "🛠️",
        "GitHub Trending": "⭐",
        "机器之心": "🧠",
        "IT之家": "💻",
        "RSS": "📡",
    }

    source_order = ["HackerNews", "GitHub Trending", "Show HN", "机器之心", "IT之家", "RSS"]

    cards_html = ""
    total_count = len(all_news)

    for src_name in source_order:
        if src_name not in grouped:
            continue
        items = grouped[src_name]
        icon = source_icons.get(src_name, "📌")

        items_html = ""
        for item in items:
            desc_html = f'<p class="item-desc">{escape(item["desc"])}</p>' if item["desc"] else ""
            items_html += f'''
            <a href="{escape(item["url"])}" target="_blank" rel="noopener" class="news-item">
                <h3 class="item-title">{escape(item["title"])}</h3>
                {desc_html}
            </a>'''

        cards_html += f'''
        <div class="source-section">
            <h2 class="source-header">{icon} {src_name}</h2>
            <div class="news-list">
                {items_html}
            </div>
        </div>'''

    # 统计信息
    now_str = datetime.now(CST).strftime("%Y-%m-%d %H:%M")

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 新闻日报 — {TODAY}</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <header class="header">
        <div class="header-content">
            <h1 class="site-title">AI 新闻日报</h1>
            <p class="site-desc">每日AI资讯聚合 · 自动抓取 · 免费开源</p>
            <div class="date-badge">
                <span class="date-icon">📅</span>
                <span>{TODAY_DISPLAY}</span>
                <span class="count-badge">共 {total_count} 条</span>
            </div>
        </div>
    </header>

    <main class="container">
        {cards_html}
    </main>

    <footer class="footer">
        <div class="footer-content">
            <p>🤖 AI 新闻日报 · 每日自动更新</p>
            <p class="footer-meta">数据来源: HackerNews · GitHub Trending · Show HN · 机器之心 · IT之家</p>
            <p class="footer-meta">更新时间: {now_str} CST</p>
            <p class="footer-meta">
                <a href="https://github.com/hot124588/ai-news" target="_blank" rel="noopener">GitHub 仓库</a>
            </p>
        </div>
    </footer>
</body>
</html>'''
    return html


def build_archive_page(all_dates):
    """生成历史归档页面"""
    items_html = ""
    for d in sorted(all_dates, reverse=True):
        items_html += f'''
        <a href="{d}.html" class="archive-item">
            <span class="archive-date">📅 {d}</span>
            <span class="archive-arrow">→</span>
        </a>'''

    html = f'''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AI 新闻日报 — 历史归档</title>
    <link rel="stylesheet" href="style.css">
</head>
<body>
    <header class="header">
        <div class="header-content">
            <h1 class="site-title">📚 历史归档</h1>
            <p class="site-desc">所有历史日报</p>
            <a href="index.html" class="back-link">← 返回今日</a>
        </div>
    </header>

    <main class="container">
        <div class="archive-grid">
            {items_html}
        </div>
    </main>

    <footer class="footer">
        <div class="footer-content">
            <p>🤖 AI 新闻日报 · 每日自动更新</p>
        </div>
    </footer>
</body>
</html>'''
    return html


def build_css():
    return """/* AI News Daily — 简洁日报样式 */
:root {
    --bg: #0f0f1a;
    --card-bg: #1a1a2e;
    --card-hover: #22223a;
    --accent: #6c63ff;
    --accent-light: #8b83ff;
    --text: #e8e8f0;
    --text-muted: #8888aa;
    --border: #2a2a44;
    --header-bg: linear-gradient(135deg, #0f0f1a 0%, #1a1a3e 100%);
}

* { margin: 0; padding: 0; box-sizing: border-box; }

body {
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Noto Sans SC", sans-serif;
    background: var(--bg);
    color: var(--text);
    line-height: 1.6;
    min-height: 100vh;
}

/* HEADER */
.header {
    background: var(--header-bg);
    padding: 40px 20px;
    text-align: center;
    border-bottom: 1px solid var(--border);
}

.header-content {
    max-width: 800px;
    margin: 0 auto;
}

.site-title {
    font-size: 2rem;
    font-weight: 800;
    background: linear-gradient(135deg, var(--accent), var(--accent-light));
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    letter-spacing: -0.5px;
}

.site-desc {
    color: var(--text-muted);
    margin-top: 8px;
    font-size: 0.95rem;
}

.date-badge {
    display: inline-flex;
    align-items: center;
    gap: 10px;
    margin-top: 16px;
    padding: 8px 20px;
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 24px;
    font-size: 0.95rem;
}

.count-badge {
    background: var(--accent);
    color: #fff;
    padding: 2px 10px;
    border-radius: 12px;
    font-size: 0.8rem;
}

.back-link {
    display: inline-block;
    margin-top: 12px;
    color: var(--accent-light);
    text-decoration: none;
    font-size: 0.9rem;
}
.back-link:hover { text-decoration: underline; }

/* MAIN */
.container {
    max-width: 860px;
    margin: 0 auto;
    padding: 24px 20px;
}

/* SOURCE SECTION */
.source-section {
    margin-bottom: 28px;
}

.source-header {
    font-size: 1.2rem;
    font-weight: 700;
    color: var(--accent-light);
    padding-bottom: 10px;
    border-bottom: 2px solid var(--border);
    margin-bottom: 14px;
}

/* NEWS LIST */
.news-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
}

.news-item {
    display: block;
    padding: 12px 16px;
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    text-decoration: none;
    transition: all 0.2s ease;
    cursor: pointer;
}

.news-item:hover {
    background: var(--card-hover);
    border-color: var(--accent);
    transform: translateX(4px);
}

.item-title {
    font-size: 0.95rem;
    font-weight: 500;
    color: var(--text);
    line-height: 1.4;
}

.item-desc {
    font-size: 0.8rem;
    color: var(--text-muted);
    margin-top: 4px;
}

/* ARCHIVE */
.archive-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: 12px;
}

.archive-item {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 14px 18px;
    background: var(--card-bg);
    border: 1px solid var(--border);
    border-radius: 10px;
    text-decoration: none;
    transition: all 0.2s ease;
}

.archive-item:hover {
    background: var(--card-hover);
    border-color: var(--accent);
}

.archive-date {
    font-size: 0.9rem;
    color: var(--text);
}

.archive-arrow {
    color: var(--text-muted);
    font-size: 1.1rem;
}

/* FOOTER */
.footer {
    margin-top: 40px;
    padding: 30px 20px;
    border-top: 1px solid var(--border);
    text-align: center;
}

.footer-content {
    max-width: 800px;
    margin: 0 auto;
}

.footer p {
    color: var(--text-muted);
    font-size: 0.85rem;
    margin-bottom: 4px;
}

.footer-meta {
    font-size: 0.75rem !important;
    opacity: 0.7;
}

.footer a {
    color: var(--accent-light);
    text-decoration: none;
}
.footer a:hover { text-decoration: underline; }

/* RESPONSIVE */
@media (max-width: 600px) {
    .site-title { font-size: 1.5rem; }
    .header { padding: 28px 16px; }
    .container { padding: 16px; }
    .news-item { padding: 10px 14px; }
    .archive-grid { grid-template-columns: 1fr; }
}
"""


# ============================================================
# 主流程
# ============================================================
def main():
    print(f"🚀 AI 新闻日报 — 开始抓取 ({TODAY})")
    print("=" * 50)

    all_news = []

    # 按顺序抓取各数据源
    fetchers = [
        ("HackerNews AI", fetch_hackernews_ai, 15),
        ("GitHub Trending AI", fetch_github_trending_ai, 8),
        ("Show HN AI", fetch_show_hn_ai, 8),
        ("机器之心", fetch_jiqizhixin_ai, 10),
        ("IT之家", fetch_ithome_ai, 10),
        ("RSS", fetch_rss_ai, 5),
    ]

    for name, fetcher, limit in fetchers:
        print(f"\n📡 正在抓取: {name} ...")
        try:
            items = fetcher(limit)
            all_news.extend(items)
            print(f"   ✅ 获取 {len(items)} 条")
        except Exception as e:
            print(f"   ❌ 失败: {e}")

    # 去重（按标题）
    seen_titles = set()
    unique_news = []
    for item in all_news:
        key = item["title"].lower().strip()
        if key not in seen_titles:
            seen_titles.add(key)
            unique_news.append(item)

    print(f"\n{'=' * 50}")
    print(f"📊 共抓取 {len(unique_news)} 条去重后的AI新闻")
    for item in unique_news:
        print(f"   [{item['source']}] {item['title'][:60]}")

    # 生成 HTML
    print(f"\n📝 生成HTML页面...")
    html_content = build_html(unique_news)
    css_content = build_css()

    # 写入文件
    index_path = os.path.join(OUTPUT_DIR, "index.html")
    css_path = os.path.join(OUTPUT_DIR, "style.css")

    with open(index_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    with open(css_path, "w", encoding="utf-8") as f:
        f.write(css_content)

    # 同时生成今日存档副本（便于历史归档）
    daily_path = os.path.join(OUTPUT_DIR, f"{TODAY}.html")
    with open(daily_path, "w", encoding="utf-8") as f:
        f.write(html_content)

    print(f"✅ 页面已生成:")
    print(f"   {index_path}")
    print(f"   {css_path}")
    print(f"   {daily_path}")
    print(f"\n🌐 访问: https://hot124588.github.io/ai-news/")


if __name__ == "__main__":
    main()
