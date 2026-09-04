const devices = [
  {name:"RTR01", type:"router_firewall", ip:"10.10.254.1", network:"Core transit", connected:"CORE01"},
  {name:"CORE01", type:"layer3_core_switch", ip:"10.10.254.2", network:"Core + access gateways", connected:"RTR01", interfaces:"10.10.254.2, 10.10.10.1, 10.10.20.1, 10.10.30.1"},
  {name:"SW01", type:"access_switch", ip:"Layer 2", network:"10.10.10.0/24", connected:"CORE01"},
  {name:"SW02", type:"access_switch", ip:"Layer 2", network:"10.10.20.0/24", connected:"CORE01"},
  {name:"SW03", type:"access_switch", ip:"Layer 2", network:"10.10.30.0/24", connected:"CORE01"},
  {name:"WS01", type:"workstation", ip:"10.10.10.11", network:"10.10.10.0/24", connected:"SW01", printer:"PRNT01", api:"http://127.0.0.1:8081/status", page:"http://127.0.0.1:8081"},
  {name:"WS02", type:"workstation", ip:"10.10.10.12", network:"10.10.10.0/24", connected:"SW01", printer:"PRNT01"},
  {name:"WS03", type:"workstation", ip:"10.10.10.13", network:"10.10.10.0/24", connected:"SW01", printer:"PRNT01"},
  {name:"WS04", type:"workstation", ip:"10.10.20.11", network:"10.10.20.0/24", connected:"SW02", printer:"PRNT02"},
  {name:"WS05", type:"workstation", ip:"10.10.20.12", network:"10.10.20.0/24", connected:"SW02", printer:"PRNT02"},
  {name:"WS06", type:"workstation", ip:"10.10.20.13", network:"10.10.20.0/24", connected:"SW02", printer:"PRNT02"},
  {name:"WS07", type:"workstation", ip:"10.10.30.11", network:"10.10.30.0/24", connected:"SW03", printer:"PRNT03"},
  {name:"WS08", type:"workstation", ip:"10.10.30.12", network:"10.10.30.0/24", connected:"SW03", printer:"PRNT03"},
  {name:"WS09", type:"workstation", ip:"10.10.30.13", network:"10.10.30.0/24", connected:"SW03", printer:"PRNT03"},
  {name:"PRNT01", type:"printer", ip:"10.10.10.21", network:"10.10.10.0/24", connected:"SW01", api:"http://127.0.0.1:8080/status", page:"http://127.0.0.1:8080"},
  {name:"PRNT02", type:"printer", ip:"10.10.20.21", network:"10.10.20.0/24", connected:"SW02", api:"http://127.0.0.1:8082/status", page:"http://127.0.0.1:8082"},
  {name:"PRNT03", type:"printer", ip:"10.10.30.21", network:"10.10.30.0/24", connected:"SW03", api:"http://127.0.0.1:8083/status", page:"http://127.0.0.1:8083"}
];

const labels = {router_firewall:"Router / Firewall", layer3_core_switch:"Layer 3 Core", access_switch:"Access Switch", workstation:"Linux Workstation", printer:"Network Printer"};
const states = new Map();
let selectedName = null;

function classFor(device) {
  return device.type === "router_firewall" ? "router" : device.type === "layer3_core_switch" ? "core" : device.type.replace("access_", "");
}

function card(device) {
  const state = states.get(device.name)?.status || "configured";
  return `<button class="device ${classFor(device)} ${selectedName === device.name ? "selected" : ""}" data-device="${device.name}" onclick="selectDevice('${device.name}')">
    <div class="device-head"><span class="device-name">${device.name}</span><i class="device-state ${state}"></i></div>
    <div class="device-kind">${labels[device.type]}</div><div class="device-ip">${device.ip}</div>
  </button>`;
}

function renderTopology() {
  const groups = ["SW01", "SW02", "SW03"].map(switchName => {
    const networkDevices = devices.filter(d => d.connected === switchName && d.type !== "access_switch");
    return `<div class="access-group">${card(devices.find(d => d.name === switchName))}<h3>${networkDevices[0].network}</h3><div class="endpoint-grid">${networkDevices.map(card).join("")}</div></div>`;
  }).join("");
  document.getElementById("topology").innerHTML = `<div class="tier">${card(devices[0])}</div><div class="tier">${card(devices[1])}</div><div class="tier access-tier">${groups}</div>`;
}

function value(data, key, fallback="—") { return data && data[key] !== undefined && data[key] !== null ? data[key] : fallback; }
function fact(label, content) { return `<div class="fact"><span>${label}</span><strong>${content}</strong></div>`; }

function selectDevice(name) {
  selectedName = name;
  renderTopology();
  const device = devices.find(item => item.name === name);
  const live = states.get(name);
  const state = live?.status || "configured";
  const liveFacts = device.type === "printer" && live
    ? fact("Paper", `${live.paper} / ${live.paper_capacity} sheets`) + fact("Toner", `${live.toner}%`) + fact("Print queue", `${live.queue} jobs`)
    : device.type === "workstation" && live
      ? fact("Interface", `${live.interface} · ${live.interface_state}`) + fact("Uptime", `${Math.floor(live.uptime_seconds / 3600)}h ${Math.floor(live.uptime_seconds % 3600 / 60)}m`)
      : "";
  document.getElementById("inspector").innerHTML = `<div class="inspect-header"><div><h2>${device.name}</h2><div class="type-label">${labels[device.type]}</div></div><span class="status-pill ${state}">${state}</span></div>
    <div class="facts">${fact("IP address", device.ip)}${fact("Network", device.network)}${fact("Connected to", device.connected)}${device.printer ? fact("Assigned printer", device.printer) : ""}${liveFacts}${live?.message ? fact("Message", live.message) : ""}</div>
    <div class="live-note">${device.api ? (live ? "Status and operational statistics are being read from the device API." : "The device API could not be reached. Confirm the lab and local frontend server are running.") : "This node has no management API in the current phase. Identity and connection data come from the deployed topology plan."}</div>
    <div class="buttons"><button class="button" onclick="openDetails('${name}')">View full-screen details</button>${device.page ? `<a class="button secondary" href="${device.page}" target="_blank" rel="noopener">Open device management page ↗</a>` : ""}</div>`;
}

function openDetails(name) {
  const device = devices.find(item => item.name === name);
  const live = states.get(name);
  const state = live?.status || "configured";
  const stats = [
    ["Device type", labels[device.type]], ["Operational status", state], ["Office IP", device.ip],
    ["Network", device.network], ["Connected device", device.connected], ["Assigned printer", device.printer || "Not applicable"]
  ];
  if (device.type === "printer" && live) stats.push(["Paper", `${live.paper} / ${live.paper_capacity} sheets`], ["Toner", `${live.toner}%`], ["Queue", `${live.queue} jobs`]);
  if (device.type === "workstation" && live) stats.push(["Interface", `${live.interface} · ${live.interface_state}`], ["MAC address", live.mac_address], ["Uptime", `${Math.floor(live.uptime_seconds / 3600)} hours`]);
  document.getElementById("detailContent").innerHTML = `<div class="detail-title"><div><p class="eyebrow">DEVICE DETAILS</p><h2>${device.name}</h2><p class="subtitle">${labels[device.type]}</p></div><span class="status-pill ${state}">${state}</span></div><div class="detail-grid">${stats.map(([label, content]) => `<div class="detail-stat"><span>${label}</span><strong>${content}</strong></div>`).join("")}</div>${device.page ? `<div class="buttons"><a class="button" href="${device.page}" target="_blank" rel="noopener">Open full management interface ↗</a></div>` : ""}`;
  document.getElementById("detailView").classList.add("open");
  document.getElementById("detailView").setAttribute("aria-hidden", "false");
}

function closeDetails() {
  document.getElementById("detailView").classList.remove("open");
  document.getElementById("detailView").setAttribute("aria-hidden", "true");
}

async function refreshLiveData() {
  await Promise.all(devices.filter(d => d.api).map(async device => {
    try {
      const response = await fetch(device.api);
      if (!response.ok) throw new Error("unavailable");
      states.set(device.name, await response.json());
    } catch (error) {
      states.set(device.name, {status:"unreachable"});
    }
  }));
  renderTopology();
  if (selectedName) selectDevice(selectedName);
}

document.addEventListener("keydown", event => { if (event.key === "Escape") closeDetails(); });
renderTopology();
refreshLiveData();
setInterval(refreshLiveData, 5000);
