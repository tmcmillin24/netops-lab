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
  ping: (source, destination) => request("/api/connectivity/ping", {method: "POST", body: {source, destination}})
};
