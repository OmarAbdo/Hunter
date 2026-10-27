// Hunter's discovery page. Everything shown comes from the JSON views of the local server, and
// text from job sites is always set as text, never as markup.
"use strict";

const byId = (id) => document.getElementById(id);
const getJson = async (path) => (await fetch(path)).json();
const isWebLink = (link) => typeof link === "string" && /^https?:\/\//i.test(link);
let jobs = [];
let companies = [];

function cell(text, link) {
  const td = document.createElement("td");
  if (isWebLink(link)) {
    const anchor = document.createElement("a");
    anchor.href = link;
    anchor.target = "_blank";
    anchor.rel = "noopener noreferrer";
    anchor.textContent = text;
    td.append(anchor);
  } else {
    td.textContent = text ?? "";
  }
  return td;
}

function row(...cells) {
  const tr = document.createElement("tr");
  tr.append(...cells);
  return tr;
}

function placesText(places) {
  // Each place once, the unknown ones left out when others are known, at most three named.
  const known = [...new Set(places)].filter((place) => place !== "unknown");
  if (known.length === 0) return places.length ? "unknown" : "";
  const more = known.length - 3;
  return known.slice(0, 3).join("; ") + (more > 0 ? ` and ${more} more` : "");
}

function matches(filter, ...texts) {
  const words = filter.toLowerCase().split(/\s+/).filter(Boolean);
  const haystack = texts.join(" ").toLowerCase();
  return words.every((word) => haystack.includes(word));
}

function showJobs() {
  const filter = byId("job-filter").value;
  const shown = jobs.filter((job) => matches(filter, job.title, job.company, job.places.join(" ")));
  byId("job-rows").replaceChildren(...shown.map((job) => row(
    cell(job.posted_at ?? ""),
    cell(job.title, job.url),
    cell(job.company),
    cell(placesText(job.places)),
    cell([job.workplace, job.employment].filter(Boolean).join(", ")),
    cell(job.sources.join(", ")),
    cell(job.employer_system ?? "", job.employer_system ? job.apply_url : null),
  )));
  byId("job-count").textContent = `${shown.length} of ${jobs.length} jobs`;
}

function showCompanies() {
  const filter = byId("company-filter").value;
  const withBoards = byId("with-boards").checked;
  const shown = companies.filter((company) =>
    matches(filter, company.name) && (!withBoards || company.boards.length > 0));
  byId("company-rows").replaceChildren(...shown.map((company) => row(
    cell(company.name),
    cell(company.boards.map((board) => `${board.board} (${board.status})`).join(", ")),
    cell(company.website ?? "", company.website),
  )));
  byId("company-count").textContent = `${shown.length} of ${companies.length} companies`;
}

async function loadCampaign() {
  const chosen = byId("campaign").selectedOptions[0];
  if (!chosen) return;
  const reasons = JSON.parse(chosen.dataset.turnedDown);
  const summary = Object.entries(reasons).sort((one, other) => other[1] - one[1])
    .map(([reason, count]) => `${reason} ${count}`).join(", ");
  byId("turned-down").textContent = summary ? `Turned down: ${summary}` : "";
  jobs = await getJson(`/api/jobs?campaign=${encodeURIComponent(chosen.value)}`);
  showJobs();
}

async function loadAll() {
  const pool = await getJson("/api/pool");
  byId("pool").textContent =
    `${pool.jobs} jobs in the pool · ${pool.companies} companies · ${pool.boards} boards`;
  const campaigns = await getJson("/api/campaigns");
  byId("campaign").replaceChildren(...campaigns.map((campaign) => {
    const option = new Option(`${campaign.title} (${campaign.taken} taken)`, campaign.id);
    option.dataset.turnedDown = JSON.stringify(campaign.turned_down);
    return option;
  }));
  companies = await getJson("/api/companies");
  showCompanies();
  await loadCampaign();
}

const localTime = (moment) => new Date(moment).toLocaleString([], {
  year: "numeric", month: "2-digit", day: "2-digit", hour: "2-digit", minute: "2-digit",
});

async function showHeld() {
  // A site that asked for a long pause isn't asked again until it ends, in any run.
  const held = await getJson("/api/held");
  const items = held.map((pause) => {
    const item = document.createElement("li");
    item.textContent = `${pause.host} until ${localTime(pause.until)}`;
    return item;
  });
  if (items.length === 0) {
    const none = document.createElement("li");
    none.className = "muted";
    none.textContent = "None right now.";
    items.push(none);
  }
  byId("held-sites").replaceChildren(...items);
}

async function showRuns() {
  showHeld();
  const runs = await getJson("/api/runs");
  byId("run-rows").replaceChildren(...runs.map((run) => {
    const failed = run.sources.filter((source) => source.error);
    const failedCell = cell(failed.length ? `${failed.length} of ${run.sources.length}` : "none");
    failedCell.title = failed.map((source) => `${source.source}: ${source.error}`).join("\n");
    return row(
      cell(localTime(run.started_at)), cell(run.ended_at ? localTime(run.ended_at) : "not finished"),
      cell(String(run.fetched)),
      cell(String(run.new)), cell(String(run.taken)), failedCell, cell(String(run.linked)),
    );
  }));
}

async function followRun() {
  const live = await getJson("/api/runs/live");
  const lines = byId("run-lines");
  lines.hidden = live.lines.length === 0;
  lines.textContent = live.lines.join("\n");
  lines.scrollTop = lines.scrollHeight;
  byId("run").disabled = live.running;
  byId("run-state").textContent = live.running ? "Running…" : "";
  if (live.running) {
    setTimeout(followRun, 1000);
  } else if (live.lines.length) {
    await Promise.all([showRuns(), loadAll()]);
  }
}

async function startRun() {
  await fetch("/api/runs", { method: "POST" });
  followRun();
}

function showTab(name) {
  for (const tab of ["jobs", "companies", "runs"]) {
    byId(tab).hidden = tab !== name;
    byId(`show-${tab}`).classList.toggle("active", tab === name);
  }
}

byId("show-jobs").addEventListener("click", () => showTab("jobs"));
byId("show-companies").addEventListener("click", () => showTab("companies"));
byId("show-runs").addEventListener("click", () => showTab("runs"));
byId("run").addEventListener("click", startRun);
showRuns();
followRun();
byId("campaign").addEventListener("change", loadCampaign);
byId("job-filter").addEventListener("input", showJobs);
byId("company-filter").addEventListener("input", showCompanies);
byId("with-boards").addEventListener("change", showCompanies);
loadAll();

// Hunter stops once its window has been closed for a while; the page keeps saying it's open.
const sayOpen = () => fetch("/api/alive");
sayOpen();
setInterval(sayOpen, 5000);
