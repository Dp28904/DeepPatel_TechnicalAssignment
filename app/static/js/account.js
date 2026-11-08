// "My account" for Admins: change own name/login email, and own password (needs the
// current password). Sales Users get a read-only page without this script.

import { api } from "./api.js";
import { checkNewPassword, checkProfile } from "./password_rules.js";
import { clearErrors, showApiError, toast } from "./ui.js";

const userId = Number(document.getElementById("account").dataset.userId);
const profileForm = document.getElementById("profile-form");
const passwordForm = document.getElementById("password-form");

profileForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const card = profileForm.parentElement;
  clearErrors(card);
  const name = profileForm.elements.name.value.trim();
  const email = profileForm.elements.email.value.trim();
  if (!checkProfile(profileForm, name, email)) return;
  try {
    const saved = await api("PUT", `/api/users/${userId}`, {
      body: { name, email },
      button: document.getElementById("profile-save"),
    });
    document.querySelector(".user-name").textContent = saved.name; // header
    toast("Saved. Use the new email next time you log in.", "success");
  } catch (error) {
    showApiError(card, error);
  }
});

passwordForm.addEventListener("submit", async (event) => {
  event.preventDefault();
  const card = passwordForm.parentElement;
  clearErrors(card);
  const f = passwordForm.elements;
  let ok = true;
  if (!f.current_password.value) {
    card.querySelector('[data-error-for="current_password"]').textContent = "Enter your current password.";
    ok = false;
  }
  ok = checkNewPassword(passwordForm, f.new_password.value, f.confirm_password.value) && ok;
  if (!ok) return;
  try {
    await api("POST", "/api/auth/password", {
      body: { current_password: f.current_password.value, new_password: f.new_password.value },
      button: document.getElementById("password-save"),
      redirectOn401: false,
    });
    passwordForm.reset();
    toast("Password changed. Other devices have been signed out.", "success");
  } catch (error) {
    showApiError(card, error); // e.g. "Current password is incorrect."
  }
});
