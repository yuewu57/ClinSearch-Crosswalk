import "./styles.css";

const app = document.querySelector<HTMLElement>("#app");

if (!app) {
  throw new Error("Application root was not found");
}

app.innerHTML = `
  <section class="shell">
    <p class="eyebrow">ClinSearch-Crosswalk</p>
    <h1>Ovid MEDLINE → PubMed</h1>
    <p class="lede">Browser implementation under parity validation against the Python reference converter.</p>
    <div class="status">Development branch — not for clinical retrieval yet.</div>
  </section>
`;
