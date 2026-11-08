import { api } from "./api.js";
import { el, showFormError, statusBadge, toast } from "./ui.js";

const rows = document.getElementById("rows");
const selfId = Number(document.body.dataset.userId);

function roleBadge(role) {
  return el("span", { class: `badge badge-${role.toLowerCase()}` }, role === "ADMIN" ? "Admin" : "Sales User");
}

async function load() {
  try {
    const users = await api("GET", "/api/users");
    rows.replaceChildren(...users.map((u) => el("tr", {},
      el("td", {}, u.name, u.id === selfId ? el("span", { class: "muted" }, " (you)") : null),
      el("td", {}, u.email),
      el("td", {}, roleBadge(u.role)),
      el("td", {}, statusBadge(u.is_active)),
      el("td", { class: "actions" },
        u.id === selfId
          ? el("a", { class: "btn btn-ghost btn-sm", href: "/account" }, "My account")
          : u.can_edit_profile
            ? el("a", { class: "btn btn-ghost btn-sm", href: `/users/${u.id}` }, "Edit")
            : el("span", { class: "muted" }, "Admin account")),
    )));
  } catch (error) {
    rows.replaceChildren();
    showFormError(document, error.message);
  }
}

load();

if (new URLSearchParams(window.location.search).get("created")) {
  toast("User created. They can log in now with the email and password you set.", "success");
  history.replaceState(null, "", "/users");
}
