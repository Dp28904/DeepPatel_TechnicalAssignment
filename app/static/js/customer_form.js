import { api } from "./api.js";
import { clearErrors, confirmAction, showApiError, showFieldError, toast } from "./ui.js";

const form = document.getElementById("customer-form");
const card = form.parentElement;
const customerId = form.dataset.customerId;
const editable = form.dataset.editable === "true";
// form.elements avoids clashes with <form> properties (form.name is the form's own name).
const f = form.elements;

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
const MOBILE_RE = /^\+?\d{10,15}$/;

function readForm() {
  return {
    name: f.name.value.trim(),
    email: f.email.value.trim() || null,
    mobile: f.mobile.value.trim() || null,
    city: f.city.value.trim() || null,
    is_active: f.is_active.checked,
  };
}

function fillForm(customer) {
  f.name.value = customer.name;
  f.email.value = customer.email ?? "";
  f.mobile.value = customer.mobile ?? "";
  f.city.value = customer.city ?? "";
  f.is_active.checked = customer.is_active;
  document.getElementById("page-title").textContent = customer.name;
}

/** Quick checks for instant feedback. The server validates everything again. */
function validate(data) {
  let ok = true;
  if (!data.name) {
    showFieldError(form, "name", "Name is required.");
    ok = false;
  }
  if (data.email && !EMAIL_RE.test(data.email)) {
    showFieldError(form, "email", "Enter a valid email address.");
    ok = false;
  }
  if (data.mobile && !MOBILE_RE.test(data.mobile.replace(/[\s\-()]/g, ""))) {
    showFieldError(form, "mobile", "Mobile must be 10-15 digits, optionally starting with +.");
    ok = false;
  }
  return ok;
}

async function load() {
  try {
    fillForm(await api("GET", `/api/customers/${customerId}`));
  } catch (error) {
    showApiError(card, error);
    form.hidden = error.status === 404;
  }
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearErrors(card);
  const data = readForm();
  if (!validate(data)) return;

  const button = document.getElementById("save-button");
  try {
    if (customerId) {
      fillForm(await api("PUT", `/api/customers/${customerId}`, { body: data, button }));
      toast("Customer saved.", "success");
    } else {
      const created = await api("POST", "/api/customers", { body: data, button });
      window.location.href = `/customers/${created.id}`;
    }
  } catch (error) {
    showApiError(card, error);
  }
});

document.getElementById("delete-button")?.addEventListener("click", async (event) => {
  if (!confirmAction("Delete this customer? This cannot be undone.")) return;
  clearErrors(card);
  try {
    await api("DELETE", `/api/customers/${customerId}`, { button: event.currentTarget });
    window.location.href = "/customers";
  } catch (error) {
    showApiError(card, error); // e.g. 409 "used by N orders, deactivate instead"
  }
});

if (!editable) {
  form.querySelectorAll("input").forEach((input) => (input.disabled = true));
}
if (customerId) load();
