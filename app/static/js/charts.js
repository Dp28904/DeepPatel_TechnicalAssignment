// Small, dependency-free chart helpers (SVG + HTML) for the dashboard.
//
// Design rules (kept on purpose):
// - Colour is assigned by role through CSS custom properties (see app.css "Charts").
// - Thin marks: 2px lines, <=24px bars with a 4px rounded data end, square at the baseline.
// - Every chart has a hover AND keyboard-focus tooltip, and a table twin, so no value
//   is reachable only by hovering or only by colour.
// - All text is inserted with textContent (never innerHTML): names come from the database.

import { el } from "./ui.js";

const SVG_NS = "http://www.w3.org/2000/svg";

function svg(tag, attrs = {}) {
  const node = document.createElementNS(SVG_NS, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
}

// --- Number formatting ---------------------------------------------------------------
const fullFormat = new Intl.NumberFormat("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const intFormat = new Intl.NumberFormat("en-IN");
const compactFormat = new Intl.NumberFormat("en-IN", { notation: "compact", maximumFractionDigits: 1 });

export const formatAmount = (value) => fullFormat.format(Number(value));
export const formatCount = (value) => intFormat.format(Number(value));
export const formatCompact = (value) => compactFormat.format(Number(value));

/** A "nice" axis maximum and tick step for 0..max (e.g. 27,226 -> 30,000 in steps of 10,000). */
function niceScale(max, tickCount = 4) {
  if (!(max > 0)) return { max: 1, step: 0.25 };
  const rough = max / tickCount;
  const power = 10 ** Math.floor(Math.log10(rough));
  const step = [1, 2, 2.5, 5, 10].map((m) => m * power).find((s) => s >= rough);
  return { max: Math.ceil(max / step) * step, step };
}

// --- Tooltip (one shared element) ---------------------------------------------------
let tooltipNode;
function tooltip() {
  if (!tooltipNode) {
    tooltipNode = el("div", { class: "chart-tooltip", role: "status", hidden: true });
    document.body.append(tooltipNode);
  }
  return tooltipNode;
}

/** Show the tooltip near (x, y) page coordinates. Value leads, label follows. */
export function showTooltip(x, y, value, label, detail) {
  const tip = tooltip();
  const parts = [el("strong", {}, value), el("span", {}, label)];
  if (detail) parts.push(el("span", { class: "chart-tooltip-detail" }, detail));
  tip.replaceChildren(...parts); // never pass null: it would render as the text "null"
  tip.hidden = false;
  const { width, height } = tip.getBoundingClientRect();
  const left = Math.min(Math.max(8, x + 12), window.innerWidth - width - 8);
  const top = y - height - 12 < 8 ? y + 16 : y - height - 12;
  tip.style.left = `${left + window.scrollX}px`;
  tip.style.top = `${top + window.scrollY}px`;
}

export function hideTooltip() {
  if (tooltipNode) tooltipNode.hidden = true;
}

function attachTooltip(node, content) {
  const show = (x, y) => showTooltip(x, y, ...content());
  node.addEventListener("pointermove", (event) => show(event.clientX, event.clientY));
  node.addEventListener("pointerleave", hideTooltip);
  node.addEventListener("focus", () => {
    const box = node.getBoundingClientRect();
    show(box.left + box.width / 2, box.top);
  });
  node.addEventListener("blur", hideTooltip);
}

export function emptyState(container, message) {
  container.replaceChildren(el("p", { class: "chart-empty" }, message));
}

// --- Line chart (trend over time, single series) ---------------------------------------
/**
 * points: [{ label: "Aug 2026", short: "Aug", value: Number, detail: "2 orders" }]
 * The line is drawn with an area wash; the last point carries a direct label; a
 * crosshair snaps to the nearest month on hover, and arrow keys move it on focus.
 */
export function lineChart(container, points, { ariaLabel }) {
  if (!points.length) return emptyState(container, "No confirmed sales in this period.");

  const draw = () => {
    const width = Math.max(300, container.clientWidth);
    const height = 260;
    const margin = { top: 20, right: 72, bottom: 30, left: 56 };
    const plotW = width - margin.left - margin.right;
    const plotH = height - margin.top - margin.bottom;
    const { max, step } = niceScale(Math.max(...points.map((p) => p.value)));
    const x = (i) => margin.left + (points.length === 1 ? plotW / 2 : (i * plotW) / (points.length - 1));
    const y = (v) => margin.top + plotH - (v / max) * plotH;

    const root = svg("svg", {
      viewBox: `0 0 ${width} ${height}`, width: "100%", height, class: "line-chart",
      role: "img", "aria-label": ariaLabel, tabindex: 0,
    });

    // Gridlines and y-axis ticks (recessive hairlines).
    for (let v = 0; v <= max + step / 2; v += step) {
      root.append(svg("line", { x1: margin.left, x2: width - margin.right, y1: y(v), y2: y(v), class: v === 0 ? "chart-baseline" : "chart-gridline" }));
      const tick = svg("text", { x: margin.left - 8, y: y(v) + 4, "text-anchor": "end", class: "chart-tick" });
      tick.textContent = formatCompact(v);
      root.append(tick);
    }

    // X labels: thin out so they never collide.
    const every = Math.max(1, Math.ceil(points.length / Math.max(1, Math.floor(plotW / 64))));
    points.forEach((p, i) => {
      if (i % every !== 0 && i !== points.length - 1) return;
      const label = svg("text", { x: x(i), y: height - 8, "text-anchor": "middle", class: "chart-tick" });
      label.textContent = p.short;
      root.append(label);
    });

    // Area wash + 2px line.
    const line = points.map((p, i) => `${i ? "L" : "M"}${x(i)},${y(p.value)}`).join(" ");
    const baseline = y(0);
    root.append(svg("path", { d: `${line} L${x(points.length - 1)},${baseline} L${x(0)},${baseline} Z`, class: "chart-area" }));
    root.append(svg("path", { d: line, class: "chart-line" }));

    // End dot with a surface ring, and the one direct label: the latest value.
    const last = points.length - 1;
    root.append(svg("circle", { cx: x(last), cy: y(points[last].value), r: 4, class: "chart-dot" }));
    const endLabel = svg("text", { x: x(last) + 10, y: y(points[last].value) + 4, class: "chart-end-label" });
    endLabel.textContent = formatCompact(points[last].value);
    root.append(endLabel);

    // Crosshair layer.
    const cross = svg("line", { y1: margin.top, y2: margin.top + plotH, class: "chart-crosshair", visibility: "hidden" });
    const hoverDot = svg("circle", { r: 4, class: "chart-dot", visibility: "hidden" });
    root.append(cross, hoverDot);
    const hit = svg("rect", { x: margin.left - 10, y: margin.top, width: plotW + 20, height: plotH, fill: "transparent" });
    root.append(hit);

    let active = last;
    const highlight = (i, clientX, clientY) => {
      active = i;
      const p = points[i];
      for (const node of [cross]) { node.setAttribute("x1", x(i)); node.setAttribute("x2", x(i)); node.setAttribute("visibility", "visible"); }
      hoverDot.setAttribute("cx", x(i));
      hoverDot.setAttribute("cy", y(p.value));
      hoverDot.setAttribute("visibility", "visible");
      const box = root.getBoundingClientRect();
      const scale = box.width / width;
      showTooltip(clientX ?? box.left + x(i) * scale, clientY ?? box.top + y(p.value) * scale, formatAmount(p.value), p.label, p.detail);
    };
    const clear = () => {
      cross.setAttribute("visibility", "hidden");
      hoverDot.setAttribute("visibility", "hidden");
      hideTooltip();
    };
    hit.addEventListener("pointermove", (event) => {
      const box = root.getBoundingClientRect();
      const px = ((event.clientX - box.left) / box.width) * width;
      let nearest = 0;
      points.forEach((_, i) => { if (Math.abs(x(i) - px) < Math.abs(x(nearest) - px)) nearest = i; });
      highlight(nearest, event.clientX, event.clientY);
    });
    hit.addEventListener("pointerleave", clear);
    root.addEventListener("focus", () => highlight(active));
    root.addEventListener("blur", clear);
    root.addEventListener("keydown", (event) => {
      if (event.key === "ArrowLeft") highlight(Math.max(0, active - 1));
      else if (event.key === "ArrowRight") highlight(Math.min(last, active + 1));
      else return;
      event.preventDefault();
    });

    container.replaceChildren(root);
  };

  draw();
  if (!container._resizeObserver) {
    let lastWidth = container.clientWidth;
    container._resizeObserver = new ResizeObserver(() => {
      if (Math.abs(container.clientWidth - lastWidth) > 4) {
        lastWidth = container.clientWidth;
        draw();
      }
    });
    container._resizeObserver.observe(container);
  }
  container._redraw = draw;
}

// --- Ranked horizontal bars (compare magnitude, one hue) -------------------------------
/**
 * rows: [{ label, sublabel?, href?, value: Number, valueText, detail? }], largest first.
 * The value is printed at the bar tip; the whole row is the hover/focus target.
 */
export function barList(container, rows, { emptyMessage, ariaLabel }) {
  if (!rows.length) return emptyState(container, emptyMessage);
  const max = Math.max(...rows.map((r) => r.value)) || 1;
  const list = el("ol", { class: "bar-list", "aria-label": ariaLabel });
  for (const row of rows) {
    const bar = el("span", { class: "bar-list-bar" });
    // Length is proportional to the value within the space left after reserving room
    // for the label at the tip, so a bar is never clipped to the same length as another.
    bar.style.width = `max(2px, calc((100% - var(--bar-label-room)) * ${row.value / max}))`;
    const item = el("li", { class: "bar-list-row", tabindex: 0 },
      el("span", { class: "bar-list-label" },
        row.href ? el("a", { href: row.href, tabindex: -1 }, row.label) : row.label,
        row.sublabel ? el("span", { class: "bar-list-sublabel" }, row.sublabel) : null,
      ),
      el("span", { class: "bar-list-track" }, bar, el("span", { class: "bar-list-value" }, row.valueText)),
    );
    attachTooltip(item, () => [row.valueText, row.label, row.detail]);
    list.append(item);
  }
  container.replaceChildren(list);
}

// --- Tall segmented bar (one whole split into <= 6 parts) ----------------------------
/**
 * parts: [{ label, value: Number, colorVar: "--viz-series-1", detail }]
 * Each part is a block with a 2px gap; its share is printed inside only when it fits;
 * a legend lists the names in block order. Zero parts draw no block.
 */
export function segmentedBar(container, parts, { emptyMessage, ariaLabel }) {
  const total = parts.reduce((sum, p) => sum + p.value, 0);
  if (!total) return emptyState(container, emptyMessage);

  const bar = el("div", { class: "segmented-bar", role: "img", "aria-label": ariaLabel });
  for (const part of parts) {
    if (!part.value) continue;
    const share = `${Math.round((part.value / total) * 100)}%`;
    const block = el("div", { class: "segmented-block", tabindex: 0, "aria-label": `${part.label}: ${part.detail}, ${share}` },
      el("span", { class: "segmented-label" }, share));
    block.style.flexGrow = String(part.value);
    block.style.background = `var(${part.colorVar})`;
    attachTooltip(block, () => [share, part.label, part.detail]);
    bar.append(block);
  }
  const legend = el("ul", { class: "chart-legend" },
    ...parts.map((part) => el("li", {},
      el("span", { class: "legend-swatch", style: `background: var(${part.colorVar})` }),
      `${part.label} (${part.detail})`)));
  container.replaceChildren(bar, legend);

  // Print the share inside a block only if it fits with padding; otherwise the
  // tooltip, the legend and the table view carry it.
  requestAnimationFrame(() => {
    for (const block of bar.children) {
      const label = block.firstChild;
      label.hidden = label.scrollWidth + 16 > block.clientWidth;
    }
  });
}

// --- Meters (stock against a threshold) ------------------------------------------------
/**
 * items: [{ label, sublabel, href, value: Number, max: Number }]
 * Severity is carried by the fill AND by an icon + word, never by colour alone.
 */
export function meterList(container, items, { emptyMessage }) {
  if (!items.length) return emptyState(container, emptyMessage);
  const list = el("ul", { class: "meter-list" });
  for (const item of items) {
    const ratio = Math.min(1, item.value / item.max);
    const level = item.value === 0 ? "critical" : ratio < 0.5 ? "warning" : "accent";
    const status = { critical: ["✕", "Out of stock"], warning: ["!", "Very low"], accent: ["↓", "Low"] }[level];
    const fill = el("span", { class: `meter-fill meter-${level}` });
    fill.style.width = `${Math.max(item.value ? 4 : 0, ratio * 100)}%`;
    list.append(el("li", { class: "meter-row" },
      el("span", { class: "bar-list-label" },
        el("a", { href: item.href }, item.label),
        el("span", { class: "bar-list-sublabel" }, item.sublabel)),
      el("span", { class: "meter-track", role: "meter", "aria-valuemin": 0, "aria-valuemax": item.max, "aria-valuenow": item.value, "aria-label": `${item.label} stock` }, fill),
      el("span", { class: `meter-status meter-status-${level}` },
        el("span", { class: "meter-icon", "aria-hidden": "true" }, status[0]),
        `${item.value} left · ${status[1]}`),
    ));
  }
  container.replaceChildren(list);
}

// --- Table twin -------------------------------------------------------------------------
/** columns: [{ label, value: (row) => text, numeric? }] */
export function dataTable(rows, columns) {
  return el("table", { class: "data-table" },
    el("thead", {}, el("tr", {}, ...columns.map((c) => el("th", { class: c.numeric ? "num" : "" }, c.label)))),
    el("tbody", {}, ...(rows.length
      ? rows.map((row) => el("tr", {}, ...columns.map((c) => el("td", { class: c.numeric ? "num" : "" }, c.value(row)))))
      : [el("tr", {}, el("td", { colspan: columns.length, class: "muted" }, "No data for this period."))])),
  );
}
