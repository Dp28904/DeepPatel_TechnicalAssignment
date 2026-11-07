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
