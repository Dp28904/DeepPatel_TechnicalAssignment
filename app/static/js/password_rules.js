// Shared client-side checks for name/email and new-password forms.
// The server validates everything again; these give instant, clear messages.

import { showFieldError } from "./ui.js";

export const MIN_PASSWORD_LENGTH = 8;
const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function checkProfile(form, name, email) {
  let ok = true;
  if (!name) {
    showFieldError(form, "name", "Name is required.");
    ok = false;
  }
  if (!EMAIL_RE.test(email)) {
    showFieldError(form, "email", "Enter a valid email address.");
    ok = false;
  }
  return ok;
}

export function checkNewPassword(form, password, repeat) {
  let ok = true;
  if (password.length < MIN_PASSWORD_LENGTH) {
    showFieldError(form, "new_password", `Use at least ${MIN_PASSWORD_LENGTH} characters.`);
    ok = false;
  }
  if (password !== repeat) {
    showFieldError(form, "confirm_password", "The two passwords do not match.");
    ok = false;
  }
  return ok;
}
