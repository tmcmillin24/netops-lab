import assert from "node:assert/strict";
import fs from "node:fs";

const html = fs.readFileSync("frontend/index.html", "utf8");
const app = fs.readFileSync("frontend/app.js", "utf8");
const api = fs.readFileSync("frontend/api.js", "utf8");
const styles = fs.readFileSync("frontend/styles.css", "utf8");

for (const page of ["Dashboard", "Network", "Systems", "Active Directory", "Tickets", "Automation", "Architecture"]) {
  assert.match(html, new RegExp(`>${page}<`), `${page} navigation is missing`);
}

assert.match(app, /Planned Phase/);
assert.match(app, /state\.devices\.map/);
assert.match(app, /deviceCard/);
assert.match(app, /renderDrawer/);
assert.match(app, /Printer resources/);
assert.doesNotMatch(app, /Active printer incidents/);
assert.match(app, /openImpactedDevices/);
assert.match(app, /printer_alerts\?\.\[0\]/);
assert.match(app, /data-infrastructure-action/);
assert.match(app, /Printing unavailable/);
assert.match(app, /Backend unavailable/);
assert.match(app, /pingSource: "WS01"/);
assert.match(app, /state\.pingSource = event\.target\.value/);
assert.match(api, /\/api\/lab/);
assert.match(api, /\/api\/devices/);
assert.match(api, /\/api\/connectivity\/ping/);
assert.doesNotMatch(app, /http:\/\/127\.0\.0\.1:808[0-3]\/status/);
assert.match(styles, /\.backend-banner\[hidden\]\s*\{\s*display:\s*none;/);

console.log("Frontend structure checks passed.");
