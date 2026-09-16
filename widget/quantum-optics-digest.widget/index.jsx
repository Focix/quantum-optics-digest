// Übersicht widget: today's digest on the desktop.
// Reads the published latest.json, so it needs no checkout and no local run.
// Install: see widget/README.md.
import { run } from "uebersicht";

const SITE = "https://focix.github.io/quantum-optics-digest/";
const DATA = `${SITE}data/latest.json`;

const PER_SECTION = 5; // papers per section; watchlist papers are shown on top of this
const SECTIONS = [
  ["A", "Superconducting artificial atoms"],
  ["B", "Quantum optics on other platforms"],
];
const KINDS = { T: "theory", E: "experiment", TE: "theory and experiment" };

export const command = `curl -sfL --max-time 20 ${DATA}`;
export const refreshFreq = 30 * 60 * 1000;

export const className = `
  top: 40px; right: 30px; width: 420px;
  font: 13px/1.45 -apple-system, system-ui, sans-serif;
  color: #ebe8e0;
  background: rgba(22, 22, 20, 0.72);
  -webkit-backdrop-filter: blur(18px);
  border: 1px solid rgba(255, 255, 255, 0.09);
  border-radius: 12px;
  padding: 14px 16px 12px;
  box-shadow: 0 8px 30px rgba(0, 0, 0, 0.35);

  header { display: flex; align-items: baseline; justify-content: space-between; cursor: pointer; }
  h1 { font-size: 13px; font-weight: 600; letter-spacing: .02em; margin: 0; }
  .date { color: #9c9a92; font-size: 11px; }
  .stale { color: #f0a06a; }
  .empty, .error { color: #9c9a92; margin: 10px 0 2px; }
  .error { color: #ff8a80; }
  h2 { font-size: 11px; font-weight: 600; text-transform: uppercase; letter-spacing: .06em;
       color: #f0a06a; margin: 12px 0 4px; }
  ol { list-style: none; margin: 0; padding: 0; }
  li { padding: 5px 0; border-top: 1px solid rgba(255, 255, 255, 0.07); cursor: pointer; }
  li:hover .title { text-decoration: underline; }
  li.read .title { color: #fff; }
  .score { display: inline-block; min-width: 2.1em; text-align: right; margin-right: 6px;
           font-variant-numeric: tabular-nums; color: #9c9a92; }
  li.read .score { color: #f0a06a; font-weight: 600; }
  .kind { display: inline-block; min-width: 1.6em; text-align: center; margin-right: 6px;
          font-size: 9px; font-weight: 700; line-height: 15px; border-radius: 3px;
          padding: 0 3px; color: #fff; vertical-align: 1px; }
  .kind-T { background: #2b5f9e; } .kind-E { background: #2e7d4f; } .kind-TE { background: #7a4b9d; }
  .watch { color: #f0a06a; margin-right: 4px; }
  .title { font-weight: 500; }
  .why { color: #b6b3aa; margin: 2px 0 0 calc(2.1em + 6px); font-size: 12px; }
`;

const open = (url) => run(`open ${JSON.stringify(url)}`);

const paperUrl = (p) => p.url || `https://arxiv.org/abs/${p.id}`;

const watchedNames = (p) =>
  (p.tags || []).filter((t) => t.startsWith("watch:")).map((t) => t.slice(6));

// Watchlist papers always show, whatever they scored; the rest by score.
const pick = (items, section) => {
  const all = items
    .filter((p) => p.section === section)
    .sort((a, b) => (b.score ?? 0) - (a.score ?? 0));
  const top = all.slice(0, PER_SECTION);
  const watched = all.slice(PER_SECTION).filter((p) => watchedNames(p).length);
  return [...top, ...watched];
};

const prettyDate = (run) =>
  new Date(`${run}T12:00:00`).toLocaleDateString(undefined, {
    weekday: "short",
    day: "numeric",
    month: "short",
  });

// A run older than yesterday means the routine did not publish; say so rather than
// showing day-old papers as if they were today's.
const isStale = (run) => (Date.now() - new Date(`${run}T12:00:00`).getTime()) / 864e5 > 2;

const Paper = ({ p }) => {
  const names = watchedNames(p);
  return (
    <li className={p.score >= 80 ? "read" : ""} onClick={() => open(paperUrl(p))}>
      <span className="score">{p.score ?? ""}</span>
      {KINDS[p.kind] ? (
        <span className={`kind kind-${p.kind}`} title={KINDS[p.kind]}>
          {p.kind}
        </span>
      ) : null}
      {names.length ? <span className="watch" title={`watchlist: ${names.join(", ")}`}>★</span> : null}
      <span className="title">{p.title}</span>
      {p.why ? <div className="why">{p.why}</div> : null}
    </li>
  );
};

export const render = ({ output, error }) => {
  let digest = null;
  let problem = error ? String(error) : null;
  if (!problem && output) {
    try {
      digest = JSON.parse(output);
    } catch (e) {
      problem = `bad JSON from ${DATA}`;
    }
  }
  // curl -sf says nothing on a network failure or a 404, so an empty output is its own message.
  if (!digest && !problem) problem = "Digest unavailable — offline, or the site has not published yet.";

  const items = digest ? Object.values(digest.items || {}) : [];
  const sections = SECTIONS.map(([key, title]) => [key, title, pick(items, key)]).filter(
    ([, , picked]) => picked.length
  );

  return (
    <div>
      <header onClick={() => open(SITE)}>
        <h1>Quantum Optics Digest</h1>
        {digest ? (
          <span className={`date ${isStale(digest.run) ? "stale" : ""}`}>
            {prettyDate(digest.run)}
          </span>
        ) : null}
      </header>
      {problem ? <div className="error">{problem}</div> : null}
      {digest && !sections.length ? (
        <div className="empty">Nothing scored above the threshold.</div>
      ) : null}
      {sections.map(([key, title, picked]) => (
        <div key={key}>
          <h2>{title}</h2>
          <ol>
            {picked.map((p) => (
              <Paper key={p.id} p={p} />
            ))}
          </ol>
        </div>
      ))}
    </div>
  );
};
