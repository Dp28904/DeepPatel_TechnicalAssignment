import { api } from "./api.js";
import {
  debounce, el, formatMoney, isAdmin, readQuery, renderPager, showFormError, statusBadge, writeQuery,
} from "./ui.js";

const filters = document.getElementById("filters");
const f = filters.elements;
const rows = document.getElementById("rows");
const pager = document.getElementById("pager");

const state = readQuery({ search: "", category: "", status: isAdmin() ? "all" : "active", page: "1" });
f.search.value = state.search;
if (f.status) f.status.value = state.status;

async function loadCategories() {
  const categories = await api("GET", "/api/products/categories");
  f.category.append(...categories.map((c) => el("option", { value: c }, c)));
  f.category.value = state.category;
}

async function load() {
  writeQuery(state);
  const params = new URLSearchParams({ page: state.page, page_size: 20, status: state.status });
  if (state.search) params.set("search", state.search);
  if (state.category) params.set("category", state.category);

  try {
    render(await api("GET", `/api/products?${params}`));
  } catch (error) {
    rows.replaceChildren();
    showFormError(document, error.message);
  }
}

function render(data) {
  if (!data.items.length) {
    rows.replaceChildren(el("tr", {}, el("td", { colspan: 7, class: "muted" }, "No products found.")));
  } else {
    rows.replaceChildren(
      ...data.items.map((p) =>
        el("tr", {},
          el("td", {}, el("a", { href: `/products/${p.id}` }, p.code)),
          el("td", {}, p.name),
          el("td", {}, p.category),
          el("td", { class: "num" }, formatMoney(p.price)),
          el("td", { class: "num" }, String(p.stock_quantity)),
          el("td", {}, statusBadge(p.is_active)),
          el("td", { class: "actions" }, el("a", { href: `/products/${p.id}` }, isAdmin() ? "Edit" : "View")),
        ),
      ),
    );
  }
  renderPager(pager, data, (page) => {
    state.page = String(page);
    load();
  });
}

function onFilterChange() {
  state.search = f.search.value.trim();
  state.category = f.category.value;
  if (f.status) state.status = f.status.value;
  state.page = "1";
  load();
}

filters.addEventListener("submit", (event) => event.preventDefault());
f.search.addEventListener("input", debounce(onFilterChange));
f.category.addEventListener("change", onFilterChange);
f.status?.addEventListener("change", onFilterChange);

loadCategories().catch((error) => showFormError(document, error.message));
load();
