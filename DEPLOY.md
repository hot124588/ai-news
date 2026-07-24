# 🚀 一键部署指南

> 全程在 GitHub 网页上操作，不需要装任何软件，不需要命令行。

---

## 第一步：创建仓库

1. 打开 https://github.com/new
2. **Repository name** 填：`ai-news`
3. **Public**（公开）
4. 其他默认，点 **Create repository**

## 第二步：上传文件

1. 创建好仓库后，点 **uploading an existing file**（上传已有文件）
   - 或者点页面上的 **Add file → Upload files**
2. 把下面这些文件从 `E:/CFOK/2026-07-24/ai-news/` 拖进去：
   - `.github/workflows/daily-news.yml`
   - `scripts/fetch-news.py`
   - `README.md`
   - `.gitignore`
3. 点 **Commit changes**

## 第三步：启用 GitHub Pages

1. 进入仓库 **Settings → Pages**
2. **Source** 选 **Deploy from a branch**
3. **Branch** 选 `gh-pages` → `/ (root)` → **Save**
4. 等2分钟，页面会显示：
   ```
   Your site is live at https://hot124588.github.io/ai-news/
   ```

## 第四步：手动跑一次看看效果

1. 点仓库顶部的 **Actions** 标签
2. 左侧点 **🌤️ AI 新闻日报 — 每日自动更新**
3. 点右侧 **Run workflow → Run workflow**
4. 等几分钟，绿色的 ✅ 出现就说明成功了
5. 打开 https://hot124588.github.io/ai-news/ 看效果

## 第五步：之后每天自动更新

配置好后就不用管了，每天 **北京时间 08:00** 自动抓取最新AI新闻并更新页面。

## 如果出问题

1. 去 **Actions** 标签看运行日志，哪一步红了鼠标点进去看报错
2. 常见问题：网络超时（GitHub Actions 连国内网站慢），多跑一次就好

## 文件结构说明

```
ai-news/
├── .github/workflows/
│   └── daily-news.yml    ← GitHub Action 自动任务（每天8点跑）
├── scripts/
│   └── fetch-news.py     ← Python 抓取脚本（抓新闻+生成页面）
├── README.md             ← 项目说明
└── .gitignore
```
