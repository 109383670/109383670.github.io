---
_organized: true
---
# 报告画廊 · AI 报告静态展示站

一个零构建、易部署、易扩展的**静态网站**，专门用于展示 AI 生成的报告类网页。深色科技风界面，支持 **HTML 报告**（自包含网页）和 **Markdown 报告**（站内阅读器渲染）两种类型。

加一份报告 = **丢一个文件 + 在 JSON 里加一行**。无需改动任何代码。

---

## ✨ 特性

- 🚀 **零构建** — 纯 HTML/CSS/JS，无 npm、无打包步骤，push 即上线
- 📦 **两种报告类型** — HTML 报告新标签页打开；Markdown 报告站内精排阅读
- 🔍 **搜索 / 标签过滤 / 排序** — 内置实时搜索与多维度筛选
- 🎨 **深色科技风** — 渐变光晕、玻璃拟态卡片、霓虹强调、微动效
- 📱 **响应式** — 桌面 / 平板 / 手机自适应
- 🔧 **零代码扩展** — 只动 `manifest.json` + 丢文件即可加新报告
- 🤖 **自动同步** — 内置 `sync_manifest.py`，自动发现报告并提取标题/摘要/标签，支持 git 钩子全自动
- 🌐 **离线友好** — Markdown 渲染依赖本地打包，不依赖 CDN

---

## 📁 目录结构

```
reports-gallery/
├─ index.html              # 网站入口（画廊 + 阅读器双视图）
├─ assets/
│  ├─ style.css            # 样式（深色科技风）
│  ├─ app.js               # 应用逻辑（加载/渲染/路由/搜索）
│  └─ vendor/
│     └─ marked.min.js     # Markdown 解析库（本地打包）
├─ reports/
│  ├─ manifest.json        # ★ 报告清单（加报告只改这里）
│  ├─ sample-report/       # 示例：HTML 报告
│  │  ├─ index.html
│  │  └─ thumbnail.svg
│  └─ sample-markdown/     # 示例：Markdown 报告
│     ├─ report.md
│     └─ thumbnail.svg
├─ tools/
│  └─ sync_manifest.py     # ★ 自动同步清单（扫描/提取元数据/git 钩子）
├─ README.md
├─ .gitignore
└─ LICENSE
```

---

## 🚀 本地预览

因为网站通过 `fetch` 加载 `manifest.json`，必须通过 HTTP 服务器访问（直接双击 `index.html` 即 `file://` 协议会无法加载）。

**方式一：Python（推荐，系统自带）**

```bash
cd reports-gallery
python3 -m http.server 8000
```

浏览器打开 <http://localhost:8000>

**方式二：Node.js**

```bash
npx serve reports-gallery
# 或
npx http-server reports-gallery -p 8000
```

**方式三：VS Code**

安装 *Live Server* 扩展，右键 `index.html` → *Open with Live Server*。

---

## 🌍 部署到 GitHub Pages（推荐）

### 第 1 步：创建 GitHub 仓库

1. 登录 GitHub → 右上角 `+` → **New repository**
2. 仓库名建议用 `reports-gallery`（或任意名）
3. 选 **Public**（免费账户 Pages 需要 Public）
4. **不要**勾选 "Add a README"（本目录已有）
5. 点击 **Create repository**

### 第 2 步：把代码推上去

在本目录下执行（把 `YOUR-USERNAME` 换成你的 GitHub 用户名）：

```bash
cd reports-gallery
git init
git add .
git commit -m "初始化报告画廊"
git branch -M main
git remote add origin https://github.com/YOUR-USERNAME/reports-gallery.git
git push -u origin main
```

> 若本地未配置 git 身份，先执行：
> ```bash
> git config --global user.name "你的名字"
> git config --global user.email "your@email.com"
> ```

### 第 3 步：开启 GitHub Pages

1. 打开仓库页面 → **Settings** → 左侧 **Pages**
2. **Source** 选 `Deploy from a branch`
3. **Branch** 选 `main`，文件夹选 `/ (root)`
4. 点击 **Save**
5. 等待 1~2 分钟，页面顶部会显示你的网站地址：

   ```
   https://YOUR-USERNAME.github.io/reports-gallery/
   ```

### 第 4 步：以后更新网站

只要改完内容执行 `git push`，GitHub Pages 会自动重新部署。

> **想用自定义域名？** 在 Pages 设置里填 Custom domain，并在你的 DNS 加一条 CNAME 指向 `YOUR-USERNAME.github.io`。

---

## ☁️ 备选：部署到 Netlify / Vercel / Cloudflare Pages

这些平台同样支持，且通常更快、支持自定义域名更方便：

1. 把仓库连接到平台（或直接拖拽本目录）
2. 构建命令留空、输出目录填 `.`（或根目录）
3. 部署完成即获得一个 `*.netlify.app` / `*.vercel.app` 地址

---

## 🔧 自动同步报告清单（推荐）

手动维护 `manifest.json` 太繁琐？本站内置 **自动同步工具** `tools/sync_manifest.py`：
把报告文件丢进 `reports/`，运行一条命令，它会**自动发现文件、提取标题/摘要/标签/日期/缩略图，并合并进 `manifest.json`**——你完全不用碰 JSON。

```bash
python3 tools/sync_manifest.py
```

> 纯 Python 标准库，无需 pip 安装任何依赖。Python 3.7+ 即可。

### 工作机制

| 情况 | 行为 |
|------|------|
| **新文件** | 自动新增条目，逐字段提取元数据 |
| **已有条目** | 只补全**缺失**字段，**绝不覆盖你手填过的内容** |
| **文件被删除** | 默认保留条目（防误删）；加 `--prune` 清理 |

**元数据来源优先级**（高 → 低）：

1. **Markdown 的 YAML frontmatter**（文件顶部 `---` 包裹的头部）
2. **HTML 的 `<meta>` 标签**（`title` / `description` / `keywords`）
3. **内容启发式**：首个 `# H1` 作标题、首个实质段落作摘要、正文里的 `#标签`
4. **文件信息**：`同级 thumbnail.*` 作缩略图、`文件修改时间` 作日期

### 在报告里写明元数据（可选，提取更准）

**Markdown** —— 在文件最顶部加 frontmatter：

```markdown
---
title: 2026 Q3 行业洞察报告
date: 2026-09-15
tags: ["行业洞察", "Q3"]
summary: 一两句话摘要，覆盖自动提取。
---

# 正文从这里开始……
```

**HTML** —— 在 `<head>` 里加 meta 标签：

```html
<title>报告标题</title>
<meta name="description" content="一两句话摘要。">
<meta name="keywords" content="标签1, 标签2, 标签3">
```

> 即使不写这些，工具也会用启发式自动提取；写了会更准确。正文里出现的 `#标签`（如 `#AI #趋势`）也会被识别。

### 命令一览

```bash
python3 tools/sync_manifest.py              # 同步并写入（默认）
python3 tools/sync_manifest.py --dry-run    # 只预览改动，不写盘
python3 tools/sync_manifest.py --force      # 强制按内容重新提取所有字段（覆盖手填）
python3 tools/sync_manifest.py --prune      # 清理已删除文件对应的条目
python3 tools/sync_manifest.py --watch      # 持续监听 reports/ 自动同步（开发用）
python3 tools/sync_manifest.py --install-hook    # 安装 git pre-commit 钩子
python3 tools/sync_manifest.py --uninstall-hook  # 卸载钩子
```

### 全自动：git 钩子（最省心）

```bash
git init                              # 若尚未初始化
python3 tools/sync_manifest.py --install-hook
```

之后**每次 `git commit` 前会自动同步** `manifest.json` 并纳入提交。你只需把报告文件丢进 `reports/`、`git add`、`git commit`，清单永远是新的。卸载用 `--uninstall-hook`。

### 全自动：监听模式（本地开发用）

```bash
python3 tools/sync_manifest.py --watch
```

工具会每 2 秒检查一次 `reports/`，检测到文件变动就自动同步。适合一边放报告一边在浏览器预览效果。

---

## ➕ 如何添加新报告

> 💡 **推荐先用上面的自动同步工具**，几乎不用手动写 JSON。下面两节适合想精细控制、或想了解字段含义的情况。

### 方式 A：添加 HTML 报告（适合视觉丰富、交互性强的页面）

1. **把报告放进 `reports/` 目录**

   - 如果报告是一个独立 HTML 文件：直接放进 `reports/`，例如 `reports/my-report.html`
   - 如果报告是一个含资源（CSS/JS/图片）的文件夹：把整个文件夹放进 `reports/`，入口文件命名为 `index.html`，例如：
     ```
     reports/
     └─ my-report/
        ├─ index.html
        ├─ style.css
        └─ chart.js
     ```

2. **在 `reports/manifest.json` 的 `reports` 数组追加一条记录：**

   ```json
   {
     "id": "my-report",
     "type": "html",
     "title": "我的报告标题",
     "summary": "一两句话简介，会显示在卡片上。",
     "tags": ["标签1", "标签2"],
     "date": "2026-06-22",
     "path": "reports/my-report/index.html",
     "thumbnail": "reports/my-report/thumbnail.png"
   }
   ```

3. 保存，刷新页面即可看到新卡片。

> **关于缩略图**：`thumbnail` 字段可选。支持 PNG/JPG/SVG。若省略，卡片会显示一个带标题首字的渐变占位图。

### 方式 B：添加 Markdown 报告（适合文字为主的分析文档）

1. **把 `.md` 文件放进 `reports/` 目录**，例如 `reports/llm-survey.md`

2. **在 `manifest.json` 追加一条 `type` 为 `markdown` 的记录：**

   ```json
   {
     "id": "llm-survey",
     "type": "markdown",
     "title": "大语言模型调研报告",
     "summary": "对比当前主流 LLM 的能力与成本。",
     "tags": ["AI", "调研"],
     "date": "2026-06-22",
     "path": "reports/llm-survey.md",
     "thumbnail": "reports/llm-survey/thumbnail.svg"
   }
   ```

3. 保存，刷新即可。Markdown 会在站内阅读器中渲染为排版精良的文档（支持标题、列表、表格、代码块、引用、图片等）。

> **自动类型推断**：如果省略 `type` 字段，程序会根据 `path` 后缀自动判断（`.md` → markdown，其他 → html）。但建议显式写明，更清晰。

---

## 📝 manifest.json 字段说明

| 字段 | 必填 | 说明 |
|------|------|------|
| `id` | ✅ | 报告唯一标识，用于阅读器路由（URL `#/report/<id>`）。**不可重复**，建议用英文短横线 |
| `type` | 建议 | `html` 或 `markdown`。省略时按 `path` 后缀推断 |
| `title` | ✅ | 卡片与阅读器标题 |
| `summary` | 可选 | 卡片简介，建议 1~2 句 |
| `tags` | 可选 | 标签数组，用于过滤。如 `["市场", "2026"]` |
| `date` | 可选 | 发布日期，格式 `YYYY-MM-DD`，用于排序显示 |
| `path` | ✅ | 报告文件相对路径（相对网站根目录） |
| `thumbnail` | 可选 | 缩略图路径。PNG/JPG/SVG。省略则显示渐变占位 |

---

## 🎨 自定义主题

所有颜色变量集中在 `assets/style.css` 顶部的 `:root`：

```css
:root {
  --accent-1: #6366f1;   /* 主强调色（靛蓝） */
  --accent-2: #06b6d4;   /* 副强调色（青） */
  --accent-3: #a855f7;   /* 渐变末端（紫） */
  --bg-base: #0a0e1a;    /* 页面背景 */
  /* ...更多变量见源文件 */
}
```

**换主色调**：把 `--accent-1` 改成你喜欢的颜色即可全局生效。

**换站点名称**：编辑 `index.html` 里 `<span>报告画廊</span>` 和 `<title>` 标签，以及顶部导航的品牌字母 `R`。

---

## 🛡 防止搜索引擎收录与爬虫爬取

本站已内置多重防收录措施，默认对搜索引擎和 AI 训练爬虫关闭。

### 已启用的保护

| 措施 | 位置 | 作用 |
|------|------|------|
| `robots.txt` | 网站根目录 | 用 `Disallow: /` 屏蔽所有遵守协议的爬虫，并单独显式屏蔽 20+ 个 AI 训练爬虫（GPTBot、ClaudeBot、CCBot、Google-Extended 等） |
| `<meta name="robots">` | `index.html` 及示例报告 | 页面级声明 `noindex, nofollow, noarchive, noimageindex, nosnippet`，即使被访问也不会被收录、不缓存快照、不索引图片 |
| `<meta name="googlebot">` | 同上 | 针对 Google 单独声明，确保 Google 搜索与 Gemini 训练都不收录 |

### 如何对新加的报告生效

**Markdown 报告**：自动生效——内容由站内阅读器在 `index.html` 中渲染，而 `index.html` 已声明 noindex。

**HTML 报告（你新加的自包含网页）**：**需要在报告自己的 `<head>` 里手动加一行**，因为它们是独立页面：

```html
<meta name="robots" content="noindex, nofollow, noarchive, noimageindex, nosnippet">
```

### 诚实说明：这些措施能防到什么程度？

- ✅ **对遵守协议的爬虫有效**：Google、Bing、OpenAI、Anthropic、Common Crawl 等主流方通常会遵守 `robots.txt` 和 meta 标签。这覆盖了绝大部分正规搜索引擎和 AI 训练数据来源。
- ❌ **对恶意爬虫无效**：数据贩卖商、不守规矩的抓取方会直接忽略 `robots.txt`。这些手段是"声明意愿"，不是技术屏障。
- ⚠ **已收录内容无法立即删除**：若之前已开放收录，需在 Google Search Console / Bing Webmaster Tools 提交移除请求。

### 需要更强的访问控制？

如果你的报告确实敏感、需要真正的访问鉴权，静态站本身做不到，需借助托管层：

- **Netlify / Vercel 的密码保护 / 身份认证**（Pro 套餐）
- **Cloudflare Access**（在 CDN 层加登录/邮箱白名单）
- **私有 GitHub 仓库**（免费 GitHub Pages 仅支持 Public；私有需 GitHub Pro/Team）
- 自建服务器 + Basic Auth / IP 白名单

### 改变主意：希望被收录？

删除 `robots.txt`（或改为 `Allow: /`）+ 删除 HTML 里的 noindex meta 标签，并提交到 [Google Search Console](https://search.google.com/search-console) 即可。

---

## ❓ 常见问题

**Q：打开页面是空白 / 卡在"加载中"？**
A：你可能在用 `file://` 协议直接打开了文件。请用本地 HTTP 服务器预览（见上文「本地预览」）。

**Q：Markdown 报告里的图片显示不出来？**
A：图片路径是相对**网站根目录**解析的，请用相对站点根的路径（如 `reports/my-report/img.png`），或使用绝对 URL。

**Q：修改了 `manifest.json` 但页面没更新？**
A：浏览器缓存。强制刷新（Cmd/Ctrl + Shift + R），或在开发者工具里关闭缓存。代码已加 `cache: "no-store"` 尽量避免此问题。

**Q：可以用子目录部署吗（如 `username.github.io/reports-gallery/`）？**
A：可以。本站所有路径都用相对路径，天然支持子路径部署，无需额外配置。

**Q：怎么让报告支持数学公式？**
A：可在 `index.html` 里额外引入 KaTeX/MathJax，并在 `app.js` 的渲染回调里调用渲染。默认不内置以保持轻量。

---

## 📄 许可证

MIT License — 你可以自由使用、修改、分发。`marked.js`（位于 `assets/vendor/`）同样采用 MIT 许可。
