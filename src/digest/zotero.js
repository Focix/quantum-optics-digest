// Save-to-Zotero button. Talks to the Zotero Web API straight from the page; the user ID and
// write key live in this browser's localStorage only. The "to-read" collection is the source of
// truth: on load every paper in it gets a tick, everything else shows +Z.
(() => {
  const KEY = "qod.zotero", API = "https://api.zotero.org", TAG = "digest";
  const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch (e) { return d; } };
  const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
  let cfg = load(KEY, null);
  const inColl = new Map(); // arXiv id (or DOI) -> item key, from the collection sync or this session's saves
  const cache = {};
  const root = document.body.dataset.root || "";
  const dialog = document.getElementById("zot-dialog");
  const form = dialog && dialog.querySelector("form");
  const status = document.getElementById("zot-status");

  const headers = (extra) => Object.assign({ "Zotero-API-Key": cfg.apiKey, "Zotero-API-Version": "3" }, extra || {});
  async function api(path, opts) {
    opts = opts || {};
    const res = await fetch(API + "/users/" + cfg.userId + path, Object.assign({}, opts, { headers: headers(opts.headers) }));
    if (!res.ok) throw new Error("Zotero " + res.status + ": " + (await res.text()).slice(0, 200));
    return res;
  }
  async function post(path, body) {
    const res = await api(path, { method: "POST", body: JSON.stringify(body),
      headers: { "Content-Type": "application/json", "Zotero-Write-Token": Math.random().toString(36).slice(2) + Date.now().toString(36) } });
    const r = await res.json();
    if (Object.keys(r.failed || {}).length) throw new Error("Zotero rejected: " + JSON.stringify(r.failed).slice(0, 200));
    return r.successful;
  }
  async function patch(key, version, data) {
    await api("/items/" + key, { method: "PATCH", body: JSON.stringify(data),
      headers: { "Content-Type": "application/json", "If-Unmodified-Since-Version": version } });
  }

  // -- identify papers -----------------------------------------------------
  const strip = (id) => id.replace(/v\d+$/, "");
  function idsOf(data) {
    const ids = [];
    let m;
    if ((m = /^arXiv:\s*(\S+)/i.exec(data.archiveID || ""))) ids.push(strip(m[1]));
    if ((m = /10\.48550\/arXiv\.(\S+)/i.exec(data.DOI || ""))) ids.push(strip(m[1]));
    if ((m = /arxiv\.org\/(?:abs|pdf)\/([^v?#\s]+)/i.exec(data.url || ""))) ids.push(strip(m[1]));
    if ((m = /arXiv:\s*(\S+)/.exec(data.extra || ""))) ids.push(strip(m[1]));
    if (data.DOI && !/10\.48550/i.test(data.DOI)) ids.push("doi:" + data.DOI.toLowerCase());
    return ids;
  }
  const isArxiv = (id) => /^\d{4}\.\d{4,5}$/.test(id) || /^[a-z\-]+\/\d{7}$/.test(id);
  function lookupIds(rec) {
    const ids = [];
    if (isArxiv(rec.id)) ids.push(rec.id);
    const m = /doi\.org\/(.+)$/i.exec(rec.url || "");
    if (m) ids.push("doi:" + decodeURIComponent(m[1]).toLowerCase());
    return ids;
  }

  // -- buttons -------------------------------------------------------------
  function markDone(b, key) {
    b.classList.add("zot-done"); b.textContent = "✓"; b.disabled = false; b.dataset.key = key;
    b.title = "in " + cfg.collectionName + " · click to remove";
  }
  function markTodo(b) {
    b.classList.remove("zot-done"); b.textContent = "+Z"; b.title = "Save to Zotero"; b.disabled = false; delete b.dataset.key;
  }
  function refresh() {
    document.body.classList.toggle("zot-on", !!cfg);
    document.querySelectorAll("button.zot").forEach((b) => {
      const key = inColl.get(b.dataset.id);
      if (key) markDone(b, key); else markTodo(b);
    });
  }
  async function sync() {
    inColl.clear();
    if (!cfg) { refresh(); return; }
    try {
      for (let start = 0, total = 1; start < total; start += 100) {
        const res = await api("/collections/" + cfg.collectionKey + "/items/top?limit=100&start=" + start);
        total = Number(res.headers.get("Total-Results") || "0");
        for (const it of await res.json()) for (const id of idsOf(it.data)) inColl.set(id, it.key);
      }
    } catch (e) { console.warn("Zotero sync failed", e); }
    refresh();
  }

  // -- connect -------------------------------------------------------------
  async function connect(userId, apiKey, name) {
    cfg = { userId: userId.trim(), apiKey: apiKey.trim(), collectionName: (name || "to-read").trim() || "to-read" };
    const res = await api("/collections?limit=100");
    const found = (await res.json()).find((c) => c.data.name.toLowerCase() === cfg.collectionName.toLowerCase());
    if (found) cfg.collectionKey = found.key;
    else cfg.collectionKey = (await post("/collections", [{ name: cfg.collectionName, parentCollection: false }]))["0"].key;
    save(KEY, cfg);
  }

  // -- build items ---------------------------------------------------------
  function creators(authors) {
    return (authors || []).map((a) => {
      const parts = a.trim().split(/\s+/);
      if (parts.length < 2) return { creatorType: "author", name: a.trim() };
      return { creatorType: "author", firstName: parts.slice(0, -1).join(" "), lastName: parts[parts.length - 1] };
    });
  }
  function itemFor(rec) {
    const arxiv = isArxiv(rec.id);
    const url = rec.url || "https://arxiv.org/abs/" + rec.id;
    const base = { title: rec.title, creators: creators(rec.authors), abstractNote: rec.abstract || "", date: rec.submitted || "",
      url: url, accessDate: new Date().toISOString().slice(0, 10), collections: [cfg.collectionKey], tags: [{ tag: TAG }] };
    if (arxiv) Object.assign(base, { itemType: "preprint", repository: "arXiv", archiveID: "arXiv:" + rec.id,
      DOI: "10.48550/arXiv." + rec.id, libraryCatalog: "arXiv.org", extra: "arXiv: " + rec.id + (rec.categories && rec.categories.length ? " [" + rec.categories[0] + "]" : "") });
    else Object.assign(base, { itemType: "journalArticle", DOI: /doi\.org\//.test(url) ? decodeURIComponent(url.split("doi.org/")[1]) : "" });
    return { item: base, pdf: arxiv ? "https://arxiv.org/pdf/" + rec.id : null };
  }
  async function record(btn) {
    const src = root + "data/" + btn.dataset.src + ".json";
    if (!cache[src]) cache[src] = fetch(src).then((r) => { if (!r.ok) throw new Error("no data file " + src); return r.json(); });
    const rec = (await cache[src]).items[btn.dataset.id];
    if (!rec) throw new Error("paper not in " + src);
    return rec;
  }

  // -- add / remove --------------------------------------------------------
  async function existing(rec) {
    // a top-level item anywhere in the library that is this paper, or null
    for (const id of lookupIds(rec)) {
      const q = id.startsWith("doi:") ? id.slice(4) : id;
      const res = await api("/items/top?limit=10&qmode=everything&q=" + encodeURIComponent(q));
      for (const it of await res.json()) if (idsOf(it.data).includes(id)) return it;
    }
    return null;
  }
  async function add(btn) {
    btn.disabled = true; btn.textContent = "…";
    try {
      const rec = await record(btn);
      const found = await existing(rec);
      let key;
      if (found) {
        key = found.key;
        if (!(found.data.collections || []).includes(cfg.collectionKey))
          await patch(key, found.version, { collections: (found.data.collections || []).concat([cfg.collectionKey]) });
      } else {
        const { item, pdf } = itemFor(rec);
        key = (await post("/items", [item]))["0"].key;
        const children = [];
        if (pdf) children.push({ itemType: "attachment", linkMode: "linked_url", parentItem: key, title: "arXiv PDF", url: pdf, contentType: "application/pdf" });
        if (rec.why) children.push({ itemType: "note", parentItem: key, note: "<p>" + rec.why + (rec.score != null ? " (digest score " + rec.score + ")" : "") + "</p>" });
        if (children.length) await post("/items", children);
      }
      inColl.set(btn.dataset.id, key); markDone(btn, key);
    } catch (e) {
      btn.textContent = "!"; btn.title = String(e.message || e); btn.disabled = false;
    }
  }
  async function remove(btn) {
    const key = btn.dataset.key;
    if (!key) return;
    btn.disabled = true; btn.textContent = "…";
    try {
      const res = await api("/items/" + key);
      const it = await res.json();
      const libVersion = res.headers.get("Last-Modified-Version");
      const colls = it.data.collections || [];
      const mine = (it.data.tags || []).some((t) => t.tag === TAG) && colls.every((c) => c === cfg.collectionKey);
      const what = mine ? "Delete this paper from Zotero (it was saved from this page and is in no other collection)?"
                        : "Remove this paper from “" + cfg.collectionName + "”? It stays in your library.";
      if (!window.confirm(what)) { markDone(btn, key); return; }
      if (mine) {
        const kids = (await (await api("/items/" + key + "/children?format=keys")).text()).split(/\s+/).filter(Boolean);
        await api("/items?itemKey=" + [key].concat(kids).join(","), { method: "DELETE", headers: { "If-Unmodified-Since-Version": libVersion } });
      } else {
        await patch(key, it.version, { collections: colls.filter((c) => c !== cfg.collectionKey) });
      }
      inColl.delete(btn.dataset.id); markTodo(btn);
    } catch (e) {
      if (/Zotero 404/.test(String(e.message))) { inColl.delete(btn.dataset.id); markTodo(btn); return; }
      btn.textContent = "!"; btn.title = String(e.message || e); btn.disabled = false;
    }
  }

  // -- wiring --------------------------------------------------------------
  document.addEventListener("click", (ev) => {
    const btn = ev.target.closest("button.zot");
    if (btn && cfg && !btn.disabled) { ev.preventDefault(); if (btn.classList.contains("zot-done")) remove(btn); else add(btn); }
    const setup = ev.target.closest("a.zot-setup");
    if (setup && dialog) { ev.preventDefault(); showDialog(); }
  });
  function showDialog() {
    form.classList.toggle("connected", !!cfg);
    form.userId.value = ""; form.apiKey.value = "";
    form.collection.value = cfg ? cfg.collectionName : "to-read";
    form.userId.required = form.apiKey.required = !cfg;
    status.textContent = cfg ? "Connected as user " + cfg.userId + ", saving to “" + cfg.collectionName + "” (" + inColl.size + " papers). The key stays in this browser." : "";
    dialog.showModal();
  }
  if (form) {
    form.addEventListener("submit", async (ev) => {
      const action = ev.submitter && ev.submitter.value;
      if (action === "disconnect") {
        ev.preventDefault(); cfg = null; try { localStorage.removeItem(KEY); } catch (e) {}
        sync(); showDialog(); status.textContent = "Disconnected. Enter a user ID and key to connect again."; return;
      }
      if (action !== "save") return;
      ev.preventDefault();
      status.textContent = "Checking…";
      try { await connect(form.userId.value, form.apiKey.value, form.collection.value); dialog.close(); await sync(); }
      catch (e) { cfg = load(KEY, null); status.textContent = String(e.message || e); }
    });
  }
  try { localStorage.removeItem("qod.zotero.added"); } catch (e) {} // pre-sync bookkeeping, no longer used
  sync();
})();
