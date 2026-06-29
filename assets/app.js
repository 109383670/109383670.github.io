/* ========================================================================
   报告展示画廊 · 应用逻辑
   - 从 reports/manifest.json 加载报告清单
   - 渲染卡片画廊（搜索 / 标签过滤 / 排序）
   - Hash 路由双视图：画廊（#/） 与 Markdown 阅读器（#/report/<id>）
   - HTML 类型报告在新标签页打开；Markdown 类型站内渲染
   ======================================================================== */

(function () {
  "use strict";

  /* -------------------- 状态 -------------------- */
  const state = {
    reports: [],
    filtered: [],
    activeTag: null,
    query: "",
    sort: "date-desc",
  };

  /* -------------------- DOM 引用 -------------------- */
  const $ = (sel) => document.querySelector(sel);
  const galleryView = $("#gallery-view");
  const readerView = $("#reader-view");
  const galleryEl = $("#gallery");
  const tagBarEl = $("#tag-bar");
  const searchInput = $("#search");
  const sortSelect = $("#sort");
  const resultCountEl = $("#result-count");
  const heroCountEl = $("#hero-count");

  /* -------------------- 工具函数 -------------------- */

  /** 简易 HTML 转义，避免清单字段中的特殊字符破坏 DOM */
  function escapeHtml(str) {
    if (str == null) return "";
    return String(str)
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/"/g, "&quot;")
      .replace(/'/g, "&#39;");
  }

  /** 推断报告类型：缺省时根据 path 后缀判断 */
  function resolveType(report) {
    if (report.type) return report.type;
    if (/\.md$/i.test(report.path || "")) return "markdown";
    return "html";
  }

  /** 规范化日期为 YYYY-MM-DD */
  function normalizeDate(report) {
    if (!report.date) return "";
    const d = new Date(report.date);
    if (isNaN(d.getTime())) return String(report.date);
    return d.toISOString().slice(0, 10);
  }

  /** 卡片缩略图 HTML：有图显示图，无图显示渐变占位 */
  function thumbnailHtml(report) {
    if (report.thumbnail) {
      return `<img src="${escapeHtml(report.thumbnail)}" alt="${escapeHtml(report.title)}" loading="lazy" onerror="this.style.display='none';this.nextElementSibling.style.display='grid';">
              <div class="card-thumb-fallback" style="display:none;">${escapeHtml(initials(report.title))}</div>`;
    }
    return `<div class="card-thumb-fallback">${escapeHtml(initials(report.title))}</div>`;
  }

  /** 从标题取首字作为占位标识 */
  function initials(title) {
    if (!title) return "·";
    const ch = title.trim().charAt(0);
    return ch.toUpperCase();
  }

  /* -------------------- 数据加载 -------------------- */

  async function loadManifest() {
    try {
      const res = await fetch("reports/manifest.json", { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      state.reports = Array.isArray(data) ? data : data.reports || [];
      // 规范化每条记录
      state.reports = state.reports.map((r) => ({
        ...r,
        type: resolveType(r),
        _date: normalizeDate(r),
      }));
      renderTagBar();
      applyFilterAndRender();
    } catch (err) {
      galleryEl.innerHTML = renderError("无法加载报告清单", err.message);
    }
  }

  /* -------------------- 标签条 -------------------- */

  function renderTagBar() {
    const counts = {};
    state.reports.forEach((r) => {
      (r.tags || []).forEach((t) => {
        counts[t] = (counts[t] || 0) + 1;
      });
    });
    const tags = Object.keys(counts).sort((a, b) => counts[b] - counts[a]);
    if (tags.length === 0) {
      tagBarEl.innerHTML = "";
      return;
    }
    tagBarEl.innerHTML =
      `<button class="tag-chip ${state.activeTag === null ? "active" : ""}" data-tag="__all">全部</button>` +
      tags
        .map(
          (t) =>
            `<button class="tag-chip ${state.activeTag === t ? "active" : ""}" data-tag="${escapeHtml(t)}">${escapeHtml(t)} <span style="opacity:.5">${counts[t]}</span></button>`
        )
        .join("");

    tagBarEl.querySelectorAll(".tag-chip").forEach((chip) => {
      chip.addEventListener("click", () => {
        const t = chip.dataset.tag;
        state.activeTag = t === "__all" ? null : t;
        renderTagBar();
        applyFilterAndRender();
      });
    });
  }

  /* -------------------- 过滤 + 排序 -------------------- */

  function applyFilterAndRender() {
    let list = state.reports.slice();

    // 标签过滤
    if (state.activeTag) {
      list = list.filter((r) => (r.tags || []).includes(state.activeTag));
    }

    // 搜索过滤（标题 + 简介 + 标签）
    if (state.query) {
      const q = state.query.toLowerCase();
      list = list.filter((r) =>
        [r.title, r.summary, (r.tags || []).join(" ")]
          .join(" ")
          .toLowerCase()
          .includes(q)
      );
    }

    // 排序
    list.sort((a, b) => {
      if (state.sort === "date-desc") return (b._date || "").localeCompare(a._date || "");
      if (state.sort === "date-asc") return (a._date || "").localeCompare(b._date || "");
      if (state.sort === "title") return (a.title || "").localeCompare(b.title || "", "zh");
      return 0;
    });

    state.filtered = list;
    renderGallery();
  }

  /* -------------------- 画廊渲染 -------------------- */

  function renderGallery() {
    resultCountEl.textContent = state.filtered.length;
    heroCountEl.textContent = state.reports.length;

    if (state.filtered.length === 0) {
      galleryEl.innerHTML = renderEmpty();
      return;
    }

    galleryEl.innerHTML = state.filtered
      .map((r, i) => {
        const type = r.type;
        const typeLabel = type === "markdown" ? "MD" : "HTML";
        const href =
          type === "markdown"
            ? `#/report/${encodeURIComponent(r.id)}`
            : escapeHtml(r.path);
        const target = type === "markdown" ? "" : ` target="_blank" rel="noopener"`;
        const tagsHtml = (r.tags || [])
          .slice(0, 4)
          .map((t) => `<span class="card-tag">${escapeHtml(t)}</span>`)
          .join("");

        return `
        <a class="card" href="${href}"${target} style="animation-delay:${i * 40}ms">
          <div class="card-thumb">
            ${thumbnailHtml(r)}
            <span class="card-type-badge ${type}">${typeLabel}</span>
          </div>
          <div class="card-body">
            ${r._date ? `<div class="card-date">${escapeHtml(r._date)}</div>` : ""}
            <h3 class="card-title">${escapeHtml(r.title || "未命名报告")}</h3>
            ${r.summary ? `<p class="card-summary">${escapeHtml(r.summary)}</p>` : ""}
            <div class="card-tags">${tagsHtml}</div>
          </div>
        </a>`;
      })
      .join("");
  }

  function renderEmpty() {
    return `
      <div class="state-msg" style="grid-column:1/-1">
        <h3>未找到匹配的报告</h3>
        <p>试试清空搜索词或切换标签。</p>
      </div>`;
  }

  function renderError(title, detail) {
    return `
      <div class="state-msg error" style="grid-column:1/-1">
        <h3>${escapeHtml(title)}</h3>
        <p>${escapeHtml(detail)}</p>
        <p style="margin-top:12px">请确认 <code>reports/manifest.json</code> 存在且格式正确，并通过 HTTP 服务器（而非 file://）访问。</p>
      </div>`;
  }

  /* -------------------- Markdown 阅读器 -------------------- */

  async function openReader(reportId) {
    const report = state.reports.find((r) => r.id === reportId);
    if (!report) {
      showReaderError("找不到该报告", `id = ${reportId} 不在清单中。`);
      return;
    }
    if (report.type !== "markdown") {
      // HTML 报告不应进入阅读器，回退到画廊
      location.hash = "#/";
      return;
    }

    switchView("reader");
    const container = $("#reader-content");
    container.innerHTML = `
      <div class="reader-loading">
        <p>正在加载报告…</p>
      </div>`;

    try {
      const res = await fetch(report.path, { cache: "no-store" });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const md = await res.text();
      const html = window.marked
        ? window.marked.parse(md, { breaks: true, gfm: true })
        : `<p>marked.js 未加载，无法渲染 Markdown。原文：</p><pre>${escapeHtml(md)}</pre>`;

      container.innerHTML = `
        <div class="prose-container">
          <header class="prose-header">
            <h1>${escapeHtml(report.title || "未命名报告")}</h1>
            <div class="prose-info">
              ${report._date ? `<span>📅 ${escapeHtml(report._date)}</span>` : ""}
              <span class="reader-type">MD</span>
              ${report.tags && report.tags.length
                ? `<span class="prose-tags">${report.tags.map((t) => `<span class="card-tag">${escapeHtml(t)}</span>`).join("")}</span>`
                : ""}
            </div>
          </header>
          <article class="prose">${html}</article>
        </div>`;
      window.scrollTo(0, 0);
    } catch (err) {
      showReaderError("无法加载报告内容", err.message);
    }
  }

  function showReaderError(title, detail) {
    switchView("reader");
    $("#reader-content").innerHTML = `
      <div class="reader-error">
        <h3>${escapeHtml(title)}</h3>
        <p>${escapeHtml(detail)}</p>
        <p style="margin-top:16px"><a href="#/" style="color:var(--accent-2)">← 返回画廊</a></p>
      </div>`;
  }

  /* -------------------- 视图切换 -------------------- */

  function switchView(view) {
    galleryView.classList.toggle("active", view === "gallery");
    readerView.classList.toggle("active", view === "reader");
    if (view === "gallery") {
      // 回到画廊时清空阅读器内容，避免残留
      $("#reader-content").innerHTML = "";
    }
  }

  /* -------------------- 路由 -------------------- */

  function handleRoute() {
    const hash = location.hash || "#/";
    const match = hash.match(/^#\/report\/(.+)$/);
    if (match) {
      openReader(decodeURIComponent(match[1]));
    } else {
      switchView("gallery");
    }
  }

  /* -------------------- 事件绑定 -------------------- */

  function bindEvents() {
    // 搜索：实时过滤
    let searchTimer;
    searchInput.addEventListener("input", (e) => {
      clearTimeout(searchTimer);
      searchTimer = setTimeout(() => {
        state.query = e.target.value.trim();
        applyFilterAndRender();
      }, 120);
    });

    // 排序
    sortSelect.addEventListener("change", (e) => {
      state.sort = e.target.value;
      applyFilterAndRender();
    });

    // 路由
    window.addEventListener("hashchange", handleRoute);

    // 返回画廊按钮
    $("#back-to-gallery").addEventListener("click", (e) => {
      e.preventDefault();
      location.hash = "#/";
    });
  }

  /* -------------------- 初始化 -------------------- */

  function init() {
    bindEvents();
    loadManifest();
    handleRoute(); // 处理刷新时直接落在 #/report/<id> 的情况
  }

  document.addEventListener("DOMContentLoaded", init);
})();
