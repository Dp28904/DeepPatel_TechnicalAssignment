// Admin: edit a Sales User's name/login email and set a new password.

import { api } from "./api.js";
import { checkNewPassword, checkProfile } from "./password_rules.js";
import { clearErrors, confirmAction, el, showApiError, showFormError, toast } from "./ui.js";

const panels = document.getElementById("user-panels");
const userId = Number(panels.dataset.userId);
const selfId = Number(panels.dataset.selfId);
const profileForm = document.getElementById("profile-form");
const passwordForm = document.getElementById("password-form");
const p = profileForm.elements;
const pw = passwordForm.elements;

function showNote(id, text, link) {
  const note = document.getElementById(id);
  note.replaceChildren(text, link ? el("a", { href: link.href }, link.text) : "");
  note.hidden = false;
}

function render(user) {
  document.getElementById("page-title").textContent = user.name;
  document.getElementById("role-badge").replaceChildren(
    el("span", { class: `badge badge-${user.role.toLowerCase()}` }, user.role === "ADMIN" ? "Admin" : "Sales User"));
  p.name.value = user.name;
  p.email.value = user.email;

  if (!user.can_edit_profile) {
    profileForm.querySelectorAll("input, button").forEach((node) => (node.disabled = true));
    showNote("profile-note", "Admins cannot edit another Admin's account.");
  }
  if (user.can_reset_password) {
    passwordForm.hidden = false;
  } else if (user.id === selfId) {
    showNote("password-note", "Change your own password on ", { href: "/account", text: "My account" });
  } else {
    showNote("password-note", "Admins can set passwords for Sales Users only.");
  }
  panels.hidden = false;
}

profileForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const card = profileForm.parentElement;
  clearErrors(card);
  const name = p.name.value.trim();
  const email = p.email.value.trim();
  if (!checkProfile(profileForm, name, email)) return;
  try {
    render(await api("PUT", `/api/users/${userId}`, { body: { name, email }, button: document.getElementById("profile-save") }));
    toast("Saved. The new email is now this user's login.", "success");
  } catch (error) {
    showApiError(card, error);
  }
});

passwordForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const card = passwordForm.parentElement;
  clearErrors(card);
  const password = pw.new_password.value;
  if (!checkNewPassword(passwordForm, password, pw.confirm_password.value)) return;
  if (!confirmAction(`Set a new password for ${p.name.value}?\n\nThey will be signed out everywhere and must log in with the new password.`)) return;
  try {
    await api("POST", `/api/users/${userId}/password`, {
      body: { new_password: password },
      button: document.getElementById("password-save"),
    });
    passwordForm.reset();
    toast("Password changed. The user has been signed out of all sessions.", "success");
  } catch (error) {
    showApiError(card, error);
  }
});

api("GET", `/api/users/${userId}`)
  .then(render)
  .catch((error) => showFormError(document, error.message));
