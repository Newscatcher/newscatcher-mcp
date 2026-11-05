#!/usr/bin/env node
/**
 * NewsCatcher report renderer.
 *
 * Turns files saved by the NewsCatcher MCP tools into one self-contained HTML report (charts, tables, links) and
 * prints a short markdown summary of the key numbers for the chat. The model never has to retype the data.
 * No dependencies, no network, never reads an API key. Node 18+.
 *
 *   node render-report.mjs --title "Acme launch coverage" --subtitle "Oct 1 – Nov 4, 2026" \
 *     --articles "All coverage=clips.json"   list_articles(save_as="json"|"csv")
 *     --counts "Daily volume=counts.json"    count_articles(save_as="json"|"csv")
 *     --stories "Main stories=stories.json"  search_news(save_as="json"|"csv")
 *     --rows "Competitor news=rows.json"     export_research(file_format="json"|"csv")
 *     --notes notes.md                       a short analysis written by the model (markdown); "-" reads stdin
 *     --method "Queries and filters …"       extra method notes
 *     --out report.html                      default ./newscatcher-exports/report-<title>-<date>.html
 *
 * Every input flag can repeat; "Label=path" names the section, a bare path uses a default label.
 */
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { dirname, resolve, basename } from "node:path";

// ------------------------------------------------------------------ arguments
const KINDS = ["articles", "counts", "stories", "rows"];
function parseArgs(argv) {
  const o = { inputs: [], method: [] };
  for (let i = 0; i < argv.length; i++) {
    const k = argv[i];
    const v = argv[i + 1];
    const need = () => {
      if (v === undefined || v.startsWith("--")) fail(`${k} needs a value`);
      i++;
      return v;
    };
    if (k === "--help" || k === "-h") o.help = true;
    else if (k === "--title") o.title = need();
    else if (k === "--subtitle") o.subtitle = need();
    else if (k === "--notes") o.notes = need();
    else if (k === "--method") o.method.push(need());
    else if (k === "--out") o.out = need();
    else if (KINDS.includes(k.slice(2))) {
      const raw = need();
      const eq = raw.indexOf("=");
      const looksLabelled = eq > 0 && !/^[a-zA-Z]:[\\/]/.test(raw);
      o.inputs.push({ kind: k.slice(2), label: looksLabelled ? raw.slice(0, eq).trim() : "", path: looksLabelled ? raw.slice(eq + 1).trim() : raw });
    } else fail(`unknown option ${k} (see --help)`);
  }
  return o;
}
function fail(msg) {
  process.stderr.write(`render-report: ${msg}\n`);
  process.exit(1);
}

// ------------------------------------------------------------------ reading files
function readText(p) {
  try {
    return readFileSync(p === "-" ? 0 : p, "utf8").replace(/^\uFEFF/, ""); // "-" = stdin (notes via a heredoc)
  } catch (e) {
    fail(`can't read ${p}: ${e.message}`);
  }
}
/** RFC 4180 CSV → array of objects keyed by the header row. */
function parseCsv(text) {
  const rows = [];
  let row = [], field = "", q = false;
  for (let i = 0; i < text.length; i++) {
    const c = text[i];
    if (q) {
      if (c === '"') {
        if (text[i + 1] === '"') { field += '"'; i++; } else q = false;
      } else field += c;
    } else if (c === '"') q = true;
    else if (c === ",") { row.push(field); field = ""; }
    else if (c === "\n" || c === "\r") {
      if (c === "\r" && text[i + 1] === "\n") i++;
      row.push(field); field = "";
      if (row.length > 1 || row[0] !== "") rows.push(row);
      row = [];
    } else field += c;
  }
  if (field !== "" || row.length) { row.push(field); rows.push(row); }
  const [head = [], ...body] = rows;
  return body.map((r) => Object.fromEntries(head.map((h, i) => [h.trim(), r[i] ?? ""])));
}
function readData(p) {
  const t = readText(p);
  if (/\.csv$/i.test(p)) return parseCsv(t);
  try {
    let d = JSON.parse(t);
    // a saved MCP tool result: {"content":[{"type":"text","text":"<json>"}]} or {"result":"<json>"}
    if (d && typeof d === "object" && !Array.isArray(d)) {
      const inner = d.result ?? d.content?.[0]?.text;
      if (typeof inner === "string" && /^\s*[[{]/.test(inner)) d = JSON.parse(inner);
    }
    return d;
  } catch (e) {
    fail(`${p} is not valid JSON or CSV: ${e.message}`);
  }
}

// ------------------------------------------------------------------ helpers
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]);
const safeUrl = (u) => (typeof u === "string" && /^https?:\/\//i.test(u.trim()) ? u.trim() : "");
const link = (u, text) => (safeUrl(u) ? `<a href="${esc(safeUrl(u))}" target="_blank" rel="noopener noreferrer">${esc(text)}</a>` : esc(text));
const num = (n) => (n === null || n === undefined || Number.isNaN(n) ? "n/a" : Number(n).toLocaleString("en-US"));
const many = (n, one, other = `${one}s`) => `${num(n)} ${n === 1 ? one : other}`;
const pct = (x, digits = 1) => `${(100 * x).toFixed(digits)}%`;
const clip = (s, n) => { const t = String(s ?? "").replace(/\s+/g, " ").trim(); return t.length > n ? `${t.slice(0, n - 1)}…` : t; };
const compact = (n) => (Math.abs(n) >= 1e6 ? `${+(n / 1e6).toFixed(1)}M` : Math.abs(n) >= 1e4 ? `${+(n / 1e3).toFixed(1)}K` : n.toLocaleString("en-US"));
const jsonScript = (id, data) => `<script type="application/json" id="${id}">${JSON.stringify(data).replace(/</g, "\\u003c")}</script>`;
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];
function toDate(s) {
  if (!s) return null;
  let t = String(s).trim();
  if (/^\d{4}-\d{2}-\d{2} \d/.test(t)) t = t.replace(" ", "T");
  if (/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}(:\d{2}(\.\d+)?)?$/.test(t)) t += "Z";
  const d = new Date(t);
  return Number.isNaN(d.getTime()) ? null : d;
}
const isoDay = (d) => d.toISOString().slice(0, 10);
const shortDay = (d) => `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}`;
const longDay = (d) => `${MONTHS[d.getUTCMonth()]} ${d.getUTCDate()}, ${d.getUTCFullYear()}`;
function dayLabel(label) {
  if (/^\d{4}-\d{2}$/.test(label)) { const [y, m] = label.split("-"); return `${MONTHS[+m - 1]} ${y}`; }
  const d = toDate(label);
  return d ? shortDay(d) : label;
}
function countBy(items, key) {
  const m = new Map();
  for (const it of items) { const k = key(it); if (k) m.set(k, (m.get(k) ?? 0) + 1); }
  return [...m.entries()].sort((a, b) => b[1] - a[1]);
}
function niceMax(v) {
  if (v <= 0) return 1;
  const p = 10 ** Math.floor(Math.log10(v));
  for (const m of [1, 1.2, 1.5, 2, 2.5, 3, 4, 5, 6, 8, 10]) if (m * p >= v) return m * p;
  return 10 * p;
}
let uid = 0;
const nextId = (p) => `${p}${++uid}`;

const SERIES = 5; // categorical slots used (validated light + dark, adjacent pairs)

// ------------------------------------------------------------------ normalising inputs
function normArticles(d) {
  const list = Array.isArray(d) ? d : d?.articles ?? d?.results ?? [];
  return list.map((r) => ({
    published_at: r.published_at,
    date: toDate(r.published_at),
    title: r.title ?? "",
    title_en: r.title_en && r.title_en !== r.title ? r.title_en : "",
    source: (typeof r.source === "object" ? r.source?.name : r.source) || r.domain || r.source?.domain || "",
    domain: r.domain || (typeof r.source === "object" ? r.source?.domain : "") || "",
    country: r.country ?? "",
    language: r.language ?? "",
    author: r.author ?? "",
    rank: Number(r.rank) > 0 && Number(r.rank) < 999999 ? Number(r.rank) : null,
    url: r.url ?? "",
    snippet: r.snippet ?? "",
  }));
}
function normCounts(d) {
  if (Array.isArray(d)) {
    // CSV written by count_articles: bucket,from,to,partial,<query>…
    const queries = Object.keys(d[0] ?? {}).filter((k) => !["bucket", "from", "to", "partial"].includes(k));
    return {
      queries,
      interval: "",
      buckets: d.map((r) => ({ label: r.bucket, from: r.from, to: r.to, partial: r.partial === "yes", counts: Object.fromEntries(queries.map((q) => [q, r[q] === "" || r[q] === "n/a" ? null : Number(r[q])])) })),
    };
  }
  const buckets = (d?.buckets ?? []).map((b) => ({ ...b, label: b.label ?? String(b.from ?? "").slice(0, d?.interval === "month" ? 7 : 10) }));
  const queries = d?.queries ?? Object.keys(buckets[0]?.counts ?? d?.totals ?? {});
  return { ...d, queries, buckets };
}
function normStories(d) {
  const list = Array.isArray(d) ? d : d?.results ?? [];
  return {
    meta: Array.isArray(d) ? {} : d,
    items: list.map((r) => ({
      date: toDate(r.published_at),
      title: r.title ?? "",
      title_en: r.title_en && r.title_en !== r.title ? r.title_en : "",
      summary: r.summary || r.summary_en || r.snippet || "",
      source: (typeof r.source === "object" ? r.source?.name : r.source) || r.domain || "",
      story_id: r.story_id || r.story?.id || "",
      newsrooms: Number(r.newsrooms || r.story?.newsrooms || 0) || null,
      url: r.url ?? "",
    })),
  };
}
function normRows(d) {
  const rows = Array.isArray(d) ? d : d?.rows ?? [];
  const columns = (!Array.isArray(d) && d?.columns) || [...new Set(rows.flatMap((r) => Object.keys(r)))];
  return { rows, columns };
}

// ------------------------------------------------------------------ charts (inline SVG)
/** Multi-series line chart over buckets with a crosshair tooltip; null values leave gaps. */
function lineChart(labels, series, opts = {}) {
  const W = 960, H = 280, L = 52, R = 18, T = 14, B = 30;
  const n = labels.length;
  const max = niceMax(Math.max(1, ...series.flatMap((s) => s.values.filter((v) => v !== null))));
  const x = (i) => (n === 1 ? L + (W - L - R) / 2 : L + (i * (W - L - R)) / (n - 1));
  const y = (v) => T + (H - T - B) * (1 - v / max);
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((f) => f * max);
  const useCompact = max >= 10000;
  const grid = ticks
    .map((t) => `<line x1="${L}" x2="${W - R}" y1="${y(t).toFixed(1)}" y2="${y(t).toFixed(1)}" class="${t === 0 ? "axis" : "grid"}"/><text x="${L - 8}" y="${(y(t) + 4).toFixed(1)}" class="tick" text-anchor="end">${useCompact ? compact(t) : Math.round(t).toLocaleString("en-US")}</text>`)
    .join("");
  const step = Math.max(1, Math.ceil(n / 8));
  const xl = labels
    .map((lab, i) => (i % step === 0 || i === n - 1) && !(i !== n - 1 && n - 1 - i < step / 2) ? `<text x="${x(i).toFixed(1)}" y="${H - 8}" class="tick" text-anchor="middle">${esc(dayLabel(lab))}</text>` : "")
    .join("");
  const paths = series
    .map((s, si) => {
      let d = "", pen = false;
      s.values.forEach((v, i) => {
        if (v === null) { pen = false; return; }
        d += `${pen ? "L" : "M"}${x(i).toFixed(1)},${y(v).toFixed(1)}`;
        pen = true;
      });
      const area = series.length === 1 && n > 1 && s.values.every((v) => v !== null)
        ? `<path d="${d}L${x(n - 1).toFixed(1)},${y(0).toFixed(1)}L${x(0).toFixed(1)},${y(0).toFixed(1)}Z" class="wash" style="fill:var(--series-${si + 1})"/>`
        : "";
      let last = -1;
      s.values.forEach((v, i) => { if (v !== null) last = i; });
      const dot = last >= 0 ? `<circle cx="${x(last).toFixed(1)}" cy="${y(s.values[last]).toFixed(1)}" r="4" class="dot" style="fill:var(--series-${si + 1})"/>` : "";
      return `${area}<path d="${d}" class="line" style="stroke:var(--series-${si + 1})"/>${dot}`;
    })
    .join("");
  const id = nextId("lc");
  const data = { labels: labels.map(dayLabel), partial: opts.partial ?? [], series: series.map((s) => ({ name: s.name, values: s.values })), x: labels.map((_, i) => +x(i).toFixed(1)), y: series.map((s) => s.values.map((v) => (v === null ? null : +y(v).toFixed(1)))), top: T, bottom: H - B, width: W };
  return `<figure class="chart" data-line="${id}">
<svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opts.aria ?? "Line chart")}">${grid}${xl}${paths}
<line class="cross" x1="0" x2="0" y1="${T}" y2="${H - B}" visibility="hidden"/>
<g class="hover-dots"></g>
<rect class="hit" x="${L}" y="${T}" width="${W - L - R}" height="${H - T - B}" tabindex="0" aria-label="Move with arrow keys to read values"/></svg>
${jsonScript(id, data)}</figure>`;
}

/** Single-series columns (one per bucket) with a per-column tooltip. */
function columnChart(points, opts = {}) {
  const W = 960, H = 220, L = 52, R = 18, T = 12, B = 28;
  const n = points.length;
  const max = niceMax(Math.max(1, ...points.map((p) => p.value)));
  const slot = (W - L - R) / Math.max(1, n);
  const bw = Math.max(2, Math.min(24, slot - 2));
  const y = (v) => T + (H - T - B) * (1 - v / max);
  const ticks = [0, 0.5, 1].map((f) => f * max);
  const grid = ticks
    .map((t) => `<line x1="${L}" x2="${W - R}" y1="${y(t).toFixed(1)}" y2="${y(t).toFixed(1)}" class="${t === 0 ? "axis" : "grid"}"/><text x="${L - 8}" y="${(y(t) + 4).toFixed(1)}" class="tick" text-anchor="end">${max >= 10000 ? compact(t) : Math.round(t).toLocaleString("en-US")}</text>`)
    .join("");
  const step = Math.max(1, Math.ceil(n / 8));
  const bars = points
    .map((p, i) => {
      const cx = L + slot * i + slot / 2;
      const x0 = cx - bw / 2, top = y(p.value), base = y(0);
      const r = Math.min(4, bw / 2, base - top);
      const d = p.value > 0
        ? `M${x0.toFixed(1)},${base.toFixed(1)}V${(top + r).toFixed(1)}Q${x0.toFixed(1)},${top.toFixed(1)} ${(x0 + r).toFixed(1)},${top.toFixed(1)}H${(x0 + bw - r).toFixed(1)}Q${(x0 + bw).toFixed(1)},${top.toFixed(1)} ${(x0 + bw).toFixed(1)},${(top + r).toFixed(1)}V${base.toFixed(1)}Z`
        : "";
      const lab = i % step === 0 ? `<text x="${cx.toFixed(1)}" y="${H - 8}" class="tick" text-anchor="middle">${esc(p.short)}</text>` : "";
      return `<g class="col" tabindex="0" data-tip-label="${esc(p.label)}" data-tip-value="${esc(num(p.value))} ${esc(opts.unit ?? "")}"><rect class="hit" x="${(L + slot * i).toFixed(1)}" y="${T}" width="${slot.toFixed(1)}" height="${H - T - B}"/>${d ? `<path d="${d}" style="fill:var(--series-1)"/>` : ""}</g>${lab}`;
    })
    .join("");
  return `<figure class="chart"><svg viewBox="0 0 ${W} ${H}" role="img" aria-label="${esc(opts.aria ?? "Column chart")}">${grid}${bars}</svg></figure>`;
}

/** Horizontal bars as an HTML list: name, bar, value. */
function barList(entries, total, opts = {}) {
  if (!entries.length) return `<p class="muted">None.</p>`;
  const max = Math.max(...entries.map((e) => e[1]));
  return `<ol class="bars">${entries
    .map(([name, v, extra]) => `<li><span class="bl-name" title="${esc(extra ? `${name} · ${extra}` : name)}">${esc(clip(name, 48))}${extra ? ` <span class="muted">· ${esc(extra)}</span>` : ""}</span><span class="bl-track"><span class="bl-bar" style="width:${((100 * v) / max).toFixed(1)}%"></span></span><span class="bl-val">${num(v)}${total ? ` <span class="muted">${pct(v / total, 0)}</span>` : ""}</span></li>`)
    .join("")}</ol>${opts.note ? `<p class="muted small">${esc(opts.note)}</p>` : ""}`;
}

/** Tall segmented bar: one whole split into parts, with its legend (left out when a chart below carries it). */
function shareBar(parts, withLegend = true) {
  const total = parts.reduce((s, p) => s + p.value, 0) || 1;
  const blocks = parts
    .map((p, i) => {
      const share = p.value / total;
      if (p.value <= 0) return "";
      const ink = i === 3 ? "#0b0b0b" : "#ffffff"; // slot 4 (yellow) takes near-black text
      return `<span class="seg" tabindex="0" style="flex:${share.toFixed(4)};background:var(--series-${i + 1});color:${ink}" data-tip-label="${esc(p.name)}" data-tip-value="${pct(share)} · ${num(p.value)}">${share >= 0.08 ? pct(share, 0) : ""}</span>`;
    })
    .join("");
  const legend = parts.map((p, i) => `<span class="key"><span class="swatch" style="background:var(--series-${i + 1})"></span>${esc(p.name)}</span>`).join("");
  return `<div class="segbar" role="img" aria-label="${esc(parts.map((p) => `${p.name} ${pct(p.value / total)}`).join(", "))}">${blocks}</div>${withLegend ? `<div class="legend">${legend}</div>` : ""}`;
}

const tiles = (items) => `<div class="tiles">${items.map((t) => `<div class="tile"><div class="tile-label">${esc(t.label)}</div><div class="tile-value">${esc(t.value)}</div>${t.sub ? `<div class="tile-sub">${esc(t.sub)}</div>` : ""}</div>`).join("")}</div>`;

function table(cols, rows, opts = {}) {
  const cls = (c) => [c.num ? "num" : "", c.nowrap ? "nowrap" : ""].filter(Boolean).join(" ");
  const attr = (c) => (cls(c) ? ` class="${cls(c)}"` : "");
  return `<div class="table-wrap"><table${opts.cls ? ` class="${opts.cls}"` : ""}><thead><tr>${cols.map((c) => `<th${attr(c)}>${esc(c.label)}</th>`).join("")}</tr></thead><tbody>${rows
    .map((r) => `<tr>${cols.map((c) => `<td${attr(c)}>${c.html ? c.html(r) : esc(c.get(r))}</td>`).join("")}</tr>`)
    .join("")}</tbody></table></div>`;
}

// ------------------------------------------------------------------ sections
const summary = [];
const method = [];

function countsSection(label, d, file) {
  const c = normCounts(d);
  const qs = c.queries.slice(0, SERIES);
  const dropped = c.queries.length - qs.length;
  const totals = qs.map((q) => c.buckets.reduce((s, b) => s + (b.counts?.[q] ?? 0), 0));
  const all = totals.reduce((s, v) => s + v, 0) || 1;
  const gaps = c.buckets.filter((b) => qs.some((q) => b.counts?.[q] === null || b.counts?.[q] === undefined)).length;
  const peaks = qs.map((q) => {
    let best = null;
    for (const b of c.buckets) if (b.counts?.[q] !== null && b.counts?.[q] !== undefined && (!best || b.counts[q] > best.counts[q])) best = b;
    return best ? `${q}: ${dayLabel(best.label)}${best.partial ? " (partial)" : ""}, ${num(best.counts[q])}` : "";
  }).filter(Boolean);
  const unit = { day: "day", week: "week", month: "month" }[c.interval] ?? "bucket";
  let h = `<section><h2>${esc(label || (qs.length > 1 ? "Share of voice" : "Coverage over time"))}</h2>`;
  h += `<p class="lede">Exact article counts per ${unit}, ${esc(dayLabel(c.buckets[0]?.label ?? ""))} to ${esc(dayLabel(c.buckets.at(-1)?.label ?? ""))}.</p>`;
  if (qs.length > 1) h += shareBar(qs.map((q, i) => ({ name: q, value: totals[i] })), c.buckets.length < 2);
  if (c.buckets.length > 1) {
    // one legend serves the share bar above and the lines below (same colour per query)
    if (qs.length > 1) h += `<div class="legend">${qs.map((q, i) => `<span class="key"><span class="linekey" style="background:var(--series-${i + 1})"></span>${esc(q)} <span class="muted">${num(totals[i])}</span></span>`).join("")}</div>`;
    h += lineChart(c.buckets.map((b) => b.label), qs.map((q) => ({ name: q, values: c.buckets.map((b) => (b.counts?.[q] ?? null)) })), { partial: c.buckets.map((b) => !!b.partial), aria: `Articles per ${unit}` });
  }
  if (peaks.length && c.buckets.length > 1) h += `<p><strong>Peak ${esc(unit)}:</strong> ${peaks.map(esc).join(" · ")}</p>`;
  const notes = [
    c.buckets.at(-1)?.partial ? `The last ${unit} is partial.` : "",
    gaps ? `${gaps} ${unit}${gaps > 1 ? "s" : ""} could not be counted (n/a); totals cover the counted ones.` : "",
    dropped > 0 ? `${dropped} more ${dropped > 1 ? "queries are" : "query is"} in the file but not charted (5 at most).` : "",
  ].filter(Boolean);
  if (notes.length) h += `<p class="muted small">${notes.map(esc).join(" ")}</p>`;
  const cols = [{ label: unit, get: (b) => `${dayLabel(b.label)}${b.partial ? " (partial)" : ""}` }, ...qs.map((q) => ({ label: q, num: true, get: (b) => num(b.counts?.[q] ?? null) }))];
  const foot = { label: "Total", partial: false, counts: Object.fromEntries(qs.map((q, i) => [q, totals[i]])) };
  const share = qs.length > 1 ? [{ label: "Share", counts: Object.fromEntries(qs.map((q, i) => [q, pct(totals[i] / all)])) }] : [];
  h += `<details><summary>Table</summary>${table(cols, [...c.buckets, foot], { cls: "numbers" })}${share.length ? `<p class="small">Share of voice: ${qs.map((q, i) => `${esc(q)} ${pct(totals[i] / all)}`).join(" · ")}</p>` : ""}</details></section>`;
  summary.push(`- ${label || "Counts"}: ${qs.map((q, i) => `${q} ${num(totals[i])}${qs.length > 1 ? ` (${pct(totals[i] / all)})` : ""}`).join(", ")}${peaks.length && c.buckets.length > 1 ? ` · peak ${peaks.join("; ")}` : ""}`);
  method.push(`${label || "Counts"}: count_articles, queries ${qs.map((q) => `«${q}»`).join(", ")}${c.search_in ? `, searched in ${[].concat(c.search_in).join("/")}` : ""}${c.interval ? `, per ${c.interval}` : ""}${c.filters && Object.keys(c.filters).length ? `, filters ${JSON.stringify(c.filters)}` : ""} (${basename(file)})`);
  return { html: h, tiles: qs.length > 1 ? [{ label: "Leader", value: clip(qs[totals.indexOf(Math.max(...totals))], 40), sub: `${pct(Math.max(...totals) / all)} share of voice` }] : [{ label: "Articles counted", value: compact(totals[0] ?? 0), sub: label || clip(qs[0], 48) }] };
}

const NOT_PERSON = /\b(staff|admin|editor|editorial|desk|team|news|newswire|wire|press|provided|media|agency|reuters|afp|associated|bloomberg|dpa|pti|ians|bureau|correspondent|contributor|club|chronicle|times|post|herald|journal|gazette|daily|tribune|online|magazine|redaktion|redacci[oó]n|r[eé]daction)\b/i;
function person(a) {
  const au = String(a ?? "").replace(/^by\s+/i, "").split(/,| and | & |\|/)[0].trim();
  const words = au.split(/\s+/);
  if (!au || au.length > 60 || words.length < 2 || words.length > 5 || NOT_PERSON.test(au) || /\d|@|https?:/.test(au)) return "";
  return au;
}

function articlesSection(label, d, file) {
  const arts = normArticles(d);
  const name = label || "Coverage";
  const dated = arts.filter((a) => a.date);
  const outletOf = (a) => a.domain || a.source;
  const outlets = new Map();
  for (const a of arts) {
    const k = outletOf(a);
    if (!k) continue;
    const o = outlets.get(k) ?? { name: a.source || a.domain, count: 0, rank: null, latest: null, best: null };
    o.count++;
    if (a.rank && (!o.rank || a.rank < o.rank)) o.rank = a.rank;
    if (a.date && (!o.latest || a.date > o.latest)) o.latest = a.date;
    if (!o.best || (a.date && o.best.date && a.date > o.best.date)) o.best = a;
    outlets.set(k, o);
  }
  const countries = countBy(arts, (a) => a.country?.toUpperCase());
  const langs = countBy(arts, (a) => a.language?.toLowerCase());
  const authors = new Map();
  for (const a of arts) {
    const p = person(a.author);
    if (!p) continue;
    const e = authors.get(p) ?? { count: 0, outlets: new Map() };
    e.count++;
    e.outlets.set(a.source || a.domain, (e.outlets.get(a.source || a.domain) ?? 0) + 1);
    authors.set(p, e);
  }
  const first = dated.length ? new Date(Math.min(...dated.map((a) => a.date))) : null;
  const last = dated.length ? new Date(Math.max(...dated.map((a) => a.date))) : null;
  let h = `<section><h2>${esc(name)}</h2><p class="lede">${many(arts.length, "article")} from ${many(outlets.size, "outlet")}${first ? (isoDay(first) === isoDay(last) ? `, on ${esc(longDay(first))}` : `, ${esc(longDay(first))} to ${esc(longDay(last))}`) : ""}.${arts.length >= 1000 ? " 1,000 is the most one export holds, so the query can match more: these figures describe this set." : ""}</p>`;
  if (first && last && isoDay(first) !== isoDay(last)) {
    const days = Math.round((Date.UTC(last.getUTCFullYear(), last.getUTCMonth(), last.getUTCDate()) - Date.UTC(first.getUTCFullYear(), first.getUTCMonth(), first.getUTCDate())) / 86400000) + 1;
    const weekly = days > 70;
    const byKey = new Map();
    for (const a of dated) {
      const d0 = new Date(Date.UTC(a.date.getUTCFullYear(), a.date.getUTCMonth(), a.date.getUTCDate()));
      if (weekly) d0.setUTCDate(d0.getUTCDate() - ((d0.getUTCDay() + 6) % 7));
      byKey.set(isoDay(d0), (byKey.get(isoDay(d0)) ?? 0) + 1);
    }
    const pts = [];
    const cur = new Date(Date.UTC(first.getUTCFullYear(), first.getUTCMonth(), first.getUTCDate()));
    if (weekly) cur.setUTCDate(cur.getUTCDate() - ((cur.getUTCDay() + 6) % 7));
    while (cur <= last) {
      const k = isoDay(cur);
      pts.push({ label: weekly ? `Week of ${longDay(cur)}` : longDay(cur), short: shortDay(cur), value: byKey.get(k) ?? 0 });
      cur.setUTCDate(cur.getUTCDate() + (weekly ? 7 : 1));
    }
    const peak = pts.reduce((b, p) => (p.value > b.value ? p : b), pts[0]);
    h += `<h3>Articles per ${weekly ? "week" : "day"}</h3>${columnChart(pts, { unit: "articles", aria: `Articles per ${weekly ? "week" : "day"}` })}<p class="small">Peak: ${esc(peak.label)}, ${num(peak.value)} articles.</p>`;
    summary.push(`- ${name}: peak ${peak.label} (${num(peak.value)} articles)`);
  }
  const top = [...outlets.values()].sort((a, b) => b.count - a.count || (a.rank ?? 1e9) - (b.rank ?? 1e9)).slice(0, 15);
  h += `<div class="grid2"><div><h3>Top outlets</h3>${barList(top.map((o) => [o.name, o.count, o.rank ? `rank ${num(o.rank)}` : ""]), arts.length)}</div>`;
  const topAuthors = [...authors.entries()].sort((a, b) => b[1].count - a[1].count).slice(0, 12);
  h += `<div><h3>Top authors</h3>${topAuthors.length ? barList(topAuthors.map(([n, e]) => [n, e.count, [...e.outlets.entries()].sort((a, b) => b[1] - a[1]).slice(0, 2).map((x) => x[0]).join(", ")])) : `<p class="muted">No person bylines in this set.</p>`}</div></div>`;
  h += `<div class="grid2"><div><h3>Countries</h3>${barList(countries.slice(0, 10), arts.length)}</div><div><h3>Languages</h3>${barList(langs.slice(0, 10), arts.length)}</div></div>`;
  const clips = [...outlets.values()].map((o) => ({ ...o.best, rank: o.rank })).sort((a, b) => (a.rank ?? 1e9) - (b.rank ?? 1e9) || (b.date ?? 0) - (a.date ?? 0)).slice(0, 25);
  h += `<h3>Top clips</h3><p class="muted small">One article per outlet, biggest outlets first${arts.length > clips.length ? `; all ${num(arts.length)} are in ${esc(basename(file))}` : ""}.</p>`;
  h += table(
    [
      { label: "Date", nowrap: true, get: (a) => (a.date ? shortDay(a.date) : "") },
      { label: "Outlet", get: (a) => a.source || a.domain },
      { label: "Headline", html: (a) => `${link(a.url, clip(a.title_en || a.title, 160))}${a.title_en ? `<div class="muted small">${esc(clip(a.title, 120))}</div>` : ""}` },
      { label: "Where", nowrap: true, get: (a) => [a.country, a.language].filter(Boolean).join(" · ") },
    ],
    clips,
  );
  h += `</section>`;
  summary.push(`- ${name}: ${many(arts.length, "article")} · ${many(outlets.size, "outlet")} · ${many(countries.length, "country", "countries")} · ${many(langs.length, "language")}${top.length ? ` · top outlets ${top.slice(0, 5).map((o) => `${o.name} ${o.count}`).join(", ")}` : ""}`);
  method.push(`${name}: list_articles export, ${num(arts.length)} articles (${basename(file)})`);
  return { html: h, tiles: [{ label: "Articles", value: compact(arts.length), sub: name }, { label: "Outlets", value: compact(outlets.size) }, { label: "Countries", value: String(countries.length), sub: `${langs.length} languages` }] };
}

const seenStories = new Set();
function storiesSection(label, d, file) {
  const s = normStories(d);
  const items = [];
  let dupes = 0;
  for (const it of s.items) {
    const key = it.story_id || it.url;
    if (key && seenStories.has(key)) { dupes++; continue; }
    if (key) seenStories.add(key);
    items.push(it);
  }
  const name = label || (s.meta.query ? `Stories: ${s.meta.query}` : "Stories");
  let h = `<section><h2>${esc(name)}</h2>`;
  if (!items.length) h += `<p class="muted">No stories${dupes ? " beyond those already shown above" : ""}.</p>`;
  h += `<ol class="stories">${items
    .map((it) => `<li><div class="st-title">${link(it.url, clip(it.title_en || it.title, 200))}</div>${it.title_en ? `<div class="muted small">${esc(clip(it.title, 160))}</div>` : ""}<div class="st-meta">${esc([it.source, it.date ? shortDay(it.date) : "", it.newsrooms ? `${it.newsrooms} newsroom${it.newsrooms > 1 ? "s" : ""}` : ""].filter(Boolean).join(" · "))}</div>${it.summary ? `<p>${esc(clip(it.summary, 360))}</p>` : ""}</li>`)
    .join("")}</ol>`;
  if (dupes) h += `<p class="muted small">${dupes} ${dupes > 1 ? "stories" : "story"} already shown above ${dupes > 1 ? "were" : "was"} left out.</p>`;
  h += `</section>`;
  const big = [...items].sort((a, b) => (b.newsrooms ?? 0) - (a.newsrooms ?? 0))[0];
  summary.push(`- ${name}: ${many(items.length, "story", "stories")}${big?.newsrooms ? ` · biggest "${clip(big.title_en || big.title, 90)}" (${big.newsrooms} newsrooms)` : ""}`);
  method.push(`${name}: search_news${s.meta.query ? ` «${s.meta.query}»` : ""}${s.meta.window?.search_window ? `, last ${s.meta.window.search_window}` : ""}${s.meta.effort ? `, effort ${s.meta.effort}` : ""} (${basename(file)})`);
  return { html: h, tiles: [{ label: "Stories", value: String(items.length), sub: name }] };
}

const pick = (cols, re) => cols.find((c) => re.test(c));
function rowsSection(label, d, file) {
  const { rows, columns } = normRows(d);
  const name = label || "Research results";
  const cCompany = pick(columns, /^(company|company_name|organization|organisation)$/i);
  const cType = pick(columns, /^(story_type|event_type|type|category|signal_type)$/i);
  const cDate = pick(columns, /^(date|event_date|announcement_date|announced_at|published_at|date_announced)$/i);
  const cUrl = ["source_url", "url", "link", "article_url"].map((k) => columns.find((c) => c.toLowerCase() === k)).find(Boolean);
  const cHead = pick(columns, /^(headline|title|event|event_title)$/i);
  const cSummary = pick(columns, /^(summary|description|details)$/i);
  const cImp = pick(columns, /^importance$/i);
  // importance comes as 1–3 or as low/medium/high
  const impScore = (v) => (v !== "" && v !== null && Number.isFinite(Number(v)) ? Number(v) : ({ high: 3, medium: 2, low: 1 })[String(v ?? "").toLowerCase()] ?? 0);
  const topImp = cImp ? Math.max(0, ...rows.map((r) => impScore(r[cImp]))) : 0;
  const topLabel = cImp && rows.some((r) => Number.isFinite(Number(r[cImp])) && r[cImp] !== "") ? `Importance ${topImp}` : "High importance";
  const sorted = [...rows].sort((a, b) => (cImp ? impScore(b[cImp]) - impScore(a[cImp]) : 0) || (cDate ? (toDate(b[cDate]) ?? 0) - (toDate(a[cDate]) ?? 0) : 0));
  let h = `<section><h2>${esc(name)}</h2><p class="lede">${num(rows.length)} rows${cCompany ? ` about ${num(new Set(rows.map((r) => r[cCompany]).filter(Boolean)).size)} companies` : ""}.</p>`;
  let tilesOut = [{ label: "Rows", value: compact(rows.length), sub: name }];
  if (cCompany) {
    const by = new Map();
    for (const r of rows) {
      const k = r[cCompany] || "(unknown)";
      const e = by.get(k) ?? { n: 0, types: new Map(), latest: null, high: 0 };
      e.n++;
      if (cType && r[cType]) e.types.set(r[cType], (e.types.get(r[cType]) ?? 0) + 1);
      const dt = cDate ? toDate(r[cDate]) : null;
      if (dt && (!e.latest || dt > e.latest)) e.latest = dt;
      if (cImp && topImp > 0 && impScore(r[cImp]) === topImp) e.high++;
      by.set(k, e);
    }
    const board = [...by.entries()].sort((a, b) => b[1].n - a[1].n);
    h += `<h3>Scoreboard</h3>`;
    h += table(
      [
        { label: "Company", get: (e) => e[0] },
        { label: "Rows", num: true, get: (e) => num(e[1].n) },
        ...(cImp ? [{ label: topLabel, num: true, get: (e) => num(e[1].high) }] : []),
        ...(cType ? [{ label: "Top types", get: (e) => [...e[1].types.entries()].sort((a, b) => b[1] - a[1]).slice(0, 3).map(([t, n]) => `${t} ${n}`).join(", ") }] : []),
        ...(cDate ? [{ label: "Latest", get: (e) => (e[1].latest ? shortDay(e[1].latest) : "") }] : []),
      ],
      board,
      { cls: "numbers" },
    );
    summary.push(`- ${name}: ${many(rows.length, "row")} · ${many(board.length, "company", "companies")} · most: ${board.slice(0, 5).map(([k, e]) => `${k} ${e.n}`).join(", ")}`);
    tilesOut.push({ label: "Companies", value: String(board.length) });
  } else summary.push(`- ${name}: ${many(rows.length, "row")}`);
  if (cType) {
    const types = countBy(rows, (r) => r[cType]);
    h += `<h3>By ${esc(cType.replace(/_/g, " "))}</h3>${barList(types.slice(0, 12), rows.length)}`;
  }
  const LIMIT = 300;
  const shown = sorted.slice(0, LIMIT);
  // Lead with the known columns; the link rides on the headline; hide ids, duplicates and empty columns (all stay in the file).
  const empty = (c) => rows.every((r) => r[c] === "" || r[c] === null || r[c] === undefined);
  const hidden = new Set([cUrl, cHead && cSummary ? cSummary : "", cCompany ? columns.find((c) => c.toLowerCase() === "domain") : "", ...columns.filter((c) => /^(id|run_id|row_id|origin|rank)$/i.test(c) || empty(c))].filter(Boolean));
  const lead = [cDate, cCompany, cType, cImp, cHead].filter(Boolean);
  const visible = [...lead, ...columns.filter((c) => !lead.includes(c) && !hidden.has(c))].slice(0, 8);
  const cell = (v) => (typeof v === "object" && v !== null ? JSON.stringify(v) : v);
  h += `<h3>Rows</h3>${rows.length > LIMIT ? `<p class="muted small">First ${LIMIT} of ${num(rows.length)}${cImp ? ", most important first" : cDate ? ", newest first" : ""}; all rows are in ${esc(basename(file))}.</p>` : ""}`;
  h += table(
    [
      ...visible.map((c) =>
        c === cHead
          ? { label: c.replace(/_/g, " "), html: (r) => `${link(r[cUrl], clip(r[c], 200))}${cSummary && r[cSummary] && r[cSummary] !== r[c] ? `<div class="muted small">${esc(clip(r[cSummary], 260))}</div>` : ""}` }
          : { label: c.replace(/_/g, " "), nowrap: c === cDate || c === cImp, get: (r) => clip(cell(r[c]), 220) },
      ),
      ...(cUrl && !cHead ? [{ label: "source", html: (r) => (safeUrl(r[cUrl]) ? link(r[cUrl], "link") : esc(clip(r[cUrl], 60))) }] : []),
    ],
    shown,
  );
  h += `</section>`;
  method.push(`${name}: research agent export, ${num(rows.length)} rows (${basename(file)})`);
  return { html: h, tiles: tilesOut };
}

// ------------------------------------------------------------------ notes (a small, safe markdown subset)
function inline(s) {
  return esc(s)
    .replace(/\[([^\]]+)\]\((https?:\/\/[^)\s]+)\)/g, (_, t, u) => `<a href="${u}" target="_blank" rel="noopener noreferrer">${t}</a>`)
    .replace(/\*\*([^*]+)\*\*/g, "<strong>$1</strong>")
    .replace(/`([^`]+)`/g, "<code>$1</code>");
}
function markdown(md) {
  const out = [];
  let list = null;
  const close = () => { if (list) { out.push(`</${list}>`); list = null; } };
  for (const raw of md.split(/\r?\n/)) {
    const line = raw.trimEnd();
    let m;
    if (!line.trim()) { close(); continue; }
    if ((m = line.match(/^(#{1,4})\s+(.*)$/))) { close(); out.push(`<h${Math.min(4, m[1].length + 2)}>${inline(m[2])}</h${Math.min(4, m[1].length + 2)}>`); continue; }
    if ((m = line.match(/^\s*[-*•]\s+(.*)$/))) { if (list !== "ul") { close(); out.push("<ul>"); list = "ul"; } out.push(`<li>${inline(m[1])}</li>`); continue; }
    if ((m = line.match(/^\s*\d+[.)]\s+(.*)$/))) { if (list !== "ol") { close(); out.push("<ol>"); list = "ol"; } out.push(`<li>${inline(m[1])}</li>`); continue; }
    close();
    out.push(`<p>${inline(line)}</p>`);
  }
  close();
  return out.join("\n");
}

// ------------------------------------------------------------------ page
const CSS = `
:root{color-scheme:light;--page:#f9f9f7;--surface:#fcfcfb;--ink:#0b0b0b;--ink2:#52514e;--muted:#898781;--grid:#e1e0d9;--axis:#c3c2b7;--ring:rgba(11,11,11,.10);--accent:#183fd9;
--series-1:#2a78d6;--series-2:#eb6834;--series-3:#1baf7a;--series-4:#eda100;--series-5:#e87ba4}
@media (prefers-color-scheme:dark){:root:where(:not([data-theme="light"])){color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);--accent:#7d95ff;
--series-1:#3987e5;--series-2:#d95926;--series-3:#199e70;--series-4:#c98500;--series-5:#d55181}}
:root[data-theme="dark"]{color-scheme:dark;--page:#0d0d0d;--surface:#1a1a19;--ink:#f0efec;--ink2:#c3c2b7;--muted:#898781;--grid:#2c2c2a;--axis:#383835;--ring:rgba(255,255,255,.10);--accent:#7d95ff;
--series-1:#3987e5;--series-2:#d95926;--series-3:#199e70;--series-4:#c98500;--series-5:#d55181}
*{box-sizing:border-box}
body{margin:0;background:var(--page);color:var(--ink);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1080px;margin:0 auto;padding:32px 16px 64px}
header{margin-bottom:24px}
.brand{font-size:12px;letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
.brand b{color:var(--accent);font-weight:600}
h1{font-size:30px;line-height:1.2;margin:6px 0 4px;font-weight:650}
h2{font-size:20px;margin:0 0 6px;font-weight:620}
h3{font-size:14px;margin:22px 0 8px;color:var(--ink2);font-weight:600}
h4{font-size:14px;margin:16px 0 6px}
.sub{color:var(--ink2);margin:0}
section,.notes{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:20px 22px;margin:16px 0;break-inside:avoid-page}
.lede{color:var(--ink2);margin:0 0 12px}
.muted{color:var(--muted)}.small{font-size:13px}
a{color:var(--accent);text-decoration:none}a:hover{text-decoration:underline}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:12px;margin:16px 0}
.tile{background:var(--surface);border:1px solid var(--ring);border-radius:10px;padding:14px 16px}
.tile-label{font-size:13px;color:var(--ink2)}.tile-value{font-size:28px;font-weight:620;line-height:1.25;overflow-wrap:anywhere}.tile-sub{font-size:12px;color:var(--muted);overflow-wrap:anywhere}
.chart{margin:8px 0 4px;position:relative}.chart svg{width:100%;height:auto;display:block;overflow:visible}
.grid{stroke:var(--grid);stroke-width:1}.axis{stroke:var(--axis);stroke-width:1}
.tick{fill:var(--muted);font-size:12px;font-variant-numeric:tabular-nums}
.line{fill:none;stroke-width:2;stroke-linejoin:round;stroke-linecap:round}.wash{opacity:.1}
.dot{stroke:var(--surface);stroke-width:2}
.cross{stroke:var(--axis);stroke-width:1}
.hit{fill:transparent;outline:none}
.col:hover path,.col:focus path{opacity:.75}.col{outline:none}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;margin:8px 0;font-size:13px;color:var(--ink2)}
.key{display:inline-flex;align-items:center;gap:6px}
.swatch{width:10px;height:10px;border-radius:2px;display:inline-block}
.linekey{width:14px;height:2px;border-radius:1px;display:inline-block}
.segbar{display:flex;gap:2px;height:28px;margin:6px 0 2px}
.seg{border-radius:4px;display:flex;align-items:center;padding:0 8px;font-size:12px;font-weight:600;min-width:2px;outline:none;white-space:nowrap;overflow:hidden}
.bars{list-style:none;margin:0;padding:0}
.bars li{display:grid;grid-template-columns:minmax(100px,44%) 1fr 76px;align-items:center;gap:10px;padding:3px 0;font-size:13px}
.bl-name{white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.bl-track{height:10px}.bl-bar{display:block;height:10px;background:var(--series-1);border-radius:0 4px 4px 0;min-width:2px}
.bl-val{font-variant-numeric:tabular-nums;white-space:nowrap;text-align:right}
.nowrap{white-space:nowrap}
.grid2{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:8px 28px}
.table-wrap{overflow-x:auto;margin:6px 0}
table{border-collapse:collapse;width:100%;font-size:13px}
th{text-align:left;font-weight:600;color:var(--ink2);border-bottom:1px solid var(--axis);padding:6px 8px;white-space:nowrap}
td{border-bottom:1px solid var(--grid);padding:6px 8px;vertical-align:top}
.num{text-align:right;font-variant-numeric:tabular-nums}
details summary{cursor:pointer;color:var(--ink2);font-size:13px;margin-top:8px}
.stories{padding-left:20px;margin:0}.stories li{margin:0 0 14px}.stories p{margin:4px 0 0;color:var(--ink2)}
.st-title{font-weight:600}.st-meta{font-size:12px;color:var(--muted)}
.method li{margin:2px 0;color:var(--ink2);font-size:13px}
footer{color:var(--muted);font-size:12px;margin-top:24px}
#tip{position:fixed;pointer-events:none;background:var(--surface);color:var(--ink);border:1px solid var(--ring);border-radius:8px;padding:8px 10px;font-size:12px;box-shadow:0 4px 16px rgba(0,0,0,.12);display:none;z-index:10;max-width:280px}
#tip .tv{font-weight:650;font-size:13px}#tip .tl{color:var(--ink2)}#tip .row{display:flex;align-items:center;gap:6px;margin-top:2px}
@media print{body{background:#fff}section,.tile,.notes{border-color:#ddd}#tip{display:none}}
`;

// Tooltip and crosshair. Labels come from data, so they are set with textContent only.
const JS = `
(() => {
  const tip = document.getElementById("tip");
  const show = (x, y, build) => { tip.replaceChildren(); build(tip); tip.style.display = "block";
    const r = tip.getBoundingClientRect(); let left = x + 14, top = y + 14;
    if (left + r.width > innerWidth - 8) left = x - r.width - 14; if (top + r.height > innerHeight - 8) top = y - r.height - 14;
    tip.style.left = left + "px"; tip.style.top = top + "px"; };
  const hide = () => { tip.style.display = "none"; };
  const el = (tag, cls, text) => { const e = document.createElement(tag); if (cls) e.className = cls; if (text !== undefined) e.textContent = text; return e; };
  document.querySelectorAll("[data-tip-label]").forEach((m) => {
    const build = (t) => { t.append(el("div", "tv", m.dataset.tipValue), el("div", "tl", m.dataset.tipLabel)); };
    m.addEventListener("pointermove", (e) => show(e.clientX, e.clientY, build));
    m.addEventListener("pointerleave", hide);
    m.addEventListener("focus", () => { const r = m.getBoundingClientRect(); show(r.left + r.width / 2, r.top, build); });
    m.addEventListener("blur", hide);
  });
  document.querySelectorAll("figure[data-line]").forEach((fig) => {
    const d = JSON.parse(document.getElementById(fig.dataset.line).textContent);
    const svg = fig.querySelector("svg"), cross = svg.querySelector(".cross"), hit = svg.querySelector(".hit"), dots = svg.querySelector(".hover-dots");
    const ns = "http://www.w3.org/2000/svg";
    let idx = -1;
    const place = (i, cx, cy) => {
      idx = i; const x = d.x[i]; cross.setAttribute("x1", x); cross.setAttribute("x2", x); cross.setAttribute("visibility", "visible");
      dots.replaceChildren();
      d.y.forEach((ys, si) => { if (ys[i] === null) return; const c = document.createElementNS(ns, "circle");
        c.setAttribute("cx", x); c.setAttribute("cy", ys[i]); c.setAttribute("r", 4); c.setAttribute("class", "dot"); c.style.fill = "var(--series-" + (si + 1) + ")"; dots.append(c); });
      show(cx, cy, (t) => {
        t.append(el("div", "tl", d.labels[i] + (d.partial[i] ? " (partial)" : "")));
        d.series.forEach((s, si) => { const row = el("div", "row"); const k = el("span", "linekey"); k.style.background = "var(--series-" + (si + 1) + ")";
          const v = s.values[i]; row.append(k, el("span", "tv", v === null ? "n/a" : v.toLocaleString("en-US")), el("span", "tl", s.name)); t.append(row); });
      });
    };
    const nearest = (clientX) => { const r = svg.getBoundingClientRect(); const vx = (clientX - r.left) * d.width / r.width;
      let best = 0; d.x.forEach((x, i) => { if (Math.abs(x - vx) < Math.abs(d.x[best] - vx)) best = i; }); return best; };
    hit.addEventListener("pointermove", (e) => place(nearest(e.clientX), e.clientX, e.clientY));
    const off = () => { cross.setAttribute("visibility", "hidden"); dots.replaceChildren(); hide(); };
    hit.addEventListener("pointerleave", off); hit.addEventListener("blur", off);
    hit.addEventListener("keydown", (e) => { if (e.key !== "ArrowRight" && e.key !== "ArrowLeft") return; e.preventDefault();
      const i = Math.max(0, Math.min(d.x.length - 1, (idx < 0 ? 0 : idx + (e.key === "ArrowRight" ? 1 : -1))));
      const r = svg.getBoundingClientRect(); place(i, r.left + d.x[i] * r.width / d.width, r.top + 20); });
  });
})();
`;

// ------------------------------------------------------------------ main
const args = parseArgs(process.argv.slice(2));
if (args.help || !args.inputs.length) {
  process.stdout.write(readFileSync(new URL(import.meta.url), "utf8").split("*/")[0].replace(/^#!.*\n\/\*\*?/, "").replace(/^ \* ?/gm, "") + "\n");
  process.exit(args.help ? 0 : 1);
}
const title = args.title || "News report";
const parts = [];
const allTiles = [];
for (const inp of args.inputs) {
  const data = readData(inp.path);
  const fn = { articles: articlesSection, counts: countsSection, stories: storiesSection, rows: rowsSection }[inp.kind];
  const r = fn(inp.label, data, inp.path);
  parts.push(r.html);
  allTiles.push(...r.tiles);
}
const seen = new Set();
const headTiles = allTiles.filter((t) => (seen.has(t.label) ? false : seen.add(t.label))).slice(0, 5);
const notes = args.notes ? `<div class="notes"><h2>Summary</h2>${markdown(readText(args.notes))}</div>` : "";
const generated = new Date();
const html = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>${esc(title)}</title><style>${CSS}</style></head>
<body><main>
<header><div class="brand">News report · <b>NewsCatcher</b></div><h1>${esc(title)}</h1>${args.subtitle ? `<p class="sub">${esc(args.subtitle)}</p>` : ""}</header>
${tiles(headTiles)}
${notes}
${parts.join("\n")}
<section><h2>Method</h2><ul class="method">${[...method, ...args.method].map((m) => `<li>${esc(m)}</li>`).join("")}</ul>
<p class="muted small">Counts are exact for each query and window. Links open the original articles.</p></section>
<footer>Generated ${esc(generated.toISOString().slice(0, 16).replace("T", " "))} UTC from NewsCatcher data.</footer>
</main><div id="tip" role="tooltip"></div><script>${JS}</script></body></html>`;
const out = resolve(args.out ?? `newscatcher-exports/report-${title.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "").slice(0, 50) || "news"}-${generated.toISOString().slice(0, 10)}.html`);
mkdirSync(dirname(out), { recursive: true });
writeFileSync(out, html);
process.stdout.write(`Report: ${out} (${Math.round(Buffer.byteLength(html) / 1024)} KB)\n${summary.join("\n")}\n`);
