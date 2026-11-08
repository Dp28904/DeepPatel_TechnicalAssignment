// Order detail: shows the order, and lets the user confirm or cancel it.
// Each action asks for confirmation first and disables its button while running.

import { api } from "./api.js";
import { confirmAction, el, formatDateTime, formatMoney, showFormError, toast } from "./ui.js";
import { orderStatusBadge } from "./orders_shared.js";

const view = document.getElementById("order-view");
const orderId = view.dataset.orderId;
const editButton = document.getElementById("edit-button");
const confirmButton = document.getElementById("confirm-button");
const cancelButton = document.getElementById("cancel-button");
const stockProblems = document.getElementById("stock-problems");
const errorBanner = document.getElementById("form-error");

let order = null;

const setText = (id, text) => (document.getElementById(id).textContent = text);

function render() {
  view.hidden = false;
  setText("order-number", order.order_number);
  document.getElementById("order-status").replaceChildren(orderStatusBadge(order.status));
  setText("customer", order.customer.name);
  setText("order-date", order.order_date);
  setText("created-by", order.created_by.name);
  setText("created-at", formatDateTime(order.created_at));
  document.getElementById("confirmed-block").hidden = !order.confirmed_at;
  setText("confirmed-at", formatDateTime(order.confirmed_at));
  document.getElementById("cancelled-block").hidden = !order.cancelled_at;
  setText("cancelled-at", formatDateTime(order.cancelled_at));

  // Stock only matters while the order is still a Draft.
  const showStock = order.status === "DRAFT";
  document.getElementById("stock-header").hidden = !showStock;
  document.getElementById("item-rows").replaceChildren(
    ...order.items.map((item) => {
      const short = item.available_stock < item.quantity;
      return el("tr", {},
        el("td", {}, item.product_code),
        el("td", {}, item.product_name),
        el("td", { class: "num" }, String(item.quantity)),
        el("td", { class: "num" }, formatMoney(item.rate)),
        el("td", { class: "num" }, formatMoney(item.amount)),
        showStock
          ? el("td", { class: `num ${short ? "text-warning" : ""}`, title: short ? "Not enough stock to confirm" : "" }, String(item.available_stock))
          : null,
      );
    }),
  );

  setText("subtotal", formatMoney(order.subtotal));
  setText("discount-label", `Discount (${Number(order.discount_percent)}%)`);
  setText("discount-amount", `− ${formatMoney(order.discount_amount)}`);
  setText("grand-total", formatMoney(order.grand_total));

  editButton.hidden = !order.can_edit;
  editButton.href = `/orders/${order.id}/edit`;
  confirmButton.hidden = !order.can_confirm;
  cancelButton.hidden = !order.can_cancel;
}

function showError(error) {
  stockProblems.hidden = true;
  if (error.code === "insufficient_stock" && Array.isArray(error.details)) {
    stockProblems.replaceChildren(
      el("strong", {}, error.message),
      el("ul", {}, ...error.details.map((d) =>
        el("li", {}, `${d.product_code} ${d.product_name}: ordered ${d.requested}, only ${d.available} in stock`),
      )),
    );
    stockProblems.hidden = false;
    errorBanner.hidden = true;
  } else {
    showFormError(document, error.message);
  }
}

async function runAction(action, button) {
  errorBanner.hidden = true;
  stockProblems.hidden = true;
  // Disable both buttons so the user cannot fire confirm and cancel together.
  confirmButton.disabled = cancelButton.disabled = true;
  try {
    order = await api("POST", `/api/orders/${orderId}/${action}`, { button });
    render();
    toast(`Order ${order.order_number} ${action === "confirm" ? "confirmed" : "cancelled"}.`, "success");
  } catch (error) {
    showError(error);
    // The order may have changed (e.g. someone else confirmed it): show the latest state.
    await load();
  } finally {
    confirmButton.disabled = cancelButton.disabled = false;
  }
}

confirmButton.addEventListener("click", () => {
  const message = `Confirm order ${order.order_number}?\n\nStock will be deducted for every item and the order can no longer be edited.`;
  if (confirmAction(message)) runAction("confirm", confirmButton);
});

cancelButton.addEventListener("click", () => {
  const message = order.status === "CONFIRMED"
    ? `Cancel confirmed order ${order.order_number}?\n\nThe deducted stock will be added back. This cannot be undone.`
    : `Cancel draft order ${order.order_number}? This cannot be undone.`;
  if (confirmAction(message)) runAction("cancel", cancelButton);
});

async function load() {
  try {
    order = await api("GET", `/api/orders/${orderId}`);
    render();
  } catch (error) {
    showFormError(document, error.message); // 404 for missing or someone else's order
  }
}

load();
