const state = {
  data: null,
};

const els = {
  refreshButton: document.getElementById("refreshButton"),
  lastFetch: document.getElementById("lastFetch"),
  codexSevenDayTotal: document.getElementById("codexSevenDayTotal"),
  codexPlanType: document.getElementById("codexPlanType"),
  claudeSevenDayTotal: document.getElementById("claudeSevenDayTotal"),
  claudeSnapshotState: document.getElementById("claudeSnapshotState"),
  codexSessionCount: document.getElementById("codexSessionCount"),
  claudeSessionCount: document.getElementById("claudeSessionCount"),
  limitGrid: document.getElementById("limitGrid"),
  codexDailyChart: document.getElementById("codexDailyChart"),
  claudeDailyChart: document.getElementById("claudeDailyChart"),
  codexHistoryChart: document.getElementById("codexHistoryChart"),
  codexSessionsTable: document.getElementById("codexSessionsTable"),
  claudeSessionsTable: document.getElementById("claudeSessionsTable"),
  claudeSetupNote: document.getElementById("claudeSetupNote"),
  claudeSetupCommand: document.getElementById("claudeSetupCommand"),
};

function formatNumber(value) {
  return new Intl.NumberFormat("en-US").format(value || 0);
}

function formatPercent(value) {
  if (value === null || value === undefined) {
    return "-";
  }
  return `${Math.round(value)}%`;
}

function formatStamp(value) {
  if (!value) {
    return "-";
  }
  const date = new Date(value);
  return `${date.toLocaleDateString()} ${date.toLocaleTimeString([], {
    hour: "2-digit",
    minute: "2-digit",
  })}`;
}

function escapeHtml(value) {
  return String(value ?? "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;");
}

function renderLimitCard(title, providerClass, limit, fallbackText) {
  if (!limit) {
    return `
      <article class="limit-card ${providerClass}">
        <p class="limit-title">${escapeHtml(title)}</p>
        <div class="limit-empty">${escapeHtml(fallbackText)}</div>
      </article>
    `;
  }

  const used =
    limit.used_percent ?? limit.used_percentage ?? limit.primary?.used_percent ?? 0;
  const resetAt = limit.resets_at ?? limit.primary?.resets_at ?? "-";
  const windowMinutes = limit.window_minutes ?? limit.primary?.window_minutes ?? null;
  const windowLabel = windowMinutes
    ? `${windowMinutes / 60}h window`
    : title.includes("7d")
      ? "7 day window"
      : "5 hour window";

  return `
    <article class="limit-card ${providerClass}">
      <p class="limit-title">${escapeHtml(title)}</p>
      <div class="meter-shell">
        <div class="meter-track">
          <div class="meter-fill" style="width:${Math.max(
            0,
            Math.min(100, used)
          )}%"></div>
        </div>
        <strong>${formatPercent(used)}</strong>
      </div>
      <div class="limit-meta">
        <span>${escapeHtml(windowLabel)}</span>
        <span>Reset ${escapeHtml(formatStamp(resetAt))}</span>
      </div>
    </article>
  `;
}

function renderLimitGrid(data) {
  const codex = data.codex.current_limits;
  const claude = data.claude.current_limits;

  const cards = [
    renderLimitCard(
      "Codex 5h",
      "codex-card",
      codex?.primary,
      "No Codex 5h data found."
    ),
    renderLimitCard(
      "Codex 7d",
      "codex-card",
      codex?.secondary,
      "No Codex 7d data found."
    ),
    renderLimitCard(
      "Claude 5h",
      "claude-card",
      claude?.five_hour,
      "Enable the optional statusLine snapshot to show Claude live limits."
    ),
    renderLimitCard(
      "Claude 7d",
      "claude-card",
      claude?.seven_day,
      "Enable the optional statusLine snapshot to show Claude live limits."
    ),
  ];

  els.limitGrid.innerHTML = cards.join("");
}

function renderBarChart(target, series, providerClass) {
  const maxValue = Math.max(...series.map((item) => item.total_tokens), 1);
  target.innerHTML = series
    .map((item) => {
      const height = Math.max(8, (item.total_tokens / maxValue) * 100);
      return `
        <div class="bar-col">
          <div class="bar-stack">
            <div class="bar ${providerClass}" style="height:${height}%"></div>
          </div>
          <span class="bar-value">${formatNumber(item.total_tokens)}</span>
          <span class="bar-label">${escapeHtml(item.label)}</span>
        </div>
      `;
    })
    .join("");
}

function renderHistoryChart(target, events) {
  if (!events.length) {
    target.innerHTML = `<div class="chart-empty">No Codex rate limit history found.</div>`;
    return;
  }

  const width = 900;
  const height = 220;
  const padding = 20;
  const pointsPrimary = [];
  const pointsSecondary = [];

  events.forEach((event, index) => {
    const x =
      padding + (index / Math.max(1, events.length - 1)) * (width - padding * 2);
    const yPrimary =
      height - padding - (event.primary.used_percent / 100) * (height - padding * 2);
    const ySecondary =
      height -
      padding -
      (event.secondary.used_percent / 100) * (height - padding * 2);
    pointsPrimary.push(`${x},${yPrimary}`);
    pointsSecondary.push(`${x},${ySecondary}`);
  });

  target.innerHTML = `
    <svg viewBox="0 0 ${width} ${height}" class="history-svg" role="img" aria-label="Codex rate limit history">
      <line x1="${padding}" y1="${height - padding}" x2="${width - padding}" y2="${height - padding}" class="axis-line"></line>
      <line x1="${padding}" y1="${padding}" x2="${padding}" y2="${height - padding}" class="axis-line"></line>
      <polyline fill="none" points="${pointsSecondary.join(" ")}" class="line-secondary"></polyline>
      <polyline fill="none" points="${pointsPrimary.join(" ")}" class="line-primary"></polyline>
    </svg>
    <div class="history-legend">
      <span><i class="swatch swatch-primary"></i>5h</span>
      <span><i class="swatch swatch-secondary"></i>7d</span>
    </div>
  `;
}

function renderSessionsTable(target, rows, columns) {
  target.innerHTML = rows
    .map((row) => {
      return `
        <tr>
          <td>${escapeHtml(formatStamp(row.updated_at))}</td>
          <td>${escapeHtml(formatNumber(row.total_tokens))}</td>
          <td>${escapeHtml(columns.model ? row[columns.model] || "-" : row[columns.source] || "-")}</td>
          <td class="path-cell">${escapeHtml(row.path || row.cwd || "-")}</td>
        </tr>
      `;
    })
    .join("");
}

function renderSetupPanel(data) {
  const snapshotPath = data.paths.claude_statusline_snapshot;
  const enabled = data.claude.statusline_snapshot_detected;
  els.claudeSetupNote.textContent = enabled
    ? `Claude live limits are active. Snapshot file: ${snapshotPath}`
    : `Claude session token totals already work. To add 5h and 7d limit bars, install the optional statusLine helper. Snapshot target: ${snapshotPath}`;
  els.claudeSetupCommand.textContent =
    "powershell -ExecutionPolicy Bypass -File .\\tools\\install_claude_statusline.ps1";
}

function renderSummary(data) {
  els.lastFetch.textContent = formatStamp(data.generated_at);
  els.codexSevenDayTotal.textContent = `${formatNumber(
    data.codex.seven_day_total_tokens
  )} tokens`;
  els.codexPlanType.textContent = data.codex.current_limits?.plan_type
    ? `Plan ${data.codex.current_limits.plan_type}`
    : "Plan unknown";
  els.claudeSevenDayTotal.textContent = `${formatNumber(
    data.claude.seven_day_total_tokens
  )} tokens`;
  els.claudeSnapshotState.textContent = data.claude.statusline_snapshot_detected
    ? "Live limit snapshot detected"
    : "Token-only mode";
  els.codexSessionCount.textContent = formatNumber(data.codex.session_count);
  els.claudeSessionCount.textContent = formatNumber(data.claude.session_count);
}

function renderAll(data) {
  state.data = data;
  renderSummary(data);
  renderLimitGrid(data);
  renderBarChart(els.codexDailyChart, data.codex.daily_tokens, "codex-bar");
  renderBarChart(els.claudeDailyChart, data.claude.daily_tokens, "claude-bar");
  renderHistoryChart(els.codexHistoryChart, data.codex.rate_limit_history);
  renderSessionsTable(els.codexSessionsTable, data.codex.recent_sessions, {
    source: "source",
  });
  renderSessionsTable(els.claudeSessionsTable, data.claude.recent_sessions, {
    model: "model",
  });
  renderSetupPanel(data);
}

async function loadData() {
  const response = await fetch("/api/data", { cache: "no-store" });
  if (!response.ok) {
    throw new Error(`Request failed with ${response.status}`);
  }
  const data = await response.json();
  renderAll(data);
}

async function refresh() {
  els.refreshButton.disabled = true;
  try {
    await loadData();
  } catch (error) {
    console.error(error);
    els.lastFetch.textContent = "Fetch failed";
  } finally {
    els.refreshButton.disabled = false;
  }
}

els.refreshButton.addEventListener("click", refresh);
refresh();
setInterval(refresh, 15000);
