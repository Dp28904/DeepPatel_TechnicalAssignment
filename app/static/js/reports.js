// Reports page: four tabs, each with its own filter form. Data comes from /api/reports.

import { api } from "./api.js";
import {
  clearErrors, el, formatDateTime, formatMoney, renderPager, showFieldError, showFormError, statusBadge,
} from "./ui.js";

const TABS = ["customer-sales", "product-sales", "low-stock", "stock-movements"];
const MOVEMENT_LABELS = {
  OPENING: "Opening stock",
  ADJUSTMENT_IN: "Adjustment in",
  ADJUSTMENT_OUT: "Adjustment out",
  ORDER_CONFIRM: "Order confirmed",
  ORDER_CANCEL: "Order cancelled",
};

const panel = (name) => document.querySelector(`[data-panel="${name}"]`);
const formFor = (name) => document.querySelector(`form[data-report="${name}"]`);
const loaded = new Set();
let movementPage = 1;

function emptyRow(columns, text = "No data for these filters.") {
  return el("tr", {}, el("td", { colspan: columns, class: "muted" }, text));
}

function dateParams(form) {
  const params = new URLSearchParams();
  for (const key of ["from", "to"]) if (form.elements[key].value) params.set(key, form.elements[key].value);
  return params;
}

function checkDates(form) {
  const { from, to } = form.elements;
  if (from.value && to.value && from.value > to.value) {
    showFormError(document, "'From' date must be on or before 'To' date.");
    return false;
  }
  return true;
}

// --- Loaders ------------------------------------------------------------------
const loaders = {
  async "customer-sales"(form) {
    if (!checkDates(form)) return;
    const data = await api("GET", `/api/reports/customer-sales?${dateParams(form)}`, { button: form.querySelector("button") });
    const p = panel("customer-sales");
    p.querySelector("[data-rows]").replaceChildren(
      ...(data.rows.length ? data.rows.map((r) => el("tr", { class: r.confirmed_orders ? "" : "muted-row" },
        el("td", {}, el("a", { href: `/customers/${r.customer_id}` }, r.customer_name)),
        el("td", {}, r.city ?? ""),
        el("td", {}, statusBadge(r.is_active)),
        el("td", { class: "num" }, String(r.confirmed_orders)),
        el("td", { class: "num" }, formatMoney(r.total_sales)),
      )) : [emptyRow(5)]),
    );
    p.querySelector("[data-totals]").replaceChildren(el("tr", {},
      el("th", { colspan: 3 }, `${data.totals.customers} customers, ${data.totals.customers_with_sales} with sales`),
      el("th", { class: "num" }, String(data.totals.confirmed_orders)),
      el("th", { class: "num" }, formatMoney(data.totals.total_sales)),
    ));
  },

  async "product-sales"(form) {
    if (!checkDates(form)) return;
    const data = await api("GET", `/api/reports/product-sales?${dateParams(form)}`, { button: form.querySelector("button") });
    const p = panel("product-sales");
    p.querySelector("[data-rows]").replaceChildren(
      ...(data.rows.length ? data.rows.map((r) => el("tr", { class: r.quantity_sold ? "" : "muted-row" },
        el("td", {}, el("a", { href: `/products/${r.product_id}` }, r.code)),
        el("td", {}, r.name),
        el("td", {}, r.category),
        el("td", { class: "num" }, String(r.quantity_sold)),
        el("td", { class: "num" }, String(r.order_count)),
        el("td", { class: "num" }, formatMoney(r.gross_value)),
      )) : [emptyRow(6)]),
    );
    p.querySelector("[data-totals]").replaceChildren(el("tr", {},
      el("th", { colspan: 3 }, "Total"),
      el("th", { class: "num" }, String(data.totals.quantity_sold)),
      el("th", {}, ""),
      el("th", { class: "num" }, formatMoney(data.totals.gross_value)),
    ));
  },

  async "low-stock"(form) {
    const thresholdText = form.elements.threshold.value.trim();
    if (!/^\d+$/.test(thresholdText)) {
      showFieldError(form, "threshold", "Enter a whole number of 0 or more.");
      return;
    }
    const params = new URLSearchParams({ threshold: thresholdText, include_inactive: form.elements.include_inactive.checked });
    const data = await api("GET", `/api/reports/low-stock?${params}`, { button: form.querySelector("button") });
    panel("low-stock").querySelector("[data-rows]").replaceChildren(
      ...(data.rows.length ? data.rows.map((r) => el("tr", {},
        el("td", {}, el("a", { href: `/products/${r.product_id}` }, r.code)),
        el("td", {}, r.name),
        el("td", {}, r.category),
        el("td", { class: "num" }, formatMoney(r.price)),
        el("td", { class: `num ${r.stock_quantity === 0 ? "text-warning" : ""}` }, String(r.stock_quantity)),
        el("td", { class: "num" }, String(r.below_threshold_by)),
        el("td", {}, statusBadge(r.is_active)),
      )) : [emptyRow(7, `No products below ${data.threshold}.`)]),
    );
  },

  async "stock-movements"(form) {
    if (!checkDates(form)) return;
    const params = dateParams(form);
    for (const key of ["product_id", "movement_type"]) if (form.elements[key].value) params.set(key, form.elements[key].value);
    params.set("page", movementPage);
    params.set("page_size", 25);
    const data = await api("GET", `/api/reports/stock-movements?${params}`, { button: form.querySelector("button") });
    const p = panel("stock-movements");
    p.querySelector("[data-rows]").replaceChildren(
      ...(data.items.length ? data.items.map((m) => el("tr", {},
        el("td", {}, formatDateTime(m.created_at)),
        el("td", {}, el("a", { href: `/products/${m.product_id}` }, `${m.product_code} ${m.product_name}`)),
        el("td", {}, MOVEMENT_LABELS[m.movement_type] ?? m.movement_type),
        el("td", { class: `num ${m.quantity_change < 0 ? "negative" : "positive"}` }, m.quantity_change > 0 ? `+${m.quantity_change}` : String(m.quantity_change)),
        el("td", {}, m.order_id ? el("a", { href: `/orders/${m.order_id}` }, m.order_number) : "–"),
        el("td", { class: "wrap" }, m.reason ?? ""),
        el("td", {}, m.created_by_name),
      )) : [emptyRow(7)]),
    );
    renderPager(p.querySelector("[data-pager]"), data, (page) => {
      movementPage = page;
      run("stock-movements");
    });
  },
};

async function run(name) {
  const form = formFor(name);
  clearErrors(form);
  document.getElementById("form-error").hidden = true;
  try {
    await loaders[name](form);
    loaded.add(name);
  } catch (error) {
    showFormError(document, error.message);
  }
}

// --- Tabs ---------------------------------------------------------------------
function showTab(name) {
  if (!TABS.includes(name)) name = TABS[0];
  for (const tab of TABS) {
    panel(tab).hidden = tab !== name;
    document.querySelector(`[data-tab="${tab}"]`).setAttribute("aria-selected", String(tab === name));
  }
  history.replaceState(null, "", `?tab=${name}`);
  if (!loaded.has(name)) run(name);
}

document.querySelectorAll("[data-tab]").forEach((button) =>
  button.addEventListener("click", () => showTab(button.dataset.tab)),
);
document.querySelectorAll("form[data-report]").forEach((form) =>
  form.addEventListener("submit", (event) => {
    event.preventDefault();
    if (form.dataset.report === "stock-movements") movementPage = 1;
    run(form.dataset.report);
  }),
);

async function loadProductOptions() {
  const select = formFor("stock-movements").elements.product_id;
  for (let page = 1; ; page += 1) {
    const data = await api("GET", `/api/products?status=all&page=${page}&page_size=100`);
    select.append(...data.items.map((p) => el("option", { value: p.id }, `${p.code} — ${p.name}`)));
    if (page >= data.pages) break;
  }
}

loadProductOptions().catch(() => {});
showTab(new URLSearchParams(window.location.search).get("tab"));
