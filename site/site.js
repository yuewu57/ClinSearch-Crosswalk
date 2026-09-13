const config = window.CLINSEARCH_CROSSWALK_SITE_CONFIG || {};
const launchLink = document.querySelector("[data-converter-link]");
const status = document.querySelector("[data-deployment-status]");
const version = document.querySelector("[data-version]");
let converterUrl = "";

try {
  const candidate = new URL(config.converterUrl);
  if (candidate.protocol === "https:" &&
      candidate.hostname.endsWith(".streamlit.app") &&
      !candidate.username && !candidate.password &&
      !candidate.search && !candidate.hash &&
      (!candidate.port || candidate.port === "443") &&
      candidate.pathname === "/") {
    converterUrl = candidate.href;
  }
} catch (_) {
  // An unset or invalid URL must not produce a broken or unsafe launch link.
}

if (launchLink && converterUrl) {
  launchLink.href = converterUrl;
  launchLink.removeAttribute("aria-disabled");
  if (status) status.textContent = "The interactive converter opens on Streamlit Community Cloud.";
} else if (launchLink) {
  launchLink.removeAttribute("href");
  launchLink.setAttribute("aria-disabled", "true");
  launchLink.title = "The public converter URL has not been configured yet.";
}

if (version && config.softwareVersion && config.rulesetVersion) {
  version.textContent = `Software ${config.softwareVersion} · Conversion ruleset ${config.rulesetVersion}`;
}
