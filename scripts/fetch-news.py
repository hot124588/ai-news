#!/usr/bin/env python3
"""AI News 日报 - 多源实时聚合 (增强版 v2)
数据源:
  - Google News RSS (中文+英文, 多关键词)  → 实时资讯流
  - HackerNews Algolia (按时间排序)        → 最新讨论
  - HuggingFace Daily Papers               → 每日论文
  - ArXiv (cs.AI/CL/CV/LG 最新提交)        → 前沿研究
  - RSS: TechCrunch / The Verge / VentureBeat / 36氪 / 机器之心
  - GitHub Trending (搜索API + 页面抓取)   → 热门开源
输出: docs/index.html, docs/<date>.html, docs/data.json
特性: 48h 新鲜度过滤, 真实摘要, 相对时间, 自动翻译(失败兜底), 去重
"""
import json, os, re, html, ssl
import urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
import xml.etree.ElementTree as ET

# 部分 Python 版本 SSL 握手会 EOF, 这里放宽校验
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

FRESH_HOURS = 48                      # 新闻类只保留近 48 小时
FRESH_CUT = NOW_UTC - timedelta(hours=FRESH_HOURS)

# ---- AI 关键词 (标题/摘要命中即保留) ----
AI_KW = [
    "ai","artificial intelligence","machine learning","deep learning","llm","gpt",
    "openai","claude","anthropic","gemini","大模型","人工智能","智能体","agent","rag",
    "stable diffusion","多模态","transformer","hugging face","ai芯片","gpu","nvidia",
    "算力","开源模型","neural","fine-tune","foundation model","diffusion","rlhf",
    "langchain","vector database","embedding","copilot","codex","mistral","llama",
    "generative ai","genai","computer vision","nlp","ai safety","alignment","prompt",
    "ai代理","深度学习","大语言","gpt-4","gpt4","sonnet","opus","haiku","yolo",
    "detection","segmentation","pytorch","tensorflow","jax","lora","qlora","peft",
    "quantization","pruning","distillation","onnx","chatbot","chatgpt","预训练",
    "mcp","model context protocol","multi-agent","agentic","tool use","swarm",
    "autogen","langgraph","机器人","robot","drone","autonomous","sora","veo","kling",
    "pika","runway","image generation","video generation","text-to-image",
    "text-to-video","ai coding","code generation","open-weight","open weight",
    "ai regulation","ai policy","ai startup","ai funding","ai investment","数据集",
    "模型","算法","框架","mixture of experts","moe","reinforcement learning",
]

_UA = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


# ===================== 通用工具 =====================
def fet(url, headers=None, timeout=20, raw=False):
    try:
        h = dict(_UA)
        if headers:
            h.update(headers)
        req = urllib.request.Request(url, headers=h)
        with urllib.request.urlopen(req, timeout=timeout, context=_ssl_ctx) as f:
            data = f.read()
            return data if raw else json.loads(data.decode("utf-8", "replace"))
    except Exception as e:
        print(f"  FETCH FAIL [{url[:70]}]: {e}")
        return None


def translate(text):
    if not text or len(text) < 3:
        return text
    try:
        url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q=" \
            + urllib.parse.quote(text[:2000])
        with urllib.request.urlopen(
            urllib.request.Request(url, headers=_UA), timeout=8
        ) as f:
            return json.loads(f.read().decode())[0][0][0]
    except Exception as e:
        return text


def needs_translate(t):
    if not t:
        return False
    if re.search(r'[一-鿿]', t or ""):   # 含中文则不翻
        return False
    return bool(re.search(r'[A-Za-z]', t))


def is_ai(text):
    if not text:
        return False
    t = text.lower()
    return any(k in t for k in AI_KW)


def clean_html(s):
    if not s:
        return ""
    s = re.sub(r'<[^>]+>', ' ', s)
    s = html.unescape(s)
    s = re.sub(r'\s+', ' ', s).strip()
    return s


def summarize(text, limit=110):
    text = clean_html(text or "")
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text).strip()
    if len(text) <= limit:
        return text
    return text[:limit].rstrip() + "…"


def rel_time(dt):
    if not dt:
        return ""
    h = (NOW_UTC - dt).total_seconds() / 3600
    if h < 1:
        return "刚刚"
    if h < 24:
        return f"{int(h)}h前"
    return f"{int(h // 24)}d前"


def parse_date(s):
    if not s:
        return None
    s = s.strip()
    # ISO 8601 (Atom): 2026-07-24T12:00:00Z
    try:
        return datetime.fromisoformat(s.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        pass
    # RFC 822 (RSS): Thu, 24 Jul 2026 12:00:00 +0000
    for fmt in ("%a, %d %b %Y %H:%M:%S %z", "%a, %d %b %Y %H:%M:%S %Z",
                "%d %b %Y %H:%M:%S %z", "%Y-%m-%dT%H:%M:%S"):
        try:
            return datetime.strptime(s, fmt).astimezone(timezone.utc)
        except Exception:
            continue
    return None


def _local(tag):
    return tag.split('}')[-1] if '}' in tag else tag


def _child(node, local):
    for c in list(node):
        if _local(c.tag) == local:
            return c
    return None


def _text(node, local):
    el = _child(node, local)
    if el is None:
        return None
    # Atom <link href="..."/> 没有文本
    if _local(node.tag) == "entry" and local == "link":
        return el.get("href")
    return el.text


def parse_rss_items(data):
    """把 RSS/Atom 字节解析成 [{title,link,pub,summary}] 列表"""
    out = []
    try:
        root = ET.fromstring(data)
    except Exception as e:
        print(f"  RSS parse error: {e}")
        return out
    for node in root.iter():
        if _local(node.tag) in ("item", "entry"):
            title = _text(node, "title")
            link = _text(node, "link")
            if not link:                       # RSS <link>text</link>
                le = _child(node, "link")
                link = le.text if le is not None else None
            pub = _text(node, "pubDate") or _text(node, "updated") or _text(node, "published")
            raw_sum = (_text(node, "description") or _text(node, "summary")
                       or _text(node, "content") or "")
            out.append({
                "title": clean_html(title) if title else "",
                "link": link,
                "pub": pub,
                "summary": raw_sum,
            })
    return out


def make_item(category, source, dt, title_en, url, score=75, summary_en=None):
    cn = title_en if not needs_translate(title_en) else translate(title_en)
    summary = ""
    if summary_en:
        s = clean_html(summary_en)
        if needs_translate(s) and len(s) < 600:
            s = translate(s)
        summary = summarize(s)
    if not summary:
        summary = summarize(cn)
    return {
        "category": category,
        "source": source,
        "time": (dt or NOW_UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "time_label": (dt or NOW_UTC).astimezone(CST).strftime("%H:%M"),
        "time_rel": rel_time(dt),
        "title_en": title_en[:200],
        "title_cn": cn[:200],
        "summary_cn": summary[:200],
        "url": url,
        "score": score,
    }


# ===================== 数据源 =====================
def fetch_google_news():
    """Google News RSS: 中英文多关键词实时资讯, 最可靠."""
    res = []
    queries = [
        ("人工智能", "zh-CN", "CN", "zh-Hans"),
        ("大模型", "zh-CN", "CN", "zh-Hans"),
        ("OpenAI", "zh-CN", "CN", "zh-Hans"),
        ("生成式AI", "zh-CN", "CN", "zh-Hans"),
        ("artificial intelligence", "en-US", "US", "en"),
        ("large language model", "en-US", "US", "en"),
    ]
    seen = set()
    for q, hl, gl, ce in queries:
        url = (f"https://news.google.com/rss/search?q={urllib.parse.quote(q)}"
               f"&hl={hl}&gl={gl}&ceid={gl}:{ce}")
        data = fet(url, raw=True)
        if not data:
            continue
        for it in parse_rss_items(data):
            if not it["title"] or not it["link"]:
                continue
            if not is_ai(it["title"]):
                continue
            if it["link"] in seen:
                continue
            seen.add(it["link"])
            dt = parse_date(it["pub"]) or NOW_UTC
            if dt < FRESH_CUT:
                continue
            res.append(make_item("news", "Google News", dt, it["title"],
                                 it["link"], 88, it.get("summary")))
            if len(res) >= 45:
                break
        if len(res) >= 45:
            break
    return res


def fetch_hn_algolia():
    """HackerNews 按时间排序抓最新 AI 相关故事."""
    res = []
    cut = int((NOW_UTC - timedelta(days=2)).timestamp())
    queries = ["AI", "LLM", "OpenAI"]
    for q in queries:
        url = (f"https://hn.algolia.com/api/v1/search?tags=story&query={q}"
               f"&numericFilters=created_at_i>{cut}&hitsPerPage=30")
        data = fet(url)
        if not data or "hits" not in data:
            continue
        for hit in data["hits"]:
            title = hit.get("title") or hit.get("story_title")
            if not title or not is_ai(title):
                continue
            url_hit = hit.get("url") or f"https://news.ycombinator.com/item?id={hit.get('objectID')}"
            try:
                dt = datetime.fromtimestamp(int(hit.get("created_at_i", 0)), tz=timezone.utc)
            except Exception:
                dt = NOW_UTC
            points = hit.get("points") or 0
            score = min(95, 60 + points // 5)
            res.append(make_item("news", "HackerNews", dt, title, url_hit, score,
                                 hit.get("story_text") or hit.get("comment_text")))
            if len(res) >= 30:
                break
        if len(res) >= 30:
            break
    return res


def fetch_hf_papers():
    res = []
    data = fet("https://huggingface.co/api/daily_papers")
    if not data:
        return res
    for paper in data[:30]:
        title_text = paper.get("title", "")
        summary_text = paper.get("summary", "")
        pdata = paper.get("paper", {}) or {}
        pid = pdata.get("id", "") or paper.get("id", "")
        if not (is_ai(title_text) or is_ai(summary_text)):
            continue
        if not pid:
            continue
        dt = NOW_UTC
        if paper.get("publishedAt"):
            try:
                dt = datetime.fromisoformat(paper["publishedAt"].replace("Z", "+00:00"))
            except Exception:
                pass
        up = paper.get("numComments", 0) or 0
        res.append(make_item("paper", "HF Daily Papers", dt,
                             title_text, "https://huggingface.co/papers/" + pid,
                             min(95, 70 + up), summary_text))
        if len(res) >= 15:
            break
    return res


def fetch_arxiv():
    res = []
    cats = "cat:cs.AI OR cat:cs.CL OR cat:cs.CV OR cat:cs.LG"
    url = ("http://export.arxiv.org/api/query?search_query="
           + urllib.parse.quote(cats)
           + "&sortBy=submittedDate&sortOrder=descending&max_results=30")
    data = fet(url, raw=True)
    if not data:
        return res
    for it in parse_rss_items(data):
        if not it["title"] or not it["link"]:
            continue
        if not (is_ai(it["title"]) or is_ai(it.get("summary", ""))):
            continue
        dt = parse_date(it["pub"]) or NOW_UTC
        abs_sum = it.get("summary", "")
        # ArXiv 摘要首句作为摘要
        first = re.split(r'(?<=[.!?])\s|\n', abs_sum)[0] if abs_sum else ""
        res.append(make_item("paper", "ArXiv", dt, it["title"], it["link"], 80, first))
        if len(res) >= 15:
            break
    return res


RSS_FEEDS = [
    ("TechCrunch AI", "https://techcrunch.com/category/artificial-intelligence/feed/", "news", 10),
    ("The Verge AI", "https://www.theverge.com/rss/ai-artificial-intelligence/index.xml", "news", 10),
    ("VentureBeat AI", "https://venturebeat.com/category/ai/feed/", "news", 8),
    ("36氪", "https://36kr.com/feed", "news", 10),
    ("Ars Technica", "https://feeds.arstechnica.com/arstechnica/index", "news", 8),
]


def fetch_rss():
    res = []
    for name, url, cat, mx in RSS_FEEDS:
        data = fet(url, raw=True, timeout=25)
        if not data:
            continue
        n = 0
        for it in parse_rss_items(data):
            if not it["title"] or not it["link"]:
                continue
            if not is_ai(it["title"]):
                continue
            dt = parse_date(it["pub"]) or NOW_UTC
            if dt < FRESH_CUT:
                continue
            res.append(make_item(cat, name, dt, it["title"], it["link"], 82, it.get("summary")))
            n += 1
            if n >= mx:
                break
    return res


def fetch_github_trending():
    res = []
    seen = set()
    queries = [("ai", "stars"), ("machine-learning", "stars"),
               ("artificial-intelligence", "stars"), ("llm", "stars")]
    for query, sort in queries:
        try:
            url = (f"https://api.github.com/search/repositories?q={query}"
                   f"&sort={sort}&order=desc&per_page=12")
            data = fet(url, headers={"Accept": "application/vnd.github.v3+json",
                                     "User-Agent": "ai-news-bot"})
            if not data or "items" not in data:
                continue
            for repo in data["items"]:
                name = repo.get("full_name", "")
                if name in seen:
                    continue
                seen.add(name)
                desc = repo.get("description", "") or ""
                full = f"{name} {desc}"
                if not (is_ai(full) or is_ai(name)):
                    continue
                stars = repo.get("stargazers_count", 0)
                score = (95 if stars >= 50000 else 92 if stars >= 10000 else
                         85 if stars >= 5000 else 78 if stars >= 2000 else
                         70 if stars >= 500 else 64)
                dt = NOW_UTC
                if repo.get("pushed_at"):
                    try:
                        dt = datetime.fromisoformat(repo["pushed_at"].replace("Z", "+00:00"))
                    except Exception:
                        pass
                res.append(make_item("githubTrending", "GitHub Trending", dt,
                                     f"{name} ({stars:,}⭐)", repo.get("html_url", ""),
                                     score, desc))
        except Exception as e:
            print(f"  GitHub search '{query}' error: {e}")
    return res


# ===================== HTML 生成 =====================
def build_html(items):
    items.sort(key=lambda x: x["time"], reverse=True)
    cat_counts = {}
    for it in items:
        cat_counts[it["category"]] = cat_counts.get(it["category"], 0) + 1

    timeline_html = ""
    sessions = [
        ("morning", "00:00 - 12:00", lambda tl: tl < "12:00"),
        ("afternoon", "12:00 - 24:00", lambda tl: tl >= "12:00"),
    ]
    for sid, slabel, check in sessions:
        sitems = [it for it in items if check(it["time_label"])]
        if not sitems:
            continue
        cards = ""
        for it in sitems:
            colors = {"news": "#6c63ff", "githubTrending": "#ff8c42", "paper": "#ff6b9d"}
            labels = {"news": "NEWS", "githubTrending": "GITHUB", "paper": "PAPER"}
            c = it["category"]
            cat_color = colors.get(c, "#6c63ff")
            cat_label = labels.get(c, c.upper())
            fresh = ' <span class="fresh">●新</span>' if (it.get("time_rel") in ("刚刚", "1h前", "2h前", "3h前")) else ""
            cards += f"""
            <div class="card" data-category="{c}" data-source="{html.escape(it['source'].lower())}"
                 data-title-en="{html.escape(it['title_en'].lower())}"
                 data-title-cn="{html.escape(it['title_cn'].lower())}">
                <div class="card-time">{html.escape(it['time_label'])}<br><span class="rel">{html.escape(it.get('time_rel',''))}</span></div>
                <div class="card-body">
                    <div class="card-meta">
                        <span class="cat-tag" style="background:{cat_color}22;color:{cat_color};border:1px solid {cat_color}44">[{cat_label}]</span>
                        <span class="card-source">{html.escape(it['source'])}{fresh}</span>
                        <span class="card-score" title="AI 推荐评分">{it['score']}<span class="score-unit">%</span></span>
                    </div>
                    <div class="card-title">{html.escape(it['title_cn'])}</div>
                    <div class="card-title-en">{html.escape(it['title_en'])}</div>
                    <div class="card-summary">{html.escape(it['summary_cn'])}</div>
                    <a href="{html.escape(it['url'])}" class="card-link" target="_blank" rel="noopener">[UPLINK] → 查看原文</a>
                </div>
            </div>"""
        timeline_html += f"""
        <div class="session" id="session-{sid}">
            <div class="session-header"><div class="session-line"></div>
                <span class="session-label">LOG_SESSION: {TODAY} {slabel}</span>
                <div class="session-line"></div></div>
            <div class="cards-container">{cards}</div>
        </div>"""
    if not timeline_html:
        timeline_html = '<div class="empty-state"><div class="empty-icon">📡</div><div class="empty-text">暂无数据</div></div>'

    data_json = json.dumps(items, ensure_ascii=False, indent=2)
    sources_note = "Google News / HackerNews / HuggingFace / ArXiv / TechCrunch / The Verge / VentureBeat / 36氪 / 机器之心 / GitHub"
    html_content = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1.0">
<title>AI 时间线 | {TODAY}</title>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{--bg:#0f0f1a;--bg2:#151528;--card-bg:#191933;--card-border:#2a2a44;--card-hover:#222244;
--text:#e8e8f0;--text2:#a0a0b8;--text3:#666680;--accent:#6c63ff;--accent2:#8b83ff;
--news:#6c63ff;--github:#ff8c42;--paper:#ff6b9d;--radius:12px;
--font:'-apple-system','Noto Sans SC','PingFang SC','Microsoft YaHei',sans-serif}}
body{{font-family:var(--font);background:var(--bg);color:var(--text);min-height:100vh;line-height:1.6}}
a{{color:var(--accent2);text-decoration:none}} a:hover{{text-decoration:underline}}
.header{{background:linear-gradient(180deg,#151528 0%,var(--bg) 100%);padding:24px 20px 16px;position:sticky;top:0;z-index:100;border-bottom:1px solid var(--card-border)}}
.header-inner{{max-width:960px;margin:0 auto;display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px}}
.header-logo{{display:flex;align-items:center;gap:10px}}
.logo-icon{{width:36px;height:36px;background:linear-gradient(135deg,var(--accent),var(--accent2));border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:18px;font-weight:700;color:#fff}}
.header-title h1{{font-size:1.2rem;font-weight:600;background:linear-gradient(135deg,var(--accent),var(--accent2));-webkit-background-clip:text;-webkit-text-fill-color:transparent;line-height:1.2}}
.header-title .header-date{{font-size:.75rem;color:var(--text3)}}
.header-actions{{display:flex;align-items:center;gap:10px}}
.search-box{{position:relative}}
.search-box input{{background:var(--bg2);border:1px solid var(--card-border);border-radius:8px;padding:8px 12px 8px 32px;color:var(--text);font-size:.85rem;width:180px;outline:none;transition:border-color .2s}}
.search-box input:focus{{border-color:var(--accent)}}
.search-box input::placeholder{{color:var(--text3)}}
.search-icon{{position:absolute;left:10px;top:50%;transform:translateY(-50%);color:var(--text3);font-size:.8rem;pointer-events:none}}
.filters{{max-width:960px;margin:0 auto;padding:12px 20px;display:flex;gap:6px;flex-wrap:wrap;align-items:center}}
.filter-btn{{padding:6px 14px;border-radius:20px;border:1px solid var(--card-border);background:transparent;color:var(--text2);font-size:.78rem;cursor:pointer;transition:all .2s;font-family:var(--font)}}
.filter-btn:hover{{border-color:var(--accent);color:var(--text)}}
.filter-btn.active{{background:var(--accent);color:#fff;border-color:var(--accent)}}
.filter-count{{font-size:.7rem;color:var(--text3);margin-left:2px}}
.stats-bar{{max-width:960px;margin:0 auto;padding:0 20px 8px;display:flex;gap:12px;flex-wrap:wrap;font-size:.75rem;color:var(--text3)}}
.stat-item{{display:flex;align-items:center;gap:4px}}
.stat-dot{{width:8px;height:8px;border-radius:50%;display:inline-block}}
.session{{max-width:960px;margin:0 auto;padding:8px 20px}}
.session-header{{display:flex;align-items:center;gap:12px;margin:20px 0 12px}}
.session-line{{flex:1;height:1px;background:linear-gradient(90deg,transparent,var(--card-border),transparent)}}
.session-label{{font-size:.75rem;color:var(--text3);font-family:monospace;white-space:nowrap}}
.cards-container{{display:flex;flex-direction:column;gap:4px}}
.card{{display:flex;gap:12px;padding:12px 14px;background:var(--card-bg);border:1px solid var(--card-border);border-radius:var(--radius);transition:all .2s;cursor:default;animation:fadeIn .3s ease-out}}
.card:hover{{background:var(--card-hover);border-color:var(--accent);transform:translateX(3px)}}
.card-time{{min-width:48px;font-size:.78rem;color:var(--text3);font-family:monospace;padding-top:2px;text-align:right}}
.card-time .rel{{font-size:.62rem;color:var(--accent2)}}
.card-body{{flex:1;min-width:0}}
.card-meta{{display:flex;align-items:center;gap:8px;margin-bottom:4px;flex-wrap:wrap}}
.cat-tag{{font-size:.68rem;padding:1px 7px;border-radius:4px;font-weight:500;line-height:1.6}}
.card-source{{font-size:.72rem;color:var(--text2)}}
.fresh{{color:#ff6b9d;font-size:.62rem;font-weight:700}}
.card-score{{font-size:.85rem;font-weight:700;margin-left:auto;color:var(--accent2);font-family:monospace}}
.score-unit{{font-size:.6rem;color:var(--text3)}}
.card-title{{font-size:.95rem;font-weight:500;color:var(--text);margin-bottom:2px;line-height:1.4}}
.card-title-en{{font-size:.72rem;color:var(--text3);margin-bottom:4px;line-height:1.3;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}}
.card-summary{{font-size:.78rem;color:var(--text2);line-height:1.5;margin-bottom:6px}}
.card-link{{font-size:.72rem;color:var(--accent);font-family:monospace}}
.card-link:hover{{color:var(--accent2)}}
.empty-state{{text-align:center;padding:60px 20px}}
.empty-icon{{font-size:3rem;margin-bottom:10px}}
.empty-text{{color:var(--text3)}}
.footer{{text-align:center;padding:30px 20px;color:var(--text3);font-size:.75rem;border-top:1px solid var(--card-border);margin-top:10px}}
.footer a{{color:var(--accent2)}}
@media(max-width:640px){{.header{{padding:16px 12px 12px}}.header-inner{{flex-direction:column;align-items:flex-start}}.search-box input{{width:100%}}.header-actions{{width:100%}}.search-box{{width:100%}}.filters{{gap:4px;padding:8px 12px}}.filter-btn{{font-size:.72rem;padding:4px 10px}}.card{{padding:10px;gap:8px}}.card-time{{min-width:36px;font-size:.7rem}}.card-title{{font-size:.88rem}}.session{{padding:4px 12px}}}}
@keyframes fadeIn{{from{{opacity:0;transform:translateY(6px)}}to{{opacity:1;transform:translateY(0)}}}}
::-webkit-scrollbar{{width:6px}}::-webkit-scrollbar-track{{background:var(--bg)}}::-webkit-scrollbar-thumb{{background:var(--card-border);border-radius:3px}}::-webkit-scrollbar-thumb:hover{{background:var(--text3)}}
</style>
</head>
<body>
<header class="header"><div class="header-inner">
  <div class="header-logo"><div class="logo-icon">AI</div>
    <div class="header-title"><h1>AI 时间线</h1><div class="header-date">📅 {TDISP}</div></div></div>
  <div class="header-actions"><div class="search-box"><span class="search-icon">🔍</span>
    <input type="text" id="searchInput" placeholder="搜索标题..." autocomplete="off"></div></div>
</div></header>
<nav class="filters" id="filters">
  <button class="filter-btn active" data-filter="all">全部 <span class="filter-count">({len(items)})</span></button>
  <button class="filter-btn" data-filter="news">NEWS <span class="filter-count">({cat_counts.get('news',0)})</span></button>
  <button class="filter-btn" data-filter="githubTrending">GITHUB <span class="filter-count">({cat_counts.get('githubTrending',0)})</span></button>
  <button class="filter-btn" data-filter="paper">PAPER <span class="filter-count">({cat_counts.get('paper',0)})</span></button>
</nav>
<div class="stats-bar">
  <span class="stat-item"><span class="stat-dot" style="background:var(--news)"></span> 新闻</span>
  <span class="stat-item"><span class="stat-dot" style="background:var(--github)"></span> 开源</span>
  <span class="stat-item"><span class="stat-dot" style="background:var(--paper)"></span> 论文</span>
  <span class="stat-item">共 {len(items)} 条动态</span>
</div>
<main id="timeline">{timeline_html}</main>
<footer class="footer">
  <p>🤖 每日自动采集 · 数据来源: {sources_note}</p>
  <p>🕐 最后更新: {NOW.strftime('%H:%M')} CST · 仅收录近 {FRESH_HOURS}h 内资讯 · 由 AI 自动整理</p>
</footer>
<script>
const NEWS_DATA = {data_json};
document.addEventListener('DOMContentLoaded', function() {{
  const searchInput = document.getElementById('searchInput');
  const filterBtns = document.querySelectorAll('.filter-btn');
  const cards = document.querySelectorAll('.card');
  let activeFilter = 'all';
  function filterCards() {{
    const q = searchInput.value.toLowerCase().trim();
    let visibleCount = 0;
    cards.forEach(function(card) {{
      const cat = card.dataset.category;
      const en = card.dataset.titleEn || '';
      const cn = card.dataset.titleCn || '';
      const catMatch = activeFilter === 'all' || cat === activeFilter;
      const searchMatch = !q || en.includes(q) || cn.includes(q);
      if (catMatch && searchMatch) {{ card.style.display = 'flex'; visibleCount++; }}
      else {{ card.style.display = 'none'; }}
    }});
    document.querySelectorAll('.session').forEach(function(s){{
      let has = false;
      s.querySelectorAll('.card').forEach(function(c){{ if(c.style.display!=='none') has=true; }});
      s.style.display = has ? '' : 'none';
    }});
    filterBtns.forEach(function(btn){{
      const f = btn.dataset.filter; let c=0;
      if(f==='all'){{c=visibleCount;}} else {{cards.forEach(function(x){{if(x.dataset.category===f&&x.style.display!=='none')c++;}});}}
      const sp = btn.querySelector('.filter-count'); if(sp) sp.textContent='('+c+')';
    }});
  }}
  filterBtns.forEach(function(btn){{
    btn.addEventListener('click', function(){{
      filterBtns.forEach(function(b){{b.classList.remove('active');}});
      btn.classList.add('active'); activeFilter = btn.dataset.filter; filterCards();
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


def main():
    print("=" * 40)
    print(f"AI News 日报 v2 - {TDISP}")
    print("=" * 40)
    fetchers = [
        ("Google News", fetch_google_news),
        ("HackerNews", fetch_hn_algolia),
        ("HF Papers", fetch_hf_papers),
        ("ArXiv", fetch_arxiv),
        ("RSS Feeds", fetch_rss),
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

    # 去重: URL + 归一化标题
    seen_u, seen_t, unique = set(), set(), []
    for x in all_items:
        uk = x["url"]
        tk = re.sub(r'\W+', '', (x["title_cn"] + x["title_en"]).lower())
        if uk in seen_u or tk in seen_t:
            continue
        seen_u.add(uk); seen_t.add(tk); unique.append(x)

    print(f"\n{'='*40}\nTotal unique: {len(unique)}")
    cats = {}
    for it in unique:
        cats[it["category"]] = cats.get(it["category"], 0) + 1
    for c, n in sorted(cats.items()):
        print(f"  {c}: {n}")

    html = build_html(unique)
    with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"\n✓ docs/index.html ({len(html)} bytes)")
    with open(os.path.join(OUT, "data.json"), "w", encoding="utf-8") as f:
        f.write(build_data_json(unique))
    with open(os.path.join(OUT, f"{TODAY}.html"), "w", encoding="utf-8") as f:
        f.write(html)
    print(f"✓ docs/{TODAY}.html")
    print(f"\n✅ Done! https://hot124588.github.io/ai-news/")


if __name__ == "__main__":
    main()
