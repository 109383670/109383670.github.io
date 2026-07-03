#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
============================================================================
 报告清单自动同步工具  ·  tools/sync_manifest.py
============================================================================
 扫描 reports/ 目录，自动发现报告文件（.md / .html），提取元数据，
 并与 reports/manifest.json 智能合并：

   • 新文件 → 自动新增条目，自动提取 标题/摘要/标签/日期/缩略图
   • 已有条目 → 只补全【缺失】字段，绝不覆盖你手动填过的内容
       （加 --force 可强制按文件内容重新提取并覆盖）
   • 已删除的文件 → 默认保留条目；加 --prune 清理掉

 元数据来源优先级（高 → 低）：
   1. Markdown 的 YAML frontmatter（--- 包裹的头部）
   2. HTML 的 <meta> 标签（title / description / keywords）
   3. 内容启发式：首个 H1 / 首个段落 / 正文 #标签
   4. 文件修改时间（date）、同级 thumbnail.* （缩略图）

 用法：
   python3 tools/sync_manifest.py             # 同步并写入（默认）
   python3 tools/sync_manifest.py --dry-run    # 只预览改动，不写盘
   python3 tools/sync_manifest.py --force      # 强制按内容重新提取所有字段
   python3 tools/sync_manifest.py --prune      # 清理已删除文件对应的条目
   python3 tools/sync_manifest.py --watch      # 持续监听 reports/ 自动同步
   python3 tools/sync_manifest.py --install-hook    # 安装 git pre-commit 钩子
   python3 tools/sync_manifest.py --uninstall-hook  # 卸载钩子

 详见 README.md「🔧 自动同步报告清单」一节。
============================================================================
"""

import argparse
import hashlib
import html as html_module
import os
import re
import sys
import time
from collections import Counter
from datetime import datetime, timezone

# ----------------------------------------------------------------------------
# 路径常量（脚本可从任意目录调用，均以仓库根为基准）
# ----------------------------------------------------------------------------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, os.pardir))
REPORTS_DIR = os.path.join(ROOT_DIR, "reports")
MANIFEST_PATH = os.path.join(REPORTS_DIR, "manifest.json")

REPORT_EXTS = (".md", ".markdown", ".htm", ".html")
THUMB_NAMES = ("thumbnail", "cover", "thumb", "banner")
THUMB_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".svg", ".gif")

# 摘要/标签上限
SUMMARY_MAX = 160
TAGS_MAX = 8


# ============================================================================
# 通用工具
# ============================================================================

def relpath(path):
    """转为相对仓库根的路径，统一用正斜杠（网站里 fetch 需要正斜杠）。"""
    return os.path.relpath(path, ROOT_DIR).replace(os.sep, "/")


def norm_id(path):
    """从文件路径生成稳定且 URL 友好的 id。
       reports/foo.md            -> foo
       reports/my-report/index.html -> my-report
       reports/2026/调研报告.md  -> 调研报告
    """
    p = relpath(path)
    parts = p.split("/")
    # 去掉 reports/ 前缀
    parts = [x for x in parts if x != "reports"]
    if not parts:
        return "report"
    fname = parts[-1]
    stem = os.path.splitext(fname)[0]
    if stem.lower() == "index" and len(parts) >= 2:
        stem = parts[-2]
    # 仅保留字母数字、中文、连字符；其余替换为连字符
    stem = re.sub(r"[^\w\u4e00-\u9fff-]+", "-", stem, flags=re.UNICODE).strip("-")
    return stem or "report"


def slugify_tags(tags):
    """清洗标签：去空白、去重、限数量。"""
    seen = []
    for t in tags:
        t = str(t).strip()
        if t and t not in seen:
            seen.append(t)
        if len(seen) >= TAGS_MAX:
            break
    return seen


def truncate(s, n=SUMMARY_MAX):
    s = (s or "").strip().replace("\n", " ")
    s = re.sub(r"\s+", " ", s)
    return s[:n] + ("…" if len(s) > n else "")


# ============================================================================
# 内容标签兜底（无 frontmatter / 无 #标签 时的第三道防线）
# ============================================================================

# 标题关键词 → 推荐标签
DOMAIN_TAG_MAP = {
    "时间轴":   ["读书"],
    "时间线":   ["读书"],
    "小说":     ["读书", "文学"],
    "结构分析":  ["读书"],
    "MBTI":     ["心理类型"],
    "人格":     ["心理类型"],
    "荣格":     ["心理类型"],
    "Ni":       ["心理类型"],
    "Ne":       ["心理类型"],
    "模型":     ["AI"],
    "深度学习":  ["AI"],
    "GPT":      ["AI"],
    "大语言模型": ["AI"],
    "创作":     ["创作"],
    "写作":     ["创作"],
    "产出":     ["统计"],
    "报告":     ["报告"],
    "调研":     ["调研"],
    "市场":     ["市场"],
    "行业":     ["行业"],
    "趋势":     ["趋势"],
    "读书":     ["读书"],
    "阅读":     ["读书"],
}

# 中文常用停用词（用于正文词频过滤）
STOP_WORDS = {
    "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都",
    "一", "个", "上", "也", "很", "到", "说", "要", "去", "你",
    "会", "着", "没有", "看", "好", "自己", "这", "他", "她", "它",
    "们", "那", "什么", "怎么", "如何", "为", "以", "从", "对", "与",
    "但", "而", "或", "被", "把", "让", "向", "将", "能", "可以",
    "更", "最", "和", "与", "及", "以及", "除了", "关于", "通过",
    "这个", "那个", "这些", "那些", "一个", "一些", "一部", "一种",
    "包括", "进行", "使用", "基于", "相关", "不同", "我们", "他们",
    "可以", "需要", "可能", "已经", "没有", "不是", "如果", "因为",
    "所以", "但是", "虽然", "不过", "而且", "然后", "之后", "以前",
    "同时", "目前", "目前", "以上", "以下", "方面", "中的", "来源",
}


def extract_content_tags(body, title=""):
    """基于内容的关键词标签提取（第三道防线）。
    - 1) 标题关键词 → 领域映射
    - 2) 正文中文 2-gram 词频
    返回清洗后的标签列表（可能为空列表）。
    """
    tags = set()

    # 1) 标题关键词映射
    if title:
        for keyword, suggested in DOMAIN_TAG_MAP.items():
            if keyword in title:
                tags.update(suggested)
        # 标题按常见分隔符拆分，再逐一匹配
        parts = re.split(r"[·•·　\s,，、/／_（）()《》]", title)
        for part in parts:
            part = part.strip()
            if not part or len(part) < 2 or part in STOP_WORDS:
                continue
            for keyword, suggested in DOMAIN_TAG_MAP.items():
                if keyword in part:
                    tags.update(suggested)

    if tags:
        return slugify_tags(list(tags))

    # 2) 正文中文 2-gram 频率
    # 只保留中文字符（自动忽略 HTML/MD 标记）
    chinese_only = re.sub(r"[^\u4e00-\u9fff]", "", body)
    if len(chinese_only) >= 20:
        bigrams = Counter()
        for i in range(len(chinese_only) - 1):
            bg = chinese_only[i:i + 2]
            if bg not in STOP_WORDS:
                bigrams[bg] += 1

        threshold = max(3, len(chinese_only) // 200)
        for bg, count in bigrams.most_common(8):
            if count >= threshold and bg not in STOP_WORDS:
                tags.add(bg)

    return slugify_tags(list(tags))


# ============================================================================
# Markdown：frontmatter + 内容解析
# ============================================================================

_FRONTMATTER_RE = re.compile(r"\A---\s*\n(.*?)\n---\s*\n?(.*)\Z", re.DOTALL)


def parse_frontmatter(text):
    """极简 YAML 解析（仅支持 key: value 与 key: [a, b]）。
       无需 PyYAML，覆盖 90% 报告场景。"""
    m = _FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw, body = m.group(1), m.group(2)
    data = {}
    for line in raw.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or ":" not in line:
            continue
        key, _, val = line.partition(":")
        key = key.strip()
        val = val.strip()
        if not key:
            continue
        # 列表形 [a, b, c]
        if val.startswith("[") and val.endswith("]"):
            items = [x.strip().strip("\"'") for x in val[1:-1].split(",") if x.strip()]
            data[key] = items
        else:
            data[key] = val.strip("\"'")
    return data, body


def strip_md_inline(s):
    """去掉 markdown 行内格式符号。"""
    s = re.sub(r"`{1,3}([^`]*)`{1,3}", r"\1", s)            # `code`
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)              # ![alt](url)
    s = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", s)          # [text](url)
    s = re.sub(r"\*\*([^*]+)\*\*", r"\1", s)                # **bold**
    s = re.sub(r"\*([^*]+)\*", r"\1", s)                    # *italic*
    s = re.sub(r"__([^_]+)__", r"\1", s)                    # __bold__
    s = re.sub(r"\b_([^_]+)_\b", r"\1", s)                  # _italic_
    s = re.sub(r"^#{1,6}\s*", "", s)                        # 标题井号
    s = re.sub(r"^\s*[-*+]\s+", "", s)                      # 列表符
    s = re.sub(r"^\s*\d+\.\s+", "", s)                      # 有序列表
    return s.strip()


def _looks_like_metadata_line(line):
    """识别「作者：xxx 发布日期：xxx」这类 AI 报告常见的元信息行。
       特征：包含多个 `词：` 分隔的小片段，或整行是加粗的标签式信息。"""
    s = strip_md_inline(line)
    if not s:
        return False
    # 去掉加粗后的纯文本里，出现 2 个及以上「词：」模式 → 多半是元信息行
    # （正常散文段落极少同时含多个冒号短语）
    pairs = re.findall(r"[\u4e00-\u9fff\w]{1,8}[：:]", s)
    if len(pairs) >= 2:
        return True
    meta_keys = ("发布日期", "作者", "阅读时长", "更新时间", "创建日期",
                 "日期", "来源", "版本", "日期：")
    return any(k in s for k in meta_keys) and len(s) < 80


def parse_markdown(text):
    fm, body = parse_frontmatter(text)
    title = None
    summary = None
    tags = list(fm.get("tags", []))

    # 标题：frontmatter > 首个 H1
    if fm.get("title"):
        title = str(fm["title"]).strip()
    else:
        for line in body.splitlines():
            line = line.strip()
            if re.match(r"^#{1}\s+", line):
                title = strip_md_inline(line)
                break

    # 摘要：frontmatter > 第一个实质段落
    if fm.get("summary") or fm.get("description"):
        summary = truncate(str(fm.get("summary") or fm.get("description")))
    else:
        for line in body.splitlines():
            stripped = line.strip()
            if not stripped:
                continue
            # 跳过标题、引用、图片、列表项、分隔线
            if re.match(r"^#{1,6}\s", stripped):
                continue
            if stripped.startswith(">"):
                continue
            if stripped.startswith("!["):
                continue
            if stripped.startswith("---") or stripped.startswith("***"):
                continue
            # 跳过「作者：xxx 发布日期：xxx」这类元信息行
            if _looks_like_metadata_line(stripped):
                continue
            # 太短（<6 字符）的行多半是装饰，继续找
            clean = strip_md_inline(stripped)
            if len(clean) < 6:
                continue
            summary = truncate(clean)
            break

    # 标签：frontmatter + 正文 #标签 + 内容语义兜底
    if not tags:
        for m in re.finditer(r"(?:^|\s)#([\w\u4e00-\u9fff]+)", body):
            tags.append(m.group(1))
    if not tags:
        tags = extract_content_tags(body, title=title)

    return {
        "title": title,
        "summary": summary,
        "tags": slugify_tags(tags),
        "date": str(fm["date"]).strip() if fm.get("date") else None,
    }


# ============================================================================
# HTML：<meta> + 内容解析
# ============================================================================

_META_RE = re.compile(
    r'<meta\s+[^>]*?name\s*=\s*["\']?(?P<key>[a-zA-Z\-]+)["\']?[^>]*?'
    r'content\s*=\s*["\'](?P<val>[^"\']*)["\']',
    re.IGNORECASE,
)
_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_H1_RE = re.compile(r"<h1[^>]*>(.*?)</h1>", re.IGNORECASE | re.DOTALL)
_TAG_RE = re.compile(r"<[^>]+>")


def _text_from_html(html_fragment):
    """剥离标签并解码实体。"""
    txt = _TAG_RE.sub(" ", html_fragment)
    return html_module.unescape(txt).strip()


def _first_paragraph(html):
    """取第一个 <p>...</p> 的纯文本。"""
    m = re.search(r"<p[^>]*>(.*?)</p>", html, re.IGNORECASE | re.DOTALL)
    if not m:
        return None
    return _text_from_html(m.group(1))


def parse_html(text):
    metas = {}
    for m in _META_RE.finditer(text):
        key = m.group("key").lower().strip()
        if key not in metas:  # 取第一个
            metas[key] = html_module.unescape(m.group("val")).strip()

    # 标题
    title = metas.get("og:title") or metas.get("twitter:title")
    if not title:
        tm = _TITLE_RE.search(text)
        title = _text_from_html(tm.group(1)) if tm else None
    if not title:
        h1 = _H1_RE.search(text)
        title = _text_from_html(h1.group(1)) if h1 else None

    # 摘要
    summary = metas.get("description") or metas.get("og:description")
    if not summary:
        p = _first_paragraph(text)
        summary = truncate(p) if p else None
    else:
        summary = truncate(summary)

    # 标签：keywords meta + 正文 #标签
    tags = []
    if metas.get("keywords"):
        tags = [t.strip() for t in metas["keywords"].split(",") if t.strip()]
    # 关键：先剔除 <style>/<script> 块，否则会误抓 #3b82f6 等颜色码
    body_only = re.sub(
        r"<(script|style)\b[^>]*>.*?</\1>",
        " ", text, flags=re.IGNORECASE | re.DOTALL,
    )
    for m in re.finditer(r"(?:^|\s)#([\w\u4e00-\u9fff]+)", body_only):
        candidate = m.group(1)
        # 过滤掉纯十六进制颜色码（3/6/8 位）和明显的代码标识
        if re.fullmatch(r"[0-9a-fA-F]{3,8}", candidate):
            continue
        tags.append(candidate)

    # 第三道防线：内容标签兜底（前两者皆空时）
    if not tags:
        visible_text = _TAG_RE.sub(" ", body_only)
        tags = extract_content_tags(visible_text, title=title)

    return {
        "title": title,
        "summary": summary,
        "tags": slugify_tags(tags),
        "date": metas.get("date") or metas.get("article:published_time"),
    }


# ============================================================================
# 文件元数据提取主入口
# ============================================================================

def find_thumbnail(report_path):
    """在同目录寻找报告专属缩略图。

    匹配策略（防止共享目录误匹配）：
    - index.*（文件夹式报告）→ 用目录级的 thumbnail.* / cover.*
    - 独立文件 → 先找 {文件名}.thumbnail.*，再找 {文件名}-thumbnail.*
    - 都不匹配 → 返回 None（前端会显示彩色占位）
    """
    d = os.path.dirname(report_path)
    base = os.path.splitext(os.path.basename(report_path))[0]
    try:
        siblings = {s.lower(): s for s in os.listdir(d)}
    except OSError:
        return None

    # 文件夹式报告：index.* -> thumbnail.* / cover.*
    if base.lower() == "index":
        for name in THUMB_NAMES:
            for ext in THUMB_EXTS:
                cand_lower = f"{name}{ext}"
                if cand_lower in siblings:
                    return relpath(os.path.join(d, siblings[cand_lower]))

    # 独立文件：{文件名}.thumbnail.* 或 {文件名}-thumbnail.*
    for prefix in (base, f"{base}-"):
        for name in THUMB_NAMES:
            for ext in THUMB_EXTS:
                cand = f"{prefix}{name}{ext}"
                cand_lower = cand.lower()
                if cand_lower in siblings:
                    return relpath(os.path.join(d, siblings[cand_lower]))

    return None


def extract(report_path):
    """从单个报告文件提取全部可推断字段。返回 dict。"""
    try:
        with open(report_path, "r", encoding="utf-8") as f:
            text = f.read()
    except UnicodeDecodeError:
        with open(report_path, "r", encoding="utf-8", errors="replace") as f:
            text = f.read()

    ext = os.path.splitext(report_path)[1].lower()
    if ext in (".md", ".markdown"):
        meta = parse_markdown(text)
        rtype = "markdown"
    else:
        meta = parse_html(text)
        rtype = "html"

    # 日期：内容 > 文件 mtime
    date = meta.get("date")
    if not date:
        mtime = os.path.getmtime(report_path)
        date = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")

    return {
        "id": norm_id(report_path),
        "type": rtype,
        "title": meta.get("title") or os.path.splitext(os.path.basename(report_path))[0],
        "summary": meta.get("summary"),
        "tags": meta.get("tags") or [],
        "date": date,
        "path": relpath(report_path),
        "thumbnail": find_thumbnail(report_path),
    }


# ============================================================================
# 发现报告文件
# ============================================================================

def discover():
    """遍历 reports/，返回所有报告文件绝对路径列表。"""
    found = []
    if not os.path.isdir(REPORTS_DIR):
        return found
    for dirpath, _dirs, files in os.walk(REPORTS_DIR):
        for fn in sorted(files):
            ext = os.path.splitext(fn)[1].lower()
            if ext in REPORT_EXTS:
                found.append(os.path.join(dirpath, fn))
    return found


# ============================================================================
# 合并：已存在清单 + 新发现，保留用户手填字段
# ============================================================================

# 这些字段被视作「需要提取」：缺失时才补，--force 时强制覆盖
EXTRACT_FIELDS = ("title", "summary", "tags", "date", "thumbnail", "type")
KEY_ORDER = ("id", "type", "title", "summary", "tags", "date", "path", "thumbnail")


def load_manifest():
    if not os.path.exists(MANIFEST_PATH):
        return {}
    try:
        with open(MANIFEST_PATH, "r", encoding="utf-8") as f:
            data = __import__("json").load(f)
    except Exception as e:
        print(f"⚠️  读取 manifest.json 失败：{e}", file=sys.stderr)
        return {}
    # 兼容 {reports:[...]} 与 直接是列表 两种写法
    if isinstance(data, list):
        return {"reports": data}
    return data


def save_manifest(manifest):
    reports = manifest.get("reports", [])
    # 排序键，保证输出稳定（减少 git diff 噪声）
    def sort_key(r):
        return (r.get("date") or "", r.get("title") or "", r.get("path") or "")
    reports_sorted = sorted(reports, key=sort_key, reverse=True)  # 新的在前

    out = {
        "$schema": manifest.get("$schema",
                                "https://json-schema.org/draft/2020-12/schema"),
        "$comment": manifest.get(
            "$comment",
            "报告清单。加新报告只需在 reports/ 放入文件，运行 tools/sync_manifest.py 自动同步。",
        ),
        "reports": [ordered(r) for r in reports_sorted],
    }
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        __import__("json").dump(out, f, ensure_ascii=False, indent=2)
        f.write("\n")


def ordered(report):
    """按固定键顺序输出，未出现的键放最后。"""
    result = {}
    for k in KEY_ORDER:
        if k in report:
            result[k] = report[k]
    for k, v in report.items():
        if k not in result:
            result[k] = v
    return result


def merge(manifest, discovered, force=False, prune=False):
    """合并：返回 (新manifest, 变更日志列表)。"""
    existing = {r["path"]: r for r in manifest.get("reports", []) if "path" in r}
    changes = []

    # 处理每个发现的文件
    for path in discovered:
        rel = relpath(path)
        ext_meta = extract(path)

        if rel in existing:
            old = existing[rel]
            # 用已有 path 对应的 entry，补全缺失字段（或 force 覆盖）
            updated = dict(old)
            updated["id"] = old.get("id") or ext_meta["id"]  # id 不轻易改
            for field in EXTRACT_FIELDS:
                if field == "type":
                    # type 仅在缺失时补
                    if "type" not in old or not old.get("type"):
                        updated["type"] = ext_meta["type"]
                    continue
                if force or not old.get(field):
                    new_val = ext_meta.get(field)
                    if new_val and old.get(field) != new_val:
                        updated[field] = new_val
            updated["path"] = rel
            if updated != old:
                changes.append(("update", rel, diff(old, updated)))
            existing[rel] = updated
        else:
            # 新报告
            existing[rel] = ext_meta
            changes.append(("add", rel, ext_meta))

    # 清理已删除文件
    if prune:
        discovered_rels = {relpath(p) for p in discovered}
        for rel in list(existing.keys()):
            if rel not in discovered_rels:
                changes.append(("remove", rel, existing[rel]))
                del existing[rel]

    new_manifest = dict(manifest)
    new_manifest["reports"] = list(existing.values())
    return new_manifest, changes


def diff(old, new):
    """返回两 dict 字段差异（仅展示真正改动的键）。"""
    keys = set(old) | set(new)
    out = {}
    for k in keys:
        if old.get(k) != new.get(k):
            out[k] = {"from": old.get(k), "to": new.get(k)}
    return out


def print_changes(changes):
    if not changes:
        print("✅ 清单已是最新，无改动。")
        return
    for kind, rel, detail in changes:
        if kind == "add":
            t = detail.get("title", "(未命名)")
            tags = ", ".join(detail.get("tags", [])) or "—"
            print(f"➕ 新增  {rel}")
            print(f"         标题：{t}")
            print(f"         摘要：{detail.get('summary') or '—'}")
            print(f"         标签：{tags}    日期：{detail.get('date')}    类型：{detail.get('type')}")
        elif kind == "update":
            print(f"✏️  更新  {rel}")
            for k, v in detail.items():
                print(f"         {k}: {short(v['from'])}  →  {short(v['to'])}")
        elif kind == "remove":
            print(f"🗑  删除  {rel}  （{detail.get('title', '')}）")


def short(v):
    if isinstance(v, list):
        return ", ".join(map(str, v))
    return str(v) if v is not None else "(空)"


# ============================================================================
# Git pre-commit 钩子
# ============================================================================

HOOK_PATH = os.path.join(ROOT_DIR, ".git", "hooks", "pre-commit")
HOOK_CONTENT = """#!/bin/sh
# 由 tools/sync_manifest.py 自动安装
# 提交前自动同步 reports/manifest.json，确保画廊内容与文件一致
echo "→ 同步报告清单 (tools/sync_manifest.py)..."
python3 tools/sync_manifest.py --quiet || true
git add reports/manifest.json
"""


def install_hook():
    git_dir = os.path.join(ROOT_DIR, ".git")
    if not os.path.isdir(git_dir):
        print("⚠️  未找到 .git 目录——请先在仓库根执行 git init。")
        sys.exit(1)
    os.makedirs(os.path.dirname(HOOK_PATH), exist_ok=True)
    with open(HOOK_PATH, "w", encoding="utf-8") as f:
        f.write(HOOK_CONTENT)
    os.chmod(HOOK_PATH, 0o755)
    print(f"✅ 已安装 git pre-commit 钩子：{HOOK_PATH}")
    print("   每次 git commit 前会自动运行同步，并把 manifest.json 加入提交。")


def uninstall_hook():
    if os.path.exists(HOOK_PATH):
        os.remove(HOOK_PATH)
        print(f"✅ 已卸载 pre-commit 钩子：{HOOK_PATH}")
    else:
        print("（钩子本就不存在，无需卸载）")


# ============================================================================
# --watch 模式：持续监听
# ============================================================================

def fingerprint():
    """对 reports/ 下所有报告文件生成 (路径, mtime, size) 指纹。"""
    fp = {}
    for p in discover():
        st = os.stat(p)
        fp[relpath(p)] = (st.st_mtime, st.st_size)
    return fp


def watch_loop():
    print("👁  监听 reports/ 变化中（每 2 秒检查一次，Ctrl+C 退出）…\n")
    last = fingerprint()
    sync_once(quiet=True)
    try:
        while True:
            time.sleep(2)
            curr = fingerprint()
            if curr != last:
                print("\n──── 检测到变化 ────")
                sync_once(quiet=False)
                last = fingerprint()
    except KeyboardInterrupt:
        print("\n👋 已停止监听。")


# ============================================================================
# 主流程
# ============================================================================

def sync_once(dry_run=False, force=False, prune=False, quiet=False):
    manifest = load_manifest()
    discovered = discover()

    # 幂等检查：路径去重（避免同一路径重复）
    new_manifest, changes = merge(manifest, discovered, force=force, prune=prune)

    if changes and not quiet:
        print_changes(changes)
    elif not quiet:
        print("✅ 清单已是最新，无改动。")

    if changes and not dry_run:
        save_manifest(new_manifest)
        if not quiet:
            print(f"\n💾 已写入 {relpath(MANIFEST_PATH)}")
    elif changes and dry_run:
        print("\n（--dry-run 模式，未写盘）")
    return changes


def main():
    ap = argparse.ArgumentParser(
        description="自动同步 reports/manifest.json：发现新报告并提取元数据。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="示例：\n"
               "  python3 tools/sync_manifest.py            # 同步\n"
               "  python3 tools/sync_manifest.py --dry-run  # 预览\n"
               "  python3 tools/sync_manifest.py --watch    # 监听\n",
    )
    ap.add_argument("--dry-run", action="store_true", help="只预览改动，不写盘")
    ap.add_argument("--force", action="store_true", help="强制按内容重新提取所有字段")
    ap.add_argument("--prune", action="store_true", help="清理已删除文件对应的条目")
    ap.add_argument("--watch", action="store_true", help="持续监听 reports/ 自动同步")
    ap.add_argument("--quiet", action="store_true", help="无改动时静默")
    ap.add_argument("--install-hook", action="store_true", help="安装 git pre-commit 钩子")
    ap.add_argument("--uninstall-hook", action="store_true", help="卸载 git pre-commit 钩子")
    args = ap.parse_args()

    if args.install_hook:
        install_hook()
        return
    if args.uninstall_hook:
        uninstall_hook()
        return
    if args.watch:
        watch_loop()
        return

    sync_once(dry_run=args.dry_run, force=args.force, prune=args.prune, quiet=args.quiet)


if __name__ == "__main__":
    main()
