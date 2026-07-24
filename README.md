# 🤖 AI 新闻日报

每日AI资讯自动聚合。每天多次自动抓取 Google News、HackerNews、GitHub Trending、HuggingFace / ArXiv 论文、36氪、TechCrunch 等中英文来源的AI相关新闻，生成美观的静态日报页面。

## 每日更新

每天自动运行 **4 次**（北京时间 08:00 / 14:00 / 20:00 / 02:00），打开即看最新AI资讯。

[🌐 访问 AI 日报 →](https://hot124588.github.io/ai-news/)

## 数据来源

| 来源 | 类型 | 内容 |
|------|------|------|
| Google News RSS | 实时资讯 | 中/英多关键词聚合的 AI 快讯（主源，最稳定） |
| HackerNews (Algolia) | 国际社区 | 按时间排序的最新 AI 讨论（非仅 Top） |
| GitHub Trending | 开源项目 | AI/ML 热门趋势仓库 |
| HuggingFace Daily Papers | 论文 | 每日精选 AI 论文 |
| ArXiv | 论文 | cs.AI / CL / CV / LG 最新研究 |
| 36氪 | 中文媒体 | 国内 AI 行业动态 |
| TechCrunch / The Verge / VentureBeat / Ars Technica | 英文媒体 | 国际 AI 科技报道 |

> 注：机器之心 RSS 与 IT之家 已失效（404 / 重定向到 HTML 页），已从抓取列表移除；新增 Google News、HuggingFace Daily Papers、ArXiv、VentureBeat、Ars Technica 等更可靠、更新鲜的源。

## 特性

- **48 小时新鲜度过滤**：自动剔除旧闻，只留近两天的资讯
- **真实内容摘要**：抓取正文摘要，而非仅截断标题
- **相对时间显示**：「3 小时前」+ ●新 标记，一眼看出新鲜度
- **中英文混合源**：中文源为主、英文源补充，翻译失败自动兜底

## 技术栈

- Python 脚本（`scripts/fetch-news.py`）→ 抓取 + 生成静态 HTML
- GitHub Actions → 定时自动运行（每天 4 次）
- GitHub Pages → 免费托管
- **零成本**：无需服务器、无需 API Key

## 部署方法

见下方「一键部署」步骤。
 
