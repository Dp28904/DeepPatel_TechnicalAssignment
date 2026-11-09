import { api } from "./api.js";
import { debounce, el, isAdmin, readQuery, renderPager, showFormError, statusBadge, writeQuery } from "./ui.js";

const filters = document.getElementById("filters");
const rows = document.getElementById("rows");
const pager = document.getElementById("pager");
const f = filters.elements;

const state = readQuery({ search: "", status: isAdmin() ? "all" : "active", page: "1" });
f.search.value = state.search;
if (f.status) f.status.value = state.status;

async function load() {
  writeQuery(state);
  const params = new URLSearchParams({ page: state.page, page_size: 20, status: state.status });
  if (state.search) params.set("search", state.search);

  try {
    const data = await api("GET", `/api/customers?${params}`);
    render(data);
  } catch (error) {
    rows.replaceChildren();
    showFormError(document, error.message);
  }
}

function render(data) {
  if (!data.items.length) {
    rows.replaceChildren(el("tr", {}, el("td", { colspan: 6, class: "muted" }, "No customers found.")));
  } else {
    rows.replaceChildren(
      ...data.items.map((c) =>
        el("tr", {},
          el("td", {}, el("a", { href: `/customers/${c.id}` }, c.name)),
          el("td", {}, c.email ?? ""),
          el("td", {}, c.mobile ?? ""),
          el("td", {}, c.city ?? ""),
          el("td", {}, statusBadge(c.is_active)),
          el("td", { class: "actions" }, el("a", { href: `/customers/${c.id}` }, isAdmin() ? "Edit" : "View")),
        ),
      ),
    );
  }
  renderPager(pager, data, (page) => {
    state.page = String(page);
    load();
  });
}

filters.addEventListener("submit", (event) => event.preventDefault());
f.search.addEventListener("input", debounce(() => {
  state.search = f.search.value.trim();
  state.page = "1";
  load();
}));
f.status?.addEventListener("change", () => {
  state.status = f.status.value;
  state.page = "1";
  load();
});

load();
