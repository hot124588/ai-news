python
    #!/usr/bin/env python3
    import json, os, re, urllib.request, urllib.parse
    from datetime import datetime, timezone, timedelta
    from html import escape

    OUT = "docs"
    os.makedirs(OUT, exist_ok=True)
    CST = timezone(timedelta(hours=8))
    NOW = datetime.now(CST)
    TODAY = NOW.strftime("%Y-%m-%d")
    TDISP = NOW.strftime("%Y年%m月%d日")
    AI_KW = ["ai","artificial intelligence","machine learning","deep learning",
        "llm","gpt","openai","claude","anthropic","gemini","大模型","人工智能",
        "智能体","agent","rag","stable diffusion","多模态","transformer",
        "hugging face","ai芯片","gpu","nvidia","算力","开源模型"]

    def fet(url):
        try:
            r = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(r, timeout=15) as f:
                return json.loads(f.read().decode("utf-8","replace"))
        except: return None

    def fet_text(url):
        try:
            r = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(r, timeout=15) as f:
                return f.read().decode("utf-8","replace")
        except: return None

    def translate(text):
        if not text or len(text)<3: return text
        try:
            url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q=" + urllib.parse.quote(text[:2000])
            with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=8) as f:
                return json.loads(f.read().decode())[0][0][0]
        except: return text

    def is_ai(t):
        t = t.lower()
        return any(k in t for k in AI_KW)

    def fetch_hn():
        res = []
        ids = fet("https://hacker-news.firebaseio.com/v0/topstories.json")
        if not ids: return res
        for i in ids[:50]:
            it = fet(f"https://hacker-news.firebaseio.com/v0/item/{i}.json")
            if it and it.get("title") and is_ai(it["title"]):
                t = it["title"][:120]
                res.append({"title_cn": translate(t),"title_en": t,
                    "url": it.get("url", f"https://news.ycombinator.com/item?id={i}"),
                    "src": "HackerNews","desc": f"👍 {it.get('score', 0)} 分"})
                if len(res) >= 12: break
        return res

    def fetch_show():
        res = []
        ids = fet("https://hacker-news.firebaseio.com/v0/showstories.json")
        if not ids: return res
        for i in ids[:30]:
            it = fet(f"https://hacker-news.firebaseio.com/v0/item/{i}.json")
            if it and it.get("title") and is_ai(it["title"]):
                t = it["title"][:120]
                res.append({"title_cn": translate(t),"title_en": t,
                    "url": it.get("url", f"https://news.ycombinator.com/item?id={i}"),
                    "src": "Show HN","desc": ""})
                if len(res) >= 6: break
        return res

    def build_html(items):
        icons = {"HackerNews":"📰", "Show HN":"🛠️"}
        sec = ""
        for src in ["HackerNews", "Show HN"]:
            its = [x for x in items if x["src"] == src]
            if not its: continue
            ih = ""
            for x in its:
                en = f'<p class="en">{escape(x["title_en"])}</p>' if x.get("title_en") else ""
                ih += f'<a href="{escape(x["url"])}" class="ni"><h3>{escape(x["title_cn"])}</h3>{en}</a>'
            sec += f'<section><h2>{icons.get(src,"")} {src}</h2><div class="nl">{ih}</div></section>'
        return f'''<!DOCTYPE html>
    <html lang="zh-CN">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
    <title>AI 新闻日报 — {TODAY}</title>
    <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{font-family:-apple-system,"Noto Sans SC","Microsoft YaHei",sans-serif;background:#0f0f1a;color:#e8e8f0;line-height:1.6}}
    .hd{{padding:36px 20px 28px;text-align:center;border-bottom:1px solid #2a2a44}}
    h1{{font-size:1.8rem;background:linear-gradient(135deg,#6c63ff,#8b83ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
    .ds{{color:#8888aa;margin-top:6px;font-size:.9rem}}
    .dt{{display:inline-flex;align-items:center;gap:10px;margin-top:14px;padding:6px 18px;background:#1a1a2e;border:1px solid #2a2a44;border-radius:24px;font-size:.9rem}}
    .c{{background:#6c63ff;color:#fff;padding:2px 10px;border-radius:12px;font-size:.8rem;margin-left:6px}}
    .ct{{max-width:860px;margin:0 auto;padding:20px}}
    section{{margin-bottom:24px}}
    h2{{font-size:1.1rem;color:#8b83ff;padding-bottom:8px;border-bottom:2px solid #2a2a44;margin-bottom:12px}}
    .nl{{display:flex;flex-direction:column;gap:6px}}
    .ni{{display:block;padding:10px 16px;background:#1a1a2e;border:1px solid #2a2a44;border-radius:10px;text-decoration:none;color:inherit;transition:all .2s}}
    .ni:hover{{background:#22223a;border-color:#6c63ff;transform:translateX(4px)}}
    .ni h3{{font-size:.95rem;font-weight:500}}
    .en{{font-size:.75rem;color:#666688;margin-top:3px}}
    .ft{{margin-top:32px;padding:24px 20px;border-top:1px solid #2a2a44;text-align:center;color:#8888aa;font-size:.85rem}}
    </style></head>
    <body>
    <header class="hd"><h1>AI 新闻日报</h1><p class="ds">每日AI资讯 · 自动翻译中文</p><div class="dt"><span>📅 {TDISP}</span><span class="c">{len(items)} 条</span></div></header>
    <main class="ct">{sec}</main>
    <footer class="ft"><p>🤖 每日自动更新 · 英文标题已自动翻译</p></footer>
    </body></html>'''

    def main():
        print("🚀 AI News Daily - fetching...")
        all_items = []
        for name, fn in [("HackerNews", fetch_hn), ("Show HN", fetch_show)]:
            print(f"  {name}...", end=" ")
            try:
                items = fn()
                all_items.extend(items)
                print(f"{len(items)} items")
            except Exception as e:
                print(f"FAIL: {e}")
        seen = set()
        unique = []
        for x in all_items:
            if x["title_cn"] not in seen:
                seen.add(x["title_cn"]); unique.append(x)
        print(f"\n  Total: {len(unique)} items")
        html = build_html(unique)
        with open(os.path.join(OUT, "index.html"), "w", encoding="utf-8") as f: f.write(html)
        with open(os.path.join(OUT, f"{TODAY}.html"), "w", encoding="utf-8") as f: f.write(html)
        print("  Done!  https://hot124588.github.io/ai-news/")

    if name == "main":
        main()
