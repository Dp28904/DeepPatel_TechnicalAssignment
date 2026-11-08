// Admin: add a new Sales User or Admin.

import { api } from "./api.js";
import { MIN_PASSWORD_LENGTH, checkProfile } from "./password_rules.js";
import { clearErrors, showApiError, showFieldError } from "./ui.js";

const form = document.getElementById("new-user-form");
const f = form.elements;
const card = form.parentElement;

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearErrors(card);

  const name = f.name.value.trim();
  const email = f.email.value.trim();
  const role = form.querySelector("input[name=role]:checked")?.value;
  const password = f.password.value; // never trimmed: spaces are part of a password

  let ok = checkProfile(form, name, email);
  if (!role) {
    showFieldError(form, "role", "Choose a role.");
    ok = false;
  }
  if (password.length < MIN_PASSWORD_LENGTH) {
    showFieldError(form, "password", `Use at least ${MIN_PASSWORD_LENGTH} characters.`);
    ok = false;
  }
  if (password !== f.confirm_password.value) {
    showFieldError(form, "confirm_password", "The two passwords do not match.");
    ok = false;
  }
  if (!ok) return;

  try {
    await api("POST", "/api/users", {
      body: { name, email, role, password },
      button: document.getElementById("create-button"),
    });
    window.location.href = "/users?created=1";
  } catch (error) {
    showApiError(card, error); // e.g. "The email ... is already used by another account."
  }
});
