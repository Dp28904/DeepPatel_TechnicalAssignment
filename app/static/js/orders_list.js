import { api } from "./api.js";
import { orderStatusBadge } from "./orders_shared.js";
import { debounce, el, formatMoney, isAdmin, readQuery, renderPager, showFormError, writeQuery } from "./ui.js";

const filters = document.getElementById("filters");
const f = filters.elements;
const rows = document.getElementById("rows");
const pager = document.getElementById("pager");
const columns = isAdmin() ? 7 : 6;

const state = readQuery({ search: "", status: "", from: "", to: "", page: "1" });
for (const key of ["search", "status", "from", "to"]) f[key].value = state[key];

async function load() {
  writeQuery(state);
  const params = new URLSearchParams({ page: state.page, page_size: 20 });
  for (const key of ["search", "status", "from", "to"]) if (state[key]) params.set(key, state[key]);

  try {
    render(await api("GET", `/api/orders?${params}`));
  } catch (error) {
    rows.replaceChildren();
    showFormError(document, error.message);
  }
}

function render(data) {
  document.getElementById("form-error").hidden = true;
  if (!data.items.length) {
    rows.replaceChildren(el("tr", {}, el("td", { colspan: columns, class: "muted" }, "No orders found.")));
  } else {
    rows.replaceChildren(
      ...data.items.map((o) =>
        el("tr", {},
          el("td", {}, el("a", { href: `/orders/${o.id}` }, o.order_number)),
          el("td", {}, o.order_date),
          el("td", {}, o.customer_name),
          el("td", { class: "num" }, String(o.item_count)),
          el("td", { class: "num" }, formatMoney(o.grand_total)),
          el("td", {}, orderStatusBadge(o.status)),
          isAdmin() ? el("td", {}, o.created_by_name) : null,
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
  for (const key of ["search", "status", "from", "to"]) state[key] = f[key].value.trim();
  state.page = "1";
  load();
}

filters.addEventListener("submit", (event) => event.preventDefault());
f.search.addEventListener("input", debounce(onFilterChange));
for (const key of ["status", "from", "to"]) f[key].addEventListener("change", onFilterChange);

load();
