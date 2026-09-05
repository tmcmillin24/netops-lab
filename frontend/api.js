export const API_BASE = "http://127.0.0.1:8000";

export class ApiError extends Error {
  constructor(message, options = {}) {
    super(message);
    this.name = "ApiError";
    this.code = options.code || "request_failed";
    this.status = options.status || 0;
    this.details = options.details || null;
  }
}

async function request(path, options = {}) {
  const config = {
    method: options.method || "GET",
    headers: {"Content-Type": "application/json"}
  };
  if (options.body !== undefined) config.body = JSON.stringify(options.body);

  let response;
  try {
    response = await fetch(`${API_BASE}${path}`, config);
  } catch (error) {
    throw new ApiError("Backend unavailable", {code: "backend_unavailable", details: error.message});
  }

  let payload;
  try {
    payload = await response.json();
  } catch (error) {
    throw new ApiError("The backend returned an unreadable response.", {code: "invalid_response", status: response.status});
  }

  if (!response.ok) {
    const structured = payload.error || {};
    throw new ApiError(structured.message || payload.detail || "The operation failed.", {
      code: structured.code,
      status: response.status,
      details: structured.details
    });
  }
  return payload;
}

export const api = {
  health: () => request("/api/health"),
  overview: () => request("/api/lab"),
  devices: () => request("/api/devices"),
  device: hostname => request(`/api/devices/${encodeURIComponent(hostname)}`),
  printers: () => request("/api/printers"),
  workstations: () => request("/api/workstations"),
  submitPrintJob: (printer, source, pages) => request(`/api/printers/${encodeURIComponent(printer)}/jobs`, {
    method: "POST",
    body: {source, ...(pages ? {pages: Number(pages)} : {})}
  }),
  printerAction: (printer, action) => request(`/api/printers/${encodeURIComponent(printer)}/actions/${action}`, {method: "POST"}),
  workstationAction: (workstation, action) => request(`/api/workstations/${encodeURIComponent(workstation)}/actions/${action}`, {method: "POST"}),
  infrastructureAction: (hostname, action) => request(`/api/devices/${encodeURIComponent(hostname)}/actions/${action}`, {method: "POST"}),
  ping: (source, destination) => request("/api/connectivity/ping", {method: "POST", body: {source, destination}}),
  diagnostic: (diagnosticType, source, destination) => request("/api/connectivity/diagnostic", {method: "POST", body: {diagnostic_type: diagnosticType, source, destination}}),
  networkInfo: hostname => request(`/api/connectivity/network-info/${encodeURIComponent(hostname)}`),
  directory: () => request("/api/directory"),
  directoryAccountHealth: () => request("/api/directory/account-health"),
  directoryUserAction: (username, action) => request(`/api/directory/users/${encodeURIComponent(username)}/actions/${action}`, {method: "POST"}),
  resetDirectoryPassword: username => request(`/api/directory/users/${encodeURIComponent(username)}/password-reset`, {method: "POST"}),
  directoryMembership: (group, username, action) => request(`/api/directory/groups/${encodeURIComponent(group)}/members/${encodeURIComponent(username)}/${action}`, {method: "POST"}),
  provisioningOptions: () => request("/api/provisioning/options"),
  draftWorkstation: body => request("/api/provisioning/workstations/draft", {method: "POST", body}),
  applyWorkstation: draftId => request("/api/provisioning/workstations/apply", {method: "POST", body: {draft_id: draftId}}),
  employeeOptions: () => request("/api/provisioning/employees/options"),
  createEmployee: body => request("/api/provisioning/employees", {method: "POST", body}),
  assignEmployee: (username, workstation) => request(`/api/provisioning/employees/${encodeURIComponent(username)}/assign`, {method: "POST", body: {workstation}}),
  unassignEmployee: username => request(`/api/provisioning/employees/${encodeURIComponent(username)}/unassign`, {method: "POST"}),
  removeDevice: hostname => request(`/api/provisioning/devices/${encodeURIComponent(hostname)}`, {method: "DELETE"}),
  fileserver: () => request("/api/fileserver"),
  fileAccessCheck: body => request("/api/fileserver/access-check", {method: "POST", body}),
  fileUserAccess: username => request(`/api/fileserver/users/${encodeURIComponent(username)}/access`),
  fileShareAccess: share => request(`/api/fileserver/shares/${encodeURIComponent(share)}/access`),
  fileShareMembership: (share, body) => request(`/api/fileserver/shares/${encodeURIComponent(share)}/memberships`, {method: "POST", body})
};
