const launchLink = document.querySelector("[data-converter-link]");
const converterUrl = window.QUE2_SITE_CONFIG?.converterUrl;

if (converterUrl) {
  launchLink.href = converterUrl;
} else {
  launchLink.removeAttribute("href");
  launchLink.setAttribute("aria-disabled", "true");
  launchLink.title = "Converter deployment URL has not been configured yet";
}
