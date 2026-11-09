// Live total PREVIEW for the order form.
//
// The authoritative calculation is on the server (app/modules/orders/calculations.py);
// whatever the browser shows, the server recalculates every amount when the order is
// saved, and the page then displays the server's figures.
//
// To match the server exactly, this uses whole paise (integers) instead of floating
// point, and the same rounding rule: 2 decimals, half-up.

/** "1500.5" -> 150050 paise. Accepts at most 2 decimals; returns null if invalid. */
export function toPaise(text) {
  const match = /^(\d+)(?:\.(\d{1,2}))?$/.exec(String(text).trim());
  if (!match) return null;
  return Number(match[1]) * 100 + Number((match[2] ?? "").padEnd(2, "0"));
}

/** 150050 -> "1500.50" */
export function paiseToString(paise) {
  return `${Math.floor(paise / 100)}.${String(paise % 100).padStart(2, "0")}`;
}

/** "12.5" -> 1250 basis points (hundredths of a percent); null if invalid. */
export function toBasisPoints(text) {
  return toPaise(text); // same shape: whole number with up to 2 decimals
}

/**
 * lines: [{ quantity: int, ratePaise: int }], discountBasisPoints: int
 * Returns paise values: { amounts, subtotal, discount, grandTotal }.
 */
export function previewTotals(lines, discountBasisPoints) {
  const amounts = lines.map((line) => line.quantity * line.ratePaise);
  const subtotal = amounts.reduce((sum, amount) => sum + amount, 0);
  // subtotal x percent / 100, rounded half-up to whole paise. In basis points:
  // subtotal x bp / 10000, and adding 5000 before integer division rounds half-up.
  const discount = Math.floor((subtotal * discountBasisPoints + 5000) / 10000);
  return { amounts, subtotal, discount, grandTotal: subtotal - discount };
}
