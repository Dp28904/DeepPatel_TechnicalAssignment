// CSV product import: upload the file, then show either the imported products or
// every problem with its row number. The button is disabled while uploading.

import { api } from "./api.js";
import { clearErrors, el, formatMoney, showFieldError, statusBadge } from "./ui.js";

const form = document.getElementById("import-form");
const button = document.getElementById("import-button");
const result = document.getElementById("result");
const summary = document.getElementById("result-summary");
const head = document.getElementById("result-head");
const body = document.getElementById("result-rows");

const MAX_BYTES = 1024 * 1024;

function showSuccess(data) {
  summary.replaceChildren(
    el("div", { class: "alert alert-success" },
      `Imported ${data.imported_count} product(s). ${data.opening_stock_movements} opening stock movement(s) recorded.`),
  );
  head.replaceChildren(el("tr", {},
    el("th", {}, "Code"), el("th", {}, "Name"), el("th", {}, "Category"),
    el("th", { class: "num" }, "Price"), el("th", { class: "num" }, "Stock"), el("th", {}, "Status")));
  body.replaceChildren(...data.products.map((p) => el("tr", {},
    el("td", {}, el("a", { href: `/products/${p.id}` }, p.code)),
    el("td", {}, p.name),
    el("td", {}, p.category),
    el("td", { class: "num" }, formatMoney(p.price)),
    el("td", { class: "num" }, String(p.stock_quantity)),
    el("td", {}, statusBadge(p.is_active)),
  )));
  result.hidden = false;
}

function showProblems(error) {
  summary.replaceChildren(el("div", { class: "alert alert-error" }, error.message));
  const problems = Array.isArray(error.details) ? error.details : [];
  head.replaceChildren(problems.length
    ? el("tr", {}, el("th", { class: "num" }, "Row"), el("th", {}, "Column"), el("th", {}, "Problem"))
    : "");
  body.replaceChildren(...problems.map((p) => el("tr", {},
    el("td", { class: "num" }, p.row ?? "–"),
    el("td", {}, p.field ?? "(whole row)"),
    el("td", { class: "wrap" }, p.message),
  )));
  result.hidden = false;
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearErrors(form);
  result.hidden = true;

  const file = form.elements.file.files[0];
  if (!file) return showFieldError(form, "file", "Choose a CSV file to upload.");
  if (!file.name.toLowerCase().endsWith(".csv")) return showFieldError(form, "file", "The file must have a .csv extension.");
  if (file.size > MAX_BYTES) return showFieldError(form, "file", "The file is larger than 1 MB.");

  const data = new FormData();
  data.append("file", file);
  button.textContent = "Importing…";
  try {
    showSuccess(await api("POST", "/api/imports/products", { body: data, button }));
    form.reset();
  } catch (error) {
    showProblems(error);
  } finally {
    button.textContent = "Validate and import";
  }
});
