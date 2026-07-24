 python
    #!/usr/bin/env python3
    import json, os, re, urllib.request, urllib.parse
    from datetime import datetime, timezone, timedelta
    from html import escape

    OUTPUT_DIR = "docs"
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    CST = timezone(timedelta(hours=8))
    TODAY = datetime.now(CST).strftime("%Y-%m-%d")
    TODAY_DISPLAY = datetime.now(CST).strftime("%Y年%m月%d日")

    AI_关键词 = ["ai","artificial intelligence","machine learning","deep learning","llm",
        "gpt","openai","claude","anthropic","gemini","大模型","人工智能","智能体",
        "agent","rag","stable diffusion","多模态","transformer","hugging face",
        "ai芯片","gpu","nvidia","算力","开源模型","ai coding","cursor","copilot"]

    def 取json(url):
        try:
            r = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(r, timeout=15) as f:
                return json.loads(f.read().decode("utf-8","replace"))
        except: return None

    def 取文本(url):
        try:
            r = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
            with urllib.request.urlopen(r, timeout=15) as f:
                return f.read().decode("utf-8","replace")
        except: return None

    def 翻译(text):
        if not text or len(text)<3: return text
        try:
            url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q="+urllib.parse.quote(text[:2000])
            with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=8) as f:
                return json.loads(f.read().decode())[0][0][0]
        except: return text

    def 是AI相关(t):
        t = t.lower()
        return any(k in t for k in AI_关键词)

    def 抓HN():
        r = []
        ids = 取json("https://hacker-news.firebaseio.com/v0/topstories.json")
        if not ids: return r
        for i in ids[:50]:
            it = 取json(f"https://hacker-news.firebaseio.com/v0/item/{i}.json")
            if it and it.get("title") and 是AI相关(it["title"]):
                t = it["title"][:120]
                r.append({"title":翻译(t),"en":t,"url":it.get("url",f"https://news.ycombinator.com/item?id={i}"),"src":"HackerNews","desc":f"👍 {it.get('score',0)} 分"})
                if len(r)>=12: break
        return r

    def 抓SH():
        r = []
        ids = 取json("https://hacker-news.firebaseio.com/v0/showstories.json")
        if not ids: return r
        for i in ids[:30]:
            it = 取json(f"https://hacker-news.firebaseio.com/v0/item/{i}.json")
            if it and it.get("title") and 是AI相关(it["title"]):
                t = it["title"][:120]
                r.append({"title":翻译(t),"en":t,"url":it.get("url",f"https://news.ycombinator.com/item?id={i}"),"src":"Show HN","desc":""})
                if len(r)>=6: break
        return r

    def 生成HTML(all):
        ico = {"HackerNews":"📰","Show HN":"🛠️"}
        cards = ""
        for s in ["HackerNews","Show HN"]:
            its = [x for x in all if x["src"]==s]
            if not its: continue
            items = ""
            for x in its:
                en = f'<p class="en">{escape(x["en"])}</p>' if x.get("en") else ""
                items += f'<a href="{escape(x["url"])}" class="ni"><h3>{escape(x["title"])}</h3>{en}</a>'
            cards += f'<section><h2>{ico.get(s,"")} {s}</h2><div class="nl">{items}</div></section>'
        return f'''<!DOCTYPE html>
    <html lang="zh-CN">
    <head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0">
    <title>AI 新闻日报 — {TODAY}</title>
    <style>
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{font-family:-apple-system,"Noto Sans SC","Microsoft YaHei",sans-serif;background:#0f0f1a;color:#e8e8f0;line-height:1.6}}
    .header{{padding:36px 20px 28px;text-align:center;border-bottom:1px solid #2a2a44}}
    h1{{font-size:1.8rem;background:linear-gradient(135deg,#6c63ff,#8b83ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent}}
    .desc{{color:#8888aa;margin-top:6px;font-size:.9rem}}
    .date{{display:inline-flex;align-items:center;gap:10px;margin-top:14px;padding:6px 18px;background:#1a1a2e;border:1px solid #2a2a44;border-radius:24px;font-size:.9rem}}
    .cnt{{background:#6c63ff;color:#fff;padding:2px 10px;border-radius:12px;font-size:.8rem;margin-left:6px}}
    .c{{max-width:860px;margin:0 auto;padding:20px}}
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
    <header class="header"><h1>AI 新闻日报</h1><p class="desc">每日AI资讯 · 中文翻译</p><div class="date"><span>📅 {TODAY_DISPLAY}</span><span class="cnt">{len(all)} 条</span></div></header>
    <main class="c">{cards}</main>
    <footer class="ft"><p>🤖 每日自动更新</p></footer>
    </body></html>'''

    def main():
        print("🚀 开始抓取...")
        all = []
        for name,fn in [("HackerNews",抓HN),("Show HN",抓SH)]:
            print(f"  {name}...",end=" ")
            try:
Exception in thread Thread-727 (_readerthread):
Traceback (most recent call last):
  File "C:\Users\Administrator\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\Lib\threading.py", line 1075, in _bootstrap_inner
                items = fn()
                all.extend(items)
                print(f"{len(items)} 条")
            except Exception as e: print(f"失败: {e}")
        uniq = []
        seen = set()
        for x in all:
            if x["title"] not in seen: seen.add(x["title"]); uniq.append(x)
        print(f"\n共 {len(uniq)} 条")
        html = 生成HTML(uniq)
        with open(os.path.join(OUTPUT_DIR,"index.html"),"w",encoding="utf-8") as f: f.write(html)
        with open(os.path.join(OUTPUT_DIR,f"{TODAY}.html"),"w",encoding="utf-8") as f: f.write(html)
        print("✅ 完成")

    if name == "main": main()


  ┊ 💻 preparing terminal…
    self.run()
  File "C:\Users\Administrator\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\Lib\threading.py", line 1012, in run
    self._target(*self._args, **self._kwargs)
  File "C:\Users\Administrator\AppData\Roaming\uv\python\cpython-3.12-windows-x86_64-none\Lib\subprocess.py", line 1599, in _readerthread
    buffer.append(fh.read())
