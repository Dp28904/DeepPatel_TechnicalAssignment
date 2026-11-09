// New / edit Draft order form.
// - Selecting a product fetches and shows its current price and stock.
// - Item rows are added and removed without reloading the page.
// - Amounts and totals update live (a preview; the server recalculates on save).
// - Inputs are validated with clear messages before sending; the server validates again.
// - The save button is disabled while the request is in flight.

import { api } from "./api.js";
import { paiseToString, previewTotals, toBasisPoints, toPaise } from "./money.js";
import { clearErrors, el, formatMoney, showFieldError, showFormError } from "./ui.js";

const form = document.getElementById("order-form");
const f = form.elements;
const orderId = form.dataset.orderId;
const rowsBody = document.getElementById("item-rows");
const rowTemplate = document.getElementById("item-row-template");
const saveButton = document.getElementById("save-button");

const limits = {
  minQuantity: Number(document.body.dataset.minQuantity),
  maxQuantity: Number(document.body.dataset.maxQuantity),
  maxDiscountBp: toBasisPoints(document.body.dataset.maxDiscount),
  maxDiscount: document.body.dataset.maxDiscount,
};

let activeProducts = [];
// When editing, lines already on the order keep their stored rate (product_id -> paise).
const storedRates = new Map();

// --- Loading data ---------------------------------------------------------
async function fetchAll(url) {
  const items = [];
  for (let page = 1; ; page += 1) {
    const separator = url.includes("?") ? "&" : "?";
    const data = await api("GET", `${url}${separator}page=${page}&page_size=100`);
    items.push(...data.items);
    if (page >= data.pages) return items;
  }
}

function fillCustomerOptions(customers, selected) {
  const options = [el("option", { value: "" }, "Select a customer…")];
  options.push(...customers.map((c) => el("option", { value: c.id }, c.city ? `${c.name} (${c.city})` : c.name)));
  if (selected && !customers.some((c) => c.id === selected.id)) {
    options.push(el("option", { value: selected.id }, `${selected.name} (inactive)`));
  }
  f.customer_id.replaceChildren(...options);
  if (selected) f.customer_id.value = String(selected.id);
}

// --- Item rows ------------------------------------------------------------
const rows = () => [...rowsBody.querySelectorAll(".item-row")];
const part = (row, role) => row.querySelector(`[data-role="${role}"]`);

function addRow(item = null) {
  const row = rowTemplate.content.firstElementChild.cloneNode(true);
  const select = row.querySelector(".product-select");
  const qty = row.querySelector(".qty-input");

  select.append(...activeProducts.map((p) => el("option", { value: p.id }, `${p.code} — ${p.name}`)));
  if (item) {
    if (!activeProducts.some((p) => p.id === item.product_id)) {
      select.append(el("option", { value: item.product_id }, `${item.product_code} — ${item.product_name} (inactive)`));
    }
    select.value = String(item.product_id);
    qty.value = item.quantity;
    row.dataset.ratePaise = toPaise(item.rate);
    row.dataset.stock = item.available_stock;
  }

  select.addEventListener("change", () => onProductChange(row));
  qty.addEventListener("input", () => {
    setRowError(row, "qty", "");
    refresh();
  });
  row.querySelector(".remove-row").addEventListener("click", () => {
    row.remove();
    refresh();
  });

  rowsBody.append(row);
  refresh();
  return row;
}

async function onProductChange(row) {
  const select = row.querySelector(".product-select");
  const productId = Number(select.value);
  setRowError(row, "product", "");
  delete row.dataset.ratePaise;
  delete row.dataset.stock;
  refresh();
  if (!productId) return;

  part(row, "rate").textContent = "…";
  try {
    // Fetch the latest price and stock for the chosen product.
    const product = await api("GET", `/api/products/${productId}`);
    if (Number(select.value) !== productId) return; // user picked something else meanwhile
    row.dataset.ratePaise = storedRates.get(productId) ?? toPaise(product.price);
    row.dataset.stock = product.stock_quantity;
  } catch (error) {
    setRowError(row, "product", error.message);
  }
  refresh();
}

function setRowError(row, which, message) {
  part(row, `${which}-error`).textContent = message;
  const input = row.querySelector(which === "qty" ? ".qty-input" : ".product-select");
  input.classList.toggle("is-invalid", Boolean(message));
}

function readQuantity(row) {
  const text = row.querySelector(".qty-input").value.trim();
  return /^\d+$/.test(text) ? Number(text) : null;
}

// --- Live calculation -----------------------------------------------------
function refresh() {
  const productCounts = new Map();
  for (const row of rows()) {
    const id = row.querySelector(".product-select").value;
    if (id) productCounts.set(id, (productCounts.get(id) ?? 0) + 1);
  }

  const lines = [];
  for (const row of rows()) {
    const productId = row.querySelector(".product-select").value;
    const ratePaise = row.dataset.ratePaise ? Number(row.dataset.ratePaise) : null;
    const stock = row.dataset.stock !== undefined ? Number(row.dataset.stock) : null;
    const quantity = readQuantity(row);

    part(row, "rate").textContent = ratePaise === null ? "–" : formatMoney(paiseToString(ratePaise));
    const stockCell = part(row, "stock");
    stockCell.textContent = stock === null ? "–" : String(stock);
    const short = stock !== null && quantity !== null && quantity > stock;
    stockCell.classList.toggle("text-warning", short);
    stockCell.title = short ? `Only ${stock} in stock. The order can be saved, but confirming it will fail.` : "";

    const duplicate = Boolean(productId) && productCounts.get(productId) > 1;
    if (duplicate) {
      setRowError(row, "product", "This product is already in the order. Change the quantity on one row instead.");
      row.dataset.duplicate = "true";
    } else if (row.dataset.duplicate) {
      setRowError(row, "product", ""); // the duplicate was resolved
      delete row.dataset.duplicate;
    }

    if (ratePaise !== null && quantity !== null && quantity >= limits.minQuantity) {
      const amount = quantity * ratePaise;
      part(row, "amount").textContent = formatMoney(paiseToString(amount));
      lines.push({ quantity, ratePaise });
    } else {
      part(row, "amount").textContent = "–";
    }
  }

  const discountBp = toBasisPoints(f.discount_percent.value || "0") ?? 0;
  const totals = previewTotals(lines, Math.min(discountBp, limits.maxDiscountBp));
  document.getElementById("subtotal").textContent = formatMoney(paiseToString(totals.subtotal));
  document.getElementById("discount-amount").textContent = `− ${formatMoney(paiseToString(totals.discount))}`;
  document.getElementById("grand-total").textContent = formatMoney(paiseToString(totals.grandTotal));
}

// --- Validation -------------------------------------------------------------
function todayIso() {
  const now = new Date();
  return new Date(now.getTime() - now.getTimezoneOffset() * 60000).toISOString().slice(0, 10);
}

function validate() {
  let ok = true;
  const fail = (field, message) => {
    showFieldError(form, field, message);
    ok = false;
  };

  if (!f.customer_id.value) fail("customer_id", "Select a customer.");
  if (f.order_date.value && f.order_date.value > todayIso()) fail("order_date", "Order date cannot be in the future.");

  const discountBp = toBasisPoints(f.discount_percent.value || "0");
  if (discountBp === null || discountBp > limits.maxDiscountBp) {
    fail("discount_percent", `Discount must be a number from 0 to ${limits.maxDiscount} with at most 2 decimals.`);
  }

  const items = rows();
  if (!items.length) fail("items", "Add at least one item.");

  const seen = new Set();
  for (const row of items) {
    const productId = row.querySelector(".product-select").value;
    const quantity = readQuantity(row);
    if (!productId) {
      setRowError(row, "product", "Select a product.");
      ok = false;
    } else if (seen.has(productId)) {
      setRowError(row, "product", "This product is already in the order.");
      ok = false;
    }
    seen.add(productId);
    if (quantity === null || quantity < limits.minQuantity || quantity > limits.maxQuantity) {
      setRowError(row, "qty", `Enter a whole number from ${limits.minQuantity} to ${limits.maxQuantity}.`);
      ok = false;
    }
  }
  return ok;
}

/** Map server errors such as "items.1.quantity" back to the matching row. */
function showServerErrors(error) {
  const unplaced = [];
  for (const detail of Array.isArray(error.details) ? error.details : []) {
    const match = /^items\.(\d+)\.(product_id|quantity)$/.exec(detail.field ?? "");
    const row = match ? rows()[Number(match[1])] : null;
    if (row) {
      setRowError(row, match[2] === "quantity" ? "qty" : "product", detail.message);
    } else if (!(detail.field && showFieldError(form, detail.field, detail.message))) {
      if (detail.message) unplaced.push(detail.message);
    }
  }
  showFormError(document, unplaced.length ? `${error.message} ${unplaced.join(" ")}` : error.message);
}

function clearAllErrors() {
  clearErrors(document.querySelector("main"));
  for (const row of rows()) {
    setRowError(row, "product", "");
    setRowError(row, "qty", "");
  }
}

// --- Submit -----------------------------------------------------------------
form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearAllErrors();
  if (!validate()) {
    showFormError(document, "Please fix the highlighted fields.");
    return;
  }

  // Only choices are sent. Rates, amounts and totals are always computed by the server.
  const body = {
    customer_id: Number(f.customer_id.value),
    order_date: f.order_date.value || null,
    discount_percent: f.discount_percent.value.trim() || "0",
    items: rows().map((row) => ({
      product_id: Number(row.querySelector(".product-select").value),
      quantity: readQuantity(row),
    })),
  };

  try {
    const saved = orderId
      ? await api("PUT", `/api/orders/${orderId}`, { body, button: saveButton })
      : await api("POST", "/api/orders", { body, button: saveButton });
    window.location.href = `/orders/${saved.id}`;
  } catch (error) {
    showServerErrors(error);
  }
});

document.getElementById("add-row").addEventListener("click", () => {
  const row = addRow();
  row.querySelector(".product-select").focus();
});
f.discount_percent.addEventListener("input", () => {
  showFieldError(form, "discount_percent", "");
  refresh();
});

// --- Start --------------------------------------------------------------------
async function init() {
  saveButton.disabled = true;
  try {
    const [customers, products, order] = await Promise.all([
      fetchAll("/api/customers?status=active"),
      fetchAll("/api/products?status=active"),
      orderId ? api("GET", `/api/orders/${orderId}`) : Promise.resolve(null),
    ]);
    activeProducts = products;

    if (!order) {
      fillCustomerOptions(customers, null);
      f.order_date.value = todayIso();
      addRow();
      saveButton.disabled = false;
      return;
    }

    document.getElementById("page-title").textContent = `Edit ${order.order_number}`;
    fillCustomerOptions(customers, order.customer);
    f.order_date.value = order.order_date;
    f.discount_percent.value = order.discount_percent;
    for (const item of order.items) storedRates.set(item.product_id, toPaise(item.rate));
    order.items.forEach((item) => addRow(item));

    if (!order.can_edit) {
      showFormError(document, `Order ${order.order_number} is ${order.status.toLowerCase()} and can no longer be edited.`);
      form.querySelectorAll("input, select, button").forEach((control) => (control.disabled = true));
      return;
    }
    saveButton.disabled = false;
  } catch (error) {
    showFormError(document, error.message);
  }
}

init();
