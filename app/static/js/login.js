// Login form: clear required/format checks, show/hide password, Caps Lock warning,
// and a disabled button while signing in. The server checks everything again and
// answers a wrong email OR password with the same message, so it never reveals
// which accounts exist.

import { api } from "./api.js";
import { clearErrors, showApiError, showFieldError, showFormError } from "./ui.js";

const form = document.getElementById("login-form");
const f = form.elements;
const button = document.getElementById("login-button");
const toggle = document.getElementById("password-toggle");
const capsWarning = document.getElementById("caps-warning");
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

function safeNext(path) {
  return path && path.startsWith("/") && !path.startsWith("//") ? path : "/";
}

function validate(email, password) {
  let firstInvalid = null;
  if (!email) {
    showFieldError(form, "email", "Enter your email address.");
    firstInvalid ??= f.email;
  } else if (!EMAIL_RE.test(email)) {
    showFieldError(form, "email", "This doesn't look like an email address. Use the format name@company.com.");
    firstInvalid ??= f.email;
  }
  if (!password) {
    showFieldError(form, "password", "Enter your password.");
    firstInvalid ??= f.password;
  }
  firstInvalid?.focus();
  return firstInvalid === null;
}

toggle.addEventListener("click", () => {
  const showing = f.password.type === "text";
  f.password.type = showing ? "password" : "text";
  toggle.textContent = showing ? "Show" : "Hide";
  toggle.setAttribute("aria-pressed", String(!showing));
  f.password.focus();
});

for (const type of ["keydown", "keyup"]) {
  f.password.addEventListener(type, (event) => {
    capsWarning.hidden = !event.getModifierState?.("CapsLock");
  });
}
f.password.addEventListener("blur", () => (capsWarning.hidden = true));

// Clear a field's message as soon as the user starts fixing it.
for (const input of [f.email, f.password]) {
  input.addEventListener("input", () => {
    input.classList.remove("is-invalid");
    form.querySelector(`[data-error-for="${input.name}"]`).textContent = "";
  });
}

form.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearErrors(form.parentElement);

  const email = f.email.value.trim();
  const password = f.password.value; // never trimmed: spaces can be part of a password
  if (!validate(email, password)) return;

  button.textContent = "Signing in…";
  try {
    await api("POST", "/api/auth/login", { body: { email, password }, button, redirectOn401: false });
    button.textContent = "Signed in ✓";
    window.location.href = safeNext(form.dataset.next);
  } catch (error) {
    button.textContent = "Sign in";
    if (error.status === 401) {
      showFormError(form.parentElement, "The email or password is incorrect.", [
        "Check that Caps Lock is off and the email is spelled correctly.",
        "If you have forgotten your password, ask your Admin to set a new one.",
      ]);
      f.password.select();
    } else {
      showApiError(form.parentElement, error);
    }
  }
});
