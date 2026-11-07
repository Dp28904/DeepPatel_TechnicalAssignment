import { api } from "./api.js";
import { clearErrors, confirmAction, el, showApiError, showFieldError, toast } from "./ui.js";

const form = document.getElementById("product-form");
const f = form.elements; // avoids clashes with <form> properties such as form.name
const card = form.parentElement;
const productId = form.dataset.productId;
const editable = form.dataset.editable === "true";

const CODE_RE = /^[A-Za-z0-9-]{1,30}$/;
const PRICE_RE = /^\d+(\.\d{1,2})?$/; // non-negative, at most 2 decimals
const WHOLE_RE = /^\d+$/;

function readForm() {
  const data = {
    code: f.code.value.trim().toUpperCase(),
    name: f.name.value.trim(),
    category: f.category.value.trim(),
    price: f.price.value.trim(), // sent as a string so no float rounding happens
    is_active: f.is_active.checked,
  };
  if (!productId) data.stock_quantity = f.stock_quantity.value.trim();
  return data;
}

function fillForm(product) {
  f.code.value = product.code;
  f.name.value = product.name;
  f.category.value = product.category;
  f.price.value = product.price;
  f.stock_quantity.value = product.stock_quantity;
  f.is_active.checked = product.is_active;
  document.getElementById("page-title").textContent = `${product.code} · ${product.name}`;
}

/** Quick checks for instant feedback. The server validates everything again. */
function validate(data) {
  let ok = true;
  const fail = (field, message) => {
    showFieldError(form, field, message);
    ok = false;
  };
  if (!CODE_RE.test(data.code)) fail("code", "Code must be 1-30 letters, digits or dashes.");
  if (!data.name) fail("name", "Name is required.");
  if (!data.category) fail("category", "Category is required.");
  if (!PRICE_RE.test(data.price)) fail("price", "Price must be a number ≥ 0 with at most 2 decimals.");
  if (data.stock_quantity !== undefined) {
    if (!WHOLE_RE.test(data.stock_quantity)) fail("stock_quantity", "Stock must be a whole number ≥ 0.");
    else data.stock_quantity = Number(data.stock_quantity);
  }
  return ok;
}

async function loadCategories() {
  const categories = await api("GET", "/api/products/categories");
  document.getElementById("category-options").replaceChildren(...categories.map((c) => el("option", { value: c })));
}

async function load() {
  try {
    fillForm(await api("GET", `/api/products/${productId}`));
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
    if (productId) {
      fillForm(await api("PUT", `/api/products/${productId}`, { body: data, button }));
      toast("Product saved.", "success");
    } else {
      const created = await api("POST", "/api/products", { body: data, button });
      window.location.href = `/products/${created.id}`;
    }
  } catch (error) {
    showApiError(card, error);
  }
});

document.getElementById("delete-button")?.addEventListener("click", async (event) => {
  if (!confirmAction("Delete this product? This cannot be undone.")) return;
  clearErrors(card);
  try {
    await api("DELETE", `/api/products/${productId}`, { button: event.currentTarget });
    window.location.href = "/products";
  } catch (error) {
    showApiError(card, error); // e.g. 409 "referenced by stock movements, deactivate instead"
  }
});

// --- Stock adjustment (Admin) ---------------------------------------------
const adjustForm = document.getElementById("adjust-form");
if (adjustForm) {
  const a = adjustForm.elements;
  const adjustCard = adjustForm.parentElement;

  adjustForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    clearErrors(adjustCard);

    const quantity = a.quantity.value.trim();
    const reason = a.reason.value.trim();
    let ok = true;
    if (!/^[1-9]\d*$/.test(quantity)) {
      showFieldError(adjustForm, "quantity", "Enter a whole number of at least 1.");
      ok = false;
    }
    if (reason.length < 3) {
      showFieldError(adjustForm, "reason", "A reason of at least 3 characters is required.");
      ok = false;
    }
    if (!ok) return;

    const sign = a.adjustment_type.value === "INCREASE" ? "+" : "−";
    if (!confirmAction(`Apply ${sign}${quantity} to stock? Reason: "${reason}"`)) return;

    try {
      const result = await api("POST", `/api/products/${productId}/adjust-stock`, {
        body: { adjustment_type: a.adjustment_type.value, quantity: Number(quantity), reason },
        button: document.getElementById("adjust-button"),
      });
      fillForm(result.product);
      adjustForm.reset();
      toast(`Stock is now ${result.product.stock_quantity}.`, "success");
    } catch (error) {
      showApiError(adjustCard, error); // e.g. 409 "only N in stock"
    }
  });
}

if (!editable) {
  form.querySelectorAll("input").forEach((input) => (input.disabled = true));
}
if (editable) loadCategories().catch(() => {});
if (productId) load();
