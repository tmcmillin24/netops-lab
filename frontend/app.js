import {api, ApiError} from "./api.js?v=phase11-cleanup";

const state = {
  page: "dashboard",
  overview: null,
  devices: [],
  directory: null,
  directoryHealth: null,
  directoryLoading: false,
  directoryView: "users",
  connected: false,
  selectedDevice: null,
  selectedDirectoryUser: null,
  fileAccessShare: null,
  drawerReturn: null,
  loading: true,
  refreshing: false,
  pingResult: null,
  diagnosticsActive: false,
  diagnosticType: "ping",
  pingSource: "WS01",
  pingDestination: "PRNT01"
};

const pageTitles = {
  dashboard: "Dashboard",
  network: "Network",
  systems: "Systems",
  "active-directory": "Active Directory",
  monitoring: "Monitoring",
  tickets: "Tickets",
  automation: "Automation",
  architecture: "Architecture"
};

const typeLabels = {
  router_firewall: "Router / Firewall",
  layer3_core_switch: "Layer 3 Core Switch",
  access_switch: "Access Switch",
  workstation: "Linux Workstation",
  printer: "Network Printer",
  domain_controller: "Samba AD Domain Controller",
  file_server: "Samba File Server"
};

const diagnosticHelp = {
  ping: "Send one ICMP echo and show the command response.",
  reachability: "Verify basic Layer 3 reachability between the selected devices.",
  traceroute: "Show the routed path with a safe eight-hop limit.",
  dns: "Resolve the destination's Containerlab hostname from the source.",
  "service-health": "Check the destination container and managed service."
};

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
  const events = overview.recent_events || [];
  const alertSummary = overview.monitoring?.summary || {active: 0, critical: 0, warning: 0, notice: 0};
  const infrastructure = [
    ["Routing and switching", state.devices.filter(device => ["router_firewall", "layer3_core_switch", "access_switch"].includes(device.device_type))],
    ["Workstation services", state.devices.filter(device => device.device_type === "workstation")],
    ["Printer services", state.devices.filter(device => device.device_type === "printer")],
    ["Server services", state.devices.filter(device => ["domain_controller", "file_server"].includes(device.device_type))]
  ];
  return `${pageIntro("Lab overview", "Live health and operational state from the centralized backend.")}
    ${alertSummary.active ? `<button class="operational-alert-summary" type="button" data-page-link="monitoring"><span><strong>${alertSummary.active} active operational ${alertSummary.active === 1 ? "alert" : "alerts"}</strong><small>${alertSummary.critical} critical · ${alertSummary.warning} warning · ${alertSummary.notice} notice</small></span>${badge(overview.operational_health)}</button>` : ""}
    <section class="metric-grid" aria-label="Lab health summary">
      ${metric("Total devices", overview.total_devices, "Current inventory")}
      ${metric("Online", overview.online_devices, "Click to inspect available devices", "good", "online-devices")}
      ${metric("Offline", overview.offline_devices, "Click to inspect immediate problems", overview.offline_devices ? "bad" : "good", "offline-devices")}
      ${metric("Printer attention", overview.printers_requiring_attention, "Click to inspect active faults", overview.printers_requiring_attention ? "warn" : "good", "printer-alerts")}
      ${metric("Service attention", overview.services_requiring_attention || 0, "Click to inspect server services", overview.services_requiring_attention ? "warn" : "good", "service-alerts")}
      ${metric("Account Attention", alertSummary.account_attention || 0, "Accounts requiring review", alertSummary.account_attention ? "warn" : "good", "account-alerts")}
      ${metric("Overall health", overview.operational_health || overview.network_health, "Devices, services, and accounts", (overview.operational_health || overview.network_health) === "healthy" ? "good" : "bad")}
    </section>
    <div class="dashboard-grid">
      <section class="panel"><div class="panel-header"><div><h3>Infrastructure health</h3><p>Grouped live availability</p></div>${badge(overview.network_health)}</div>
        <div class="health-list">${infrastructure.map(([label, devices]) => {
          const healthy = devices.filter(device => !["offline", "unavailable"].includes(device.status) && device.dependency_status !== "impacted" && !["unavailable", "attention"].includes(device.service_health)).length;
          return `<div class="health-row"><div><strong>${label}</strong><br><span>${healthy} of ${devices.length} available</span></div>${badge(healthy === devices.length ? "healthy" : "warning")}</div>`;
        }).join("")}</div>
      </section>
      <section class="panel"><div class="panel-header"><div><h3>Recent lab events</h3><p>Infrastructure and endpoint state changes</p></div></div>
        <div class="event-list recent-event-list">${events.length ? events.slice(0, 15).map(event => `<button type="button" class="event-row event-button" data-device="${event.hostname}"><i class="${slug(event.type)}"></i><div><strong>${escapeHtml(event.hostname)}</strong><small>${escapeHtml(event.message)}</small></div>${badge(event.type)}</button>`).join("") : `<div class="empty-state">No recent state changes.</div>`}</div>
      </section>
    </div>`;
}

function formatAlertTime(value) {
  if (!value) return "—";
  return new Date(value).toLocaleString([], {month: "short", day: "numeric", hour: "2-digit", minute: "2-digit"});
}

function renderMonitoring() {
  if (state.loading) return loadingState("Evaluating current alert conditions…");
  if (!state.connected || !state.overview) return unavailableState();
  const monitoring = state.overview.monitoring || {summary: {}, active_alerts: [], resolved_alerts: []};
  const alerts = monitoring.active_alerts;
  const rows = alerts.map(alert => {
    const device = alert.related?.device;
    const username = alert.related?.username;
    const target = device ? `data-alert-device="${escapeHtml(device)}"` : username ? `data-alert-user="${escapeHtml(username)}"` : "";
    return `<tr ${target} tabindex="0"><td>${badge(alert.severity)}</td><td><strong>${escapeHtml(alert.source)}</strong><br><small>${escapeHtml(alert.source_type.replaceAll("_", " "))}</small></td><td>${escapeHtml(alert.summary)}</td><td>${formatAlertTime(alert.detected_at)}</td><td>${badge("active")}</td></tr>`;
  }).join("");
  return `${pageIntro("Monitoring and alerts", "Current health conditions derived from live lab state.")}
    <section class="monitoring-summary" aria-label="Alert summary">
      ${metric("Active", monitoring.summary.active || 0, "Current conditions", monitoring.summary.active ? "bad" : "good")}
      ${metric("Critical", monitoring.summary.critical || 0, "Immediate attention", monitoring.summary.critical ? "bad" : "good")}
      ${metric("Warnings", monitoring.summary.warning || 0, "Operational attention", monitoring.summary.warning ? "warn" : "good")}
      ${metric("Notices", monitoring.summary.notice || 0, "Lower severity", monitoring.summary.notice ? "warn" : "good")}
      ${metric("Account attention", monitoring.summary.account_attention || 0, "Live directory state", monitoring.summary.account_attention ? "warn" : "good")}
    </section>
    <section class="panel"><div class="panel-header"><div><h3>Active alerts</h3><p>Current conditions requiring operational attention</p></div></div><div class="table-wrap monitoring-table"><table><thead><tr><th>Severity</th><th>Source</th><th>Issue</th><th>Detected</th><th>Status</th></tr></thead><tbody>${rows || '<tr><td colspan="5">No active alerts.</td></tr>'}</tbody></table></div></section>`;
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
    <small>${escapeHtml(device.form_factor === "laptop" ? "Linux Laptop" : typeLabels[device.device_type])}</small><small>${escapeHtml(device.ip_address || "Layer 2")}</small>
  </button>`;
}

function diagnosticTranscript(result) {
  const type = result.diagnostic_type || state.diagnosticType;
  const source = result.source || state.pingSource;
  const destination = result.destination || state.pingDestination;
  const lines = [
    `netops@${source.toLowerCase()}:~$ ${type} ${destination.toLowerCase()}`,
    `TARGET  ${destination}${result.destination_ip ? ` (${result.destination_ip})` : ""}`,
    `RESULT  ${result.success ? "SUCCESS" : "FAILED"}`,
  ];
  if (result.message) lines.push(`DETAIL  ${result.message}`);
  if (result.latency_ms !== null && result.latency_ms !== undefined) lines.push(`LATENCY ${result.latency_ms} ms`);
  if (result.service_health) lines.push(`SERVICE ${result.service_health}`, `DEVICE  ${result.device_status}`);
  if (result.query) lines.push(`QUERY   ${result.query}`);
  if (result.addresses?.length) lines.push("", "ANSWER", ...result.addresses.map(address => `  ${address}`));
  if (result.hops?.length) lines.push("", "ROUTE", ...result.hops.map(hop => `  ${hop}`));
  if (result.output) lines.push("", "COMMAND OUTPUT", ...result.output.split("\n").map(line => `  ${line}`));
  return `<section class="terminal-result ${result.success ? "success" : "error"}"><header><span></span><span></span><span></span><strong>controlled diagnostic</strong></header><pre>${escapeHtml(lines.join("\n"))}</pre></section>`;
}

function renderNetwork() {
  if (state.loading) return loadingState("Building the current topology…");
  if (!state.connected) return unavailableState();
  const byName = Object.fromEntries(state.devices.map(device => [device.hostname, device]));
  const router = byName.RTR01;
  const core = byName.CORE01;
  const serviceDevices = [byName.DC01, byName.FILE01].filter(Boolean);
  const switches = ["SW01", "SW02", "SW03"].map(name => byName[name]).filter(Boolean);
  const groups = switches.map(networkSwitch => {
    const endpoints = state.devices.filter(device => device.connected_switch === networkSwitch.hostname && ["workstation", "printer"].includes(device.device_type));
    const floor = endpoints[0]?.floor || networkSwitch.floor || networkSwitch.network;
    const department = endpoints[0]?.department || networkSwitch.department || "Access network";
    return `<div class="access-group">${deviceCard(networkSwitch)}<div class="network-label"><strong>${escapeHtml(floor)}</strong><span>${escapeHtml(department)}</span></div><div class="endpoint-grid">${endpoints.map(deviceCard).join("")}</div></div>`;
  }).join("");
  const addressableDevices = state.devices.filter(device => device.ip_address);
  const sourceOptions = addressableDevices.map(device => `<option value="${device.hostname}" ${device.hostname === state.pingSource ? "selected" : ""}>${device.hostname} · ${device.ip_address}${device.floor ? ` · ${escapeHtml(device.floor)}` : ""}</option>`).join("");
  const destinationOptions = addressableDevices.map(device => `<option value="${device.hostname}" ${device.hostname === state.pingDestination ? "selected" : ""}>${device.hostname} · ${device.ip_address}${device.floor ? ` · ${escapeHtml(device.floor)}` : ""}</option>`).join("");
  return `${pageIntro("Office topology", "Live status across three routed access networks. Select any node for details.")}<div class="page-actions"><button class="action-button" type="button" data-add-workstation>＋ Add device</button></div>
    <div class="network-layout">
      <section class="panel topology-panel"><div class="topology-legend"><span>${badge("online")} Available</span><span>${badge("attention")} Attention</span><span>${badge("offline")} Offline</span></div>
        <div id="topology" class="topology">${router ? `<div class="topology-tier">${deviceCard(router)}</div>` : ""}${core ? `<div class="topology-tier">${deviceCard(core)}</div>` : ""}${serviceDevices.length ? `<div class="topology-tier services-tier"><div><div class="network-label"><strong>Services</strong><span>netopslab.test · 10.10.40.0/24</span></div><div class="service-grid">${serviceDevices.map(deviceCard).join("")}</div></div></div>` : ""}<div class="topology-tier access-tier">${groups}</div></div>
      </section>
      <aside class="panel diagnostic-panel"><h3>Connectivity diagnostics</h3><p>Run an allowlisted test between addressable inventory devices.</p>
        <div class="field"><label for="diagnosticType">Diagnostic type</label><select id="diagnosticType">${[["ping", "Ping"], ["reachability", "Reachability"], ["traceroute", "Traceroute"], ["dns", "DNS lookup"], ["service-health", "Service health"]].map(([value, label]) => `<option value="${value}" ${state.diagnosticType === value ? "selected" : ""}>${label}</option>`).join("")}</select></div>
        <div class="field"><label for="pingSource">Source device</label><select id="pingSource">${sourceOptions}</select></div>
        <div class="field"><label for="pingDestination">Destination device</label><select id="pingDestination">${destinationOptions}</select></div>
        <div class="diagnostic-help">${escapeHtml(diagnosticHelp[state.diagnosticType])}</div>
        <button id="runPing" class="action-button" type="button">Run connectivity test</button>
        ${state.pingResult ? diagnosticTranscript(state.pingResult) : ""}
      </aside>
    </div>`;
}

function renderSystems() {
  if (state.loading) return loadingState("Loading workstation and printer services…");
  if (!state.connected) return unavailableState();
  const workstations = state.devices.filter(device => device.device_type === "workstation" && device.form_factor !== "laptop");
  const laptops = state.devices.filter(device => device.device_type === "workstation" && device.form_factor === "laptop");
  const printers = state.devices.filter(device => device.device_type === "printer");
  const servers = state.devices.filter(device => ["domain_controller", "file_server"].includes(device.device_type));
  const endpointRows = devices => devices.map(device => `<tr data-device="${device.hostname}" tabindex="0"><td><strong>${device.hostname}</strong></td><td>${badge(device.status)}</td><td>${escapeHtml(device.ip_address)}</td><td>${escapeHtml(device.connected_switch)}</td><td>${escapeHtml(device.assigned_printer)}</td><td>${escapeHtml(device.assigned_user || "Unassigned")}</td><td>${device.reachable ? "Reachable" : "Unreachable"}</td><td>${badge(device.service_health)}</td></tr>`).join("");
  const endpointTable = (devices, sizeClass) => `<div class="table-wrap system-table-scroll ${sizeClass}"><table><thead><tr><th>Hostname</th><th>Status</th><th>Office IP</th><th>Access switch</th><th>Default printer</th><th>Assigned employee</th><th>Reachability</th><th>Service</th></tr></thead><tbody>${endpointRows(devices)}</tbody></table></div>`;
  return `${pageIntro("Systems inventory", "Live server, endpoint, and printer state from the backend.")}
    <section class="panel system-section"><div class="panel-header"><div><h3>Servers</h3><p>${servers.length} infrastructure services</p></div></div><div class="table-wrap"><table><thead><tr><th>Hostname</th><th>Status</th><th>Role</th><th>Office IP</th><th>Network</th><th>Services</th><th>Service health</th></tr></thead><tbody>${servers.map(device => `<tr data-device="${device.hostname}" tabindex="0"><td><strong>${device.hostname}</strong></td><td>${badge(device.status)}</td><td>${escapeHtml(typeLabels[device.device_type])}</td><td>${escapeHtml(device.ip_address)}</td><td>${escapeHtml(device.network)}</td><td>${device.device_type === "file_server" ? "SMB · 5 shares" : "AD DS · DNS · Kerberos"}</td><td>${badge(device.service_health)}</td></tr>`).join("")}</tbody></table></div></section>
    <section class="panel system-section"><div class="panel-header"><div><h3>Workstations</h3><p>${workstations.length} managed desktop endpoints · 5 visible before scrolling</p></div></div>${endpointTable(workstations, "workstation-list")}</section>
    <section class="panel system-section"><div class="panel-header"><div><h3>Laptops</h3><p>${laptops.length} managed portable endpoints · 3 visible before scrolling</p></div></div>${endpointTable(laptops, "laptop-list")}</section>
    <section class="panel system-section"><div class="panel-header"><div><h3>Printers</h3><p>${printers.length} network print services · 2 visible before scrolling</p></div></div><div class="table-wrap system-table-scroll printer-list"><table><thead><tr><th>Hostname</th><th>Status</th><th>Office IP</th><th>Paper</th><th>Toner</th><th>Queue</th><th>Service</th></tr></thead><tbody>
      ${printers.map(device => `<tr data-device="${device.hostname}" tabindex="0"><td><strong>${device.hostname}</strong></td><td>${badge(device.status)}</td><td>${escapeHtml(device.ip_address)}</td><td>${resource(device.live?.paper, device.live?.paper_capacity, device.live?.paper_level)}</td><td>${resource(device.live?.toner, 100, device.live?.toner_level, "%")}</td><td>${escapeHtml(device.live?.queue)}</td><td>${badge(device.service_health)}</td></tr>`).join("")}
    </tbody></table></div></section>`;
}

function renderActiveDirectory() {
  if (state.directoryLoading && !state.directory) return loadingState("Querying DC01…");
  const directory = state.directory;
  if (!directory || directory.status === "unavailable") {
    return `${pageIntro("Active Directory", "Samba AD foundation for the NetOps Lab domain.")}<div class="panel empty-state"><strong>DC01 unavailable</strong>Directory or DNS health could not be verified.</div>`;
  }
  const activeUsers = directory.users.filter(user => user.enabled);
  const employees = activeUsers.filter(user => user.account_type === "employee");
  const unassignedUsers = employees.filter(user => !user.workstation);
  const remoteUsers = employees.filter(user => user.remote);
  const disabledUsers = directory.users.filter(user => !user.enabled);
  const workstations = state.devices.filter(device => device.device_type === "workstation");
  const accountStatus = user => user.enabled ? user.locked ? "locked" : user.password_expired ? "password expired" : "enabled" : "disabled";
  const userRows = users => users.map(user => `<tr tabindex="0" data-ad-user="${user.username}" class="${user.enabled ? "" : "disabled-account"}"><td><strong>${escapeHtml(user.display_name)}</strong><br><small>${escapeHtml(user.username)}</small></td><td>${escapeHtml(user.role)}</td><td>${escapeHtml(user.department)}</td><td>${escapeHtml(user.workstation || "Unassigned")}</td><td>${badge(accountStatus(user))}</td></tr>`).join("");
  const disabledRows = disabledUsers.map(user => `<tr tabindex="0" data-ad-user="${user.username}" class="disabled-account"><td><strong>${escapeHtml(user.display_name)}</strong></td><td>${escapeHtml(user.username)}</td><td>${badge("disabled")}</td></tr>`).join("");
  const views = {
    users: `<div class="panel-header"><div><h3>Users</h3><p>${activeUsers.length} active domain accounts · 8 visible before scrolling</p></div></div><div class="table-wrap directory-table-scroll"><table><thead><tr><th>Name</th><th>Title</th><th>Department</th><th>Workstation</th><th>Status</th></tr></thead><tbody>${userRows(activeUsers)}</tbody></table></div>`,
    unassigned: `<div class="panel-header"><div><h3>Unassigned Members</h3><p>${unassignedUsers.length} enabled employees without a device</p></div></div><div class="table-wrap directory-table-scroll"><table><thead><tr><th>Name</th><th>Title</th><th>Department</th><th>Workstation</th><th>Status</th></tr></thead><tbody>${userRows(unassignedUsers) || '<tr><td colspan="5">No enabled employees are currently unassigned.</td></tr>'}</tbody></table></div>`,
    remote: `<div class="panel-header"><div><h3>Remote Users</h3><p>${remoteUsers.length} employees issued company laptops</p></div></div><div class="table-wrap directory-table-scroll"><table><thead><tr><th>Name</th><th>Title</th><th>Department</th><th>Laptop</th><th>Status</th></tr></thead><tbody>${userRows(remoteUsers)}</tbody></table></div>`,
    computers: `<div class="panel-header"><div><h3>Computers</h3><p>${workstations.length} pre-staged workstation objects · 8 visible before scrolling</p></div></div><div class="table-wrap directory-table-scroll"><table><thead><tr><th>Computer</th><th>Assigned user</th><th>Floor</th><th>Department</th><th>Join state</th></tr></thead><tbody>${workstations.map(device => { const user = activeUsers.find(item => item.workstation === device.hostname); return `<tr tabindex="0" ${user ? `data-ad-user="${user.username}"` : ""}><td><strong>${escapeHtml(device.hostname)}</strong></td><td>${escapeHtml(user?.display_name || "Unassigned")}</td><td>${escapeHtml(device.floor)}</td><td>${escapeHtml(device.department)}</td><td>${badge(device.domain_joined ? "joined" : "not joined")}</td></tr>`; }).join("")}</tbody></table></div>`,
    groups: `<div class="panel-header"><div><h3>Security Groups</h3><p>${directory.groups.length} role-based access groups · select one to view members</p></div></div><div class="group-list directory-object-list directory-list-scroll">${directory.groups.map(group => `<button class="group-row" type="button" data-directory-group="${escapeHtml(group.name)}"><span><strong>${escapeHtml(group.name)}</strong><small>${escapeHtml(group.description)}</small></span><small>${group.members.length} members</small></button>`).join("")}</div>`,
    disabled: `<div class="panel-header"><div><h3>Disabled Accounts</h3><p>Former employees retained for audit history</p></div></div><div class="table-wrap directory-table-scroll"><table><thead><tr><th>Name</th><th>Username</th><th>Status</th></tr></thead><tbody>${disabledRows}</tbody></table></div>`
  };
  const policy = directory.password_policy || {};
  const categories = [["users", "Users", activeUsers.length], ["unassigned", "Unassigned", unassignedUsers.length], ["remote", "Remote Users", remoteUsers.length], ["computers", "Computers", workstations.length], ["groups", "Security Groups", directory.groups.length], ["disabled", "Disabled", disabledUsers.length]];
  return `${pageIntro("Active Directory", "Live identity data from DC01 · Samba AD-compatible domain services.")}<div class="page-actions"><button class="action-button" type="button" data-add-employee>＋ Add employee</button></div>
    <section class="directory-summary">
      <article><span>Domain</span><strong>${escapeHtml(directory.domain)}</strong><small>${escapeHtml(directory.domain_controller)} · ${badge(directory.status)}</small></article>
      <article><span>Active accounts</span><strong>${activeUsers.length}</strong><small>${employees.length} employees · ${activeUsers.length - employees.length} administrative/service</small></article>
      <article><span>Computers</span><strong>${workstations.length}</strong><small>Pre-staged objects</small></article>
      <article><span>Password policy</span><strong>${policy.minimum_length || "—"} characters</strong><small>${policy.complexity ? "Complexity on" : "Complexity off"} · lock after ${policy.lockout_threshold ?? "—"} attempts</small></article>
    </section>
    <div class="directory-tabbar"><nav class="directory-tabs" aria-label="Directory objects">${categories.map(([view, label, count]) => `<button type="button" data-directory-view="${view}" class="${state.directoryView === view ? "active" : ""}"><span>${label}</span><small>${count}</small></button>`).join("")}</nav></div>
    <section class="panel directory-content">${views[state.directoryView] || views.users}</section>`;
}

function openDirectoryUser(username) {
  const user = state.directory?.users.find(item => item.username === username);
  if (!user) return;
  state.selectedDevice = null;
  state.selectedDirectoryUser = username;
  state.fileAccessShare = null;
  document.getElementById("deviceDrawer").classList.add("open");
  document.getElementById("deviceDrawer").setAttribute("aria-hidden", "false");
  document.getElementById("drawerBackdrop").hidden = false;
  const groupOptions = state.directory.groups.map(group => `<option value="${group.name}" data-member="${user.groups.includes(group.name)}">${escapeHtml(group.name)}${user.groups.includes(group.name) ? " · Member" : ""}</option>`).join("");
  const currentStatus = user.enabled ? user.locked ? "locked" : user.password_expired ? "password expired" : "enabled" : "disabled";
  const recoveryActions = [
    user.locked ? `<button class="action-button" data-ad-action="unlock" data-ad-user="${user.username}">Unlock account</button>` : "",
    user.password_expired ? `<button class="action-button warning" data-ad-reset="${user.username}">Reset expired password</button>` : "",
    !user.enabled ? `<button class="action-button" data-ad-action="enable" data-ad-user="${user.username}">Enable account</button>` : "",
  ].filter(Boolean).join("");
  const recoverySection = recoveryActions
    ? `<section class="drawer-section account-recovery"><h3>Recommended recovery</h3><p class="section-note">Only actions relevant to the current account state are shown.</p><div class="action-grid">${recoveryActions}</div></section>`
    : `<section class="drawer-section account-recovery"><div class="account-state-clear"><strong>Account is operational</strong><span>No account-state recovery is currently required.</span></div></section>`;
  const administrativeActions = user.enabled
    ? `${user.password_expired ? "" : `<button class="action-button warning" data-ad-reset="${user.username}">Reset password</button>`}<button class="action-button danger" data-ad-action="disable" data-ad-user="${user.username}">Disable account</button>`
    : "";
  document.getElementById("drawerContent").innerHTML = `<header class="drawer-header"><div class="drawer-header-row"><div><h2>${escapeHtml(user.display_name)}</h2><p>${escapeHtml(user.username)} · ${escapeHtml(user.role)}</p></div>${badge(currentStatus)}</div></header>${recoverySection}<div id="actionFeedback" class="action-feedback directory-action-feedback"></div><section class="drawer-section"><h3>Organization</h3><div class="facts">${fact("Department", user.department)}${fact("Floor", user.floor)}${fact("Assigned workstation", user.workstation || "Unassigned")}${fact("Account type", String(user.account_type || "employee").replaceAll("_", " "))}${fact("Remote user", user.remote ? "Yes" : "No")}${fact("Privileged identity", user.privileged ? "Yes" : "No")}${fact("Domain", state.directory.domain)}</div>${user.account_type === "employee" && user.workstation ? `<button class="action-button secondary account-device-action" data-unassign-employee="${user.username}" type="button">Unassign from ${escapeHtml(user.workstation)}</button>` : user.account_type === "employee" && user.enabled ? `<button class="action-button account-device-action" data-open-assignment="${user.username}" type="button">Assign a device</button>` : ""}</section><section class="drawer-section"><h3>Account state</h3><div class="facts">${fact("Enabled", user.enabled ? "Yes" : "No")}${fact("Locked", user.locked ? "Yes" : "No")}${fact("Password expired", user.password_expired ? "Yes" : "No")}${fact("Bad password attempts", user.bad_password_count)}${fact("Groups", user.groups.join(", ") || "None")}</div></section><section class="drawer-section"><h3>File Share Access</h3><p class="section-note">Effective access from AD security-group membership.</p><div id="userFileShareAccess" class="loading-state compact"><strong>Loading FILE01 access</strong>Querying live group membership…</div></section><section class="drawer-section"><h3>Group membership</h3><div class="field"><label for="adGroup">Security group</label><select id="adGroup">${groupOptions}</select></div><button id="adGroupAction" class="action-button secondary" data-ad-membership data-ad-user="${user.username}">Update membership</button></section>${administrativeActions ? `<section class="drawer-section account-administration"><h3>Account administration</h3><p class="section-note">Routine and potentially disruptive account actions.</p><div class="action-grid">${administrativeActions}</div></section>` : ""}`;
  updateDirectoryGroupAction();
  loadDirectoryUserFileAccess(username);
}

function updateDirectoryGroupAction() {
  const group = document.getElementById("adGroup");
  const button = document.getElementById("adGroupAction");
  if (!group || !button) return;
  const isMember = group.selectedOptions[0]?.dataset.member === "true";
  button.dataset.adMembership = isMember ? "remove" : "add";
  button.classList.toggle("secondary", isMember);
  button.textContent = `${isMember ? "Remove from" : "Add to"} ${group.value}`;
}

async function loadDirectoryUserFileAccess(username) {
  try {
    const access = await api.fileUserAccess(username);
    if (state.selectedDirectoryUser !== username) return;
    const target = document.getElementById("userFileShareAccess");
    if (!target) return;
    target.className = "user-share-access-list";
    target.innerHTML = access.shares.map(share => {
      const controls = share.groups.map(group => `<button class="action-button ${group.member ? "secondary" : ""}" type="button" data-file-membership="${group.member ? "remove" : "add"}" data-share="${escapeHtml(share.name)}" data-group="${escapeHtml(group.name)}" data-username="${escapeHtml(username)}" data-return-user="${escapeHtml(username)}">${group.member ? "Remove" : "Add"} ${escapeHtml(group.name)}</button>`).join("");
      const detail = share.granted ? `${escapeHtml(share.access_level)} via ${escapeHtml(share.granting_groups.join(", "))}` : "No Access";
      return `<article class="user-share-access ${share.granted ? "granted" : "denied"}"><div><strong>${escapeHtml(share.name)}</strong><small>${detail}</small></div><div class="user-share-controls">${controls}</div></article>`;
    }).join("");
  } catch (error) {
    const target = document.getElementById("userFileShareAccess");
    if (target && state.selectedDirectoryUser === username) target.innerHTML = `<div class="diagnostic-result error">${escapeHtml(error.message)}</div>`;
  }
}

function openDirectoryGroup(groupName) {
  const group = state.directory?.groups.find(item => item.name === groupName);
  if (!group) return;
  const members = group.members.map(username => {
    const user = state.directory.users.find(item => item.username === username);
    return user ? `<button class="directory-member" type="button" data-ad-user="${user.username}"><span><strong>${escapeHtml(user.display_name)}</strong><small>${escapeHtml(user.username)} · ${escapeHtml(user.role)}</small></span>${badge(user.enabled ? "enabled" : "disabled")}</button>` : `<div class="directory-member"><strong>${escapeHtml(username)}</strong></div>`;
  }).join("");
  state.selectedDevice = null;
  document.getElementById("deviceDrawer").classList.add("open");
  document.getElementById("deviceDrawer").setAttribute("aria-hidden", "false");
  document.getElementById("drawerBackdrop").hidden = false;
  document.getElementById("drawerContent").innerHTML = `<header class="drawer-header"><div><p>Security group</p><h2>${escapeHtml(group.name)}</h2><p>${escapeHtml(group.description)}</p></div></header><section class="drawer-section"><h3>Members (${group.members.length})</h3><div class="directory-members">${members || '<div class="empty-state">No users are assigned to this group.</div>'}</div></section>`;
}

async function openManageFileAccess(shareName) {
  state.selectedDevice = "FILE01";
  state.selectedDirectoryUser = null;
  state.fileAccessShare = shareName;
  document.getElementById("deviceDrawer").classList.add("open");
  document.getElementById("deviceDrawer").setAttribute("aria-hidden", "false");
  document.getElementById("drawerBackdrop").hidden = false;
  document.getElementById("drawerContent").innerHTML = `<header class="drawer-header"><button class="drawer-back" type="button" data-file-access-back>← FILE01</button><div><p>Manage group-based access</p><h2>${escapeHtml(shareName)} share</h2></div></header><div class="loading-state compact"><strong>Loading live group membership</strong>Querying only this share's access groups…</div>`;
  try {
    const access = await api.fileShareAccess(shareName);
    if (state.fileAccessShare !== shareName) return;
    const groupSummary = access.groups.map(group => `<div class="fact"><span>${escapeHtml(group.name)}</span><strong>${escapeHtml(group.access_level)}</strong></div>`).join("");
    const current = access.effective_users.map(user => `<div class="access-member"><span><strong>${escapeHtml(user.display_name)}</strong><small>${escapeHtml(user.username)} · ${escapeHtml(user.access_level)} through ${escapeHtml(user.groups.join(", "))}</small></span><span>${user.groups.map(group => `<button class="action-button secondary" type="button" data-file-membership="remove" data-share="${escapeHtml(shareName)}" data-group="${escapeHtml(group)}" data-username="${escapeHtml(user.username)}">Remove ${escapeHtml(group)}</button>`).join(" ")}</span></div>`).join("");
    const available = access.available_users.map(user => `<div class="access-member"><span><strong>${escapeHtml(user.display_name)}</strong><small>${escapeHtml(user.username)} · ${escapeHtml(user.role)}</small></span><span>${access.groups.map(group => `<button class="action-button" type="button" data-file-membership="add" data-share="${escapeHtml(shareName)}" data-group="${escapeHtml(group.name)}" data-username="${escapeHtml(user.username)}">Add to ${escapeHtml(group.name)}</button>`).join(" ")}</span></div>`).join("");
    document.getElementById("deviceDrawer").classList.add("open");
    document.getElementById("deviceDrawer").setAttribute("aria-hidden", "false");
    document.getElementById("drawerBackdrop").hidden = false;
    document.getElementById("drawerContent").innerHTML = `<header class="drawer-header"><button class="drawer-back" type="button" data-file-access-back>← FILE01</button><div><p>Manage group-based access</p><h2>${escapeHtml(shareName)} share</h2><p>User → AD security group → FILE01 permission</p></div></header><section class="drawer-section"><h3>Allowed groups</h3><div class="facts">${groupSummary}</div></section><section class="drawer-section"><h3>Current access (${access.effective_users.length})</h3><div class="access-member-list">${current || '<div class="event-box">No users currently receive access.</div>'}</div></section><section class="drawer-section"><h3>Available users</h3><div class="access-member-list">${available || '<div class="event-box">Every eligible user already has access.</div>'}</div><div id="actionFeedback" class="action-feedback"></div></section>`;
  } catch (error) { showActionError(error); }
}

async function openWorkstationWizard() {
  try {
    const options = await api.provisioningOptions();
    state.selectedDevice = null;
    document.getElementById("deviceDrawer").classList.add("open");
    document.getElementById("deviceDrawer").setAttribute("aria-hidden", "false");
    document.getElementById("drawerBackdrop").hidden = false;
    const floors = Object.entries(options.floors).map(([value, item]) => `<option value="${value}">${escapeHtml(item.floor)} · ${escapeHtml(item.department)}</option>`).join("");
    document.getElementById("drawerContent").innerHTML = `<header class="drawer-header"><div><p>Network provisioning</p><h2>Add device</h2><p>Create an unassigned workstation or laptop. Applying the draft redeploys Containerlab.</p></div></header><section class="drawer-section"><h3>Device and placement</h3><div class="field"><label for="provisionDeviceType">Device type</label><select id="provisionDeviceType"><option value="workstation">Workstation (WS)</option><option value="laptop">Laptop (LTP)</option></select></div><div class="field"><label for="provisionFloor">Floor and department</label><select id="provisionFloor">${floors}</select></div><div class="field"><label for="provisionHostname">Hostname</label><input id="provisionHostname" value="${escapeHtml(options.suggested_hostnames.workstation)}" data-ws-name="${escapeHtml(options.suggested_hostnames.workstation)}" data-ltp-name="${escapeHtml(options.suggested_hostnames.laptop)}" maxlength="12"></div><button class="action-button" type="button" data-draft-workstation>Review draft</button><div id="actionFeedback" class="action-feedback"></div></section>`;
  } catch (error) { showActionError(error); }
}

async function draftWorkstation() {
  const body = {device_type: document.getElementById("provisionDeviceType").value, floor: document.getElementById("provisionFloor").value, hostname: document.getElementById("provisionHostname").value};
  try {
    const draft = await api.draftWorkstation(body);
    document.getElementById("actionFeedback").innerHTML = `<div class="draft-review"><strong>${escapeHtml(draft.hostname)} · ${escapeHtml(draft.ip_address)}</strong><span>${escapeHtml(draft.floor)} · ${escapeHtml(draft.department)}</span><span>${escapeHtml(draft.switch)} · ${escapeHtml(draft.printer)}</span><p>Applying briefly redeploys the entire lab.</p><button class="action-button warning" type="button" data-apply-workstation="${draft.draft_id}">Apply lab change</button></div>`;
  } catch (error) { showActionError(error); }
}

async function openEmployeeWizard() {
  try {
    const options = await api.employeeOptions();
    state.selectedDevice = null;
    document.getElementById("deviceDrawer").classList.add("open");
    document.getElementById("deviceDrawer").setAttribute("aria-hidden", "false");
    document.getElementById("drawerBackdrop").hidden = false;
    const workstations = `<option value="">Unassigned — assign a device later</option>${options.workstations.map(item => `<option value="${item.hostname}">${item.hostname} · ${escapeHtml(item.floor)} · ${escapeHtml(item.department)}</option>`).join("")}`;
    document.getElementById("drawerContent").innerHTML = `<header class="drawer-header"><div><p>Active Directory</p><h2>Add employee</h2><p>Create an Employees-group account now and optionally assign an available device.</p></div></header><section class="drawer-section"><div class="field"><label for="newEmployeeWorkstation">Initial device assignment</label><select id="newEmployeeWorkstation">${workstations}</select></div><div class="field"><label for="employeeGivenName">First name</label><input id="employeeGivenName" maxlength="32"></div><div class="field"><label for="employeeSurname">Last name</label><input id="employeeSurname" maxlength="32"></div><div class="field"><label for="employeeRole">Job title</label><input id="employeeRole" maxlength="64"></div><div class="field"><label for="employeeUsername">Username</label><input id="employeeUsername" placeholder="first.last" maxlength="32"></div><button class="action-button" type="button" data-create-employee>Create employee</button><div id="actionFeedback" class="action-feedback"></div></section>`;
  } catch (error) { showActionError(error); }
}

async function createEmployee() {
  const selectedWorkstation = document.getElementById("newEmployeeWorkstation").value;
  const body = {workstation: selectedWorkstation || null, employee: {given_name: document.getElementById("employeeGivenName").value, surname: document.getElementById("employeeSurname").value, role: document.getElementById("employeeRole").value, username: document.getElementById("employeeUsername").value}};
  try {
    const result = await api.createEmployee(body);
    await loadDirectory();
    closeDrawer();
    renderPage();
    showToast(result.message);
    showToast(`Temporary password: ${result.temporary_password}`);
  } catch (error) { showActionError(error); }
}

async function openAssignmentWizard(username) {
  try {
    const options = await api.employeeOptions();
    const user = state.directory?.users.find(item => item.username === username);
    const devices = options.workstations.map(item => `<option value="${item.hostname}">${item.hostname} · ${escapeHtml(item.floor)} · ${escapeHtml(item.department)}</option>`).join("");
    document.getElementById("drawerContent").innerHTML = `<header class="drawer-header"><button class="drawer-back" type="button" data-return-ad-user="${escapeHtml(username)}">← Account details</button><div><p>Device assignment</p><h2>${escapeHtml(user?.display_name || username)}</h2><p>Selecting a device applies its floor and department security group.</p></div></header><section class="drawer-section"><div class="field"><label for="employeeAssignmentDevice">Available device</label><select id="employeeAssignmentDevice">${devices}</select></div><button class="action-button" type="button" data-assign-employee="${escapeHtml(username)}" ${devices ? "" : "disabled"}>Assign device</button>${devices ? "" : '<div class="diagnostic-result">No unassigned devices are available.</div>'}<div id="actionFeedback" class="action-feedback"></div></section>`;
  } catch (error) { showActionError(error); }
}

async function loadDirectory() {
  state.directoryLoading = true;
  try {
    state.directory = await api.directory();
  } catch (error) {
    state.directory = {status: "unavailable", error: error.message};
  } finally {
    state.directoryLoading = false;
  }
}

async function loadDirectoryHealth() {
  try {
    state.directoryHealth = await api.directoryAccountHealth();
  } catch (error) {
    state.directoryHealth = {status: "unavailable", error: error.message};
  }
}

function resource(value, maximum, level, suffix = "") {
  if (value === undefined) return "—";
  const width = Math.max(0, Math.min(100, value / maximum * 100));
  const tone = level === "empty" ? "empty" : ["notice", "low", "very low"].includes(level) ? "warning" : "";
  return `<div class="resource"><span>${value}${suffix}</span><span class="resource-track"><i class="resource-fill ${tone}" style="width:${width}%"></i></span></div>`;
}

function renderPlanned(page) {
  const plans = {
    tickets: ["◇", "Tickets", "Ticketing and ITSM workflows will connect real infrastructure events to support operations in a future phase."],
    automation: ["↻", "Automation", "Controlled remediation, health checks, and repeatable infrastructure tasks are planned for a future phase."]
  };
  const [icon, title, description] = plans[page];
  return `<section class="planned-page"><div class="planned-card"><div class="planned-icon">${icon}</div><h2>${title}</h2><p>${description}</p><span class="planned-label">Planned Phase</span></div></section>`;
}

function renderArchitecture() {
  return `${pageIntro("Current architecture", "How the browser reaches real containerized infrastructure while preserving a safe control boundary.")}
    <section class="panel"><div class="panel-header"><div><h3>Runtime and data flow</h3><p>Current local development architecture</p></div></div><div class="architecture-flow">
      ${architectureNode("Browser", "Vanilla frontend on macOS · port 8090")}${architectureNode("FastAPI", "Central API inside Lima · port 8000")}${architectureNode("Docker", "Container runtime inside the netlab VM")}${architectureNode("Containerlab", `${state.devices.length || 25}-device routed small-office topology`)}${architectureNode("Device services", "Live endpoint, Samba AD, and SMB file services")}
    </div></section>
    <section class="panel system-section"><div class="panel-header"><div><h3>Design principles</h3><p>Operational behavior over decorative simulation</p></div></div><div class="principles">
      <div class="principle"><strong>One safe backend</strong><span>The frontend uses structured API routes and never receives shell or Docker access.</span></div>
      <div class="principle"><strong>Two network contexts</strong><span>Office-network addressing remains distinct from Containerlab management connectivity.</span></div>
      <div class="principle"><strong>Live state</strong><span>Runtime status comes from containers and endpoint services; inventory contains configuration only.</span></div>
      <div class="principle"><strong>Controlled actions</strong><span>Printer, workstation, and ping operations are allowlisted and validated centrally.</span></div>
      <div class="principle"><strong>Portable endpoint images</strong><span>Local ARM64 images contain their application source without machine-specific bind paths.</span></div>
      <div class="principle"><strong>Incremental roadmap</strong><span>ITSM and broader automation remain clearly identified future phases.</span></div>
    </div></section>`;
}

function architectureNode(title, description) {
  return `<div class="architecture-node"><strong>${title}</strong><span>${description}</span></div>`;
}

function renderPage() {
  document.getElementById("pageTitle").textContent = pageTitles[state.page];
  const renderers = {dashboard: renderDashboard, network: renderNetwork, systems: renderSystems, "active-directory": renderActiveDirectory, monitoring: renderMonitoring, architecture: renderArchitecture};
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
  const commonFacts = fact("Office IP", device.ip_address || "No Layer 3 address") + fact("Network", device.network) + fact("Floor", device.floor) + fact("Department", device.department) + fact("Connected to", device.connected_switch) + fact("Reachable", device.reachable ? "Yes" : "No") + fact("Service health", device.service_health) + fact("Status source", device.status_source);
  let specific = "";
  if (device.device_type === "printer") {
    const sources = state.devices.filter(item => item.device_type === "workstation" && item.assigned_printer === device.hostname);
    specific = `${device.status === "attention" ? `<section class="drawer-section"><div class="active-fault"><strong>Printing unavailable</strong><span>${escapeHtml(live.message || "Printer requires attention.")}</span></div></section>` : ""}<section class="drawer-section"><h3>Printer resources</h3><div class="facts">${fact("Paper", live.paper !== undefined ? `${live.paper} / ${live.paper_capacity} sheets` : null)}${fact("Paper level", live.paper_level)}${fact("Toner", live.toner !== undefined ? `${live.toner}%` : null)}${fact("Toner level", live.toner_level)}${fact("Queue", live.queue !== undefined ? `${live.queue} jobs` : null)}</div></section>
      <section class="drawer-section"><h3>Print queue</h3><div class="job-list">${live.jobs?.length ? live.jobs.map(job => `<div class="job"><strong>#${job.id}</strong><span>${escapeHtml(job.device)} · ${job.pages} pages</span>${badge(job.status)}</div>`).join("") : `<div class="event-box">No jobs queued.</div>`}</div></section>
      ${live.last_event ? `<section class="drawer-section"><h3>Latest event</h3><div class="event-box">${escapeHtml(live.last_event)}</div></section>` : ""}
      <section class="drawer-section"><h3>Submit print job</h3><div class="field"><label for="printSource">Source workstation</label><select id="printSource">${sources.map(source => `<option value="${source.hostname}">${source.hostname}</option>`).join("")}</select></div><div class="field"><label for="printPages">Pages (blank = random 1–15)</label><input id="printPages" type="number" min="1" max="15" placeholder="Random"></div><button class="action-button" data-print="${device.hostname}" type="button">Add print job</button></section>
      <section class="drawer-section"><h3>Safe actions</h3><div class="action-grid"><button class="action-button danger" data-printer-action="offline">Set Offline</button><button class="action-button" data-printer-action="ready">Set Ready</button><button class="action-button warning" data-printer-action="empty-paper">Empty Paper</button><button class="action-button secondary" data-printer-action="refill-paper">Refill Paper</button><button class="action-button warning" data-printer-action="empty-toner">Empty Toner</button><button class="action-button secondary" data-printer-action="refill-toner">Refill Toner</button><button class="action-button secondary" data-printer-action="complete" ${live.jobs?.length ? "" : "disabled"}>Complete / Retry Job</button></div><div id="actionFeedback" class="action-feedback"></div></section>
      ${device.host_port ? `<section class="drawer-section"><a class="action-button secondary" href="http://127.0.0.1:${device.host_port}" target="_blank" rel="noopener">Open direct test page ↗</a></section>` : ""}`;
  } else if (device.device_type === "workstation") {
    specific = `<section class="drawer-section"><h3>Workstation details</h3><div class="facts">${fact("Device type", device.form_factor === "laptop" ? "Laptop" : "Workstation")}${fact("Assigned employee", device.assigned_user || "Unassigned")}${fact("Default printer", device.assigned_printer)}${fact("Interface", live.interface ? `${live.interface} · ${live.interface_state}` : null)}${fact("MAC address", live.mac_address)}${fact("Uptime", live.uptime_seconds !== undefined ? `${Math.floor(live.uptime_seconds / 3600)}h ${Math.floor(live.uptime_seconds % 3600 / 60)}m` : null)}</div></section>
      ${live.last_event ? `<section class="drawer-section"><h3>Latest event</h3><div class="event-box">${escapeHtml(live.last_event)}</div></section>` : ""}
      <section class="drawer-section"><h3>Safe actions</h3><div class="action-grid"><button class="action-button danger" data-workstation-action="offline">Set Offline</button><button class="action-button" data-workstation-action="online">Set Online</button>${device.dynamic ? `<button class="action-button danger" data-remove-device="${device.hostname}" ${device.assigned_user ? "disabled" : ""}>Remove device</button>` : ""}</div>${device.dynamic && device.assigned_user ? `<div class="event-box warning">Unassign ${escapeHtml(device.assigned_user)} in Active Directory before removing this device.</div>` : device.dynamic ? `<div class="event-box warning">Removing this device redeploys the lab.</div>` : `<div class="event-box">Baseline devices are protected from removal.</div>`}<div id="actionFeedback" class="action-feedback"></div></section>`;
  } else if (device.device_type === "file_server") {
    const users = state.devices.filter(item => item.device_type === "workstation" && item.assigned_user).map(item => `<option value="${item.assigned_user}|${item.hostname}">${escapeHtml(item.assigned_user)} · ${item.hostname}</option>`).join("");
    const recoveryItems = [];
    if (live.status === "offline") recoveryItems.push(`<div class="remediation-item"><div><strong>FILE01 is offline</strong><small>The office-facing interface is unavailable.</small></div><button class="action-button" type="button" data-file-remediation="online">Bring FILE01 Online</button></div>`);
    if (live.status === "online" && !live.smb_running) recoveryItems.push(`<div class="remediation-item"><div><strong>File service stopped</strong><small>FILE01 is online, but SMB and its shares are unavailable.</small></div><button class="action-button" type="button" data-file-remediation="restart-service">Restart File Service</button></div>`);
    const recoverySection = recoveryItems.length ? `<section class="drawer-section"><h3>Recommended recovery</h3><div class="remediation-list">${recoveryItems.join("")}</div></section>` : "";
    const faultControls = live.status === "online" ? `<section class="drawer-section"><h3>Controlled service state</h3><div class="action-grid"><button class="action-button danger" type="button" data-file-fault="offline">Set FILE01 Offline</button>${live.smb_running ? '<button class="action-button warning" type="button" data-file-fault="service-stop">Stop File Service</button>' : ""}</div></section>` : "";
    specific = `${recoverySection}<section class="drawer-section"><h3>File services</h3><div class="facts">${fact("Server", live.status === "online" ? "Online" : "Offline")}${fact("File service", live.smb_running ? "Running" : "Down")}${fact("Shares", live.share_count)}${fact("Latest event", live.last_event)}</div><div class="share-list">${(live.shares || []).map(share => `<div class="share-row"><span><strong>${escapeHtml(share.name)}</strong><small>Expected: Read ${escapeHtml(share.read_groups.join(", "))} · Write ${escapeHtml(share.write_groups.join(", "))}</small><small>${share.effective_user_count ?? "View"} effective users</small></span><div class="share-actions">${badge(!share.enabled ? "disabled" : share.read_only ? "read only" : "available")}${!share.enabled ? `<button class="action-button" type="button" data-file-share-remediation="enable" data-share="${escapeHtml(share.name)}">Enable Share</button>` : `<button class="action-button warning" type="button" data-file-share-fault="share-disable" data-share="${escapeHtml(share.name)}">Disable Share</button>`}${share.read_only ? `<button class="action-button" type="button" data-file-share-remediation="restore-write" data-share="${escapeHtml(share.name)}">Restore Write Access</button>` : ""}<button class="action-button secondary" type="button" data-manage-share="${escapeHtml(share.name)}">Manage Access</button></div></div>`).join("")}</div></section>${faultControls}<section class="drawer-section"><h3>Controlled access check</h3><div class="field"><label for="fileAccessIdentity">User and assigned device</label><select id="fileAccessIdentity">${users}</select></div><div class="field"><label for="fileAccessShare">Share</label><select id="fileAccessShare">${(live.shares || []).map(share => `<option value="${escapeHtml(share.name)}">${escapeHtml(share.name)}</option>`).join("")}</select></div><div class="field"><label for="fileAccessOperation">Operation</label><select id="fileAccessOperation"><option value="read">Read</option><option value="write">Write</option></select></div><button class="action-button" type="button" data-file-access-check>Check access</button><div id="actionFeedback" class="action-feedback"></div><div class="event-box">Access decisions use live DC01 group membership. Failed checks identify the constrained recovery path.</div></section>`;
  } else {
    const interfaces = Object.entries(live.interfaces || {}).map(([name, status]) => `${name}: ${status}`).join(", ");
    specific = `<section class="drawer-section"><h3>Infrastructure state</h3><div class="facts">${fact("Interfaces", interfaces)}${fact("Dependency status", device.dependency_status)}${fact("Impacted by", device.impacted_by?.join(", "))}</div>${device.impact_reason ? `<div class="event-box warning">${escapeHtml(device.impact_reason)}</div>` : ""}</section><section class="drawer-section"><h3>Safe actions</h3><div class="action-grid"><button class="action-button danger" data-infrastructure-action="disable" type="button">Disable network function</button><button class="action-button" data-infrastructure-action="restore" type="button">Restore network function</button></div><div id="actionFeedback" class="action-feedback"></div></section>`;
  }
  const displayStatus = device.dependency_status === "impacted" ? "impacted" : device.status;
  const returnLabels = {"printer-alerts": "printer alerts", "service-alerts": "service attention", "impacted-devices": "impacted devices", "online-devices": "online devices", "offline-devices": "offline devices"};
  const back = state.drawerReturn ? `<button class="drawer-back" type="button" data-drawer-back="${state.drawerReturn}">← Back to ${returnLabels[state.drawerReturn] || "dashboard alerts"}</button>` : "";
  document.getElementById("drawerContent").innerHTML = `${back}<header class="drawer-header"><div class="drawer-header-row"><div><h2>${device.hostname}</h2><p>${escapeHtml(typeLabels[device.device_type])}</p></div>${badge(displayStatus)}</div></header>${device.impact_reason ? `<section class="drawer-section"><div class="active-fault dependency"><strong>Connectivity impacted</strong><span>${escapeHtml(device.impact_reason)}</span></div></section>` : ""}<section class="drawer-section"><h3>Identity and connectivity</h3><div class="facts">${commonFacts}</div></section><section class="drawer-section"><h3>Network troubleshooting</h3><button class="action-button secondary" data-network-info="${device.hostname}" type="button">View routes and neighbors</button><div id="networkInfoResult"></div></section>${specific}`;
}

async function openDrawer(hostname, returnTo = null) {
  state.selectedDevice = hostname;
  state.selectedDirectoryUser = null;
  state.fileAccessShare = null;
  state.drawerReturn = returnTo;
  document.getElementById("deviceDrawer").classList.add("open");
  document.getElementById("deviceDrawer").setAttribute("aria-hidden", "false");
  document.getElementById("drawerBackdrop").hidden = false;
  if (hostname === "FILE01") {
    try {
      const detail = await api.fileserver();
      const file01 = state.devices.find(item => item.hostname === "FILE01");
      if (file01) file01.live = detail;
    } catch (error) { showToast(error.message, "error"); }
  }
  renderDrawer();
  if (state.page === "network") renderPage();
}

function closeDrawer() {
  state.selectedDevice = null;
  state.selectedDirectoryUser = null;
  state.fileAccessShare = null;
  state.drawerReturn = null;
  document.getElementById("deviceDrawer").classList.remove("open");
  document.getElementById("deviceDrawer").setAttribute("aria-hidden", "true");
  document.getElementById("drawerBackdrop").hidden = true;
}

function openImpactedDevices() {
  const impacted = state.overview?.impacted_device_alerts || [];
  state.selectedDevice = null;
  state.drawerReturn = null;
  document.getElementById("deviceDrawer").classList.add("open");
  document.getElementById("deviceDrawer").setAttribute("aria-hidden", "false");
  document.getElementById("drawerBackdrop").hidden = false;
  document.getElementById("drawerContent").innerHTML = `<header class="drawer-header"><h2>Impacted devices</h2><p>Devices that are offline, unavailable, or affected by an upstream fault</p></header><section class="drawer-section"><div class="impact-list">${impacted.length ? impacted.map(alert => { const device = state.devices.find(item => item.hostname === alert.hostname); return `<button type="button" class="impact-row" data-device="${alert.hostname}" data-return-list="impacted-devices"><span><strong>${alert.hostname}</strong><small>${escapeHtml(typeLabels[device?.device_type] || "Device")}</small></span><span>${escapeHtml(alert.reason)}</span><b>Details →</b></button>`; }).join("") : `<div class="event-box">No devices are currently impacted.</div>`}</div></section>`;
}

function openDeviceStatusList(mode) {
  const isOnline = mode === "online";
  const devices = state.devices.filter(device => {
    const unavailable = ["offline", "unavailable"].includes(device.status) || device.dependency_status === "impacted";
    return isOnline ? !unavailable : unavailable;
  });
  const returnList = `${mode}-devices`;
  state.selectedDevice = null;
  state.drawerReturn = null;
  document.getElementById("deviceDrawer").classList.add("open");
  document.getElementById("deviceDrawer").setAttribute("aria-hidden", "false");
  document.getElementById("drawerBackdrop").hidden = false;
  const rows = devices.map(device => {
    const reason = isOnline
      ? `${typeLabels[device.device_type] || "Device"} · ${device.ip_address || "Layer 2"}`
      : device.impact_reason || device.live?.message || device.service_error || `${device.hostname} is ${device.status}.`;
    return `<button type="button" class="impact-row" data-device="${device.hostname}" data-return-list="${returnList}"><span><strong>${device.hostname}</strong><small>${escapeHtml(typeLabels[device.device_type] || "Device")}</small></span><span>${escapeHtml(reason)}</span><b>Details →</b></button>`;
  }).join("");
  document.getElementById("drawerContent").innerHTML = `<header class="drawer-header"><h2>${isOnline ? "Online devices" : "Offline devices"}</h2><p>${isOnline ? "Devices currently available in the office environment" : "Unavailable devices and their immediate observed problem"}</p></header><section class="drawer-section"><div class="impact-list">${rows || `<div class="event-box">No devices are currently ${mode}.</div>`}</div></section>`;
}

function openPrinterAlerts() {
  const alerts = state.overview?.printer_alerts || [];
  state.selectedDevice = null;
  state.drawerReturn = null;
  document.getElementById("deviceDrawer").classList.add("open");
  document.getElementById("deviceDrawer").setAttribute("aria-hidden", "false");
  document.getElementById("drawerBackdrop").hidden = false;
  document.getElementById("drawerContent").innerHTML = `<header class="drawer-header"><h2>Printer attention</h2><p>Active printing faults requiring recovery</p></header><section class="drawer-section"><div class="impact-list">${alerts.length ? alerts.map(alert => `<button type="button" class="impact-row" data-device="${alert.hostname}" data-return-list="printer-alerts"><span><strong>${alert.hostname}</strong><small>Network Printer</small></span><span>${escapeHtml(alert.reason)}</span><b>Details →</b></button>`).join("") : `<div class="event-box">No printers currently require attention.</div>`}</div></section>`;
}

function openServiceAlerts() {
  const alerts = state.overview?.file_service_alerts || [];
  state.selectedDevice = null;
  state.drawerReturn = null;
  document.getElementById("deviceDrawer").classList.add("open");
  document.getElementById("deviceDrawer").setAttribute("aria-hidden", "false");
  document.getElementById("drawerBackdrop").hidden = false;
  document.getElementById("drawerContent").innerHTML = `<header class="drawer-header"><h2>Service attention</h2><p>Server services requiring review or recovery</p></header><section class="drawer-section"><div class="impact-list">${alerts.length ? alerts.map(alert => `<button type="button" class="impact-row" data-device="${escapeHtml(alert.hostname)}" data-return-list="service-alerts"><span><strong>${escapeHtml(alert.hostname)}</strong><small>Infrastructure Service</small></span><span>${escapeHtml(alert.reason)}</span><b>Details →</b></button>`).join("") : `<div class="event-box">No server services currently require attention.</div>`}</div></section>`;
}

function openAccountAlerts() {
  const accounts = state.directoryHealth?.affected_users || [];
  state.selectedDevice = null;
  state.selectedDirectoryUser = null;
  state.drawerReturn = null;
  document.getElementById("deviceDrawer").classList.add("open");
  document.getElementById("deviceDrawer").setAttribute("aria-hidden", "false");
  document.getElementById("drawerBackdrop").hidden = false;
  const unavailable = state.directoryHealth?.status === "unavailable";
  document.getElementById("drawerContent").innerHTML = `<header class="drawer-header"><h2>Account health</h2><p>Live Active Directory accounts requiring review</p></header><section class="drawer-section"><div class="impact-list">${unavailable ? '<div class="event-box warning">DC01 account health is currently unavailable.</div>' : accounts.length ? accounts.map(user => `<button type="button" class="impact-row" data-dashboard-ad-user="${escapeHtml(user.username)}"><span><strong>${escapeHtml(user.display_name)}</strong><small>${escapeHtml(user.username)}</small></span><span>${escapeHtml(user.issues.join(" · "))}</span><b>Details →</b></button>`).join("") : '<div class="event-box">No accounts currently require attention.</div>'}</div></section>`;
}

async function openDashboardDirectoryUser(username) {
  const healthEntry = state.directoryHealth?.affected_users?.find(user => user.username === username);
  state.page = "active-directory";
  state.directoryView = healthEntry?.issues.includes("Disabled") ? "disabled" : "users";
  document.querySelectorAll(".nav-item").forEach(item => item.classList.toggle("active", item.dataset.page === "active-directory"));
  closeDrawer();
  renderPage();
  await loadDirectory();
  renderPage();
  openDirectoryUser(username);
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
    const overview = await api.overview();
    state.overview = overview;
    state.devices = overview.devices;
    if (overview.account_health) state.directoryHealth = overview.account_health;
    state.loading = false;
    setBackendState(true);
    document.getElementById("lastUpdated").textContent = `Updated ${new Date().toLocaleTimeString([], {hour:"2-digit", minute:"2-digit", second:"2-digit"})}`;
    const preserveInteractivePage = !force && (
      (state.page === "network" && state.diagnosticsActive) || state.page === "active-directory"
    );
    if (!preserveInteractivePage) {
      renderPage();
      if (state.selectedDevice && !state.fileAccessShare) renderDrawer();
    }
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

async function performDirectoryAction(callback, successMessage, username, button = null) {
  const drawer = document.getElementById("deviceDrawer");
  const scrollPosition = drawer.scrollTop;
  const originalLabel = button?.textContent;
  try {
    if (button) {
      button.disabled = true;
      button.textContent = "Applying…";
    }
    await callback();
    await loadDirectory();
    showToast(successMessage);
    renderPage();
    openDirectoryUser(username);
    drawer.scrollTop = scrollPosition;
    const feedback = document.getElementById("actionFeedback");
    if (feedback) feedback.innerHTML = `<div class="diagnostic-result success"><strong>Account updated</strong><span>${escapeHtml(successMessage)}</span></div>`;
  } catch (error) {
    if (button) {
      button.disabled = false;
      button.textContent = originalLabel;
    }
    showActionError(error instanceof ApiError ? error : new ApiError("The directory action failed."));
  }
}

document.addEventListener("click", async event => {
  const dashboardAdUser = event.target.closest("[data-dashboard-ad-user]");
  if (dashboardAdUser) return openDashboardDirectoryUser(dashboardAdUser.dataset.dashboardAdUser);
  const fileFault = event.target.closest("[data-file-fault]");
  if (fileFault) {
    fileFault.disabled = true;
    fileFault.textContent = "Applying…";
    try {
      const result = await api.fileServerFault(fileFault.dataset.fileFault);
      await loadData(true);
      showToast(result.last_event);
      return openDrawer("FILE01");
    } catch (error) { showActionError(error); }
    return;
  }
  const shareFault = event.target.closest("[data-file-share-fault]");
  if (shareFault) {
    shareFault.disabled = true;
    shareFault.textContent = "Applying…";
    try {
      const result = await api.fileShareFault(shareFault.dataset.share, shareFault.dataset.fileShareFault);
      await loadData(true);
      showToast(result.last_event);
      return openDrawer("FILE01");
    } catch (error) { showActionError(error); }
    return;
  }
  const fileRemediation = event.target.closest("[data-file-remediation]");
  if (fileRemediation) {
    fileRemediation.disabled = true;
    fileRemediation.textContent = "Recovering…";
    try {
      const result = await api.fileServerRemediation(fileRemediation.dataset.fileRemediation);
      await loadData(true);
      showToast(result.message);
      return openDrawer("FILE01");
    } catch (error) { showActionError(error); }
    return;
  }
  const shareRemediation = event.target.closest("[data-file-share-remediation]");
  if (shareRemediation) {
    shareRemediation.disabled = true;
    shareRemediation.textContent = "Recovering…";
    try {
      const result = await api.fileShareRemediation(shareRemediation.dataset.share, shareRemediation.dataset.fileShareRemediation);
      await loadData(true);
      showToast(result.message);
      return openDrawer("FILE01");
    } catch (error) { showActionError(error); }
    return;
  }
  const manageShare = event.target.closest("[data-manage-share]");
  if (manageShare) return openManageFileAccess(manageShare.dataset.manageShare);
  if (event.target.closest("[data-file-access-back]")) return openDrawer("FILE01");
  const fileMembership = event.target.closest("[data-file-membership]");
  if (fileMembership) {
    fileMembership.disabled = true;
    try {
      await api.fileShareMembership(fileMembership.dataset.share, {
        username: fileMembership.dataset.username,
        group: fileMembership.dataset.group,
        action: fileMembership.dataset.fileMembership
      });
      await Promise.all([loadDirectory(), loadData(true)]);
      showToast(`${fileMembership.dataset.username} ${fileMembership.dataset.fileMembership === "add" ? "added to" : "removed from"} ${fileMembership.dataset.group}.`);
      if (fileMembership.dataset.returnUser) return openDirectoryUser(fileMembership.dataset.returnUser);
      return openManageFileAccess(fileMembership.dataset.share);
    } catch (error) { showActionError(error); }
    return;
  }
  if (event.target.closest("[data-add-workstation]")) return openWorkstationWizard();
  if (event.target.closest("[data-draft-workstation]")) return draftWorkstation();
  if (event.target.closest("[data-add-employee]")) return openEmployeeWizard();
  if (event.target.closest("[data-create-employee]")) return createEmployee();
  const returnDirectoryUser = event.target.closest("[data-return-ad-user]");
  if (returnDirectoryUser) return openDirectoryUser(returnDirectoryUser.dataset.returnAdUser);
  const openAssignment = event.target.closest("[data-open-assignment]");
  if (openAssignment) return openAssignmentWizard(openAssignment.dataset.openAssignment);
  const assignEmployee = event.target.closest("[data-assign-employee]");
  if (assignEmployee) {
    const username = assignEmployee.dataset.assignEmployee;
    const workstation = document.getElementById("employeeAssignmentDevice").value;
    try {
      const result = await api.assignEmployee(username, workstation);
      await Promise.all([loadDirectory(), loadData(true)]);
      showToast(result.message);
      renderPage();
      openDirectoryUser(username);
    } catch (error) { showActionError(error); }
    return;
  }
  const unassignEmployee = event.target.closest("[data-unassign-employee]");
  if (unassignEmployee) {
    const username = unassignEmployee.dataset.unassignEmployee;
    if (!window.confirm("Unassign this employee from their device? The directory account will remain enabled.")) return;
    try {
      const result = await api.unassignEmployee(username);
      await Promise.all([loadDirectory(), loadData(true)]);
      showToast(result.message);
      renderPage();
      openDirectoryUser(username);
    } catch (error) { showActionError(error); }
    return;
  }
  const removeDevice = event.target.closest("[data-remove-device]");
  if (removeDevice) {
    const hostname = removeDevice.dataset.removeDevice;
    if (!window.confirm(`Remove ${hostname}? This will redeploy the Containerlab topology.`)) return;
    removeDevice.disabled = true;
    removeDevice.textContent = "Removing and redeploying…";
    try {
      const result = await api.removeDevice(hostname);
      closeDrawer();
      await loadData(true);
      showToast(result.message);
    } catch (error) { showActionError(error); }
    return;
  }
  const applyWorkstation = event.target.closest("[data-apply-workstation]");
  if (applyWorkstation) {
    applyWorkstation.disabled = true;
    applyWorkstation.textContent = "Redeploying lab…";
    try {
      const result = await api.applyWorkstation(applyWorkstation.dataset.applyWorkstation);
      closeDrawer();
      showToast(result.message);
      if (result.temporary_password) showToast(`Temporary password: ${result.temporary_password}`);
      await loadData(true);
    } catch (error) { showActionError(error); }
    return;
  }
  const pageLink = event.target.closest("[data-page-link]");
  if (pageLink) {
    state.page = pageLink.dataset.pageLink;
    document.querySelectorAll(".nav-item").forEach(item => item.classList.toggle("active", item.dataset.page === state.page));
    renderPage();
    content.focus();
    return;
  }
  const alertDevice = event.target.closest("[data-alert-device]");
  if (alertDevice) return openDrawer(alertDevice.dataset.alertDevice);
  const alertUser = event.target.closest("[data-alert-user]");
  if (alertUser) return openDashboardDirectoryUser(alertUser.dataset.alertUser);
  const nav = event.target.closest("[data-page]");
  if (nav) {
    state.page = nav.dataset.page;
    document.querySelectorAll(".nav-item").forEach(item => item.classList.toggle("active", item === nav));
    document.querySelector(".sidebar").classList.remove("open");
    renderPage();
    if (state.page === "active-directory") {
      await loadDirectory();
      renderPage();
    }
    content.focus();
    return;
  }
  const adUser = event.target.closest("[data-ad-user]");
  if (adUser && !adUser.dataset.adAction && !adUser.dataset.adMembership) {
    openDirectoryUser(adUser.dataset.adUser);
    return;
  }
  const directoryView = event.target.closest("[data-directory-view]");
  if (directoryView) {
    state.directoryView = directoryView.dataset.directoryView;
    renderPage();
    return;
  }
  const adGroup = event.target.closest("[data-directory-group]");
  if (adGroup) {
    openDirectoryGroup(adGroup.dataset.directoryGroup);
    return;
  }
  if (event.target.dataset.adAction) {
    const username = event.target.dataset.adUser;
    return performDirectoryAction(
      () => api.directoryUserAction(username, event.target.dataset.adAction),
      `${username}: account updated.`, username,
      event.target,
    );
  }
  if (event.target.dataset.adReset) {
    const username = event.target.dataset.adReset;
    const button = event.target;
    const originalLabel = button.textContent;
    try {
      button.disabled = true;
      button.textContent = "Resetting…";
      const result = await api.resetDirectoryPassword(username);
      await loadDirectory();
      renderPage();
      openDirectoryUser(username);
      document.getElementById("deviceDrawer").scrollTop = 0;
      document.getElementById("actionFeedback").innerHTML = `<div class="diagnostic-result success temporary-password-result"><strong>Password reset complete</strong><span>Copy this temporary password now. It will not be shown again.</span><pre>${escapeHtml(result.temporary_password)}</pre><span>${escapeHtml(result.message)}</span></div>`;
    } catch (error) {
      button.disabled = false;
      button.textContent = originalLabel;
      showActionError(error);
    }
    return;
  }
  if (event.target.dataset.adMembership) {
    const username = event.target.dataset.adUser;
    const group = document.getElementById("adGroup").value;
    return performDirectoryAction(
      () => api.directoryMembership(group, username, event.target.dataset.adMembership),
      `${username}: ${group} membership updated.`, username,
      event.target,
    );
  }
  const dashboardAction = event.target.closest("[data-dashboard-action]");
  if (dashboardAction?.dataset.dashboardAction === "printer-alerts") {
    openPrinterAlerts();
    return;
  }
  if (dashboardAction?.dataset.dashboardAction === "online-devices") {
    openDeviceStatusList("online");
    return;
  }
  if (dashboardAction?.dataset.dashboardAction === "offline-devices") {
    openDeviceStatusList("offline");
    return;
  }
  if (dashboardAction?.dataset.dashboardAction === "impacted-devices") {
    openImpactedDevices();
    return;
  }
  if (dashboardAction?.dataset.dashboardAction === "service-alerts") {
    openServiceAlerts();
    return;
  }
  if (dashboardAction?.dataset.dashboardAction === "account-alerts") {
    openAccountAlerts();
    return;
  }
  const drawerBack = event.target.closest("[data-drawer-back]");
  if (drawerBack) {
    if (drawerBack.dataset.drawerBack === "printer-alerts") openPrinterAlerts();
    else if (drawerBack.dataset.drawerBack === "service-alerts") openServiceAlerts();
    else if (drawerBack.dataset.drawerBack === "online-devices") openDeviceStatusList("online");
    else if (drawerBack.dataset.drawerBack === "offline-devices") openDeviceStatusList("offline");
    else openImpactedDevices();
    return;
  }
  const device = event.target.closest("[data-device]");
  if (device) return openDrawer(device.dataset.device, device.dataset.returnList || null);
  if (event.target.id === "runPing") {
    const source = document.getElementById("pingSource").value;
    const destination = document.getElementById("pingDestination").value;
    state.pingSource = source;
    state.pingDestination = destination;
    try {
      state.pingResult = await api.diagnostic(state.diagnosticType, source, destination);
    } catch (error) {
      state.pingResult = {diagnostic_type: state.diagnosticType, source, destination, success: false, message: error.message};
    }
    return renderPage();
  }
  if (event.target.dataset.networkInfo) {
    try {
      const result = await api.networkInfo(event.target.dataset.networkInfo);
      document.getElementById("networkInfoResult").innerHTML = `<div class="diagnostic-result"><strong>Routes</strong><pre>${escapeHtml(result.routes.join("\n") || "No routes")}</pre><strong>ARP / neighbors</strong><pre>${escapeHtml(result.neighbors.join("\n") || "No learned neighbors")}</pre></div>`;
    } catch (error) {
      showActionError(error);
    }
    return;
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
  if (event.target.closest("[data-file-access-check]")) {
    const [username, device] = document.getElementById("fileAccessIdentity").value.split("|");
    const share = document.getElementById("fileAccessShare").value;
    const operation = document.getElementById("fileAccessOperation").value;
    try {
      const result = await api.fileAccessCheck({username, device, share, operation});
      const membershipRecovery = !result.allowed && result.reason.startsWith("Access requires membership")
        ? `<div class="access-guidance"><strong>Suggested action</strong><span>Restore access through a configured AD security group.</span><button class="action-button secondary" type="button" data-manage-share="${escapeHtml(result.share)}">Manage ${escapeHtml(result.share)} Access</button></div>`
        : "";
      document.getElementById("actionFeedback").innerHTML = `<div class="diagnostic-result ${result.allowed ? "success" : "error"}"><strong>${result.allowed ? "ACCESS GRANTED" : "ACCESS DENIED"}</strong><span>${escapeHtml(result.display_name)} · ${escapeHtml(result.device)} · ${escapeHtml(result.operation)} ${escapeHtml(result.share)}</span><span>${escapeHtml(result.reason)}</span>${membershipRecovery}</div>`;
    } catch (error) { showActionError(error); }
    return;
  }
});

document.addEventListener("change", event => {
  if (event.target.id === "adGroup") {
    updateDirectoryGroupAction();
    return;
  }
  if (["diagnosticType", "pingSource", "pingDestination"].includes(event.target.id)) {
    state.pingResult = null;
    document.querySelector(".terminal-result")?.remove();
  }
  if (event.target.id === "diagnosticType") {
    state.diagnosticType = event.target.value;
    const help = document.querySelector(".diagnostic-help");
    if (help) help.textContent = diagnosticHelp[state.diagnosticType];
  }
  if (event.target.id === "pingSource") state.pingSource = event.target.value;
  if (event.target.id === "pingDestination") state.pingDestination = event.target.value;
  if (event.target.id === "provisionDeviceType") {
    const hostname = document.getElementById("provisionHostname");
    hostname.value = event.target.value === "laptop" ? hostname.dataset.ltpName : hostname.dataset.wsName;
  }
});

document.addEventListener("pointerdown", event => {
  state.diagnosticsActive = Boolean(event.target.closest(".diagnostic-panel"));
});

document.addEventListener("focusin", event => {
  if (event.target.closest(".diagnostic-panel")) state.diagnosticsActive = true;
});

document.addEventListener("focusout", event => {
  if (!event.target.closest(".diagnostic-panel")) return;
  setTimeout(() => {
    const stillInsideDiagnostics = document.activeElement?.closest?.(".diagnostic-panel");
    if (stillInsideDiagnostics) return;
    state.diagnosticsActive = false;
    if (state.page === "network" && state.connected) renderPage();
  }, 100);
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
