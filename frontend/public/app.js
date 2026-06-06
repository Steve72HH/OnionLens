const form = document.querySelector("#searchForm");
const queryInput = document.querySelector("#query");
const results = document.querySelector("#results");
const statusBox = document.querySelector("#status");
const statsBox = document.querySelector("#stats");
const backend = window.ONIONLENS_BACKEND || "http://localhost:8000";

function escapeHtml(value) {
  return String(value || "")
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#039;");
}

function renderWarningLabels(labels) {
  if (!labels || labels.length === 0) {
    return "";
  }

  return `<div class="labels">${labels
    .map((label) => `<span title="Automatisches Warnlabel">${escapeHtml(label)}</span>`)
    .join("")}</div>`;
}

async function loadStats() {
  try {
    const response = await fetch(`${backend}/stats`);
    const data = await response.json();
    const queued = data.frontier?.queued || 0;
    const done = data.frontier?.done || 0;
    const retry = data.frontier?.retry || 0;
    statsBox.innerHTML = `
      <span>${Number(data.sites || 0).toLocaleString("de-DE")} Seiten</span>
      <span>${Number(queued).toLocaleString("de-DE")} in Queue</span>
      <span>${Number(done).toLocaleString("de-DE")} gecrawlt</span>
      <span>${Number(retry).toLocaleString("de-DE")} Retry</span>
    `;
  } catch {
    statsBox.textContent = "Statistik momentan nicht erreichbar.";
  }
}

async function search(query) {
  statusBox.textContent = "Suche läuft...";
  results.innerHTML = "";

  const response = await fetch(`${backend}/search?q=${encodeURIComponent(query)}&limit=20`);
  if (!response.ok) {
    throw new Error(await response.text());
  }
  const data = await response.json();

  statusBox.textContent = `${Number(data.estimated_total_hits || 0).toLocaleString("de-DE")} Treffer in ${
    data.processing_time_ms || 0
  } ms`;
  results.innerHTML = data.hits
    .map(
      (hit) => `
        <li class="result">
          <a class="title" href="${escapeHtml(hit.url)}" rel="noreferrer">${escapeHtml(hit.title)}</a>
          <div class="url">${escapeHtml(hit.url)}</div>
          <p>${escapeHtml(hit.description)}</p>
          ${renderWarningLabels(hit.warning_labels)}
        </li>
      `,
    )
    .join("");
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const query = queryInput.value.trim();
  if (!query) {
    queryInput.focus();
    return;
  }

  try {
    await search(query);
  } catch (error) {
    statusBox.textContent = `Fehler: ${error.message}`;
  }
});

loadStats();
setInterval(loadStats, 15000);
