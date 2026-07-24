#!/usr/bin/env python3
import json, os, re, urllib.request, urllib.parse
from datetime import datetime, timezone, timedelta
from html import escape
OUT = "docs"; os.makedirs(OUT, exist_ok=True)
CST = timezone(timedelta(hours=8))
NOW = datetime.now(CST)
TODAY = NOW.strftime("%Y-%m-%d")
TDISP = NOW.strftime("%Y年%m月%d日")
AI_KW = ["ai","artificial intelligence","machine learning","deep learning","llm","gpt","openai","claude","anthropic","gemini","大模型","人工智能","智能体","agent","rag","stable diffusion","多模态","transformer","hugging face","ai芯片","gpu","nvidia","算力","开源模型"]
def fet(url):
try:
r = urllib.request.Request(url, headers={"User-Agent":"Mozilla/5.0"})
with urllib.request.urlopen(r, timeout=15) as f:
return json.loads(f.read().decode("utf-8","replace"))
except: return None
def translate(text):
if not text or len(text)<3: return text
try:
url = "https://translate.googleapis.com/translate_a/single?client=gtx&sl=en&tl=zh-CN&dt=t&q="+urllib.parse.quote(text[:2000])
with urllib.request.urlopen(urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0"}),timeout=8) as f:
return json.loads(f.read().decode())[0][0][0]
except: return text
def is_ai(t):
t=t.lower(); return any(k in t for k in AI_KW)
def fetch_hn():
res=[]; ids=fet("https://hacker-news.firebaseio.com/v0/topstories.json")
if not ids: return res
for i in ids[:50]:
it=fet(f"https://hacker-news.firebaseio.com/v0/item/{i}.json")
if it and it.get("title") and is_ai(it["title"]):
t=it["title"][:120]; res.append({"tc":translate(t),"te":t,"u":it.get("url",f"https://news.ycombinator.com/item?id={i}"),"s":"HN"})
if len(res)>=12: break
return res
def fetch_sh():
res=[]; ids=fet("https://hacker-news.firebaseio.com/v0/showstories.json")
if not ids: return res
for i in ids[:30]:
it=fet(f"https://hacker-news.firebaseio.com/v0/item/{i}.json")
if it and it.get("title") and is_ai(it["title"]):
t=it["title"][:120]; res.append({"tc":translate(t),"te":t,"u":it.get("url",f"https://news.ycombinator.com/item?id={i}"),"s":"SH"})
if len(res)>=6: break
return res
def html(items):
s=""; I={"HN":"📰 HackerNews","SH":"🛠️ Show HN"}
for k in["HN","SH"]:
its=[x for x in items if x["s"]==k]
if not its: continue
ih=""
for x in its:
e=f'<p class="e">{x["te"]}</p>'if x.get("te")else""
ih+=f'<a href="{x["u"]}" class="n"><h3>{x["tc"]}</h3>{e}</a>'
s+=f'<section><h2>{I[k]}</h2><div class="l">{ih}</div></section>'
return f'<!DOCTYPE html><html lang="zh-CN"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1.0"><title>AI日报{TODAY}</title><style>body{{font-family:-apple-system,"Noto Sans SC",sans-serif;background:#0f0f1a;color:#e8e8f0;max-width:800px;margin:0 auto;padding:20px}}h1{{text-align:center;background:linear-gradient(135deg,#6c63ff,#8b83ff);-webkit-background-clip:text;-webkit-text-fill-color:transparent;font-size:1.8rem}}.d{{text-align:center;color:#888;margin:4px 0 20px}}h2{{color:#8b83ff;border-bottom:2px solid #2a2a44;padding-bottom:8px}}.l{{display:flex;flex-direction:column;gap:6px}}.n{{display:block;padding:10px 16px;background:#1a1a2e;border:1px solid #2a2a44;border-radius:10px;text-decoration:none;color:inherit}}a:hover{{border-color:#6c63ff;transform:translateX(4px)}}.n h3{{margin:0;font-size:.95rem;font-weight:500}}.e{{font-size:.75rem;color:#666;margin-top:3px}}.f{{text-align:center;color:#888;margin-top:40px;font-size:.85rem}}</style></head><body><h1>AI 新闻日报</h1><p class="d">📅 {TDISP} · 自动翻译中文</p>{s}<p class="f">🤖 每日自动更新 · 英文已自动翻译</p></body></html>'
def main():
print("Fetching..."); al=[]
for n,f in[("HN",fetch_hn),("SH",fetch_sh)]:
try: it=f(); al.extend(it); print(f"  {n}: {len(it)}")
except: print(f"  {n}: FAIL")
uq=[];se=set()
for x in al:
if x["tc"] not in se: se.add(x["tc"]); uq.append(x)
print(f"Total: {len(uq)}")
h=html(uq)
with open("docs/index.html","w",encoding="utf-8") as f: f.write(h)
with open(f"docs/{TODAY}.html","w",encoding="utf-8") as f: f.write(h)
print("Done! https://hot124588.github.io/ai-news/")
if name=="main": main()
