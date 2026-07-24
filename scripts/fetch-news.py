#!/usr/bin/env python3
"""AI News Timeline - Multi-source AI news aggregator.
Fetches from: HackerNews, TechCrunch RSS, HuggingFace Papers, Reddit, GitHub Trending.
Outputs: docs/index.html (full page), docs/data.json (JSON data)."""

import json, os, re, html, time, xml.etree.ElementTree as ET, ssl
import urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta

# Fix SSL EOF issue on some Python versions
_ssl_ctx = ssl.create_default_context()
_ssl_ctx.check_hostname = False
_ssl_ctx.verify_mode = ssl.CERT_NONE

OUT = "docs"
os.makedirs(OUT, exist_ok=True)

CST = timezone(timedelta(hours=8))
NOW = datetime.now(CST)
TODAY = NOW.strftime("%Y-%m-%d")
TDISP = NOW.strftime("%Y年%m月%d日")
NOW_UTC = datetime.now(timezone.utc)

# Extended AI keyword list for title/summary matching
AI_KW = [
    "ai","artificial intelligence","machine learning","deep learning",
    "llm","gpt","openai","claude","anthropic","gemini",
    "大模型","人工智能","智能体","agent","rag",
    "stable diffusion","多模态","transformer",
    "hugging face","ai芯片","gpu","nvidia","算力","开源模型",
    "neural", "network", "fine-tune","foundation model","diffusion",
    "reinforcement learning","rlhf","langchain","vector database",
    "embedding","copilot","codex","mistral","llama",
    "generative ai","genai","computer vision","nlp",
    "ai safety","alignment","prompt","ai代理",
    "推理","训练","深度学习","大语言",
    "autogpt","gpt-4","gpt4","sonnet","opus","haiku",
    "yolo","detection","segmentation","classification",
    "pytorch","tensorflow","jax","keras",
    "recommendation","forecasting","prediction",
    "self-supervised","unsupervised","semi-supervised",
    "attention","attention mechanism","bert","roberta",
    "t5","bart","electra","albert","distilbert",
    "vit","vision transformer","clip","dall-e","midjourney",
    "controlnet","lora","qlora","peft","adapter",
    "quantization","pruning","distillation","onnx",
    "tensorrt","cuda","opencl","vulkan",
    "chatbot","chatgpt","bard","copilot",
    "fine tuning","pretrained","pre-trained",
    "tokenizer","token","inference","training",
    "数据集","模型","算法","框架",
    "mixture of experts","moe","sparse",
    "retrieval augmented","rag",
    "prompt engineering","prompt injection",
    "ai agents","multi-agent","agentic",
    "function calling","tool use","tool calling",
    "mcp","model context protocol","a2a",
    "swarm","crewai","autogen","langgraph",
    "vectordb","vector search","semantic search",
    "embedding model","reranker","cross-encoder",
    "cognitive","perception","reasoning",
    "spatial","navigation","embodied",
    "representation learning","self-distillation",
    "contrastive","ssl","foundation",
    "robotics","robot","drone","autonomous",
    "llmops","mlops","aiops",
    "genesis","sora","veo","kling","pika","runway",
    "image generation","video generation","text-to-image","text-to-video",
    "ai coding","code generation","code review",
    "open source ai","open-weight","open weight",
    "ai regulation","ai policy","ai safety",
    "ai startup","ai funding","ai investment",
]


def fet(url, headers=None, timeout=15, raw=False):
    try:
        h = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
        if headers:
            h.update(headers)
        r = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(r, timeout=timeout, context=_ssl_ctx) as f:
            data = f.read()
            if raw:
                return data
            return json.loads(data.decode("utf-8", "replace"))
    except Exception as e:
        print(f"  FETCH FAIL [{url[:60]}]: {e}")
        return None


def translate(text):
    if not text or len(text) < 3:
        return text
    try:
        url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q=" \
            + urllib.parse.quote(text[:2000])
        with urllib.request.urlopen(
            urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"}), timeout=8
        ) as f:
            return json.loads(f.read().decode())[0][0][0]
    except Exception as e:
        print(f"  TRANSLATE FAIL [{text[:30]}]: {e}")
        return text


def is_ai(text):
    """Check if text matches AI keywords (case-insensitive)."""
    if not text:
        return False
    t_lower = text.lower()
    for k in AI_KW:
        if k in t_lower:
            return True
    return False


def time_label(dt):
    return dt.strftime("%H:%M")


def make_item(category, source, dt, title_en, url, score=75):
    """Create a unified news item dict."""
    title_cn = translate(title_en)
    summary = summarize(title_cn)
    return {
        "category": category,
        "source": source,
        "time": dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "time_label": time_label(dt),
        "title_en": title_en[:200],
        "title_cn": title_cn[:200],
        "summary_cn": summary,
        "url": url,
        "score": score
    }


def summarize(text):
    """Generate a simple summary from translated title."""
    text = text.strip()
    if len(text) <= 30:
        return text + "。"
    dot = text.find("。")
    if 20 < dot < 100:
        base = text[:dot+1]
    else:
        base = text[:60]
    if len(base) < 15:
        base = text[:80]
    return base


# ===================== DATA SOURCES =====================

def fetch_hn():
    """HackerNews top stories + best stories."""
    res = []
    seen = set()
    for story_type, api_endpoint in [("topstories", 60), ("beststories", 30)]:
        ids = fet(f"https://hacker-news.firebaseio.com/v0/{story_type}.json")
        if not ids:
            continue
        for rank, i in enumerate(ids[:api_endpoint]):
            if i in seen:
                continue
            seen.add(i)
            it = fet("https://hacker-news.firebaseio.com/v0/item/" + str(i) + ".json")
            if not it or not it.get("title"):
                continue
            if not is_ai(it["title"]):
                continue
            t = it["title"][:140]
            score = max(55, 95 - rank * 3)
            item_time = NOW_UTC
            if it.get("time"):
                try:
                    item_time = datetime.fromtimestamp(it["time"], tz=timezone.utc)
                except:
                    pass
            res.append(make_item(
                "news", "HackerNews", item_time, t,
                it.get("url", "https://news.ycombinator.com/item?id=" + str(i)),
                score
            ))
            if len(res) >= 25:
                break
        if len(res) >= 25:
            break
    return res


def fetch_sh():
    """HackerNews Show HN stories."""
    res = []
    ids = fet("https://hacker-news.firebaseio.com/v0/showstories.json")
    if not ids:
        return res
    for rank, i in enumerate(ids[:40]):
        it = fet("https://hacker-news.firebaseio.com/v0/item/" + str(i) + ".json")
        if not it or not it.get("title"):
            continue
        if not is_ai(it["title"]):
            continue
        t = it["title"][:140]
        score = max(55, 90 - rank * 3)
        item_time = NOW_UTC
        if it.get("time"):
            try:
                item_time = datetime.fromtimestamp(it["time"], tz=timezone.utc)
            except:
                pass
        res.append(make_item(
            "news", "Show HN", item_time, t,
            it.get("url", "https://news.ycombinator.com/item?id=" + str(i)),
            score
        ))
        if len(res) >= 8:
            break
    return res


def fetch_techcrunch():
    """TechCrunch AI category RSS feed."""
    res = []
    data = fet("https://techcrunch.com/category/artificial-intelligence/feed/", raw=True)
    if not data:
        return res
    try:
        root = ET.fromstring(data)
        for item in root.iter("item"):
            title_el = item.find("title")
            link_el = item.find("link")
            pub_el = item.find("pubDate")
            if title_el is None or link_el is None:
                continue
            title_text = title_el.text or ""
            if not is_ai(title_text):
                continue
            link_text = link_el.text or ""
            dt = NOW_UTC
            if pub_el is not None and pub_el.text:
                try:
                    dt = datetime.strptime(pub_el.text.strip(),
                        "%a, %d %b %Y %H:%M:%S %z").astimezone(timezone.utc)
                except:
                    pass
            res.append(make_item("news", "TechCrunch", dt, title_text, link_text, 82))
            if len(res) >= 12:
                break
    except Exception as e:
        print(f"  TechCrunch XML parse error: {e}")
    return res


def fetch_hf_papers():
    """HuggingFace Daily Papers - check title AND summary for AI keywords."""
    res = []
    data = fet("https://huggingface.co/api/daily_papers")
    if not data:
        return res
    for paper in data[:30]:
        title_text = paper.get("title", "")
        summary_text = paper.get("summary", "")
        paper_data = paper.get("paper", {})
        paper_id = paper_data.get("id", "") if paper_data else paper.get("id", "")
        
        # Check title AND summary against AI keywords (papers are always AI-related,
        # but we want only clearly relevant ones)
        match_title = is_ai(title_text)
        match_summary = is_ai(summary_text)
        if not match_title and not match_summary:
            continue
        
        paper_url = "https://huggingface.co/papers/" + paper_id if paper_id else ""
        if not paper_url:
            continue
        
        upvotes = paper.get("numComments", 0) or 0
        score = min(95, 70 + upvotes)
        dt = NOW_UTC
        pub_date = paper.get("publishedAt")
        if pub_date:
            try:
                dt = datetime.fromisoformat(pub_date.replace("Z", "+00:00"))
            except:
                pass
        res.append(make_item("paper", "HF Daily Papers", dt, title_text, paper_url, score))
        if len(res) >= 15:
            break
    return res


def fetch_reddit():
    """Reddit AI-related subreddits."""
    res = []
    subreddits = ["MachineLearning", "ClaudeAI", "LocalLLaMA", "singularity", "OpenAI"]
    # Try multiple User-Agent patterns since Reddit blocks aggressively
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "python:ai-news-bot:v1.0 (by /u/hot124588)"
    ]
    
    for sub in subreddits:
        ua = user_agents[len(res) % len(user_agents)]
        headers = {"User-Agent": ua, "Accept": "application/json"}
        # Try www.reddit.com first, fallback to old.reddit.com
        urls = [
            f"https://www.reddit.com/r/{sub}/hot.json?limit=25",
            f"https://old.reddit.com/r/{sub}/hot.json?limit=25",
        ]
        data = None
        for url in urls:
            data = fet(url, headers=headers)
            if data:
                break
        if not data or "data" not in data:
            continue
        try:
            for child in data["data"]["children"]:
                post = child.get("data", {})
                title_text = post.get("title", "")
                if not is_ai(title_text):
                    continue
                url = post.get("url", "")
                permalink = "https://www.reddit.com" + post.get("permalink", "")
                score = min(95, 65 + post.get("ups", 0) // 100)
                if score < 60:
                    score = 65
                created = post.get("created_utc", 0)
                dt = datetime.fromtimestamp(created, tz=timezone.utc) if created else NOW_UTC
                final_url = url if url and url.startswith("http") and "reddit.com" not in url.lower() else permalink
                res.append(make_item("socialMedia", f"r/{sub}", dt, title_text, final_url, score))
                if sum(1 for x in res if x["source"].endswith(sub)) >= 8:
                    break
        except Exception as e:
            print(f"  Reddit r/{sub} parse error: {e}")
    return res


def fetch_github_trending():
    """GitHub trending AI/ML repositories."""
    res = []
    seen_repos = set()
    
    # Method 1: GitHub search API for AI repos
    search_queries = [
        ("ai", "stars", "desc"),
        ("machine-learning", "stars", "desc"),
        ("artificial-intelligence", "stars", "desc"),
    ]
    for query, sort, order in search_queries:
        try:
            url = f"https://api.github.com/search/repositories?q={query}&sort={sort}&order={order}&per_page=15"
            data = fet(url, headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "ai-news-bot"
            })
            if not data or "items" not in data:
                continue
            for repo in data["items"]:
                name = repo.get("full_name", "")
                if name in seen_repos:
                    continue
                seen_repos.add(name)
                desc = repo.get("description", "") or ""
                title_text = f"{name}: {desc}"[:200] if desc else name
                if not is_ai(title_text) and not is_ai(desc) and not is_ai(name):
                    continue
                stars = repo.get("stargazers_count", 0)
                if stars >= 100000:
                    score = 95
                elif stars >= 50000:
                    score = 92
                elif stars >= 10000:
                    score = 88
                elif stars >= 5000:
                    score = 82
                elif stars >= 2000:
                    score = 76
                elif stars >= 500:
                    score = 68
                else:
                    score = 62
                display_title = f"{name} ({stars:,}⭐)"
                repo_url = repo.get("html_url", f"https://github.com/{name}")
                dt = NOW_UTC
                pushed = repo.get("pushed_at")
                if pushed:
                    try:
                        dt = datetime.fromisoformat(pushed.replace("Z", "+00:00"))
                    except:
                        pass
                res.append(make_item("githubTrending", "GitHub Trending", dt,
                    display_title, repo_url, score))
        except Exception as e:
            print(f"  GitHub search '{query}' error: {e}")
    
    # Method 2: Scrape GitHub trending page for additional repos
    try:
        raw_html = fet("https://github.com/trending?since=daily", raw=True)
        if raw_html:
            html_str = raw_html.decode("utf-8", "replace")
            # Find repo article blocks
            articles = re.split(r'<article[^>]*class="[^"]*Box-row[^"]*"[^>]*>', html_str)
            for art in articles[1:]:  # Skip first split part
                # Extract repo name
                name_match = re.search(r'href="/repos/([^"]+)"', art)
                if not name_match:
                    name_match = re.search(r'href="/([^"]+?)"[^>]*data-hovercard-type="repository"', art)
                if not name_match:
                    name_match = re.search(r'<h2[^>]*>.*?<a[^>]*href="/([^"/]+/[^"/]+)"', art)
                if not name_match:
                    continue
                repo_name = name_match.group(1).strip()
                if repo_name in seen_repos:
                    continue
                seen_repos.add(repo_name)
                
                # Extract description
                desc_match = re.search(r'<p[^>]*class="[^"]*col-9[^"]*"[^>]*>(.*?)</p>', art, re.DOTALL)
                desc_text = re.sub(r'<[^>]+>', '', desc_match.group(1)).strip() if desc_match else ""
                
                full_text = f"{repo_name} {desc_text}"
                if not is_ai(full_text):
                    continue
                
                # Extract stars
                star_match = re.search(r'<a[^>]*href="/[^"]+/stargazers"[^>]*>.*?(\d[\d,]*k?)', art, re.DOTALL)
                star_str = star_match.group(1).strip() if star_match else "0"
                star_count = 0
                if 'k' in star_str.lower():
                    try:
                        star_count = int(float(star_str.lower().replace('k', '')) * 1000)
                    except:
                        star_count = 0
                else:
                    try:
                        star_count = int(star_str.replace(',', ''))
                    except:
                        star_count = 0
                
                score = 95 if star_count >= 50000 else (92 if star_count >= 10000 else
                    85 if star_count >= 5000 else (78 if star_count >= 2000 else
                    70 if star_count >= 500 else 65))
                display_title = f"{repo_name} ({star_count:,}⭐)"
                res.append(make_item("githubTrending", "GitHub Trending", NOW_UTC,
                    display_title, f"https://github.com/{repo_name}", score))
    except Exception as e:
        print(f"  GitHub trending page error: {e}")
    
    return res


# ===================== HTML BUILDER =====================

def build_html(items):
    """Build the complete HTML page with inline CSS/JS."""
    items.sort(key=lambda x: x["time"], reverse=True)

    cat_counts = {}
    for it in items:
        cat_counts[it["category"]] = cat_counts.get(it["category"], 0) + 1

    # Build timeline sections
    timeline_html = ""
    sessions = [
        ("morning", "00:00 - 12:00", lambda tl: tl < "12:00"),
        ("afternoon", "12:00 - 24:00", lambda tl: tl >= "12:00"),
    ]

    for session_id, session_label, check in sessions:
        session_items = [it for it in items if check(it["time_label"])]
        if not session_items:
            continue

        cards_html = ""
        for it in session_items:
            cat_color = {
                "news": "#6c63ff",
                "socialMedia": "#00d4aa",
                "githubTrending": "#ff8c42",
                "paper": "#ff6b9d"
            }.get(it["category"], "#6c63ff")

            cat_label = {
                "news": "NEWS",
                "socialMedia": "SOCIAL",
                "githubTrending": "GITHUB",
                "paper": "PAPER"
            }.get(it["category"], it["category"])

            cards_html += f"""
            <div class="card" data-category="{it['category']}" data-source="{html.escape(it['source'].lower())}"
                 data-title-en="{html.escape(it['title_en'].lower())}"
                 data-title-cn="{html.escape(it['title_cn'].lower())}">
                <div class="card-time">{html.escape(it['time_label'])}</div>
                <div class="card-body">
                    <div class="card-meta">
                        <span class="cat-tag cat-{it['category']}" style="background:{cat_color}22;color:{cat_color};border:1px solid {cat_color}44">
                            [{cat_label}]
                        </span>
                        <span class="card-source">{html.escape(it['source'])}</span>
                        <span class="card-score" title="AI推荐评分">{it['score']}<span class="score-unit">%</span></span>
                    </div>
                    <div class="card-title">{html.escape(it['title_cn'])}</div>
                    <div class="card-title-en">{html.escape(it['title_en'])}</div>
                    <div class="card-summary">{html.escape(it['summary_cn'])}</div>
                    <a href="{html.escape(it['url'])}" class="card-link" target="_blank" rel="noopener">[UPLINK] → 查看原文</a>
                </div>
            </div>"""

        timeline_html += f"""
        <div class="session" id="session-{session_id}">
            <div class="session-header">
                <div class="session-line"></div>
                <span class="session-label">LOG_SESSION: {TODAY} {session_label}</span>
                <div class="session-line"></div>
            </div>
            <div class="cards-container">
                {cards_html}
            </div>
        </div>"""

    if not timeline_html:
        timeline_html = '<div class="empty-state"><div class="empty-icon">📡</div><div class="empty-text">暂无数据</div></div>'

    data_json_str = json.dumps(items, ensure_ascii=False, indent=2)

    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>AI 时间线 | {TODAY}</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
    --bg:#0f0f1a;
    --bg2:#151528;
    --bg3:#1a1a30;
    --card-bg:#191933;
    --card-border:#2a2a44;
    --card-hover:#222244;
    --text:#e8e8f0;
    --text2:#a0a0b8;
    --text3:#666680;
    --accent:#6c63ff;
    --accent2:#8b83ff;
    --news:#6c63ff;
    --social:#00d4aa;
    --github:#ff8c42;
    --paper:#ff6b9d;
    --radius:12px;
    --font:'-apple-system','Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif
}}
body{{font-family:var(--font);background:var(--bg);color:var(--text);min-height:100vh;line-height:1.6}}
a{{color:var(--accent2);text-decoration:none}}
a:hover{{text-decoration:underline}}

/* Header */
.header{{background:linear-gradient(180deg,#151528 0%,var(--bg) 100%);padding:24px 20px 16px;position:sticky;top:0;z-index:100;border-bottom:1px solid var(--card-border)}}
.header-inner{{max-width:960px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px}}
.header-logo{{display:flex;align-items:center;gap:10px}}
.logo-icon{{width:36px;height:36px;background:linear-gradient(135deg,var(--accent),var(--accent2));border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:700;color:#fff}}
.header-title h1{{font-size:1.2rem;font-weight:600;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1.2}}
.header-title .header-date{{font-size:.75rem;color:var(--text3);-webkit-text-fill-color:var(--text3)}}
.header-actions{{display:flex;align-items:center;gap:10px}}

/* Search */
.search-box{{position:relative}}
.search-box input{{background:var(--bg2);border:1px solid var(--card-border);border-radius:8px;padding:8px 12px 8px 32px;color:var(--text);font-size:.85rem;width:180px;outline:none;transition:border-color .2s}}
.search-box input:focus{{border-color:var(--accent)}}
.search-box input::placeholder{{color:var(--text3)}}
.search-icon{{position:absolute;left:10px;top:50%;transform:translateY(-50%);color:var(--text3);font-size:.8rem;pointer-events:none}}

/* Filters */
.filters{{max-width:960px;margin:0 auto;padding:12px 20px;display:flex;gap:6px;flex-wrap:wrap;align-items:center}}
.filter-btn{{padding:6px 14px;border-radius:20px;border:1px solid var(--card-border);background:transparent;color:var(--text2);font-size:.78rem;cursor:pointer;transition:all .2s;font-family:var(--font)}}
.filter-btn:hover{{border-color:var(--accent);color:var(--text)}}
.filter-btn.active{{background:var(--accent);color:#fff;border-color:var(--accent)}}
.filter-count{{font-size:.7rem;color:var(--text3);margin-left:2px}}

/* Stats bar */
.stats-bar{{max-width:960px;margin:0 auto;padding:0 20px 8px;display:flex;gap:12px;flex-wrap:wrap;font-size:.75rem;color:var(--text3)}}
.stat-item{{display:flex;align-items:center;gap:4px}}
.stat-dot{{width:8px;height:8px;border-radius:50%;display:inline-block}}

/* Session */
.session{{max-width:960px;margin:0 auto;padding:8px 20px}}
.session-header{{display:flex;align-items:center;gap:12px;margin:20px 0 12px}}
.session-line{{flex:1;height:1px;background:linear-gradient(90deg,transparent,var(--card-border),transparent)}}
.session-label{{font-size:.75rem;color:var(--text3);font-family:monospace;white-space:nowrap}}

/* Cards */
.cards-container{{display:flex;flex-direction:column;gap:4px}}
.card{{display:flex;gap:12px;padding:12px 14px;background:var(--card-bg);border:1px solid var(--card-border);border-radius:var(--radius);transition:all .2s;cursor:default;animation:fadeIn .3s ease-out}}
.card:hover{{background:var(--card-hover);border-color:var(--accent);transform:translateX(3px)}}
.card-time{{min-width:48px;font-size:.78rem;color:var(--text3);font-family:monospace;padding-top:2px;text-align:right}}
.card-body{{flex:1;min-width:0}}
.card-meta{{display:flex;align-items:center;gap:8px;margin-bottom:4px;flex-wrap:wrap}}
.cat-tag{{font-size:.68rem;padding:1px 7px;border-radius:4px;font-weight:500;line-height:1.6}}
.card-source{{font-size:.72rem;color:var(--text2)}}
.card-score{{font-size:.85rem;font-weight:700;margin-left:auto;color:var(--accent2);font-family:monospace}}
.score-unit{{font-size:.6rem;color:var(--text3)}}
.card-title{{font-size:.95rem;font-weight:500;color:var(--text);margin-bottom:2px;line-height:1.4}}
.card-title-en{{font-size:.72rem;color:var(--text3);margin-bottom:4px;line-height:1.3;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.card-summary{{font-size:.78rem;color:var(--text2);line-height:1.5;margin-bottom:6px}}
.card-link{{font-size:.72rem;color:var(--accent);font-family:monospace}}
.card-link:hover{{color:var(--accent2)}}

/* Empty state */
.empty-state{{text-align:center;padding:60px 20px}}
.empty-icon{{font-size:3rem;margin-bottom:10px}}
.empty-text{{color:var(--text3)}}

/* Footer */
.footer{{text-align:center;padding:30px 20px;color:var(--text3);font-size:.75rem;border-top:1px solid var(--card-border);margin-top:10px}}
.footer a{{color:var(--accent2)}}

/* Responsive */
@media(max-width:640px){{
    .header{{padding:16px 12px 12px}}
    .header-inner{{flex-direction:column;align-items:flex-start}}
    .search-box input{{width:100%}}
    .header-actions{{width:100%}}
    .search-box{{width:100%}}
    .filters{{gap:4px;padding:8px 12px}}
    .filter-btn{{font-size:.72rem;padding:4px 10px}}
    .card{{padding:10px 10px;gap:8px}}
    .card-time{{min-width:36px;font-size:.7rem}}
    .card-title{{font-size:.88rem}}
    .session{{padding:4px 12px}}
}}

/* Animation */
@keyframes fadeIn{{
    from{{opacity:0;transform:translateY(6px)}}
    to{{opacity:1;transform:translateY(0)}}
}}

/* Scrollbar */
::-webkit-scrollbar{{width:6px}}
::-webkit-scrollbar-track{{background:var(--bg)}}
::-webkit-scrollbar-thumb{{background:var(--card-border);border-radius:3px}}
::-webkit-scrollbar-thumb:hover{{background:var(--text3)}}
</style>
</head>
<body>

<!-- Header -->
<header class="header">
    <div class="header-inner">
        <div class="header-logo">
            <div class="logo-icon">AI</div>
            <div class="header-title">
                <h1>AI 时间线</h1>
                <div class="header-date">📅 {TDISP}</div>
            </div>
        </div>
        <div class="header-actions">
            <div class="search-box">
                <span class="search-icon">🔍</span>
                <input type="text" id="searchInput" placeholder="搜索标题..." autocomplete="off">
            </div>
        </div>
    </div>
</header>

<!-- Filters -->
<nav class="filters" id="filters">
    <button class="filter-btn active" data-filter="all">
        全部 <span class="filter-count">({len(items)})</span>
    </button>
    <button class="filter-btn" data-filter="news">
        NEWS <span class="filter-count">({cat_counts.get('news', 0)})</span>
    </button>
    <button class="filter-btn" data-filter="socialMedia">
        SOCIAL <span class="filter-count">({cat_counts.get('socialMedia', 0)})</span>
    </button>
    <button class="filter-btn" data-filter="githubTrending">
        GITHUB <span class="filter-count">({cat_counts.get('githubTrending', 0)})</span>
    </button>
    <button class="filter-btn" data-filter="paper">
        PAPER <span class="filter-count">({cat_counts.get('paper', 0)})</span>
    </button>
</nav>

<!-- Stats -->
<div class="stats-bar">
    <span class="stat-item"><span class="stat-dot" style="background:var(--news)"></span> 新闻</span>
    <span class="stat-item"><span class="stat-dot" style="background:var(--social)"></span> 社媒</span>
    <span class="stat-item"><span class="stat-dot" style="background:var(--github)"></span> 开源</span>
    <span class="stat-item"><span class="stat-dot" style="background:var(--paper)"></span> 论文</span>
    <span class="stat-item">共 {len(items)} 条动态</span>
</div>

<!-- Timeline -->
<main id="timeline">
    {timeline_html}
</main>

<!-- Footer -->
<footer class="footer">
    <p>🤖 每日自动采集 · 数据来源: HackerNews / TechCrunch / Reddit / GitHub / HuggingFace</p>
    <p>🕐 最后更新: {NOW.strftime('%H:%M')} CST · 由 AI 自动整理</p>
</footer>

<script>
const NEWS_DATA = {data_json_str};

document.addEventListener('DOMContentLoaded', function() {{
    const searchInput = document.getElementById('searchInput');
    const filterBtns = document.querySelectorAll('.filter-btn');
    const cards = document.querySelectorAll('.card');
    let activeFilter = 'all';

    function filterCards() {{
        const searchText = searchInput.value.toLowerCase().trim();
        let visibleCount = 0;

        cards.forEach(function(card) {{
            const cardCat = card.dataset.category;
            const titleEn = card.dataset.titleEn || '';
            const titleCn = card.dataset.titleCn || '';

            const catMatch = activeFilter === 'all' || cardCat === activeFilter;

            let searchMatch = true;
            if (searchText) {{
                searchMatch = titleEn.includes(searchText) || titleCn.includes(searchText);
            }}

            if (catMatch && searchMatch) {{
                card.style.display = 'flex';
                visibleCount++;
            }} else {{
                card.style.display = 'none';
            }}
        }});

        // Show/hide session blocks
        document.querySelectorAll('.session').forEach(function(session) {{
            const allCards = session.querySelectorAll('.card');
            let hasVisible = false;
            allCards.forEach(function(c) {{
                if (c.style.display !== 'none') hasVisible = true;
            }});
            session.style.display = hasVisible ? '' : 'none';
        }});

        // Update filter counts
        filterBtns.forEach(function(btn) {{
            const filter = btn.dataset.filter;
            let count = 0;
            if (filter === 'all') {{
                count = visibleCount;
            }} else {{
                cards.forEach(function(c) {{
                    if (c.dataset.category === filter && c.style.display !== 'none') count++;
                }});
            }}
            const countSpan = btn.querySelector('.filter-count');
            if (countSpan) {{
                countSpan.textContent = '(' + count + ')';
            }}
        }});
    }}

    filterBtns.forEach(function(btn) {{
        btn.addEventListener('click', function() {{
            filterBtns.forEach(function(b) {{ b.classList.remove('active'); }});
            btn.classList.add('active');
            activeFilter = btn.dataset.filter;
            filterCards();
        }});
    }});

    searchInput.addEventListener('input', filterCards);
}});
</script>
</body>
</html>"""

    return html_content


def build_data_json(items):
    return json.dumps(items, ensure_ascii=False, indent=2)


# ===================== MAIN =====================

def main():
    print("=" * 40)
    print(f"AI News Timeline - {TDISP}")
    print("=" * 40)

    fetchers = [
        ("HackerNews", fetch_hn),
        ("Show HN", fetch_sh),
        ("TechCrunch", fetch_techcrunch),
        ("HF Papers", fetch_hf_papers),
        ("Reddit", fetch_reddit),
        ("GitHub Trending", fetch_github_trending),
    ]

    all_items = []
    for name, fn in fetchers:
        try:
            print(f"\n▶ {name}...")
            items = fn()
            all_items.extend(items)
            print(f"  ✓ {len(items)} items")
        except Exception as e:
            print(f"  ✗ FAIL: {e}")

    # Deduplicate by URL
    seen_urls = set()
    unique = []
    for x in all_items:
        url_key = x["url"]
        if url_key not in seen_urls:
            seen_urls.add(url_key)
            unique.append(x)

    print(f"\n{'='*40}")
    print(f"Total unique: {len(unique)}")

    cats = {}
    for it in unique:
        cats[it["category"]] = cats.get(it["category"], 0) + 1
    for cat, count in sorted(cats.items()):
        print(f"  {cat}: {count}")

    # Build outputs
    html = build_html(unique)
    data_json = build_data_json(unique)

    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✓ docs/index.html ({len(html)} bytes)")

    with open(os.path.join(OUT, "data.json"), "w", encoding="utf-8") as f:
        f.write(data_json)
    print(f"✓ docs/data.json ({len(data_json)} bytes)")

    dated_path = os.path.join(OUT, f"{TODAY}.html")
    with open(dated_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ {dated_path}")

    print(f"\n✅ Done! https://hot124588.github.io/ai-news/")


if __name__ == "__main__":
    main()
