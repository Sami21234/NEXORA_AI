const ACCENT = "#21808d";       // single-series magnitude bars (matches brand gradient start)
const STATUS_COLORS = {
    positive: "#22c55e",
    neutral: "#9aa4ad",
    negative: "#ef4444",
    up: "#22c55e",
    down: "#ef4444",
};
const LABELS = {
    canned: "Canned reply",
    llm: "Gemini LLM",
    positive: "Positive",
    neutral: "Neutral",
    negative: "Negative",
    up: "Helpful",
    down: "Not helpful",
};

function prettyLabel(key) {
    return LABELS[key] || key.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function statTile(label, value) {
    return `<div class="stat-tile"><div class="stat-label">${label}</div><div class="stat-value">${value}</div></div>`;
}

function buildBarChart(id, title, sub, dist, { colorFn, legend } = {}) {
    const entries = Object.entries(dist).sort((a, b) => b[1] - a[1]);

    if (entries.length === 0) {
        return `
        <div class="chart-card">
            <h3 class="chart-title">${title}</h3>
            <p class="chart-sub">${sub}</p>
            <p class="empty-state">No data logged yet.</p>
        </div>`;
    }

    const max = Math.max(...entries.map(([, v]) => v));
    const color = colorFn || (() => ACCENT);

    const legendHtml = legend
        ? `<div class="chart-legend">${entries
              .map(([k]) => `<span><span class="swatch" style="background:${color(k)}"></span>${prettyLabel(k)}</span>`)
              .join("")}</div>`
        : "";

    const rows = entries
        .map(
            ([key, val]) => `
        <div class="bar-row">
            <span class="bar-label">${prettyLabel(key)}</span>
            <div class="bar-track"><div class="bar-fill" style="width:${(val / max) * 100}%; background:${color(key)}"></div></div>
            <span class="bar-value">${val}</span>
        </div>`
        )
        .join("");

    const tableRows = entries.map(([key, val]) => `<tr><td>${prettyLabel(key)}</td><td>${val}</td></tr>`).join("");

    const tableId = `${id}-table`;
    return `
    <div class="chart-card">
        <h3 class="chart-title">${title}</h3>
        <p class="chart-sub">${sub}</p>
        ${legendHtml}
        ${rows}
        <button class="table-toggle" onclick="document.getElementById('${tableId}').classList.toggle('hidden')">View as table</button>
        <table class="data-table hidden" id="${tableId}">
            <thead><tr><th>Category</th><th>Count</th></tr></thead>
            <tbody>${tableRows}</tbody>
        </table>
    </div>`;
}

async function loadAnalytics() {
    const container = document.getElementById("dashContent");
    try {
        const res = await fetch("/analytics");
        if (!res.ok) throw new Error("request failed");
        const data = await res.json();

        const statsHtml = `
        <div class="stat-grid">
            ${statTile("Total conversations", data.total_conversations ?? 0)}
            ${statTile("Total user messages", data.total_messages ?? 0)}
            ${statTile("Avg response time", data.avg_response_time_ms != null ? `${data.avg_response_time_ms} ms` : "—")}
        </div>`;

        const intentChart = buildBarChart(
            "intent",
            "Intent distribution",
            "What users actually asked, by classified intent",
            data.intent_distribution || {}
        );

        const routingChart = buildBarChart(
            "routing",
            "Canned reply vs. Gemini LLM",
            "How many replies were answered instantly vs. sent to the LLM",
            data.canned_reply_vs_llm || {}
        );

        const sentimentChart = buildBarChart(
            "sentiment",
            "User sentiment",
            "VADER sentiment label on incoming user messages",
            data.sentiment_distribution || {},
            { colorFn: (k) => STATUS_COLORS[k] || ACCENT, legend: true }
        );

        const feedbackChart = buildBarChart(
            "feedback",
            "User feedback",
            "Thumbs up / down cast on bot replies",
            data.feedback || {},
            { colorFn: (k) => STATUS_COLORS[k] || ACCENT, legend: true }
        );

        container.innerHTML = statsHtml + intentChart + routingChart + sentimentChart + feedbackChart;
    } catch (err) {
        container.innerHTML = `<p class="dash-error">Could not load analytics. Is the server running?</p>`;
    }
}

loadAnalytics();