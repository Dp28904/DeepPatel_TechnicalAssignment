// Dashboard: loads /api/dashboard for the chosen period and renders every card.
// The server scopes the data by role (Admin: all orders, Sales User: own orders).

import { api } from "./api.js";
import {
  barList, dataTable, formatAmount, formatCompact, formatCount, lineChart, meterList, segmentedBar,
} from "./charts.js";
import { orderStatusBadge } from "./orders_shared.js";
import { el, showFormError } from "./ui.js";

const form = document.getElementById("range-filter");
const f = form.elements;
const dashboard = document.getElementById("dashboard");
const isAdmin = document.body.dataset.userRole === "ADMIN";

const card = (name) => document.querySelector(`[data-chart="${name}"]`);
const chartBody = (name) => card(name).querySelector(".chart-body");
const tableBody = (name) => card(name).querySelector(".table-body");
const setText = (id, text) => (document.getElementById(id).textContent = text);

// --- Date range presets -----------------------------------------------------------------
function iso(date) {
  return new Date(date.getTime() - date.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

function rangeFor(preset) {
  const today = new Date();
  const daysAgo = (n) => new Date(today.getFullYear(), today.getMonth(), today.getDate() - n);
  switch (preset) {
    case "30d": return { from: iso(daysAgo(29)), to: iso(today) };
    case "90d": return { from: iso(daysAgo(89)), to: iso(today) };
    case "12m": return { from: iso(new Date(today.getFullYear(), today.getMonth() - 11, 1)), to: iso(today) };
    case "ytd": return { from: iso(new Date(today.getFullYear(), 0, 1)), to: iso(today) };
    case "custom": return { from: f.from.value, to: f.to.value };
    default: return { from: "", to: "" };
  }
}

function describeRange({ from, to }) {
  if (!from && !to) return "All time";
  return `${from || "…"} → ${to || "today"}`;
}

// --- Rendering ------------------------------------------------------------------------------
const tables = {}; // chart name -> function returning its table twin

function renderKpis(data) {
  const k = data.kpis;
  setText("kpi-net-sales", formatAmount(k.net_sales));
  setText("kpi-net-sub", `Gross ${formatAmount(k.gross_sales)} − discounts ${formatAmount(k.discounts)}`);
  setText("kpi-confirmed", formatCount(k.confirmed_orders));
  setText("kpi-aov", k.confirmed_orders ? `Average order ${formatAmount(k.average_order_value)}` : "No confirmed orders yet");
  setText("kpi-drafts", formatCount(k.draft_orders));
  setText("kpi-draft-value", k.draft_orders ? `${formatAmount(k.draft_value)} awaiting confirmation` : "Nothing waiting");
  setText("kpi-low-stock", formatCount(k.low_stock_products));
  setText("kpi-low-sub", `Active products with stock below ${data.low_stock_threshold}`);
}

function renderTrend(data) {
  const points = data.monthly_sales.map((m) => ({
    label: m.label,
    short: m.label.split(" ")[0],
    value: Number(m.net_sales),
    detail: `${m.orders} confirmed order${m.orders === 1 ? "" : "s"}`,
  }));
  lineChart(chartBody("trend"), points, { ariaLabel: `Monthly net sales, ${points.length} months` });
  tables.trend = () => dataTable(data.monthly_sales, [
    { label: "Month", value: (m) => m.label },
    { label: "Confirmed orders", value: (m) => formatCount(m.orders), numeric: true },
    { label: "Net sales", value: (m) => formatAmount(m.net_sales), numeric: true },
  ]);
}

const STATUS_PARTS = [
  { status: "CONFIRMED", label: "Confirmed", colorVar: "--viz-series-1" },
  { status: "DRAFT", label: "Draft", colorVar: "--viz-series-2" },
  { status: "CANCELLED", label: "Cancelled", colorVar: "--viz-series-3" },
];

function renderStatus(data) {
  const byStatus = Object.fromEntries(data.orders_by_status.map((s) => [s.status, s]));
  const parts = STATUS_PARTS.map((p) => ({
    ...p,
    value: byStatus[p.status].orders,
    detail: `${byStatus[p.status].orders} order${byStatus[p.status].orders === 1 ? "" : "s"}, ${formatAmount(byStatus[p.status].value)}`,
  }));
  segmentedBar(chartBody("status"), parts, { emptyMessage: "No orders in this period.", ariaLabel: "Orders by status" });
  tables.status = () => dataTable(data.orders_by_status, [
    { label: "Status", value: (s) => orderStatusBadge(s.status) },
    { label: "Orders", value: (s) => formatCount(s.orders), numeric: true },
    { label: "Value", value: (s) => formatAmount(s.value), numeric: true },
  ]);
}

function renderCategories(data) {
  barList(chartBody("categories"), data.sales_by_category.map((c) => ({
    label: c.category,
    value: Number(c.gross_value),
    valueText: formatCompact(c.gross_value),
    detail: `${formatAmount(c.gross_value)} · ${formatCount(c.quantity_sold)} units`,
  })), { emptyMessage: "No confirmed sales in this period.", ariaLabel: "Sales by category" });
  tables.categories = () => dataTable(data.sales_by_category, [
    { label: "Category", value: (c) => c.category },
    { label: "Units", value: (c) => formatCount(c.quantity_sold), numeric: true },
    { label: "Gross value", value: (c) => formatAmount(c.gross_value), numeric: true },
  ]);
}

function renderCustomers(data) {
  barList(chartBody("customers"), data.top_customers.map((c) => ({
    label: c.customer_name,
    href: `/customers/${c.customer_id}`,
    value: Number(c.net_sales),
    valueText: formatCompact(c.net_sales),
    detail: `${formatAmount(c.net_sales)} · ${c.orders} order${c.orders === 1 ? "" : "s"}`,
  })), { emptyMessage: "No confirmed sales in this period.", ariaLabel: "Top customers by net sales" });
  tables.customers = () => dataTable(data.top_customers, [
    { label: "Customer", value: (c) => c.customer_name },
    { label: "Orders", value: (c) => formatCount(c.orders), numeric: true },
    { label: "Net sales", value: (c) => formatAmount(c.net_sales), numeric: true },
  ]);
}

function renderProducts(data) {
  barList(chartBody("products"), data.top_products.map((p) => ({
    label: p.name,
    sublabel: p.code,
    href: `/products/${p.product_id}`,
    value: p.quantity_sold,
    valueText: `${formatCount(p.quantity_sold)} units`,
    detail: `Gross ${formatAmount(p.gross_value)}`,
  })), { emptyMessage: "No confirmed sales in this period.", ariaLabel: "Top products by quantity sold" });
  tables.products = () => dataTable(data.top_products, [
    { label: "Code", value: (p) => p.code },
    { label: "Product", value: (p) => p.name },
    { label: "Units sold", value: (p) => formatCount(p.quantity_sold), numeric: true },
    { label: "Gross value", value: (p) => formatAmount(p.gross_value), numeric: true },
  ]);
}

function renderUsers(data) {
  if (!card("users")) return; // Admin only
  barList(chartBody("users"), data.sales_by_user.map((u) => ({
    label: u.user_name,
    value: Number(u.net_sales),
    valueText: formatCompact(u.net_sales),
    detail: `${formatAmount(u.net_sales)} · ${u.orders} order${u.orders === 1 ? "" : "s"}`,
  })), { emptyMessage: "No confirmed sales in this period.", ariaLabel: "Net sales by team member" });
  tables.users = () => dataTable(data.sales_by_user, [
    { label: "Team member", value: (u) => u.user_name },
    { label: "Orders", value: (u) => formatCount(u.orders), numeric: true },
    { label: "Net sales", value: (u) => formatAmount(u.net_sales), numeric: true },
  ]);
}

function renderLowStock(data) {
  setText("low-stock-caption", `Active products with stock below ${data.low_stock_threshold} (current stock, not the period)`);
  meterList(chartBody("low-stock"), data.low_stock.map((p) => ({
    label: p.name,
    sublabel: p.code,
    href: `/products/${p.product_id}`,
    value: p.stock_quantity,
    max: data.low_stock_threshold,
  })), { emptyMessage: "Every active product is above the threshold." });
  tables["low-stock"] = () => dataTable(data.low_stock, [
    { label: "Code", value: (p) => p.code },
    { label: "Product", value: (p) => p.name },
    { label: "In stock", value: (p) => formatCount(p.stock_quantity), numeric: true },
  ]);
}

function renderRecent(data) {
  const columns = [
    { label: "Order no.", value: (o) => el("a", { href: `/orders/${o.id}` }, o.order_number) },
    { label: "Date", value: (o) => o.order_date },
    { label: "Customer", value: (o) => o.customer_name },
    { label: "Status", value: (o) => orderStatusBadge(o.status) },
    { label: "Grand total", value: (o) => formatAmount(o.grand_total), numeric: true },
  ];
  if (isAdmin) columns.splice(4, 0, { label: "Created by", value: (o) => o.created_by_name });
  chartBody("recent").replaceChildren(dataTable(data.recent_orders, columns));
}

function refreshOpenTables() {
  for (const [name, build] of Object.entries(tables)) {
    if (!tableBody(name).hidden) tableBody(name).replaceChildren(build());
  }
}

// --- Loading ---------------------------------------------------------------------------------
async function load() {
  const range = rangeFor(f.preset.value);
  document.getElementById("range-label").textContent = describeRange(range);
  if (range.from && range.to && range.from > range.to) {
    showFormError(document, "'From' date must be on or before 'To' date.");
    return;
  }
  const params = new URLSearchParams();
  if (range.from) params.set("from", range.from);
  if (range.to) params.set("to", range.to);
  history.replaceState(null, "", `?${new URLSearchParams({ preset: f.preset.value, ...range })}`);

  dashboard.classList.add("is-loading"); // keep the previous render, dimmed, while refetching
  try {
    const data = await api("GET", `/api/dashboard?${params}`);
    document.getElementById("form-error").hidden = true;
    renderKpis(data);
    renderTrend(data);
    renderStatus(data);
    renderCategories(data);
    renderCustomers(data);
    renderProducts(data);
    renderLowStock(data);
    renderUsers(data);
    renderRecent(data);
    refreshOpenTables();
  } catch (error) {
    showFormError(document, error.message);
  } finally {
    dashboard.classList.remove("is-loading");
  }
}

// --- Events -----------------------------------------------------------------------------------
for (const toggle of document.querySelectorAll(".view-toggle")) {
  toggle.addEventListener("click", () => {
    const name = toggle.closest("[data-chart]").dataset.chart;
    const showTable = toggle.getAttribute("aria-pressed") !== "true";
    toggle.setAttribute("aria-pressed", String(showTable));
    toggle.textContent = showTable ? "Chart" : "Table";
    chartBody(name).hidden = showTable;
    tableBody(name).hidden = !showTable;
    if (showTable && tables[name]) tableBody(name).replaceChildren(tables[name]());
    if (!showTable && chartBody(name)._redraw) chartBody(name)._redraw();
  });
}

form.addEventListener("submit", (event) => event.preventDefault());
f.preset.addEventListener("change", () => {
  const custom = f.preset.value === "custom";
  form.querySelectorAll(".custom-range").forEach((node) => (node.hidden = !custom));
  if (custom && !f.from.value) {
    const r = rangeFor("12m");
    f.from.value = r.from;
    f.to.value = r.to;
  }
  load();
});
f.from.addEventListener("change", load);
f.to.addEventListener("change", load);

// Restore the period from the URL (so refresh and bookmarks keep it).
const saved = new URLSearchParams(window.location.search);
if (saved.get("preset")) {
  f.preset.value = saved.get("preset");
  if (f.preset.value === "custom") {
    f.from.value = saved.get("from") ?? "";
    f.to.value = saved.get("to") ?? "";
    form.querySelectorAll(".custom-range").forEach((node) => (node.hidden = false));
  }
}
load();
