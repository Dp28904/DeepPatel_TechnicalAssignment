// Small UI helpers shared by all pages: toasts, form errors, confirmation dialogs.

export function toast(message, type = "info", timeoutMs = 4000) {
  const region = document.getElementById("toast-region");
  if (!region) return;
  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.textContent = message;
  region.appendChild(el);
  setTimeout(() => el.remove(), timeoutMs);
}

/** Remove every inline error inside a form (or any container). */
export function clearErrors(container) {
  container.querySelectorAll(".is-invalid").forEach((el) => el.classList.remove("is-invalid"));
  container.querySelectorAll("[data-error-for]").forEach((el) => (el.textContent = ""));
  const banner = container.querySelector(".alert-error");
  if (banner) banner.hidden = true;
}

/** Show a message under the input whose name matches `field`. */
export function showFieldError(container, field, message) {
  const slot = container.querySelector(`[data-error-for="${CSS.escape(field)}"]`);
  const input = container.querySelector(`[name="${CSS.escape(field)}"]`);
  if (input) input.classList.add("is-invalid");
  if (slot) {
    slot.textContent = message;
    return true;
  }
  return false;
}

/** Show a banner message at the top of a form. */
export function showFormError(container, message) {
  const banner = container.querySelector(".alert-error") ?? document.getElementById("form-error");
  if (banner) {
    banner.textContent = message;
    banner.hidden = false;
  } else {
    toast(message, "error");
  }
}

/**
 * Render an ApiError: field-level details go next to their inputs, anything else
 * goes into the banner.
 */
export function showApiError(container, error) {
  const leftovers = [];
  if (Array.isArray(error.details)) {
    for (const detail of error.details) {
      const placed = detail?.field && showFieldError(container, detail.field, detail.message);
      if (!placed && detail?.message) leftovers.push(detail.message);
    }
  }
  const message = leftovers.length ? `${error.message} ${leftovers.join(" ")}` : error.message;
  showFormError(container, message);
}

/** Native confirmation dialog; returns true when the user agrees. */
export function confirmAction(message) {
  return window.confirm(message);
}

// --- DOM building ---------------------------------------------------------
// el() builds elements with textContent, never innerHTML, so data coming from the
// server (customer names etc.) can never inject HTML or scripts.
export function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(attrs)) {
    if (value === null || value === undefined || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "dataset") Object.assign(node.dataset, value);
    else if (key.startsWith("on") && typeof value === "function") node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, value === true ? "" : value);
  }
  for (const child of children.flat()) {
    if (child === null || child === undefined || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
  return node;
}

export function statusBadge(isActive) {
  return el("span", { class: `badge ${isActive ? "badge-active" : "badge-inactive"}` }, isActive ? "Active" : "Inactive");
}

// --- Formatting -----------------------------------------------------------
const moneyFormatter = new Intl.NumberFormat("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });

/** Display-only formatting of a money string such as "1500.00" -> "1,500.00". */
export function formatMoney(value) {
  return value === null || value === undefined || value === "" ? "" : moneyFormatter.format(Number(value));
}

export function formatDateTime(value) {
  if (!value) return "";
  // The API sends UTC timestamps without a zone marker.
  const date = new Date(value.endsWith("Z") ? value : `${value}Z`);
  return date.toLocaleString();
}

// --- Lists ----------------------------------------------------------------
export function debounce(fn, waitMs = 300) {
  let timer;
  return (...args) => {
    clearTimeout(timer);
    timer = setTimeout(() => fn(...args), waitMs);
  };
}

/** Render "Prev / Page x of y / Next" controls. */
export function renderPager(container, { page, pages, total }, onChange) {
  container.replaceChildren(
    el("span", { class: "muted" }, `${total} record${total === 1 ? "" : "s"}`),
    el("div", { class: "pager-buttons" },
      el("button", { type: "button", class: "btn btn-ghost btn-sm", disabled: page <= 1, onclick: () => onChange(page - 1) }, "‹ Prev"),
      el("span", {}, pages ? `Page ${page} of ${pages}` : "No results"),
      el("button", { type: "button", class: "btn btn-ghost btn-sm", disabled: page >= pages, onclick: () => onChange(page + 1) }, "Next ›"),
    ),
  );
}

/** Read filter values from the URL so a filtered list can be bookmarked or refreshed. */
export function readQuery(defaults) {
  const params = new URLSearchParams(window.location.search);
  const result = { ...defaults };
  for (const key of Object.keys(defaults)) {
    if (params.has(key)) result[key] = params.get(key);
  }
  return result;
}

export function writeQuery(values) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== "" && value !== null && value !== undefined) params.set(key, value);
  }
  const query = params.toString();
  history.replaceState(null, "", query ? `?${query}` : window.location.pathname);
}

export function isAdmin() {
  return document.body.dataset.userRole === "ADMIN";
}
