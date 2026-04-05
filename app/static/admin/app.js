const { applyTranslations, getLocale, onLocaleChange, setLocale, t } = window.AdminI18n;

const menuItems = [
  { key: "bigscreen", label: "Big Screen" },
  { key: "dashboard", label: "Dashboard" },
  { key: "chat", label: "Chat" },
  { key: "lineage", label: "Pipeline Lineage" },
  { key: "tools", label: "Tools" },
  { key: "prompt-templates", label: "Prompt Templates" },
  { key: "tool-versions", label: "Tool Versions" },
  { key: "data-sources", label: "Data Sources" },
  { key: "data-source-tables", label: "Data Source Tables" },
  { key: "result-preview", label: "Result Preview" },
  { key: "memory", label: "Memory" },
  { key: "scheduler", label: "Scheduler" },
  { key: "channels", label: "Channels" },
  { key: "logs", label: "Logs / Trace" },
  { key: "settings", label: "Settings" },
];

const appState = {
  currentView: "bigscreen",
  chatSessionId: "",
  chatSceneType: "",
  chatPromptTemplateKey: "",
  chatMessages: [],
  lineage: {
    data: null,
    transform: { x: 80, y: 80, scale: 1 },
    isDragging: false,
    dragStart: { x: 0, y: 0 },
  },
  recentSuggestions: {},
  locale: getLocale(),
};

const menuEl = document.getElementById("menu");
const headerEl = document.getElementById("page-header");
const contentEl = document.getElementById("page-content");
const drawerEl = document.getElementById("drawer");
const drawerTitleEl = document.getElementById("drawer-title");
const drawerBodyEl = document.getElementById("drawer-body");
const drawerCloseEl = document.getElementById("drawer-close");
const localeSelectEl = document.getElementById("locale-select");

drawerCloseEl.addEventListener("click", () => drawerEl.classList.add("hidden"));

function syncLocaleSelector() {
  if (localeSelectEl) {
    localeSelectEl.value = getLocale();
  }
}

function initLocaleSelector() {
  syncLocaleSelector();
  if (!localeSelectEl) return;
  localeSelectEl.addEventListener("change", () => {
    setLocale(localeSelectEl.value);
  });
  onLocaleChange(async (locale) => {
    appState.locale = locale;
    syncLocaleSelector();
    initMenu();
    await switchView(appState.currentView);
    applyTranslations(document.body);
  });
}

function escapeHtml(value) {
  return (value ?? "")
    .toString()
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;");
}

function formatDate(iso) {
  if (!iso) return "-";
  const dt = new Date(iso);
  if (Number.isNaN(dt.getTime())) return iso;
  return dt.toLocaleString();
}

function StatusBadge(value) {
  const str = (value ?? "").toString().toLowerCase();
  let cls = "ok";
  if (
    str.includes("fail") ||
    str.includes("error") ||
    str.includes("critical") ||
    str.includes("red") ||
    str === "false" ||
    str === "disabled"
  ) {
    cls = "bad";
  } else if (
    str.includes("warn") ||
    str.includes("degrad") ||
    str.includes("medium") ||
    str.includes("running")
  ) {
    cls = "warn";
  }
  return `<span class="status ${cls}">${escapeHtml(t(value ?? "N_A"))}</span>`;
}

function JsonViewer(data) {
  return `<pre class="json">${escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
}

function renderPageHeader(title, subtitle = "", actionsHtml = "") {
  headerEl.innerHTML = `
    <h2 class="page-title">${escapeHtml(t(title))}</h2>
    <p class="page-subtitle">${escapeHtml(t(subtitle))}</p>
    <div class="page-actions">${actionsHtml}</div>
  `;
}

function DataTable(columns, rows) {
  if (!rows.length) return `<div class="empty">${escapeHtml(t("No data"))}</div>`;
  const head = columns.map((col) => `<th>${escapeHtml(t(col.title))}</th>`).join("");
  const body = rows
    .map((row) => {
      const cells = columns
        .map((col) => {
          const value = typeof col.render === "function" ? col.render(row) : row[col.key];
          return `<td>${value ?? ""}</td>`;
        })
        .join("");
      return `<tr>${cells}</tr>`;
    })
    .join("");
  return `<div class="table-wrap"><table><thead><tr>${head}</tr></thead><tbody>${body}</tbody></table></div>`;
}

function openDrawer(title, bodyHtml) {
  drawerTitleEl.textContent = t(title);
  drawerBodyEl.innerHTML = bodyHtml;
  drawerEl.classList.remove("hidden");
  applyTranslations(drawerEl);
}

function renderError(error) {
  contentEl.innerHTML = `<div class="card"><div class="empty">${escapeHtml(
    error?.message || String(error)
  )}</div></div>`;
  applyTranslations(contentEl);
}

async function api(path, options = {}) {
  const resp = await fetch(path, {
    headers: {
      "Content-Type": "application/json",
      ...(options.headers || {}),
    },
    ...options,
  });
  const text = await resp.text();
  let data;
  try {
    data = text ? JSON.parse(text) : {};
  } catch {
    data = { detail: text };
  }
  if (!resp.ok) {
    throw new Error(data.detail || `HTTP ${resp.status}`);
  }
  return data;
}

async function fetchSuggestions(type, keyword = "", limit = 12) {
  const params = new URLSearchParams({
    type,
    keyword: keyword || "",
    limit: String(limit),
  });
  const data = await api(`/api/admin/search/suggestions?${params.toString()}`);
  return data.items || [];
}

async function attachAutocomplete(inputId, type, mapValue = (item) => item.value) {
  const input = document.getElementById(inputId);
  if (!input) return;
  const listId = `${inputId}-datalist`;
  let datalist = document.getElementById(listId);
  if (!datalist) {
    datalist = document.createElement("datalist");
    datalist.id = listId;
    input.insertAdjacentElement("afterend", datalist);
  }
  input.setAttribute("list", listId);

  const render = (items) => {
    datalist.innerHTML = items
      .map((item) => {
        const label = item.label ? ` label="${escapeHtml(item.label)}"` : "";
        return `<option value="${escapeHtml(mapValue(item))}"${label}></option>`;
      })
      .join("");
  };

  const cacheKey = `${type}::default`;
  if (appState.recentSuggestions[cacheKey]) {
    render(appState.recentSuggestions[cacheKey]);
  } else {
    try {
      const initial = await fetchSuggestions(type, "", 20);
      appState.recentSuggestions[cacheKey] = initial;
      render(initial);
    } catch {
      // ignore
    }
  }

  let timer = null;
  input.addEventListener("input", () => {
    clearTimeout(timer);
    timer = setTimeout(async () => {
      try {
        const rows = await fetchSuggestions(type, input.value.trim(), 20);
        render(rows);
      } catch {
        // ignore
      }
    }, 120);
  });
}

function updateQueryString(params) {
  const usp = new URLSearchParams();
  Object.entries(params || {}).forEach(([k, v]) => {
    if (v !== undefined && v !== null && `${v}`.trim() !== "") {
      usp.set(k, String(v));
    }
  });
  return usp.toString();
}

function renderMarkdownSafe(mdText) {
  const input = mdText || "";
  if (window.marked?.parse) {
    const rendered = window.marked.parse(input);
    if (window.DOMPurify?.sanitize) {
      return window.DOMPurify.sanitize(rendered);
    }
    return rendered;
  }
  return `<pre>${escapeHtml(input)}</pre>`;
}

function renderStructuredJson(parsed) {
  if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return null;

  if (Array.isArray(parsed.nodes) && Array.isArray(parsed.edges)) {
    const nodeRows = (parsed.nodes || []).slice(0, 200).map((n) => ({
      id: n?.id ?? "",
      name: n?.name ?? "",
      layer: n?.layer ?? "",
      last_updated: n?.last_updated ?? "",
    }));
    const edgeRows = (parsed.edges || []).slice(0, 300).map((e) => ({
      source: e?.source ?? "",
      target: e?.target ?? "",
      pipeline: e?.pipeline ?? "",
      type: e?.type ?? "",
    }));
    return `
      <div class="rich-structured">
        ${
          parsed.summary
            ? `<div class="rich-block"><div class="rich-title">${escapeHtml(t("Summary"))}</div><div class="rich-text">${escapeHtml(parsed.summary)}</div></div>`
            : ""
        }
        <div class="rich-block">
          <div class="rich-title">${escapeHtml(t("Nodes"))} (${nodeRows.length})</div>
          ${DataTable(
            [
              { title: "ID", key: "id" },
              { title: "Name", key: "name" },
              { title: "Layer", key: "layer" },
              { title: "Last Updated", key: "last_updated" },
            ],
            nodeRows
          )}
        </div>
        <div class="rich-block">
          <div class="rich-title">${escapeHtml(t("Edges"))} (${edgeRows.length})</div>
          ${DataTable(
            [
              { title: "Source", key: "source" },
              { title: "Target", key: "target" },
              { title: "Pipeline", key: "pipeline" },
              { title: "Type", key: "type" },
            ],
            edgeRows
          )}
        </div>
        <details class="trace-detail">
          <summary>${escapeHtml(t("Raw JSON"))}</summary>
          ${JsonViewer(parsed)}
        </details>
      </div>
    `;
  }

  if (
    Array.isArray(parsed.upstream) ||
    Array.isArray(parsed.downstream) ||
    Array.isArray(parsed.pipelines)
  ) {
    const upstream = Array.isArray(parsed.upstream) ? parsed.upstream : [];
    const downstream = Array.isArray(parsed.downstream) ? parsed.downstream : [];
    const pipelines = Array.isArray(parsed.pipelines) ? parsed.pipelines : [];
    const freshness = parsed.last_updated || parsed.freshness || "";
    return `
      <div class="rich-structured">
        <div class="rich-block">
          <div class="rich-title">${escapeHtml(t("Lineage Snapshot"))}</div>
          <div class="rich-text">${escapeHtml(t("Asset"))}: ${escapeHtml(parsed.table || parsed.asset || "N/A")}</div>
          ${
            freshness
              ? `<div class="rich-text">${escapeHtml(t("Freshness"))}: ${escapeHtml(freshness)}</div>`
              : ""
          }
        </div>
        <div class="rich-block">
          <div class="rich-title">${escapeHtml(t("Upstream"))} (${upstream.length})</div>
          ${upstream.length ? DataTable([{ title: "Asset", key: "asset" }], upstream.map((asset) => ({ asset }))) : `<div class="empty">${escapeHtml(t("No upstream nodes"))}</div>`}
        </div>
        <div class="rich-block">
          <div class="rich-title">${escapeHtml(t("Downstream"))} (${downstream.length})</div>
          ${downstream.length ? DataTable([{ title: "Asset", key: "asset" }], downstream.map((asset) => ({ asset }))) : `<div class="empty">${escapeHtml(t("No downstream nodes"))}</div>`}
        </div>
        <div class="rich-block">
          <div class="rich-title">${escapeHtml(t("Pipelines"))} (${pipelines.length})</div>
          ${pipelines.length ? DataTable([{ title: "Pipeline", key: "pipeline" }], pipelines.map((pipeline) => ({ pipeline }))) : `<div class="empty">${escapeHtml(t("No pipeline records"))}</div>`}
        </div>
        <details class="trace-detail">
          <summary>${escapeHtml(t("Raw JSON"))}</summary>
          ${JsonViewer(parsed)}
        </details>
      </div>
    `;
  }

  return null;
}

function tryJsonTable(text) {
  if (!text) return null;
  const trimmed = text.trim();
  let candidate = trimmed;
  if (!candidate.startsWith("{") && !candidate.startsWith("[")) {
    const fenced =
      candidate.match(/^```(?:json|javascript|js)?\s*([\s\S]*?)\s*```$/i) ||
      candidate.match(/^```(?:json|javascript|js)?\s*([\s\S]*)$/i);
    if (!fenced) return null;
    candidate = (fenced[1] || "").trim();
    if (!candidate.startsWith("{") && !candidate.startsWith("[")) return null;
  }
  try {
    const parsed = JSON.parse(candidate);
    if (Array.isArray(parsed) && parsed.length && typeof parsed[0] === "object") {
      const cols = Object.keys(parsed[0]).slice(0, 12);
      const table = DataTable(
        cols.map((key) => ({ title: key, key })),
        parsed.slice(0, 200)
      );
      return `<div class="rich-table">${table}</div>`;
    }
    if (parsed && typeof parsed === "object") {
      const structured = renderStructuredJson(parsed);
      if (structured) return structured;
      return JsonViewer(parsed);
    }
  } catch {
    return null;
  }
  return null;
}

function renderRichContent(text) {
  const asTable = tryJsonTable(text);
  if (asTable) return asTable;
  return `<div class="rich-md">${renderMarkdownSafe(text)}</div>`;
}

function renderChatMessage(msg) {
  const cls = msg.role === "user" ? "chat-msg user" : "chat-msg assistant";
  const roleLabel = msg.role === "user" ? t("You") : t("Assistant");
  let traceHtml = "";
  if (msg.tool_trace && msg.tool_trace.length) {
    traceHtml = `
      <details class="trace-detail">
        <summary>${escapeHtml(t("Tool Trace"))} (${msg.tool_trace.length})</summary>
        ${JsonViewer(msg.tool_trace)}
      </details>
    `;
  }
  return `
    <div class="${cls}">
      <div class="chat-role">${roleLabel}</div>
      <div class="chat-bubble">${renderRichContent(msg.content)}</div>
      ${traceHtml}
    </div>
  `;
}

function renderChatTimeline() {
  const timeline = document.getElementById("chat-timeline");
  if (!timeline) return;
  timeline.innerHTML = appState.chatMessages.length
    ? appState.chatMessages.map(renderChatMessage).join("")
    : `<div class="empty">${escapeHtml(t("Start by asking lineage, impact, SLA or job questions."))}</div>`;
  timeline.scrollTop = timeline.scrollHeight;
  applyTranslations(timeline);
}

async function sendChatQuestion() {
  const input = document.getElementById("chat-input");
  const sendBtn = document.getElementById("chat-send-btn");
  if (!input || !sendBtn) return;
  const question = input.value.trim();
  if (!question) return;
  input.value = "";

  appState.chatMessages.push({ role: "user", content: question });
  renderChatTimeline();
  sendBtn.disabled = true;
  appState.chatMessages.push({ role: "assistant", content: t("Thinking") });
  renderChatTimeline();

  try {
    const sceneType = document.getElementById("chat-scene-type")?.value?.trim() || "";
    const promptTemplateKey = document.getElementById("chat-template-key")?.value?.trim() || "";
    const payload = {
      question,
      session_id: appState.chatSessionId || undefined,
    };
    if (sceneType) payload.scene_type = sceneType;
    if (promptTemplateKey) payload.prompt_template_key = promptTemplateKey;
    const response = await api("/chat", {
      method: "POST",
      body: JSON.stringify(payload),
    });
    appState.chatSceneType = response.scene_type || sceneType || "";
    appState.chatPromptTemplateKey =
      response.prompt_template_key || promptTemplateKey || "";
    appState.chatSessionId = response.session_id || appState.chatSessionId;
    appState.chatMessages.pop();
    appState.chatMessages.push({
      role: "assistant",
      content: response.answer || t("No answer"),
      tool_trace: response.tool_trace || [],
    });
    renderChatTimeline();
    await loadChatSessionList();
  } catch (error) {
    appState.chatMessages.pop();
    appState.chatMessages.push({
      role: "assistant",
      content: `${t("Error")}: ${error.message}`,
    });
    renderChatTimeline();
  } finally {
    sendBtn.disabled = false;
    input.focus();
  }
}

async function loadChatSessionList() {
  const listEl = document.getElementById("chat-session-list");
  if (!listEl) return;
  try {
    const sessions = await api("/api/admin/chats?limit=200");
    const keyword = document.getElementById("chat-session-search")?.value?.trim().toLowerCase() || "";
    const filtered = keyword
      ? sessions.filter((s) => {
          const title = (s.title || "").toLowerCase();
          const key = (s.session_key || "").toLowerCase();
          return title.includes(keyword) || key.includes(keyword);
        })
      : sessions;
    if (!filtered.length) {
      listEl.innerHTML = `<div class="empty">${escapeHtml(t("No chat sessions yet."))}</div>`;
      applyTranslations(listEl);
      return;
    }
    listEl.innerHTML = filtered
      .map(
        (s) => `
      <button class="chat-session-item" data-id="${s.id}" data-session="${escapeHtml(
          s.session_key
        )}">
        <div class="title">${escapeHtml(s.title || s.session_key)}</div>
        <div class="meta">${escapeHtml(
          `${s.message_count} ${t("msgs")} · ${formatDate(s.updated_at)}`
        )}</div>
      </button>
    `
      )
      .join("");
    listEl.querySelectorAll(".chat-session-item").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        const data = await api(`/api/admin/chats/${id}`);
        appState.chatSessionId = data.session?.session_key || "";
        appState.chatMessages = (data.messages || [])
          .filter((m) => m.role === "user" || m.role === "assistant")
          .map((m) => ({ role: m.role, content: m.content }));
        const latestAssistant = [...(data.messages || [])]
          .reverse()
          .find((m) => m.role === "assistant" && m.metadata_json);
        if (latestAssistant?.metadata_json) {
          appState.chatSceneType = latestAssistant.metadata_json.scene_type || "";
          appState.chatPromptTemplateKey =
            latestAssistant.metadata_json.prompt_template_key || "";
          const sceneInput = document.getElementById("chat-scene-type");
          const templateInput = document.getElementById("chat-template-key");
          if (sceneInput) sceneInput.value = appState.chatSceneType;
          if (templateInput) templateInput.value = appState.chatPromptTemplateKey;
        }
        renderChatTimeline();
      });
    });
  } catch {
    listEl.innerHTML = `<div class="empty">${escapeHtml(t("Session list load failed."))}</div>`;
  }
  applyTranslations(listEl);
}

async function renderChatPage() {
  renderPageHeader(
    "Chat",
    "Dialogue mode with markdown/table rich output. Select scene/template to control response style.",
    `
      <button id="chat-new-btn" class="btn secondary">New Chat</button>
      <button id="chat-refresh-btn" class="btn secondary">Refresh Sessions</button>
    `
  );
  contentEl.innerHTML = `
    <div class="chat-layout">
      <section class="card chat-left">
        <h3>Sessions</h3>
        <div class="row">
          <div style="flex:1 1 200px;">
            <label>Search Session</label>
            <input id="chat-session-search" placeholder="session key / title">
          </div>
        </div>
        <div id="chat-session-list" class="chat-session-list"></div>
      </section>
      <section class="card chat-main">
        <div id="chat-timeline" class="chat-timeline"></div>
        <div class="chat-input-area">
          <textarea id="chat-input" placeholder="Ask anything: lineage, impact scope, failed jobs, SLA risk..."></textarea>
          <div class="row">
            <button id="chat-send-btn" class="btn">Send</button>
            <span class="page-subtitle">Enter = send, Shift+Enter = newline</span>
          </div>
        </div>
      </section>
      <section class="card chat-right">
        <h3>Prompt Strategy</h3>
        <div class="row">
          <div style="flex:1 1 180px;">
            <label>Scene Type</label>
            <select id="chat-scene-type">
              <option value="">auto_infer</option>
              <option value="lineage_query">lineage_query</option>
              <option value="sla_query">sla_query</option>
              <option value="daily_report">daily_report</option>
              <option value="failed_jobs_query">failed_jobs_query</option>
              <option value="risk_analysis">risk_analysis</option>
            </select>
          </div>
          <div style="flex:1 1 220px;">
            <label>Prompt Template Key</label>
            <input id="chat-template-key" placeholder="optional override key">
          </div>
        </div>
        <h3>Quick Prompts</h3>
        <div class="prompt-list">
          <button class="btn secondary prompt-btn" data-scene="lineage_query" data-q="Which teams are impacted by silver.customer_contact failure?">${escapeHtml(t("Impacted Teams"))}</button>
          <button class="btn secondary prompt-btn" data-scene="lineage_query" data-q="Show upstream lineage for API.customer_profile">${escapeHtml(t("Upstream Lineage"))}</button>
          <button class="btn secondary prompt-btn" data-scene="failed_jobs_query" data-q="List failed runs in Customer domain today">${escapeHtml(t("Failed Jobs"))}</button>
          <button class="btn secondary prompt-btn" data-scene="sla_query" data-q="Which assets are at SLA risk?">${escapeHtml(t("SLA Risks"))}</button>
        </div>
        <h3>Current Session</h3>
        <div class="session-chip">${escapeHtml(appState.chatSessionId || t("(new)"))}</div>
        <h3>Prompt Context</h3>
        <div class="session-chip">${escapeHtml(t("Scene"))}: ${escapeHtml(appState.chatSceneType || "auto_infer")}</div>
        <div class="session-chip">${escapeHtml(t("Template"))}: ${escapeHtml(appState.chatPromptTemplateKey || t("(default)"))}</div>
      </section>
    </div>
  `;

  document.getElementById("chat-send-btn").addEventListener("click", sendChatQuestion);
  document.getElementById("chat-input").addEventListener("keydown", (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendChatQuestion();
    }
  });
  document.getElementById("chat-new-btn").addEventListener("click", () => {
    appState.chatSessionId = "";
    appState.chatSceneType = "";
    appState.chatPromptTemplateKey = "";
    appState.chatMessages = [];
    renderChatPage();
  });
  document.getElementById("chat-refresh-btn").addEventListener("click", loadChatSessionList);
  document.getElementById("chat-session-search").addEventListener("input", () => {
    loadChatSessionList();
  });
  document.getElementById("chat-scene-type").value = appState.chatSceneType || "";
  document.getElementById("chat-template-key").value = appState.chatPromptTemplateKey || "";
  document.getElementById("chat-scene-type").addEventListener("change", (e) => {
    appState.chatSceneType = e.target.value || "";
  });
  document.getElementById("chat-template-key").addEventListener("input", (e) => {
    appState.chatPromptTemplateKey = e.target.value || "";
  });
  document.querySelectorAll(".prompt-btn").forEach((btn) => {
    btn.addEventListener("click", () => {
      const input = document.getElementById("chat-input");
      input.value = btn.getAttribute("data-q");
      const scene = btn.getAttribute("data-scene");
      if (scene) {
        document.getElementById("chat-scene-type").value = scene;
        appState.chatSceneType = scene;
      }
      input.focus();
    });
  });
  await attachAutocomplete("chat-session-search", "chat_session");
  await attachAutocomplete("chat-template-key", "prompt_template");

  renderChatTimeline();
  await loadChatSessionList();
}

function buildKpiCard(label, value, trendText) {
  return `
    <div class="stat-card stat-large">
      <div class="label">${escapeHtml(t(label))}</div>
      <div class="value">${escapeHtml(value)}</div>
      <div class="trend">${escapeHtml(trendText ? t(trendText) : "")}</div>
    </div>
  `;
}

async function renderBigScreen() {
  renderPageHeader(
    "Data Command Center",
    "Large-screen governance cockpit: incidents, throughput, domain health and execution pulse."
  );

  const [dashboard, jobs, trace, failed] = await Promise.all([
    api("/api/admin/dashboard"),
    api("/api/admin/jobs"),
    api("/api/admin/logs/trace?limit=200"),
    api("/runtime/failed"),
  ]);

  const runtimeErrors = trace.runtime_errors || [];
  const auditLogs = trace.audit_logs || [];
  const runningJobs = (jobs || []).filter((j) => (j.status || "").toLowerCase().includes("run")).length;
  const failedJobs = (failed.items || []).length;
  const criticalErrors = runtimeErrors.filter((e) => (e.severity || "").toLowerCase() === "critical").length;
  const toolCalls = (trace.tool_traces || []).length;

  contentEl.innerHTML = `
    <section class="stats bigscreen-kpis">
      ${buildKpiCard("Tool Calls", toolCalls, "last trace window")}
      ${buildKpiCard("Failed Jobs", failedJobs, "today")}
      ${buildKpiCard("Critical Errors", criticalErrors, "runtime_events")}
      ${buildKpiCard("Running Jobs", runningJobs, "scheduler")}
      ${buildKpiCard("Chat Sessions", dashboard.stats?.chat_sessions || 0, "admin tracked")}
      ${buildKpiCard("Data Sources", dashboard.stats?.data_sources || 0, "catalog")}
    </section>

    <section class="bigscreen-grid">
      <div class="card panel glow">
        <h3>System Health</h3>
        <div class="health-banner">
          <span>Overall Status</span>
          ${StatusBadge(dashboard.system_status || "unknown")}
        </div>
        <div class="mini-bars">
          ${(dashboard.recent_errors || [])
            .slice(0, 8)
            .map((e) => {
              const severity = (e.severity || "").toLowerCase();
              const width = severity === "critical" ? 96 : severity === "high" ? 72 : 48;
              return `<div class="bar-row"><span>${escapeHtml(e.error_code || "ERROR")}</span><div class="bar"><i style="width:${width}%"></i></div></div>`;
            })
            .join("") || `<div class="empty">No recent errors.</div>`}
        </div>
      </div>

      <div class="card panel">
        <h3>Recent Tasks</h3>
        ${DataTable(
          [
            { title: "Job", key: "job_name" },
            { title: "Status", render: (r) => StatusBadge(r.status) },
            { title: "Start", render: (r) => escapeHtml(formatDate(r.started_at)) },
            { title: "Duration", key: "duration_ms" },
          ],
          (dashboard.recent_tasks || []).slice(0, 8)
        )}
      </div>
    </section>
  `;
}

async function renderDashboard() {
  renderPageHeader("Dashboard", "System overview and admin metrics.");
  const data = await api("/api/admin/dashboard");
  const stats = data.stats || {};
  contentEl.innerHTML = `
    <div class="stats">
      ${Object.entries(stats)
        .map(
          ([k, v]) => `<div class="stat-card"><div class="label">${escapeHtml(k)}</div><div class="value">${escapeHtml(v)}</div></div>`
        )
        .join("")}
    </div>
    <div class="card">
      <h3>${escapeHtml(t("System Status"))}: ${StatusBadge(data.system_status)}</h3>
      <p class="page-subtitle">Recent task and runtime issue summary.</p>
    </div>
    <div class="card">
      <h3>Recent Errors</h3>
      ${DataTable(
        [
          { title: "Severity", render: (r) => StatusBadge(r.severity) },
          { title: "Code", key: "error_code" },
          { title: "Message", key: "error_message" },
          { title: "Occurred", render: (r) => escapeHtml(formatDate(r.occurred_at)) },
        ],
        data.recent_errors || []
      )}
    </div>
  `;
}

function lineageComputeLayout(data, direction) {
  const nodes = (data.nodes || []).map((n) => ({ ...n, id: n.qualified_name }));
  const rootId = data.root_asset;
  const edges = (data.edges || []).map((e) => ({
    id: `${e.upstream_asset}=>${e.downstream_asset}`,
    source: e.upstream_asset,
    target: e.downstream_asset,
    dependency_type: e.dependency_type,
  }));

  const byId = new Map(nodes.map((n) => [n.id, n]));
  const neighbors = (id) => {
    if (direction === "upstream") {
      return edges.filter((e) => e.target === id).map((e) => e.source);
    }
    return edges.filter((e) => e.source === id).map((e) => e.target);
  };

  const levelMap = new Map();
  levelMap.set(rootId, 0);
  const q = [rootId];
  while (q.length) {
    const cur = q.shift();
    const lvl = levelMap.get(cur) || 0;
    neighbors(cur).forEach((next) => {
      if (!levelMap.has(next)) {
        levelMap.set(next, lvl + 1);
        q.push(next);
      }
    });
  }
  nodes.forEach((n) => {
    if (!levelMap.has(n.id)) levelMap.set(n.id, 0);
  });

  const groups = new Map();
  nodes.forEach((n) => {
    const lvl = levelMap.get(n.id) || 0;
    if (!groups.has(lvl)) groups.set(lvl, []);
    groups.get(lvl).push(n);
  });

  const levelGap = 280;
  const rowGap = 100;
  const width = Math.max(groups.size * levelGap + 400, 1200);
  let maxRows = 1;
  [...groups.values()].forEach((arr) => {
    maxRows = Math.max(maxRows, arr.length);
  });
  const height = Math.max(maxRows * rowGap + 240, 700);

  [...groups.entries()].forEach(([lvl, arr]) => {
    arr.sort((a, b) => a.id.localeCompare(b.id));
    const baseX = 80 + lvl * levelGap;
    const total = arr.length;
    arr.forEach((n, idx) => {
      n.x = baseX;
      n.y = 80 + idx * rowGap + ((maxRows - total) * rowGap) / 2;
      n.width = 220;
      n.height = 64;
    });
  });
  return { nodes, edges, byId, width, height };
}

function updateLineageTransform() {
  const viewport = document.getElementById("lineage-viewport");
  if (!viewport) return;
  const t = appState.lineage.transform;
  viewport.setAttribute("transform", `translate(${t.x}, ${t.y}) scale(${t.scale})`);
}

function attachLineageInteractions() {
  const svg = document.getElementById("lineage-svg");
  if (!svg) return;
  const state = appState.lineage;
  svg.addEventListener("wheel", (e) => {
    e.preventDefault();
    const delta = e.deltaY > 0 ? -0.1 : 0.1;
    state.transform.scale = Math.min(3.5, Math.max(0.35, state.transform.scale + delta));
    updateLineageTransform();
  });
  svg.addEventListener("mousedown", (e) => {
    state.isDragging = true;
    state.dragStart = { x: e.clientX, y: e.clientY };
  });
  window.addEventListener("mousemove", (e) => {
    if (!state.isDragging) return;
    const dx = e.clientX - state.dragStart.x;
    const dy = e.clientY - state.dragStart.y;
    state.transform.x += dx;
    state.transform.y += dy;
    state.dragStart = { x: e.clientX, y: e.clientY };
    updateLineageTransform();
  });
  window.addEventListener("mouseup", () => {
    state.isDragging = false;
  });
}

function renderLineageGraph(data, direction) {
  const model = lineageComputeLayout(data, direction);
  const nodeMap = model.byId;
  const edgesSvg = model.edges
    .map((e) => {
      const s = nodeMap.get(e.source);
      const t = nodeMap.get(e.target);
      if (!s || !t) return "";
      const x1 = s.x + s.width;
      const y1 = s.y + s.height / 2;
      const x2 = t.x;
      const y2 = t.y + t.height / 2;
      const cx = (x1 + x2) / 2;
      const path = `M ${x1} ${y1} C ${cx} ${y1}, ${cx} ${y2}, ${x2} ${y2}`;
      return `<path class="lineage-edge" d="${path}"></path><text x="${cx}" y="${(y1 + y2) / 2 - 8}" class="lineage-edge-label">${escapeHtml(
        e.dependency_type || ""
      )}</text>`;
    })
    .join("");
  const nodesSvg = model.nodes
    .map(
      (n) => `<g class="lineage-node" data-node="${escapeHtml(n.id)}" transform="translate(${n.x}, ${n.y})"><rect width="${n.width}" height="${n.height}" rx="12"></rect><text x="12" y="24" class="title">${escapeHtml(
        n.qualified_name || n.id
      )}</text><text x="12" y="44" class="meta">${escapeHtml(`${n.system || "?"} · ${n.asset_type || "asset"}`)}</text></g>`
    )
    .join("");

  document.getElementById("lineage-canvas").innerHTML = `
    <svg id="lineage-svg" width="100%" height="760" viewBox="0 0 ${Math.max(model.width, 1200)} ${Math.max(
    model.height,
    760
  )}">
      <g id="lineage-viewport">${edgesSvg}${nodesSvg}</g>
    </svg>
  `;
  appState.lineage.transform = { x: 40, y: 30, scale: 1 };
  updateLineageTransform();
  attachLineageInteractions();
}

async function renderLineagePage() {
  renderPageHeader(
    "Pipeline Lineage",
    "Zoom, pan, search and inspect upstream/downstream lineage with interactive graph.",
    `<button class="btn secondary" id="lineage-zoom-in">Zoom +</button>
     <button class="btn secondary" id="lineage-zoom-out">Zoom -</button>
     <button class="btn secondary" id="lineage-reset">Reset</button>`
  );
  const assets = await api("/api/admin/assets?limit=500");
  const options = assets.map((a) => `<option value="${escapeHtml(a.qualified_name)}"></option>`).join("");
  const defaultAsset = assets[0]?.qualified_name || "Gold.customer_profile";
  contentEl.innerHTML = `
    <div class="card">
      <div class="row">
        <div style="flex:2 1 420px;"><label>Asset</label><input id="lineage-asset-input" list="lineage-assets" value="${escapeHtml(
          defaultAsset
        )}"><datalist id="lineage-assets">${options}</datalist></div>
        <div style="flex:1 1 180px;"><label>Direction</label><select id="lineage-direction"><option value="downstream">downstream</option><option value="upstream">upstream</option></select></div>
        <div style="flex:1 1 240px;"><label>Search Node</label><input id="lineage-search" list="lineage-node-options" placeholder="keyword"><datalist id="lineage-node-options"></datalist></div>
        <div style="align-self:flex-end;"><button id="lineage-locate-btn" class="btn secondary">Locate Node</button></div>
        <div style="align-self:flex-end;"><button id="lineage-load-btn" class="btn">Load Graph</button></div>
      </div>
    </div>
    <div class="card"><div id="lineage-canvas" class="lineage-canvas"><div class="empty">Loading lineage graph...</div></div></div>
  `;

  async function loadLineage() {
    const assetName = document.getElementById("lineage-asset-input").value.trim();
    const direction = document.getElementById("lineage-direction").value;
    if (!assetName) return;
    const data = await api(`/api/admin/lineage?asset_name=${encodeURIComponent(assetName)}&direction=${direction}`);
    appState.lineage.data = data;
    renderLineageGraph(data, direction);
    const nodeListEl = document.getElementById("lineage-node-options");
    if (nodeListEl) {
      nodeListEl.innerHTML = (data.nodes || [])
        .map((n) => `<option value="${escapeHtml(n.qualified_name)}"></option>`)
        .join("");
    }
  }

  function locateNode(keyword) {
    const q = (keyword || "").trim().toLowerCase();
    if (!q) return;
    const nodes = [...document.querySelectorAll(".lineage-node")];
    if (!nodes.length) return;
    const target =
      nodes.find((nodeEl) =>
        (nodeEl.getAttribute("data-node") || "").toLowerCase() === q
      ) ||
      nodes.find((nodeEl) =>
        (nodeEl.getAttribute("data-node") || "").toLowerCase().includes(q)
      );
    if (!target) return;
    nodes.forEach((nodeEl) => nodeEl.classList.remove("highlight"));
    target.classList.add("highlight");

    const svg = document.getElementById("lineage-svg");
    const scale = appState.lineage.transform.scale;
    if (svg && target.getBBox) {
      const box = target.getBBox();
      const centerX = box.x + box.width / 2;
      const centerY = box.y + box.height / 2;
      const viewWidth = svg.clientWidth || 1200;
      const viewHeight = svg.clientHeight || 760;
      appState.lineage.transform.x = viewWidth / 2 - centerX * scale;
      appState.lineage.transform.y = viewHeight / 2 - centerY * scale;
      updateLineageTransform();
    }
  }

  document.getElementById("lineage-load-btn").addEventListener("click", async () => {
    try {
      await loadLineage();
    } catch (e) {
      document.getElementById("lineage-canvas").innerHTML = `<div class="empty">${escapeHtml(e.message)}</div>`;
    }
  });
  document.getElementById("lineage-search").addEventListener("input", (e) => {
    const q = e.target.value.trim().toLowerCase();
    document.querySelectorAll(".lineage-node").forEach((nodeEl) => {
      const n = (nodeEl.getAttribute("data-node") || "").toLowerCase();
      nodeEl.classList.toggle("highlight", !!q && n.includes(q));
    });
  });
  document.getElementById("lineage-search").addEventListener("keydown", (e) => {
    if (e.key === "Enter") {
      e.preventDefault();
      locateNode(e.target.value);
    }
  });
  document.getElementById("lineage-locate-btn").addEventListener("click", () => {
    locateNode(document.getElementById("lineage-search").value);
  });
  document.getElementById("lineage-zoom-in").addEventListener("click", () => {
    appState.lineage.transform.scale = Math.min(3.5, appState.lineage.transform.scale + 0.1);
    updateLineageTransform();
  });
  document.getElementById("lineage-zoom-out").addEventListener("click", () => {
    appState.lineage.transform.scale = Math.max(0.35, appState.lineage.transform.scale - 0.1);
    updateLineageTransform();
  });
  document.getElementById("lineage-reset").addEventListener("click", () => {
    appState.lineage.transform = { x: 40, y: 30, scale: 1 };
    updateLineageTransform();
  });
  await attachAutocomplete("lineage-asset-input", "asset");
  await loadLineage();
}

async function renderTools() {
  renderPageHeader("Tools", "Tool metadata and schema overview with scene prompt bindings.");
  contentEl.innerHTML = `
    <div class="card">
      <div class="row">
        <div style="flex:2 1 260px;"><label>Search Tool</label><input id="tools-search" placeholder="tool name"></div>
        <div style="flex:1 1 180px;"><label>Enabled</label><select id="tools-enabled"><option value="">all</option><option value="true">enabled</option><option value="false">disabled</option></select></div>
        <div style="align-self:flex-end;"><button id="tools-load" class="btn">Search</button></div>
      </div>
    </div>
    <div class="card" id="tools-table-wrap"><div class="empty">Loading...</div></div>
  `;
  await attachAutocomplete("tools-search", "tool");

  const loadTools = async () => {
    const q = document.getElementById("tools-search").value.trim();
    const enabled = document.getElementById("tools-enabled").value;
    const query = updateQueryString({ q, enabled });
    const tools = await api(`/api/admin/tools${query ? `?${query}` : ""}`);
    document.getElementById("tools-table-wrap").innerHTML = DataTable(
      [
        { title: "ID", key: "id" },
        { title: "Name", key: "name" },
        { title: "Enabled", render: (r) => StatusBadge(r.enabled ? "enabled" : "disabled") },
        { title: "Version", key: "active_version" },
        { title: "Prompt Bindings", key: "bound_prompt_count" },
        { title: "Scenes", render: (r) => escapeHtml((r.bound_scenes || []).join(", ")) },
        { title: "Action", render: (r) => `<button class="btn secondary tool-detail-btn" data-id="${r.id}">Detail</button>` },
      ],
      tools
    );
    applyTranslations(document.getElementById("tools-table-wrap"));
    document.querySelectorAll(".tool-detail-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const toolId = btn.getAttribute("data-id");
        const detail = await api(`/api/admin/tools/${toolId}`);
        const templates = await api(`/api/admin/prompt-templates?limit=500`);
        const options = templates
          .map(
            (t) =>
              `<option value="${t.id}">${escapeHtml(t.name)} (${escapeHtml(
                t.scene_type
              )})</option>`
          )
          .join("");
        openDrawer(
          `Tool Detail #${toolId}`,
          `
          <div class="card"><h3>Tool Metadata</h3>${JsonViewer(detail)}</div>
          <div class="card">
            <h3>Bound Prompt Templates</h3>
            ${DataTable(
              [
                { title: "Binding ID", key: "id" },
                { title: "Scene", key: "scene_type" },
                { title: "Template Key", key: "template_key" },
                { title: "Template Name", key: "template_name" },
                { title: "Default", render: (r) => StatusBadge(r.is_default ? "default" : "no") },
                { title: "Action", render: (r) => `<button class="btn warning binding-del-btn" data-tool-id="${toolId}" data-binding-id="${r.id}">Delete</button>` },
              ],
              detail.prompt_bindings || []
            )}
            <div class="row" style="margin-top:10px;">
              <div style="flex:1 1 180px;"><label>Scene Type</label><input id="binding-scene" placeholder="lineage_query"></div>
              <div style="flex:2 1 240px;"><label>Prompt Template</label><select id="binding-template-id">${options}</select></div>
              <div style="flex:1 1 120px;align-self:flex-end;"><button class="btn" id="binding-add-btn">Add Binding</button></div>
            </div>
          </div>
        `
        );
        document.getElementById("binding-add-btn").addEventListener("click", async () => {
          const sceneType = document.getElementById("binding-scene").value.trim();
          const templateId = document.getElementById("binding-template-id").value;
          if (!sceneType || !templateId) return alert(t("scene/template required"));
          await api(`/api/admin/tools/${toolId}/prompt-bindings`, {
            method: "POST",
            body: JSON.stringify({
              scene_type: sceneType,
              prompt_template_id: Number(templateId),
              is_default: true,
            }),
          });
          drawerEl.classList.add("hidden");
          await loadTools();
        });
        document.querySelectorAll(".binding-del-btn").forEach((delBtn) => {
          delBtn.addEventListener("click", async () => {
            const bindingId = delBtn.getAttribute("data-binding-id");
            await api(`/api/admin/tools/${toolId}/prompt-bindings/${bindingId}`, {
              method: "DELETE",
            });
            drawerEl.classList.add("hidden");
            await loadTools();
          });
        });
      });
    });
  };
  document.getElementById("tools-load").addEventListener("click", loadTools);
  await loadTools();
}

async function openPromptTemplateEditor(existing = null) {
  const isEdit = !!existing;
  const template = existing || {
    name: "",
    template_key: "",
    scene_type: "lineage_query",
    description: "",
    usage_notes: "",
    prompt_content: "",
    output_format: "",
    example_input: "",
    example_output: "",
    is_default: false,
    status: "draft",
    version: "v1",
  };
  openDrawer(
    isEdit ? `${t("Edit Prompt Template")} #${template.id}` : t("Create Prompt Template"),
    `
      <div class="card">
        <div class="row">
          <div style="flex:1 1 220px;"><label>Name</label><input id="pt-name" value="${escapeHtml(template.name || "")}"></div>
          <div style="flex:1 1 220px;"><label>Key</label><input id="pt-key" value="${escapeHtml(template.template_key || "")}"></div>
          <div style="flex:1 1 180px;"><label>Scene</label><select id="pt-scene">
            ${[
              "lineage_query",
              "sla_query",
              "daily_report",
              "failed_jobs_query",
              "risk_analysis",
            ]
              .map((s) => `<option value="${s}" ${template.scene_type === s ? "selected" : ""}>${s}</option>`)
              .join("")}
          </select></div>
        </div>
        <div class="row">
          <div style="flex:2 1 300px;"><label>Description</label><input id="pt-description" value="${escapeHtml(template.description || "")}"></div>
          <div style="flex:1 1 160px;"><label>Status</label><select id="pt-status"><option value="draft" ${template.status === "draft" ? "selected" : ""}>draft</option><option value="active" ${template.status === "active" ? "selected" : ""}>active</option></select></div>
          <div style="flex:1 1 120px;"><label>Version</label><input id="pt-version" value="${escapeHtml(template.version || "v1")}"></div>
        </div>
        <div><label>Usage Notes</label><textarea id="pt-usage">${escapeHtml(template.usage_notes || "")}</textarea></div>
        <div><label>Prompt Content</label><textarea id="pt-content">${escapeHtml(template.prompt_content || "")}</textarea></div>
        <div><label>Output Format</label><textarea id="pt-output-format">${escapeHtml(template.output_format || "")}</textarea></div>
        <div class="row">
          <div style="flex:1 1 280px;"><label>Example Input</label><textarea id="pt-example-input">${escapeHtml(template.example_input || "")}</textarea></div>
          <div style="flex:1 1 280px;"><label>Example Output</label><textarea id="pt-example-output">${escapeHtml(template.example_output || "")}</textarea></div>
        </div>
        <div class="row" style="align-items:center;">
          <label style="display:flex;gap:8px;align-items:center;"><input type="checkbox" id="pt-default" ${template.is_default ? "checked" : ""}>Set as default in scene</label>
          <button class="btn secondary" id="pt-preview-btn">Preview Prompt</button>
          <button class="btn" id="pt-save-btn">${isEdit ? t("Save") : t("Create")}</button>
        </div>
      </div>
      <div class="card"><h3>Preview</h3><div id="pt-preview-box" class="empty">Click Preview to render final prompt.</div></div>
    `
  );

  const collectPayload = () => ({
    name: document.getElementById("pt-name").value.trim(),
    template_key: document.getElementById("pt-key").value.trim(),
    scene_type: document.getElementById("pt-scene").value,
    description: document.getElementById("pt-description").value.trim(),
    usage_notes: document.getElementById("pt-usage").value,
    prompt_content: document.getElementById("pt-content").value,
    output_format: document.getElementById("pt-output-format").value,
    example_input: document.getElementById("pt-example-input").value,
    example_output: document.getElementById("pt-example-output").value,
    is_default: document.getElementById("pt-default").checked,
    status: document.getElementById("pt-status").value,
    version: document.getElementById("pt-version").value.trim() || "v1",
  });

  document.getElementById("pt-preview-btn").addEventListener("click", async () => {
    const payload = collectPayload();
    if (template.id) {
      const preview = await api(`/api/admin/prompt-templates/${template.id}/preview`, {
        method: "POST",
        body: JSON.stringify({
          question: payload.example_input || "sample question",
          params: {},
        }),
      });
      document.getElementById("pt-preview-box").innerHTML = JsonViewer(preview);
      return;
    }
    const rendered = `SCENE: ${payload.scene_type}\nTEMPLATE: ${payload.template_key}\n\n${payload.prompt_content}\n\nOUTPUT FORMAT:\n${payload.output_format}\n\nUSER QUESTION:\n${payload.example_input || "sample question"}`;
    document.getElementById("pt-preview-box").innerHTML = `<pre class="json">${escapeHtml(rendered)}</pre>`;
  });

  const saveBtn = document.getElementById("pt-save-btn");
  saveBtn.addEventListener("click", async () => {
    const payload = collectPayload();
    if (!payload.name || !payload.template_key || !payload.prompt_content) {
      return alert(t("name/key/prompt content required"));
    }
    const originalText = saveBtn.textContent;
    saveBtn.disabled = true;
    saveBtn.textContent = isEdit ? `${t("Saving")}...` : `${t("Creating")}...`;
    try {
      if (isEdit) {
        await api(`/api/admin/prompt-templates/${template.id}`, {
          method: "PUT",
          body: JSON.stringify(payload),
        });
      } else {
        await api(`/api/admin/prompt-templates`, {
          method: "POST",
          body: JSON.stringify(payload),
        });
      }
      drawerEl.classList.add("hidden");
      await renderPromptTemplates();
    } catch (error) {
      alert(error?.message || String(error));
    } finally {
      saveBtn.disabled = false;
      saveBtn.textContent = originalText;
    }
  });
}

async function renderPromptTemplates() {
  renderPageHeader(
    "Prompt Templates",
    "Manage scene-based prompt templates and defaults.",
    `<button class="btn" id="pt-new-btn">New Template</button>`
  );
  contentEl.innerHTML = `
    <div class="card">
      <div class="row">
        <div style="flex:2 1 260px;"><label>Search Template</label><input id="pt-search" placeholder="name / key"></div>
        <div style="flex:1 1 180px;"><label>Scene</label><select id="pt-scene-filter">
          <option value="">all</option>
          <option value="lineage_query">lineage_query</option>
          <option value="sla_query">sla_query</option>
          <option value="daily_report">daily_report</option>
          <option value="failed_jobs_query">failed_jobs_query</option>
          <option value="risk_analysis">risk_analysis</option>
        </select></div>
        <div style="flex:1 1 160px;"><label>Status</label><select id="pt-status-filter"><option value="">all</option><option value="active">active</option><option value="draft">draft</option></select></div>
        <div style="align-self:flex-end;"><button class="btn" id="pt-search-btn">Search</button></div>
      </div>
    </div>
    <div class="card" id="pt-table-wrap"><div class="empty">Loading templates...</div></div>
  `;
  await attachAutocomplete("pt-search", "prompt_template");

  const load = async () => {
    const query = updateQueryString({
      q: document.getElementById("pt-search").value.trim(),
      scene_type: document.getElementById("pt-scene-filter").value,
      status: document.getElementById("pt-status-filter").value,
      limit: 500,
    });
    const rows = await api(`/api/admin/prompt-templates${query ? `?${query}` : ""}`);
    document.getElementById("pt-table-wrap").innerHTML = DataTable(
      [
        { title: "ID", key: "id" },
        { title: "Name", key: "name" },
        { title: "Scene", key: "scene_type" },
        { title: "Key", key: "template_key" },
        { title: "Status", render: (r) => StatusBadge(r.status) },
        { title: "Default", render: (r) => StatusBadge(r.is_default ? "default" : "no") },
        { title: "Updated", render: (r) => escapeHtml(formatDate(r.updated_at)) },
        {
          title: "Action",
          render: (r) =>
            `<button class="btn secondary pt-detail-btn" data-id="${r.id}">Detail</button>
             <button class="btn secondary pt-edit-btn" data-id="${r.id}">Edit</button>
             <button class="btn secondary pt-copy-btn" data-id="${r.id}">Copy</button>
             <button class="btn warning pt-del-btn" data-id="${r.id}">Delete</button>`,
        },
      ],
      rows
    );
    applyTranslations(document.getElementById("pt-table-wrap"));

    document.querySelectorAll(".pt-detail-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const detail = await api(`/api/admin/prompt-templates/${btn.getAttribute("data-id")}`);
        openDrawer(
          `Prompt Template #${detail.id}`,
          `
          <div class="card"><h3>Basic Info</h3>${JsonViewer({
            id: detail.id,
            name: detail.name,
            template_key: detail.template_key,
            scene_type: detail.scene_type,
            status: detail.status,
            is_default: detail.is_default,
            version: detail.version,
            updated_at: detail.updated_at,
          })}</div>
          <div class="card"><h3>Prompt Content</h3><pre class="json">${escapeHtml(detail.prompt_content || "")}</pre></div>
          <div class="card"><h3>Output Format</h3><pre class="json">${escapeHtml(detail.output_format || "")}</pre></div>
          <div class="card"><h3>Example Input</h3><pre class="json">${escapeHtml(detail.example_input || "")}</pre></div>
          <div class="card"><h3>Example Output</h3><pre class="json">${escapeHtml(detail.example_output || "")}</pre></div>
          <div class="card"><h3>Used By Tools</h3>${DataTable(
            [
              { title: "Tool", key: "tool_name" },
              { title: "Scene", key: "scene_type" },
              { title: "Default", render: (r) => StatusBadge(r.is_default ? "default" : "no") },
            ],
            detail.used_by_tools || []
          )}</div>
          <div class="row"><button class="btn" id="pt-set-default-btn">Set Default</button><button class="btn secondary" id="pt-preview-run-btn">Preview</button></div>
          <div class="card" id="pt-detail-preview"><div class="empty">Preview not run.</div></div>
        `
        );
        document.getElementById("pt-set-default-btn").addEventListener("click", async () => {
          await api(`/api/admin/prompt-templates/${detail.id}/set-default`, { method: "POST" });
          drawerEl.classList.add("hidden");
          await load();
        });
        document.getElementById("pt-preview-run-btn").addEventListener("click", async () => {
          const out = await api(`/api/admin/prompt-templates/${detail.id}/preview`, {
            method: "POST",
            body: JSON.stringify({
              question: detail.example_input || "sample question",
              params: {},
            }),
          });
          document.getElementById("pt-detail-preview").innerHTML = JsonViewer(out);
        });
      });
    });
    document.querySelectorAll(".pt-edit-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const detail = await api(`/api/admin/prompt-templates/${btn.getAttribute("data-id")}`);
        await openPromptTemplateEditor(detail);
      });
    });
    document.querySelectorAll(".pt-copy-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const detail = await api(`/api/admin/prompt-templates/${btn.getAttribute("data-id")}`);
        detail.id = null;
        detail.name = `${detail.name} Copy`;
        detail.template_key = `${detail.template_key}.copy`;
        detail.is_default = false;
        await openPromptTemplateEditor(detail);
      });
    });
    document.querySelectorAll(".pt-del-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm(t("Delete this prompt template?"))) return;
        await api(`/api/admin/prompt-templates/${btn.getAttribute("data-id")}`, {
          method: "DELETE",
        });
        await load();
      });
    });
  };
  document.getElementById("pt-search-btn").addEventListener("click", load);
  document.getElementById("pt-new-btn").addEventListener("click", async () => {
    await openPromptTemplateEditor(null);
  });
  await load();
}

async function renderToolVersions() {
  renderPageHeader("Tool Versions", "Tool version history list.");
  const data = await api("/api/admin/tool-versions");
  contentEl.innerHTML = `
    <div class="card">
      <div class="row">
        <div style="flex:2 1 260px;"><label>Search Tool</label><input id="tv-search" placeholder="tool name"></div>
        <div style="flex:1 1 180px;"><label>Active</label><select id="tv-active"><option value="">all</option><option value="true">active</option><option value="false">inactive</option></select></div>
        <div style="align-self:flex-end;"><button id="tv-load" class="btn">Search</button></div>
      </div>
    </div>
    <div class="card" id="tv-table-wrap"></div>
  `;
  await attachAutocomplete("tv-search", "tool");

  const load = async () => {
    const q = document.getElementById("tv-search").value.trim().toLowerCase();
    const active = document.getElementById("tv-active").value;
    const rows = data.filter((r) => {
      if (q && !(r.tool_name || "").toLowerCase().includes(q)) return false;
      if (active === "true" && !r.is_active) return false;
      if (active === "false" && !!r.is_active) return false;
      return true;
    });
    document.getElementById("tv-table-wrap").innerHTML = DataTable(
      [
        { title: "ID", key: "id" },
        { title: "Tool", key: "tool_name" },
        { title: "Version", key: "version" },
        { title: "Active", render: (r) => StatusBadge(r.is_active ? "active" : "inactive") },
        { title: "Created", render: (r) => escapeHtml(formatDate(r.created_at)) },
      ],
      rows
    );
  };
  document.getElementById("tv-load").addEventListener("click", load);
  await load();
}

async function renderDataSources() {
  renderPageHeader("Data Sources", "Data source catalog and details.");
  const rows = await api("/api/admin/data-sources");
  contentEl.innerHTML = `
    <div class="card">
      <div class="row">
        <div style="flex:2 1 260px;"><label>Search Data Source</label><input id="ds-search" placeholder="source name"></div>
        <div style="flex:1 1 180px;"><label>Type</label><input id="ds-type" placeholder="database / api / ..."></div>
        <div style="align-self:flex-end;"><button id="ds-load" class="btn">Search</button></div>
      </div>
    </div>
    <div class="card" id="ds-table-wrap"></div>
  `;
  await attachAutocomplete("ds-search", "data_source");

  const load = async () => {
    const q = document.getElementById("ds-search").value.trim().toLowerCase();
    const type = document.getElementById("ds-type").value.trim().toLowerCase();
    const filtered = rows.filter((item) => {
      if (q && !(item.name || "").toLowerCase().includes(q)) return false;
      if (type && !(item.source_type || "").toLowerCase().includes(type)) return false;
      return true;
    });
    document.getElementById("ds-table-wrap").innerHTML = DataTable(
      [
        { title: "ID", key: "id" },
        { title: "Name", key: "name" },
        { title: "Type", key: "source_type" },
        { title: "Enabled", render: (r) => StatusBadge(r.enabled ? "enabled" : "disabled") },
        { title: "Tables", key: "table_count" },
        { title: "Action", render: (r) => `<button class="btn secondary ds-detail-btn" data-id="${r.id}">Detail</button>` },
      ],
      filtered
    );
    applyTranslations(document.getElementById("ds-table-wrap"));
    document.querySelectorAll(".ds-detail-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const detail = await api(`/api/admin/data-sources/${btn.getAttribute("data-id")}`);
        openDrawer("Data Source Detail", `<div class="card">${JsonViewer(detail)}</div>`);
      });
    });
  };
  document.getElementById("ds-load").addEventListener("click", load);
  await load();
}

async function renderDataSourceTables() {
  renderPageHeader("Data Source Tables", "Schema/table inventory and quick preview.");
  const sources = await api("/api/admin/data-sources");
  contentEl.innerHTML = `
    <div class="card">
      <div class="row">
        <div style="flex:1 1 240px;"><label>Source</label><select id="dst-source">${sources.map((s) => `<option value="${s.id}">${escapeHtml(
    s.name
  )}</option>`).join("")}</select></div>
        <div style="flex:1 1 240px;"><label>Source Search</label><input id="dst-source-search" placeholder="source name"></div>
        <div style="flex:2 1 300px;"><label>Keyword</label><input id="dst-q" placeholder="table/schema"></div>
        <div style="align-self:flex-end;"><button id="dst-load" class="btn">Load</button></div>
      </div>
    </div>
    <div class="card" id="dst-table-wrap"><div class="empty">Click Load to query tables.</div></div>
  `;
  await attachAutocomplete("dst-source-search", "data_source");
  await attachAutocomplete("dst-q", "data_source_table", (item) => item.label || item.value);
  document.getElementById("dst-load").addEventListener("click", async () => {
    const sourceKeyword = document.getElementById("dst-source-search").value.trim().toLowerCase();
    const matchedSource = sourceKeyword
      ? sources.find((item) => (item.name || "").toLowerCase() === sourceKeyword) ||
        sources.find((item) => (item.name || "").toLowerCase().includes(sourceKeyword))
      : null;
    const sourceId = matchedSource ? String(matchedSource.id) : document.getElementById("dst-source").value;
    if (matchedSource) {
      document.getElementById("dst-source").value = String(matchedSource.id);
    }
    const q = document.getElementById("dst-q").value.trim();
    const rows = await api(`/api/admin/data-sources/${sourceId}/tables${q ? `?q=${encodeURIComponent(q)}` : ""}`);
    document.getElementById("dst-table-wrap").innerHTML = DataTable(
      [
        { title: "ID", key: "id" },
        { title: "Schema", key: "schema_name" },
        { title: "Table", key: "table_name" },
        { title: "Description", key: "description" },
        { title: "Action", render: (r) => `<button class="btn secondary dst-preview-btn" data-id="${r.id}">Preview</button>` },
      ],
      rows
    );
    applyTranslations(document.getElementById("dst-table-wrap"));
    document.querySelectorAll(".dst-preview-btn").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const result = await api(`/api/admin/preview?table_id=${btn.getAttribute("data-id")}`);
        openDrawer("Preview", `<div class="card">${JsonViewer(result)}</div>`);
      });
    });
  });
}

async function renderResultPreview() {
  renderPageHeader("Result Preview", "Preview result as JSON and table.");
  const sources = await api("/api/admin/data-sources");
  contentEl.innerHTML = `
    <div class="card">
      <div class="row">
        <div style="flex:1 1 220px;"><label>Source</label><select id="rp-source-id"><option value="">(auto)</option>${sources
          .map((s) => `<option value="${s.id}">${escapeHtml(s.name)}</option>`)
          .join("")}</select></div>
        <div style="flex:1 1 240px;"><label>Source Search</label><input id="rp-source-search" placeholder="source name"></div>
        <div style="flex:1 1 220px;"><label>Table ID</label><input id="rp-table-id" placeholder="table id"></div>
        <div style="flex:1 1 200px;"><label>Mode</label><select id="rp-mode"><option>json</option><option>table</option></select></div>
        <div style="align-self:flex-end;"><button id="rp-run" class="btn">Run Preview</button></div>
      </div>
    </div>
    <div class="card" id="rp-result"><div class="empty">Run preview to display result.</div></div>
  `;
  await attachAutocomplete("rp-source-search", "data_source");
  await attachAutocomplete("rp-table-id", "data_source_table", (item) => String(item.id || item.value));
  document.getElementById("rp-run").addEventListener("click", async () => {
    const sourceKeyword = document.getElementById("rp-source-search").value.trim().toLowerCase();
    const matchedSource = sourceKeyword
      ? sources.find((item) => (item.name || "").toLowerCase() === sourceKeyword) ||
        sources.find((item) => (item.name || "").toLowerCase().includes(sourceKeyword))
      : null;
    if (matchedSource) {
      document.getElementById("rp-source-id").value = String(matchedSource.id);
    }
    const sourceId = document.getElementById("rp-source-id").value.trim();
    const tableId = document.getElementById("rp-table-id").value.trim();
    const mode = document.getElementById("rp-mode").value;
    const params = new URLSearchParams();
    if (sourceId) params.set("source_id", sourceId);
    if (tableId) params.set("table_id", tableId);
    params.set("mode", mode);
    const data = await api(`/api/admin/preview?${params.toString()}`);
    const rows = Array.isArray(data.rows) ? data.rows : [];
    const table = rows.length
      ? DataTable(Object.keys(rows[0]).map((k) => ({ title: k, key: k })), rows)
      : `<div class='empty'>${escapeHtml(t("No tabular rows."))}</div>`;
    document.getElementById("rp-result").innerHTML = `<h3>${escapeHtml(t("JSON"))}</h3>${JsonViewer(data.json)}<h3>${escapeHtml(t("Table"))}</h3>${table}`;
    applyTranslations(document.getElementById("rp-result"));
  });
}

async function renderMemory() {
  renderPageHeader("Memory", "CRUD for memory entries.");
  const rows = await api("/api/admin/memories?limit=500");
  contentEl.innerHTML = `
    <div class="card">
      <div class="row">
        <div style="flex:2 1 260px;"><label>Search Memory</label><input id="mem-search" placeholder="title / keyword"></div>
        <div style="flex:1 1 180px;"><label>Type Filter</label><input id="mem-filter-type" placeholder="note / summary / ..."></div>
        <div style="align-self:flex-end;"><button id="mem-load" class="btn">Search</button></div>
      </div>
    </div>
    <div class="card">
      <div class="row">
        <div style="flex:1 1 160px;"><label>Type</label><input id="mem-create-type" value="note"></div>
        <div style="flex:2 1 260px;"><label>Title</label><input id="mem-create-title"></div>
      </div>
      <div><label>Content</label><textarea id="mem-create-content"></textarea></div>
      <div style="margin-top:8px;"><button id="mem-create" class="btn">Create</button></div>
    </div>
    <div class="card" id="mem-table-wrap"></div>
  `;
  await attachAutocomplete("mem-search", "memory");
  const load = async () => {
    const q = document.getElementById("mem-search").value.trim().toLowerCase();
    const type = document.getElementById("mem-filter-type").value.trim().toLowerCase();
    const filtered = rows.filter((item) => {
      if (
        q &&
        !(
          (item.title || "").toLowerCase().includes(q) ||
          (item.content || "").toLowerCase().includes(q)
        )
      ) {
        return false;
      }
      if (type && !(item.memory_type || "").toLowerCase().includes(type)) return false;
      return true;
    });
    document.getElementById("mem-table-wrap").innerHTML = DataTable(
      [
        { title: "ID", key: "id" },
        { title: "Type", key: "memory_type" },
        { title: "Title", key: "title" },
        { title: "Updated", render: (r) => escapeHtml(formatDate(r.updated_at)) },
        { title: "Action", render: (r) => `<button class="btn warning mem-del" data-id="${r.id}">Delete</button>` },
      ],
      filtered
    );
    applyTranslations(document.getElementById("mem-table-wrap"));
    document.querySelectorAll(".mem-del").forEach((btn) => {
      btn.addEventListener("click", async () => {
        if (!confirm(t("Delete this memory?"))) return;
        await api(`/api/admin/memories/${btn.getAttribute("data-id")}`, { method: "DELETE" });
        await switchView("memory");
      });
    });
  };
  document.getElementById("mem-load").addEventListener("click", load);
  document.getElementById("mem-create").addEventListener("click", async () => {
    const body = {
      memory_type: document.getElementById("mem-create-type").value.trim() || "note",
      title: document.getElementById("mem-create-title").value.trim(),
      content: document.getElementById("mem-create-content").value.trim(),
      metadata_json: {},
    };
    if (!body.title || !body.content) return alert(t("title/content required"));
    await api("/api/admin/memories", { method: "POST", body: JSON.stringify(body) });
    await switchView("memory");
  });
  await load();
}

async function renderScheduler() {
  renderPageHeader("Scheduler", "Jobs and run records.");
  const jobs = await api("/api/admin/jobs");
  contentEl.innerHTML = `
    <div class="card">
      <div class="row">
        <div style="flex:2 1 260px;"><label>Search Job</label><input id="job-search" placeholder="job name"></div>
        <div style="flex:1 1 180px;"><label>Status</label><input id="job-status-filter" placeholder="idle / running / ..."></div>
        <div style="align-self:flex-end;"><button id="job-load" class="btn">Search</button></div>
      </div>
    </div>
    <div class="card">
      <div class="row">
        <div style="flex:1 1 180px;"><label>Name</label><input id="job-name"></div>
        <div style="flex:1 1 180px;"><label>Type</label><input id="job-type" value="metadata_sync"></div>
        <div style="flex:1 1 220px;"><label>Cron</label><input id="job-cron" value="*/15 * * * *"></div>
      </div>
      <div style="margin-top:8px;"><button id="job-create" class="btn">Create Job</button></div>
    </div>
    <div class="card" id="job-table-wrap"></div>
  `;
  await attachAutocomplete("job-search", "job");

  const load = async () => {
    const keyword = document.getElementById("job-search").value.trim().toLowerCase();
    const statusFilter = document.getElementById("job-status-filter").value.trim().toLowerCase();
    const filtered = jobs.filter((job) => {
      if (keyword && !(job.name || "").toLowerCase().includes(keyword)) return false;
      if (statusFilter && !(job.status || "").toLowerCase().includes(statusFilter)) return false;
      return true;
    });
    document.getElementById("job-table-wrap").innerHTML = DataTable(
      [
        { title: "ID", key: "id" },
        { title: "Name", key: "name" },
        { title: "Status", render: (r) => StatusBadge(r.status) },
        { title: "Cron", key: "cron_expr" },
        { title: "Last Run", render: (r) => escapeHtml(formatDate(r.last_run_at)) },
        { title: "Action", render: (r) => `<button class="btn secondary job-run" data-id="${r.id}">Run</button> <button class="btn secondary job-runs" data-id="${r.id}">Runs</button>` },
      ],
      filtered
    );
    applyTranslations(document.getElementById("job-table-wrap"));
    document.querySelectorAll(".job-run").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const out = await api(`/api/admin/jobs/${btn.getAttribute("data-id")}/run`, { method: "POST" });
        openDrawer("Job Run Result", `<div class="card">${JsonViewer(out)}</div>`);
        await switchView("scheduler");
      });
    });
    document.querySelectorAll(".job-runs").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const out = await api(`/api/admin/jobs/${btn.getAttribute("data-id")}/runs`);
        openDrawer("Job Runs", `<div class="card">${JsonViewer(out)}</div>`);
      });
    });
  };
  document.getElementById("job-load").addEventListener("click", load);
  document.getElementById("job-create").addEventListener("click", async () => {
    const body = {
      name: document.getElementById("job-name").value.trim(),
      job_type: document.getElementById("job-type").value.trim() || "metadata_sync",
      cron_expr: document.getElementById("job-cron").value.trim() || "*/15 * * * *",
      enabled: true,
      config_json: {},
    };
    if (!body.name) return alert(t("name required"));
    await api("/api/admin/jobs", { method: "POST", body: JSON.stringify(body) });
    await switchView("scheduler");
  });
  await load();
}

async function renderChannels() {
  renderPageHeader("Channels", "Unified channel abstraction. Telegram config first.");
  const rows = await api("/api/admin/channels");
  contentEl.innerHTML = `
    <div class="card">
      <div class="row">
        <div style="flex:2 1 260px;"><label>Search Channel</label><input id="ch-search" placeholder="channel id / name"></div>
        <div style="flex:1 1 180px;"><label>Type Filter</label><input id="ch-type-filter" placeholder="telegram / ..."></div>
        <div style="align-self:flex-end;"><button id="ch-load" class="btn">Search</button></div>
      </div>
    </div>
    <div class="card">
      <div class="row">
        <div style="flex:1 1 160px;"><label>Channel ID</label><input id="ch-id" placeholder="telegram-main"></div>
        <div style="flex:1 1 200px;"><label>Name</label><input id="ch-name" placeholder="Telegram Main"></div>
        <div style="flex:1 1 140px;"><label>Type</label><input id="ch-type" value="telegram"></div>
      </div>
      <div><label>Config JSON</label><textarea id="ch-config">{ "bot_token":"", "webhook_url":"", "allowed_chat_id":"", "default_assistant":"assistant-default", "enabled":true }</textarea></div>
      <div style="margin-top:8px;"><button id="ch-create" class="btn">Create Channel</button></div>
    </div>
    <div class="card" id="ch-table-wrap"></div>
  `;
  await attachAutocomplete("ch-search", "channel");
  const load = async () => {
    const keyword = document.getElementById("ch-search").value.trim().toLowerCase();
    const type = document.getElementById("ch-type-filter").value.trim().toLowerCase();
    const filtered = rows.filter((item) => {
      if (
        keyword &&
        !(
          (item.channel_id || "").toLowerCase().includes(keyword) ||
          (item.channel_name || "").toLowerCase().includes(keyword)
        )
      ) {
        return false;
      }
      if (type && !(item.channel_type || "").toLowerCase().includes(type)) return false;
      return true;
    });
    document.getElementById("ch-table-wrap").innerHTML = DataTable(
      [
        { title: "ID", key: "id" },
        { title: "Channel ID", key: "channel_id" },
        { title: "Name", key: "channel_name" },
        { title: "Type", key: "channel_type" },
        { title: "Enabled", render: (r) => StatusBadge(r.enabled ? "enabled" : "disabled") },
        { title: "Action", render: (r) => `<button class="btn secondary ch-toggle" data-id="${r.id}" data-enabled="${r.enabled}">Toggle</button>` },
      ],
      filtered
    );
    applyTranslations(document.getElementById("ch-table-wrap"));
    document.querySelectorAll(".ch-toggle").forEach((btn) => {
      btn.addEventListener("click", async () => {
        const id = btn.getAttribute("data-id");
        const enabled = btn.getAttribute("data-enabled") !== "true";
        await api(`/api/admin/channels/${id}`, { method: "PUT", body: JSON.stringify({ enabled }) });
        await switchView("channels");
      });
    });
  };
  document.getElementById("ch-load").addEventListener("click", load);
  document.getElementById("ch-create").addEventListener("click", async () => {
    let cfg;
    try {
      cfg = JSON.parse(document.getElementById("ch-config").value || "{}");
    } catch {
      return alert(t("Invalid JSON"));
    }
    const body = {
      channel_id: document.getElementById("ch-id").value.trim(),
      channel_name: document.getElementById("ch-name").value.trim(),
      channel_type: document.getElementById("ch-type").value.trim() || "telegram",
      enabled: true,
      config_json: cfg,
      default_assistant_id: cfg.default_assistant || "",
    };
    if (!body.channel_id || !body.channel_name) return alert(t("channel_id/name required"));
    await api("/api/admin/channels", { method: "POST", body: JSON.stringify(body) });
    await switchView("channels");
  });
  await load();
}

async function renderLogs() {
  renderPageHeader("Logs / Trace", "Tool calls, runtime errors and audit logs.");
  const data = await api("/api/admin/logs/trace?limit=120");
  contentEl.innerHTML = `
    <div class="card">
      <div class="row">
        <div style="flex:2 1 220px;"><label>Tool</label><input id="logs-tool" placeholder="tool name"></div>
        <div style="flex:2 1 220px;"><label>Session</label><input id="logs-session" placeholder="session key"></div>
        <div style="flex:2 1 220px;"><label>Error Keyword</label><input id="logs-error" placeholder="error code/message"></div>
        <div style="align-self:flex-end;"><button id="logs-load" class="btn">Search</button></div>
      </div>
    </div>
    <div id="logs-sections"></div>
  `;
  await attachAutocomplete("logs-tool", "tool");
  await attachAutocomplete("logs-session", "chat_session");

  const load = async () => {
    const toolKeyword = document.getElementById("logs-tool").value.trim().toLowerCase();
    const sessionKeyword = document.getElementById("logs-session").value.trim().toLowerCase();
    const errorKeyword = document.getElementById("logs-error").value.trim().toLowerCase();
    const toolRows = (data.tool_traces || []).filter((item) => {
      if (toolKeyword && !(item.tool_name || "").toLowerCase().includes(toolKeyword)) return false;
      if (
        sessionKeyword &&
        !(`${item.chat_session_id || ""}`.toLowerCase().includes(sessionKeyword))
      ) {
        return false;
      }
      if (
        errorKeyword &&
        !(
          (item.error_message || "").toLowerCase().includes(errorKeyword) ||
          (item.tool_name || "").toLowerCase().includes(errorKeyword)
        )
      ) {
        return false;
      }
      return true;
    });
    const runtimeRows = (data.runtime_errors || []).filter((item) => {
      if (!errorKeyword) return true;
      return (
        (item.error_code || "").toLowerCase().includes(errorKeyword) ||
        (item.error_message || "").toLowerCase().includes(errorKeyword) ||
        (item.severity || "").toLowerCase().includes(errorKeyword)
      );
    });
    document.getElementById("logs-sections").innerHTML = `
      <div class="card">
        <h3>Tool Traces</h3>
        ${DataTable(
          [
            { title: "ID", key: "id" },
            { title: "Session", key: "chat_session_id" },
            { title: "Tool", key: "tool_name" },
            { title: "Duration", key: "duration_ms" },
            { title: "Error", key: "error_message" },
          ],
          toolRows
        )}
      </div>
      <div class="card">
        <h3>Runtime Errors</h3>
        ${DataTable(
          [
            { title: "Severity", render: (r) => StatusBadge(r.severity) },
            { title: "Code", key: "error_code" },
            { title: "Message", key: "error_message" },
            { title: "Occurred", render: (r) => escapeHtml(formatDate(r.occurred_at)) },
          ],
          runtimeRows
        )}
      </div>
      <div class="card"><h3>Audit Logs</h3>${JsonViewer(data.audit_logs || [])}</div>
    `;
    applyTranslations(document.getElementById("logs-sections"));
  };
  document.getElementById("logs-load").addEventListener("click", load);
  await load();
}

async function renderSettings() {
  renderPageHeader("Settings", "Current frontend capability and extension points.");
  contentEl.innerHTML = `
    <div class="card">
      <h3>Chat UX</h3><p>Conversation mode supports markdown/rich text rendering and auto session persistence.</p>
      <h3>Lineage UX</h3><p>Graph supports zoom, drag, search highlight and node detail drill-down.</p>
      <h3>Big Screen</h3><p>Top-level operations cockpit with runtime and governance KPIs.</p>
    </div>
  `;
}

async function switchView(view) {
  appState.currentView = view;
  document.querySelectorAll(".menu-item").forEach((el) => {
    el.classList.toggle("active", el.getAttribute("data-view") === view);
  });
  try {
    if (view === "bigscreen") await renderBigScreen();
    if (view === "dashboard") await renderDashboard();
    if (view === "chat") await renderChatPage();
    if (view === "lineage") await renderLineagePage();
    if (view === "tools") await renderTools();
    if (view === "prompt-templates") await renderPromptTemplates();
    if (view === "tool-versions") await renderToolVersions();
    if (view === "data-sources") await renderDataSources();
    if (view === "data-source-tables") await renderDataSourceTables();
    if (view === "result-preview") await renderResultPreview();
    if (view === "memory") await renderMemory();
    if (view === "scheduler") await renderScheduler();
    if (view === "channels") await renderChannels();
    if (view === "logs") await renderLogs();
    if (view === "settings") await renderSettings();
    applyTranslations(document.body);
  } catch (error) {
    renderError(error);
  }
}

function initMenu() {
  menuEl.innerHTML = menuItems
    .map(
      (item) =>
        `<button class="menu-item ${item.key === appState.currentView ? "active" : ""}" data-view="${item.key}">${escapeHtml(t(item.label))}</button>`
    )
    .join("");
  menuEl.querySelectorAll(".menu-item").forEach((btn) => {
    btn.addEventListener("click", () => switchView(btn.getAttribute("data-view")));
  });
}

initLocaleSelector();
initMenu();
switchView(appState.currentView);
