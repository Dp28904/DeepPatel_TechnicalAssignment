import { el } from "./ui.js";

const LABELS = { DRAFT: "Draft", CONFIRMED: "Confirmed", CANCELLED: "Cancelled" };

export function orderStatusBadge(status) {
  return el("span", { class: `badge badge-${status.toLowerCase()}` }, LABELS[status] ?? status);
}
