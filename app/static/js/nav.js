import { api } from "./api.js";
import { toast } from "./ui.js";

const logoutButton = document.getElementById("logout-button");

logoutButton?.addEventListener("click", async () => {
  try {
    await api("POST", "/api/auth/logout", { button: logoutButton });
    window.location.href = "/login";
  } catch (error) {
    toast(error.message, "error");
  }
});
