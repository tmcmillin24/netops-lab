import {api, ApiError} from "./api.js?v=phase6-2";

const state = {
  page: "dashboard",
  overview: null,
  devices: [],
  connected: false,
  selectedDevice: null,
  loading: true,
  refreshing: false,
  pingResult: null,
  pingSource: "WS01",
  pingDestination: "PRNT01"
};

const pageTitles = {
  dashboard: "Dashboard",
  network: "Network",
  systems: "Systems",
  "active-directory": "Active Directory",
  tickets: "Tickets",
  automation: "Automation",
  architecture: "Architecture"
};

const typeLabels = {
  router_firewall: "Router / Firewall",
  layer3_core_switch: "Layer 3 Core Switch",
  access_switch: "Access Switch",
  workstation: "Linux Workstation",
  printer: "Network Printer"
};

const directPrinterPages = {PRNT01: 8080, PRNT02: 8082, PRNT03: 8083};
const content = document.getElementById("pageContent");

function escapeHtml(value) {
  return String(value ?? "—").replace(/[&<>'"]/g, character => ({"&":"&amp;", "<":"&lt;", ">":"&gt;", "'":"&#39;", '"':"&quot;"})[character]);
}

function slug(value) {
  return String(value || "unknown").toLowerCase().replaceAll(" ", "-");
}

function badge(value) {
  const label = value || "unknown";
  return `<span class="status-badge ${slug(label)}">${escapeHtml(label)}</span>`;
}

function pageIntro(title, description) {
  return `<div class="page-intro"><div><h2>${title}</h2><p>${description}</p></div></div>`;
}

function loadingState(message = "Loading live lab data…") {
  return `<div class="panel loading-state"><strong>Contacting backend</strong>${message}</div>`;
}

function unavailableState() {
  return `<div class="panel empty-state"><strong>Backend unavailable</strong>Start the Phase 4 API inside Lima, then retry. No fallback status values are being shown.</div>`;
}

function renderDashboard() {
  if (state.loading) return loadingState();
  if (!state.connected || !state.overview) return unavailableState();
  const overview = state.overview;
  const events = state.devices
    .filter(device => device.live?.last_event)
    .map(device => ({name: device.hostname, message: device.live.last_event, type: device.live.last_event_type || "info"}));
  const infrastructure = [
    ["Routing and switching", state.devices.filter(device => ["router_firewall", "layer3_core_switch", "access_switch"].includes(device.device_type))],
    ["Workstation services", state.devices.filter(device => device.device_type === "workstation")],
    ["Printer services", state.devices.filter(device => device.device_type === "printer")]
  ];
  return `${pageIntro("Lab overview", "Live health and operational state from the centralized backend.")}
    <section class="metric-grid" aria-label="Lab health summary">
      ${metric("Total devices", overview.total_devices, "Current inventory")}
      ${metric("Online", overview.online_devices, "Available now", "good")}
      ${metric("Offline", overview.offline_devices, "Includes unavailable", overview.offline_devices ? "bad" : "good")}
      ${metric("Printer attention", overview.printers_requiring_attention, "Click to inspect active faults", overview.printers_requiring_attention ? "warn" : "good", "printer-alerts")}
      ${metric("Impacted", overview.impacted_devices || 0, "Click to inspect affected devices", overview.impacted_devices ? "warn" : "good", "impacted-devices")}
      ${metric("Network health", overview.network_health, "Container and service checks", overview.network_health === "healthy" ? "good" : "bad")}
    </section>
    <div class="dashboard-grid">
      <section class="panel"><div class="panel-header"><div><h3>Infrastructure health</h3><p>Grouped live availability</p></div>${badge(overview.network_health)}</div>
        <div class="health-list">${infrastructure.map(([label, devices]) => {
          const healthy = devices.filter(device => !["offline", "unavailable"].includes(device.status) && device.dependency_status !== "impacted").length;
          return `<div class="health-row"><div><strong>${label}</strong><br><span>${healthy} of ${devices.length} available</span></div>${badge(healthy === devices.length ? "healthy" : "warning")}</div>`;
        }).join("")}</div>
      </section>
      <section class="panel"><div class="panel-header"><div><h3>Recent endpoint events</h3><p>Current event reported by each live endpoint</p></div></div>
        <div class="event-list">${events.length ? events.slice(0, 7).map(event => `<div class="event-row"><i class="${slug(event.type)}"></i><div><strong>${escapeHtml(event.name)}</strong><small>${escapeHtml(event.message)}</small></div>${badge(event.type)}</div>`).join("") : `<div class="empty-state">No endpoint events available.</div>`}</div>
      </section>
    </div>`;
}

function metric(label, value, note, tone = "", action = "") {
  const tag = action ? "button" : "article";
  return `<${tag} class="metric ${tone} ${action ? "interactive" : ""}" ${action ? `data-dashboard-action="${action}" type="button"` : ""}><div class="metric-label">${label}</div><div class="metric-value">${escapeHtml(value)}</div><div class="metric-note">${note}</div></${tag}>`;
}

function deviceClass(device) {
  return device.device_type === "router_firewall" ? "router" : device.device_type === "layer3_core_switch" ? "core" : device.device_type.replace("access_", "");
}

function deviceCard(device) {
  const selected = state.selectedDevice === device.hostname ? "selected" : "";
  const displayStatus = device.dependency_status === "impacted" ? "impacted" : device.status;
  return `<button class="device-card ${deviceClass(device)} ${selected}" data-device="${device.hostname}" type="button">
    <span class="device-card-head"><strong>${device.hostname}</strong><i class="state-dot ${slug(displayStatus)}">${escapeHtml(displayStatus)}</i></span>
    <small>${escapeHtml(typeLabels[device.device_type])}</small><small>${escapeHtml(device.ip_address || "Layer 2")}</small>
  </button>`;
}

function renderNetwork() {
  if (state.loading) return loadingState("Building the current topology…");
  if (!state.connected) return unavailableState();
  const byName = Object.fromEntries(state.devices.map(device => [device.hostname, device]));
  const router = byName.RTR01;
  const core = byName.CORE01;
  const switches = ["SW01", "SW02", "SW03"].map(name => byName[name]).filter(Boolean);
  const groups = switches.map(networkSwitch => {
    const endpoints = state.devices.filter(device => device.connected_switch === networkSwitch.hostname && ["workstation", "printer"].includes(device.device_type));
    return `<div class="access-group">${deviceCard(networkSwitch)}<div class="network-label">${escapeHtml(endpoints[0]?.network || networkSwitch.network)}</div><div class="endpoint-grid">${endpoints.map(deviceCard).join("")}</div></div>`;
  }).join("");
  const sourceOptions = state.devices.map(device => `<option value="${device.hostname}" ${device.hostname === state.pingSource ? "selected" : ""}>${device.hostname}</option>`).join("");
  const destinationOptions = state.devices.filter(device => device.ip_address).map(device => `<option value="${device.hostname}" ${device.hostname === state.pingDestination ? "selected" : ""}>${device.hostname} · ${device.ip_address}</option>`).join("");
  return `${pageIntro("Office topology", "Live status across three routed access networks. Select any node for details.")}
    <div class="network-layout">
      <section class="panel topology-panel"><div class="topology-legend"><span>${badge("online")} Available</span><span>${badge("attention")} Attention</span><span>${badge("offline")} Offline</span></div>
        <div id="topology" class="topology">${router ? `<div class="topology-tier">${deviceCard(router)}</div>` : ""}${core ? `<div class="topology-tier">${deviceCard(core)}</div>` : ""}<div class="topology-tier access-tier">${groups}</div></div>
      </section>
      <aside class="panel diagnostic-panel"><h3>Connectivity check</h3><p>Run one controlled ping between known inventory devices. Deeper diagnostics are planned for Phase 6.</p>
        <div class="field"><label for="pingSource">Source device</label><select id="pingSource">${sourceOptions}</select></div>
        <div class="field"><label for="pingDestination">Destination device</label><select id="pingDestination">${destinationOptions}</select></div>
        <button id="runPing" class="action-button" type="button">Run connectivity test</button>
        ${state.pingResult ? `<div class="diagnostic-result ${state.pingResult.success ? "success" : "error"}"><strong>${escapeHtml(state.pingResult.source)} → ${escapeHtml(state.pingResult.destination)}</strong><br>${escapeHtml(state.pingResult.message)}${state.pingResult.latency_ms !== null && state.pingResult.latency_ms !== undefined ? `<br>Latency: ${escapeHtml(state.pingResult.latency_ms)} ms` : ""}</div>` : ""}
      </aside>
    </div>`;
}

function renderSystems() {
  if (state.loading) return loadingState("Loading workstation and printer services…");
  if (!state.connected) return unavailableState();
  const workstations = state.devices.filter(device => device.device_type === "workstation");
  const printers = state.devices.filter(device => device.device_type === "printer");
  return `${pageIntro("Systems inventory", "Live workstation and printer fleet state from the backend.")}
    <section class="panel system-section"><div class="panel-header"><div><h3>Workstations</h3><p>${workstations.length} managed endpoints</p></div></div><div class="table-wrap"><table><thead><tr><th>Hostname</th><th>Status</th><th>Office IP</th><th>Access switch</th><th>Default printer</th><th>Reachability</th><th>Service</th></tr></thead><tbody>
      ${workstations.map(device => `<tr data-device="${device.hostname}" tabindex="0"><td><strong>${device.hostname}</strong></td><td>${badge(device.status)}</td><td>${escapeHtml(device.ip_address)}</td><td>${escapeHtml(device.connected_switch)}</td><td>${escapeHtml(device.assigned_printer)}</td><td>${device.reachable ? "Reachable" : "Unreachable"}</td><td>${badge(device.service_health)}</td></tr>`).join("")}
    </tbody></table></div></section>
    <section class="panel system-section"><div class="panel-header"><div><h3>Printers</h3><p>${printers.length} network print services</p></div></div><div class="table-wrap"><table><thead><tr><th>Hostname</th><th>Status</th><th>Office IP</th><th>Paper</th><th>Toner</th><th>Queue</th><th>Service</th></tr></thead><tbody>
      ${printers.map(device => `<tr data-device="${device.hostname}" tabindex="0"><td><strong>${device.hostname}</strong></td><td>${badge(device.status)}</td><td>${escapeHtml(device.ip_address)}</td><td>${resource(device.live?.paper, device.live?.paper_capacity, device.live?.paper_level)}</td><td>${resource(device.live?.toner, 100, device.live?.toner_level, "%")}</td><td>${escapeHtml(device.live?.queue)}</td><td>${badge(device.service_health)}</td></tr>`).join("")}
    </tbody></table></div></section>`;
}

function resource(value, maximum, level, suffix = "") {
  if (value === undefined) return "—";
  const width = Math.max(0, Math.min(100, value / maximum * 100));
  const tone = level === "empty" ? "empty" : ["notice", "low", "very low"].includes(level) ? "warning" : "";
  return `<div class="resource"><span>${value}${suffix}</span><span class="resource-track"><i class="resource-fill ${tone}" style="width:${width}%"></i></span></div>`;
}

function renderPlanned(page) {
  const plans = {
    "active-directory": ["♙", "Active Directory", "Windows Server, domain services, users, groups, Group Policy, and directory health will be introduced in a future phase."],
    tickets: ["◇", "Tickets", "Ticketing and ITSM workflows will connect real infrastructure events to support operations in a future phase."],
    automation: ["↻", "Automation", "Controlled remediation, health checks, and repeatable infrastructure tasks are planned for a future phase."]
  };
  const [icon, title, description] = plans[page];
  return `<section class="planned-page"><div class="planned-card"><div class="planned-icon">${icon}</div><h2>${title}</h2><p>${description}</p><span class="planned-label">Planned Phase</span></div></section>`;
}

function renderArchitecture() {
  return `${pageIntro("Current architecture", "How the browser reaches real containerized infrastructure while preserving a safe control boundary.")}
    <section class="panel"><div class="panel-header"><div><h3>Runtime and data flow</h3><p>Current local development architecture</p></div></div><div class="architecture-flow">
      ${architectureNode("Browser", "Vanilla frontend on macOS · port 8090")}${architectureNode("FastAPI", "Central API inside Lima · port 8000")}${architectureNode("Docker", "Container runtime inside the netlab VM")}${architectureNode("Containerlab", "17-node routed small-office topology")}${architectureNode("Device services", "Live workstation and printer APIs")}
    </div></section>
    <section class="panel system-section"><div class="panel-header"><div><h3>Design principles</h3><p>Operational behavior over decorative simulation</p></div></div><div class="principles">
      <div class="principle"><strong>One safe backend</strong><span>The frontend uses structured API routes and never receives shell or Docker access.</span></div>
      <div class="principle"><strong>Two network contexts</strong><span>Office-network addressing remains distinct from Containerlab management connectivity.</span></div>
      <div class="principle"><strong>Live state</strong><span>Runtime status comes from containers and endpoint services; inventory contains configuration only.</span></div>
      <div class="principle"><strong>Controlled actions</strong><span>Printer, workstation, and ping operations are allowlisted and validated centrally.</span></div>
      <div class="principle"><strong>Portable endpoint images</strong><span>Local ARM64 images contain their application source without machine-specific bind paths.</span></div>
      <div class="principle"><strong>Incremental roadmap</strong><span>Active Directory, ITSM, and automation remain clearly identified future phases.</span></div>
    </div></section>`;
}

function architectureNode(title, description) {
  return `<div class="architecture-node"><strong>${title}</strong><span>${description}</span></div>`;
}

function renderPage() {
  document.getElementById("pageTitle").textContent = pageTitles[state.page];
  const renderers = {dashboard: renderDashboard, network: renderNetwork, systems: renderSystems, architecture: renderArchitecture};
  content.innerHTML = renderers[state.page] ? renderers[state.page]() : renderPlanned(state.page);
}

function fact(label, value) {
  if (value === undefined || value === null || value === "") return "";
  return `<div class="fact"><span>${label}</span><strong>${escapeHtml(value)}</strong></div>`;
}

function renderDrawer() {
  const device = state.devices.find(item => item.hostname === state.selectedDevice);
  if (!device) return closeDrawer();
  const live = device.live || {};
  const commonFacts = fact("Office IP", device.ip_address || "No Layer 3 address") + fact("Network", device.network) + fact("Connected to", device.connected_switch) + fact("Reachable", device.reachable ? "Yes" : "No") + fact("Service health", device.service_health) + fact("Status source", device.status_source);
  let specific = "";
  if (device.device_type === "printer") {
    const sources = state.devices.filter(item => item.device_type === "workstation" && item.assigned_printer === device.hostname);
    specific = `${device.status === "attention" ? `<section class="drawer-section"><div class="active-fault"><strong>Printing unavailable</strong><span>${escapeHtml(live.message || "Printer requires attention.")}</span></div></section>` : ""}<section class="drawer-section"><h3>Printer resources</h3><div class="facts">${fact("Paper", live.paper !== undefined ? `${live.paper} / ${live.paper_capacity} sheets` : null)}${fact("Paper level", live.paper_level)}${fact("Toner", live.toner !== undefined ? `${live.toner}%` : null)}${fact("Toner level", live.toner_level)}${fact("Queue", live.queue !== undefined ? `${live.queue} jobs` : null)}</div></section>
      <section class="drawer-section"><h3>Print queue</h3><div class="job-list">${live.jobs?.length ? live.jobs.map(job => `<div class="job"><strong>#${job.id}</strong><span>${escapeHtml(job.device)} · ${job.pages} pages</span>${badge(job.status)}</div>`).join("") : `<div class="event-box">No jobs queued.</div>`}</div></section>
      ${live.last_event ? `<section class="drawer-section"><h3>Latest event</h3><div class="event-box">${escapeHtml(live.last_event)}</div></section>` : ""}
      <section class="drawer-section"><h3>Submit print job</h3><div class="field"><label for="printSource">Source workstation</label><select id="printSource">${sources.map(source => `<option value="${source.hostname}">${source.hostname}</option>`).join("")}</select></div><div class="field"><label for="printPages">Pages (blank = random 1–15)</label><input id="printPages" type="number" min="1" max="15" placeholder="Random"></div><button class="action-button" data-print="${device.hostname}" type="button">Add print job</button></section>
      <section class="drawer-section"><h3>Safe actions</h3><div class="action-grid"><button class="action-button danger" data-printer-action="offline">Set Offline</button><button class="action-button" data-printer-action="ready">Set Ready</button><button class="action-button warning" data-printer-action="empty-paper">Empty Paper</button><button class="action-button secondary" data-printer-action="refill-paper">Refill Paper</button><button class="action-button warning" data-printer-action="empty-toner">Empty Toner</button><button class="action-button secondary" data-printer-action="refill-toner">Refill Toner</button><button class="action-button secondary" data-printer-action="complete" ${live.jobs?.length ? "" : "disabled"}>Complete / Retry Job</button></div><div id="actionFeedback" class="action-feedback"></div></section>
      <section class="drawer-section"><a class="action-button secondary" href="http://127.0.0.1:${directPrinterPages[device.hostname]}" target="_blank" rel="noopener">Open direct test page ↗</a></section>`;
  } else if (device.device_type === "workstation") {
    specific = `<section class="drawer-section"><h3>Workstation details</h3><div class="facts">${fact("Default printer", device.assigned_printer)}${fact("Interface", live.interface ? `${live.interface} · ${live.interface_state}` : null)}${fact("MAC address", live.mac_address)}${fact("Uptime", live.uptime_seconds !== undefined ? `${Math.floor(live.uptime_seconds / 3600)}h ${Math.floor(live.uptime_seconds % 3600 / 60)}m` : null)}</div></section>
      ${live.last_event ? `<section class="drawer-section"><h3>Latest event</h3><div class="event-box">${escapeHtml(live.last_event)}</div></section>` : ""}
      <section class="drawer-section"><h3>Safe actions</h3><div class="action-grid"><button class="action-button danger" data-workstation-action="offline">Set Offline</button><button class="action-button" data-workstation-action="online">Set Online</button></div><div id="actionFeedback" class="action-feedback"></div></section>`;
  } else {
    const interfaces = Object.entries(live.interfaces || {}).map(([name, status]) => `${name}: ${status}`).join(", ");
    specific = `<section class="drawer-section"><h3>Infrastructure state</h3><div class="facts">${fact("Interfaces", interfaces)}${fact("Dependency status", device.dependency_status)}${fact("Impacted by", device.impacted_by?.join(", "))}</div>${device.impact_reason ? `<div class="event-box warning">${escapeHtml(device.impact_reason)}</div>` : ""}</section><section class="drawer-section"><h3>Safe actions</h3><div class="action-grid"><button class="action-button danger" data-infrastructure-action="disable" type="button">Disable network function</button><button class="action-button" data-infrastructure-action="restore" type="button">Restore network function</button></div><div id="actionFeedback" class="action-feedback"></div></section>`;
  }
  const displayStatus = device.dependency_status === "impacted" ? "impacted" : device.status;
  document.getElementById("drawerContent").innerHTML = `<header class="drawer-header"><div class="drawer-header-row"><div><h2>${device.hostname}</h2><p>${escapeHtml(typeLabels[device.device_type])}</p></div>${badge(displayStatus)}</div></header>${device.impact_reason ? `<section class="drawer-section"><div class="active-fault dependency"><strong>Connectivity impacted</strong><span>${escapeHtml(device.impact_reason)}</span></div></section>` : ""}<section class="drawer-section"><h3>Identity and connectivity</h3><div class="facts">${commonFacts}</div></section>${specific}`;
}

function openDrawer(hostname) {
  state.selectedDevice = hostname;
  document.getElementById("deviceDrawer").classList.add("open");
  document.getElementById("deviceDrawer").setAttribute("aria-hidden", "false");
  document.getElementById("drawerBackdrop").hidden = false;
  renderDrawer();
  if (state.page === "network") renderPage();
}

function closeDrawer() {
  state.selectedDevice = null;
  document.getElementById("deviceDrawer").classList.remove("open");
  document.getElementById("deviceDrawer").setAttribute("aria-hidden", "true");
  document.getElementById("drawerBackdrop").hidden = true;
}

function openImpactedDevices() {
  const impacted = state.devices.filter(device => device.dependency_status === "impacted");
  state.selectedDevice = null;
  document.getElementById("deviceDrawer").classList.add("open");
  document.getElementById("deviceDrawer").setAttribute("aria-hidden", "false");
  document.getElementById("drawerBackdrop").hidden = false;
  document.getElementById("drawerContent").innerHTML = `<header class="drawer-header"><h2>Impacted devices</h2><p>Devices affected by an infrastructure fault</p></header><section class="drawer-section"><div class="impact-list">${impacted.length ? impacted.map(device => `<button type="button" class="impact-row" data-device="${device.hostname}"><span><strong>${device.hostname}</strong><small>${escapeHtml(typeLabels[device.device_type])}</small></span><span>${escapeHtml(device.impact_reason)}</span><b>Details →</b></button>`).join("") : `<div class="event-box">No devices are currently impacted.</div>`}</div></section>`;
}

function setBackendState(connected, error = null) {
  state.connected = connected;
  const indicator = document.getElementById("backendIndicator");
  indicator.className = `backend-indicator ${connected ? "online" : "offline"}`;
  indicator.querySelector("span").textContent = connected ? "Backend connected" : "Backend unavailable";
  document.getElementById("backendBanner").hidden = connected;
  if (error) document.getElementById("backendMessage").textContent = error.message;
}

async function loadData(force = false) {
  if (state.refreshing && !force) return;
  state.refreshing = true;
  document.getElementById("refreshButton").disabled = true;
  try {
    const [overview, devices] = await Promise.all([api.overview(), api.devices()]);
    state.overview = overview;
    state.devices = devices;
    state.loading = false;
    setBackendState(true);
    document.getElementById("lastUpdated").textContent = `Updated ${new Date().toLocaleTimeString([], {hour:"2-digit", minute:"2-digit", second:"2-digit"})}`;
    renderPage();
    if (state.selectedDevice) renderDrawer();
  } catch (error) {
    state.loading = false;
    state.overview = null;
    state.devices = [];
    setBackendState(false, error);
    renderPage();
    if (state.selectedDevice) closeDrawer();
  } finally {
    state.refreshing = false;
    document.getElementById("refreshButton").disabled = false;
  }
}

function showToast(message, type = "") {
  const toast = document.createElement("div");
  toast.className = `toast ${type}`;
  toast.textContent = message;
  document.getElementById("toastRegion").appendChild(toast);
  setTimeout(() => toast.remove(), 4500);
}

function showActionError(error) {
  const feedback = document.getElementById("actionFeedback");
  if (feedback) feedback.innerHTML = `<div class="diagnostic-result error"><strong>${escapeHtml(error.message)}</strong>${error.details ? `<details class="technical-details"><summary>Technical details</summary><pre>${escapeHtml(JSON.stringify(error.details, null, 2))}</pre></details>` : ""}</div>`;
  showToast(error.message, "error");
}

async function performAction(callback, successMessage) {
  try {
    await callback();
    showToast(successMessage);
    await loadData(true);
  } catch (error) {
    showActionError(error instanceof ApiError ? error : new ApiError("The action failed."));
  }
}

document.addEventListener("click", async event => {
  const nav = event.target.closest("[data-page]");
  if (nav) {
    state.page = nav.dataset.page;
    document.querySelectorAll(".nav-item").forEach(item => item.classList.toggle("active", item === nav));
    document.querySelector(".sidebar").classList.remove("open");
    renderPage();
    content.focus();
    return;
  }
  const dashboardAction = event.target.closest("[data-dashboard-action]");
  if (dashboardAction?.dataset.dashboardAction === "printer-alerts") {
    const alert = state.overview?.printer_alerts?.[0];
    if (alert) openDrawer(alert.hostname);
    else showToast("No printers currently require attention.");
    return;
  }
  if (dashboardAction?.dataset.dashboardAction === "impacted-devices") {
    openImpactedDevices();
    return;
  }
  const device = event.target.closest("[data-device]");
  if (device) return openDrawer(device.dataset.device);
  if (event.target.id === "runPing") {
    const source = document.getElementById("pingSource").value;
    const destination = document.getElementById("pingDestination").value;
    state.pingSource = source;
    state.pingDestination = destination;
    try {
      state.pingResult = await api.ping(source, destination);
    } catch (error) {
      state.pingResult = {success: false, message: error.message};
    }
    return renderPage();
  }
  if (event.target.dataset.print) {
    const printer = event.target.dataset.print;
    const source = document.getElementById("printSource").value;
    const pages = document.getElementById("printPages").value;
    return performAction(() => api.submitPrintJob(printer, source, pages), `Print job sent from ${source} to ${printer}.`);
  }
  if (event.target.dataset.printerAction) {
    const action = event.target.dataset.printerAction;
    return performAction(() => api.printerAction(state.selectedDevice, action), `${state.selectedDevice}: ${action.replaceAll("-", " ")} completed.`);
  }
  if (event.target.dataset.workstationAction) {
    const action = event.target.dataset.workstationAction;
    return performAction(() => api.workstationAction(state.selectedDevice, action), `${state.selectedDevice} set ${action}.`);
  }
  if (event.target.dataset.infrastructureAction) {
    const action = event.target.dataset.infrastructureAction;
    const hostname = state.selectedDevice;
    return performAction(() => api.infrastructureAction(hostname, action), `${hostname} ${action === "disable" ? "disabled" : "restored"}.`);
  }
});

document.addEventListener("change", event => {
  if (event.target.id === "pingSource") state.pingSource = event.target.value;
  if (event.target.id === "pingDestination") state.pingDestination = event.target.value;
});

document.addEventListener("keydown", event => {
  if (event.key === "Escape") closeDrawer();
  if ((event.key === "Enter" || event.key === " ") && event.target.matches("tr[data-device]")) openDrawer(event.target.dataset.device);
});
document.getElementById("closeDrawer").addEventListener("click", closeDrawer);
document.getElementById("drawerBackdrop").addEventListener("click", closeDrawer);
document.getElementById("refreshButton").addEventListener("click", () => loadData(true));
document.getElementById("retryButton").addEventListener("click", () => loadData(true));
document.getElementById("menuButton").addEventListener("click", () => document.querySelector(".sidebar").classList.toggle("open"));

renderPage();
loadData();
setInterval(loadData, 5000);
