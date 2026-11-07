import { api } from "./api.js";
import { clearErrors, showApiError, showFieldError } from "./ui.js";

const form = document.getElementById("login-form");

function safeNext(path) {
  return path && path.startsWith("/") && !path.startsWith("//") ? path : "/";
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearErrors(form.parentElement);

  const email = form.email.value.trim();
  const password = form.password.value;

  // Quick client-side checks; the server validates again.
  let valid = true;
  if (!email) {
    showFieldError(form, "email", "Email is required.");
    valid = false;
  }
  if (!password) {
    showFieldError(form, "password", "Password is required.");
    valid = false;
  }
  if (!valid) return;

  try {
    await api("POST", "/api/auth/login", {
      body: { email, password },
      button: form.querySelector("button[type=submit]"),
      redirectOn401: false,
    });
    window.location.href = safeNext(form.dataset.next);
  } catch (error) {
    showApiError(form.parentElement, error);
  }
});
