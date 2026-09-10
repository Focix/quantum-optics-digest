(() => {
  const KEY = "qod.zotero", ADDED = "qod.zotero.added", API = "https://api.zotero.org";
  const load = (k, d) => { try { return JSON.parse(localStorage.getItem(k)) ?? d; } catch (e) { return d; } };
  const save = (k, v) => { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) {} };
  let cfg = load(KEY, null);
  const added = new Set(load(ADDED, []));
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

  function refresh() {
    document.body.classList.toggle("zot-on", !!cfg);
    document.querySelectorAll("button.zot").forEach((b) => {
      if (added.has(b.dataset.id)) { b.classList.add("zot-done"); b.textContent = "\u2713"; b.title = "in Zotero"; }
    });
  }

  async function connect(userId, apiKey, name) {
    cfg = { userId: userId.trim(), apiKey: apiKey.trim(), collectionName: (name || "to-read").trim() || "to-read" };
    const res = await api("/collections?limit=100");
    const found = (await res.json()).find((c) => c.data.name.toLowerCase() === cfg.collectionName.toLowerCase());
    if (found) cfg.collectionKey = found.key;
    else cfg.collectionKey = (await post("/collections", [{ name: cfg.collectionName, parentCollection: false }]))["0"].key;
    save(KEY, cfg);
  }

  function creators(authors) {
    return (authors || []).map((a) => {
      const parts = a.trim().split(/\s+/);
      if (parts.length < 2) return { creatorType: "author", name: a.trim() };
      return { creatorType: "author", firstName: parts.slice(0, -1).join(" "), lastName: parts[parts.length - 1] };
    });
  }
  function itemFor(rec) {
    const arxiv = /^\d{4}\.\d{4,5}(v\d+)?$/.test(rec.id);
    const url = rec.url || "https://arxiv.org/abs/" + rec.id;
    const base = { title: rec.title, creators: creators(rec.authors), abstractNote: rec.abstract || "", date: rec.submitted || "",
      url: url, accessDate: new Date().toISOString().slice(0, 10), collections: [cfg.collectionKey], tags: [{ tag: "digest" }] };
    if (arxiv) Object.assign(base, { itemType: "preprint", repository: "arXiv", archiveID: "arXiv:" + rec.id,
      DOI: "10.48550/arXiv." + rec.id, libraryCatalog: "arXiv.org", extra: "arXiv: " + rec.id + (rec.categories && rec.categories.length ? " [" + rec.categories[0] + "]" : "") });
    else Object.assign(base, { itemType: "journalArticle", DOI: /doi\.org\//.test(url) ? url.split("doi.org/")[1] : "" });
    return { item: base, pdf: arxiv ? "https://arxiv.org/pdf/" + rec.id : null };
  }

  async function record(btn) {
    const src = root + "data/" + btn.dataset.src + ".json";
    if (!cache[src]) cache[src] = fetch(src).then((r) => { if (!r.ok) throw new Error("no data file " + src); return r.json(); });
    const rec = (await cache[src]).items[btn.dataset.id];
    if (!rec) throw new Error("paper not in " + src);
    return rec;
  }

  async function add(btn) {
    btn.disabled = true; btn.textContent = "\u2026";
    try {
      const rec = await record(btn);
      const q = await api("/items?limit=1&qmode=everything&q=" + encodeURIComponent(rec.id));
      if (Number(q.headers.get("Total-Results") || "0") > 0) { btn.title = "already in your library"; }
      else {
        const { item, pdf } = itemFor(rec);
        const key = (await post("/items", [item]))["0"].key;
        const children = [];
        if (pdf) children.push({ itemType: "attachment", linkMode: "linked_url", parentItem: key, title: "arXiv PDF", url: pdf, contentType: "application/pdf" });
        if (rec.why) children.push({ itemType: "note", parentItem: key, note: "<p>" + rec.why + (rec.score != null ? " (digest score " + rec.score + ")" : "") + "</p>" });
        if (children.length) await post("/items", children);
        btn.title = "saved to " + cfg.collectionName;
      }
      added.add(rec.id); save(ADDED, Array.from(added));
      btn.classList.add("zot-done"); btn.textContent = "\u2713";
    } catch (e) {
      btn.textContent = "!"; btn.title = String(e.message || e); btn.disabled = false;
    }
  }

  document.addEventListener("click", (ev) => {
    const btn = ev.target.closest("button.zot");
    if (btn && cfg && !btn.classList.contains("zot-done")) { ev.preventDefault(); add(btn); }
    const setup = ev.target.closest("a.zot-setup");
    if (setup && dialog) { ev.preventDefault(); showDialog(); }
  });
  function showDialog() {
    form.classList.toggle("connected", !!cfg);
    form.userId.value = ""; form.apiKey.value = "";
    form.collection.value = cfg ? cfg.collectionName : "to-read";
    form.userId.required = form.apiKey.required = !cfg;
    status.textContent = cfg ? "Connected as user " + cfg.userId + ", saving to \u201c" + cfg.collectionName + "\u201d. The key stays in this browser." : "";
    dialog.showModal();
  }
  if (form) {
    form.addEventListener("submit", async (ev) => {
      const action = ev.submitter && ev.submitter.value;
      if (action === "disconnect") {
        ev.preventDefault(); cfg = null; try { localStorage.removeItem(KEY); } catch (e) {}
        refresh(); showDialog(); status.textContent = "Disconnected. Enter a user ID and key to connect again."; return;
      }
      if (action !== "save") return;
      ev.preventDefault();
      status.textContent = "Checking\u2026";
      try { await connect(form.userId.value, form.apiKey.value, form.collection.value); refresh(); dialog.close(); }
      catch (e) { cfg = load(KEY, null); status.textContent = String(e.message || e); }
    });
  }
  refresh();
})();
