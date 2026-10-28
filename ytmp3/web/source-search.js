/* Search sources and website previews share the existing explicit download form. */
const Ytmp3Sources = (() => {
  const youtube = { id: "youtube", name: "YouTube", template: "https://www.youtube.com/results?search_query={query}" };
  const find = (selector) => document.querySelector(selector);
  let custom = [], selected = "youtube", mounted, bound = false, editing = null;
  let serial = 0, request, result = null;

  function isURL(value) {
    try {
      const url = new URL(value);
      return ["https:", "http:"].includes(url.protocol) && !!url.hostname && !url.username && !url.password;
    } catch { return false; }
  }
  function templateURL(value) {
    let template = value.trim();
    if (!/^https?:\/\//i.test(template)) template = `https://${template}`;
    if (!template.includes("{query}")) throw new Error("Replace the search words in the URL with {query}.");
    const url = new URL(template.replaceAll("{query}", "sample"));
    if (url.protocol !== "https:" || url.username || url.password || !url.hostname.includes(".")
        || /^(localhost|127\.|0\.|\[|appassets\.androidplatform\.net$)/i.test(url.hostname)
        || template.length > 2048) throw new Error("Use a public HTTPS search URL.");
    // The search words belong in a path/query, never in the website's identity.
    if (new URL(template.replaceAll("{query}", "different")).origin !== url.origin)
      throw new Error("Put {query} after the website name, in its path or query.");
    return template;
  }
  function sources() { return [youtube, ...custom]; }
  function source() { return sources().find((item) => item.id === selected) || youtube; }
  try {
    const saved = JSON.parse(localStorage.getItem("ytmp3_sources"));
    if (Array.isArray(saved?.custom)) custom = saved.custom.slice(0, 12).filter((item) => {
      try {
        return typeof item?.id === "string" && item.id !== "youtube" && item.id !== "manage"
          && typeof item.name === "string" && item.name.trim() && item.name.length <= 40
          && typeof item.template === "string" && templateURL(item.template) === item.template;
      } catch { return false; }
    }).filter((item, index, all) => all.findIndex((other) => other.id === item.id) === index);
    if (sources().some((item) => item.id === saved?.selected)) selected = saved.selected;
  } catch { /* An unavailable or old store keeps the default source usable. */ }
  function persist(nextCustom = custom, nextSelected = selected) {
    localStorage.setItem("ytmp3_sources", JSON.stringify({ custom: nextCustom, selected: nextSelected }));
    custom = nextCustom;
    selected = nextSelected;
  }
  function cancelSearch() {
    ++serial;
    request?.abort();
    request = null;
    result = null;
    renderResults();
  }
  function updateInput() {
    const input = find("#url-input"), button = find("#url-form button[type=submit]");
    if (!input || !button) return;
    const link = isURL(input.value.trim());
    find("#add-heading").textContent = `Search ${source().name} or add a link`;
    input.placeholder = `Search ${source().name} or paste a link`;
    const label = link ? "Save MP3 from link" : `Search ${source().name}`;
    button.title = label;
    button.setAttribute("aria-label", label);
    button.innerHTML = link
      ? '<svg class="action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><path d="M12 3v12m-4-4 4 4 4-4M4 18v2h16v-2"/></svg>'
      : '<svg class="action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" aria-hidden="true"><circle cx="10" cy="10" r="6.5"/><path d="m15 15 6 6"/></svg>';
    find("#source-select").title = `Search source: ${source().name}`;
  }
  function populatePicker() {
    const picker = find("#source-select");
    if (!picker) return;
    picker.replaceChildren();
    sources().forEach((item) => picker.add(new Option(item.name, item.id)));
    picker.add(new Option("Manage sources…", "manage"));
    picker.value = selected;
    updateInput();
  }
  function sourceRow(item) {
    const row = document.createElement("div");
    row.className = "source-list-row";
    const label = document.createElement("span");
    label.textContent = item.name;
    row.append(label);
    if (item.id === "youtube") {
      const note = document.createElement("small");
      note.className = "form-note";
      note.textContent = "Built in";
      row.append(note);
      return row;
    }
    const actions = document.createElement("div");
    actions.className = "source-list-actions";
    for (const action of ["Edit", "Remove"]) {
      const button = document.createElement("button");
      button.type = "button";
      button.className = "row-button";
      button.textContent = action;
      button.setAttribute("aria-label", `${action} ${item.name}`);
      button.onclick = () => {
        find("#source-error").textContent = "";
        if (action === "Edit") {
          editing = item.id;
          find("#source-name").value = item.name;
          find("#source-template").value = item.template;
          find("#source-form-title").textContent = "Edit source";
          find("#cancel-source-edit").hidden = false;
          find("#source-name").focus();
        } else {
          try { persist(custom.filter((entry) => entry.id !== item.id), selected === item.id ? "youtube" : selected); }
          catch { find("#source-error").textContent = "Could not save changes on this device."; return; }
          resetEditor();
          renderSources();
          populatePicker();
          cancelSearch();
          find("#source-saved").textContent = `${item.name} removed.`;
          find("#source-name").focus();
        }
      };
      actions.append(button);
    }
    row.append(actions);
    return row;
  }
  function resetEditor() {
    editing = null;
    find("#source-form").reset();
    find("#source-form-title").textContent = "Add a custom source";
    find("#cancel-source-edit").hidden = true;
    find("#source-error").textContent = "";
    find("#source-saved").textContent = "";
  }
  function renderSources() { find("#source-list").replaceChildren(...sources().map(sourceRow)); }
  function bindDialogs() {
    if (bound) return;
    bound = true;
    find("#close-sources").onclick = () => find("#source-dialog").close();
    find("#cancel-source-edit").onclick = () => { resetEditor(); find("#source-name").focus(); };
    find("#source-form").onsubmit = (event) => {
      event.preventDefault();
      find("#source-error").textContent = "";
      find("#source-saved").textContent = "";
      try {
        const name = find("#source-name").value.trim();
        if (!name) throw new Error("Enter a source name.");
        if (sources().some((item) => item.id !== editing && item.name.toLocaleLowerCase() === name.toLocaleLowerCase()))
          throw new Error("Choose a name different from your other sources.");
        if (!editing && custom.length >= 12) throw new Error("Remove a source before adding another (12 maximum).");
        const template = templateURL(find("#source-template").value);
        const item = { id: editing || crypto.randomUUID(), name, template };
        const next = editing ? custom.map((old) => old.id === editing ? item : old) : [...custom, item];
        try { persist(next, item.id); }
        catch { throw new Error("Could not save this source on the device. Your entries are still here."); }
        resetEditor();
        renderSources();
        populatePicker();
        cancelSearch();
        find("#source-saved").textContent = `${name} saved and selected.`;
      } catch (error) { find("#source-error").textContent = error.message; }
    };
    const dialog = find("#source-preview-dialog");
    find("#close-source-preview").onclick = () => dialog.close();
    dialog.addEventListener("close", () => find("#source-preview-content").replaceChildren());
    find("#save-source-preview").onclick = () => {
      const url = find("#source-preview-url").value.trim();
      if (!isURL(url) || url === dialog.dataset.searchUrl) {
        find("#source-preview-error").textContent = "Choose a track page or paste its link first.";
        find("#source-preview-url").focus();
        return;
      }
      dialog.close();
      useLink(url, true);
    };
  }
  function mount(options) {
    mounted = options;
    bindDialogs();
    populatePicker();
    renderResults();
    find("#source-select").onchange = (event) => {
      if (event.target.value === "manage") {
        event.target.value = selected;
        resetEditor();
        renderSources();
        find("#source-dialog").showModal();
        return;
      }
      try { persist(custom, event.target.value); }
      catch {
        event.target.value = selected;
        result = { query: "Search source", items: [], error: "Could not remember this source on the device. Try again." };
        renderResults(); return;
      }
      cancelSearch();
      updateInput();
      find("#url-input").focus();
    };
    find("#url-input").addEventListener("input", () => { cancelSearch(); updateInput(); });
  }
  function useLink(url, save = false) {
    if (!isURL(url) || !mounted) return;
    if (save) mounted.onSave(url);
    else { mounted.onChoose(url); updateInput(); }
  }
  function preview(url, title, isSearch = false) {
    if (mounted.native?.openSourcePreview) {
      mounted.native.openSourcePreview(url, isSearch, document.documentElement.dataset.theme);
      return;
    }
    const dialog = find("#source-preview-dialog");
    dialog.dataset.searchUrl = isSearch ? url : "";
    find("#source-preview-title").textContent = title || "Website preview";
    find("#source-preview-host").textContent = new URL(url).hostname;
    find("#source-preview-url").value = isSearch ? "" : url;
    find("#source-preview-error").textContent = "";
    find("#source-preview-open").href = url;
    find("#source-preview-help").textContent = isSearch
      ? "Some websites block previews. If needed, open the website, then paste the track link here to save it."
      : "Preview this page, then save its audio to your library.";
    const frame = document.createElement("iframe");
    const parsed = new URL(url);
    const id = ["www.youtube.com", "youtube.com", "m.youtube.com"].includes(parsed.hostname)
      ? parsed.searchParams.get("v") : parsed.hostname === "youtu.be" ? parsed.pathname.slice(1) : null;
    frame.title = title || "Website preview";
    frame.referrerPolicy = "strict-origin-when-cross-origin";
    frame.setAttribute("sandbox", "allow-scripts allow-same-origin allow-forms allow-popups");
    frame.allow = "encrypted-media; fullscreen";
    frame.src = id && /^[\w-]{11}$/.test(id) ? `https://www.youtube-nocookie.com/embed/${id}` : url;
    find("#source-preview-content").replaceChildren(frame);
    dialog.showModal();
  }
  function renderResults() {
    const box = find("#source-results");
    if (!box) return;
    box.replaceChildren();
    box.hidden = !result;
    box.closest(".download-panel").classList.toggle("has-search-results", !!result);
    if (!result) return;
    const heading = document.createElement("div");
    heading.className = "result-heading";
    const title = document.createElement("h3");
    title.textContent = `YouTube · ${result.query}`;
    const clear = document.createElement("button");
    clear.className = "icon-button";
    clear.type = "button";
    clear.textContent = "×";
    clear.setAttribute("aria-label", "Close search results");
    clear.onclick = () => { cancelSearch(); find("#url-input")?.focus(); };
    heading.append(title, clear);
    box.append(heading);
    const status = document.createElement("p");
    status.setAttribute("role", "status");
    status.className = "form-note";
    status.textContent = result.loading ? "Searching YouTube…" : result.error
      || (result.items.length ? `${result.items.length} ${result.items.length === 1 ? "result" : "results"} · Select one to preview` : "No results. Try a different name or artist.");
    box.append(status);
    if (result.error) {
      const retry = document.createElement("button");
      retry.type = "button";
      retry.className = "row-button";
      retry.textContent = "Retry search";
      retry.onclick = () => search(find("#url-input").value);
      box.append(retry);
    }
    for (const item of result.items || []) {
      const row = document.createElement("button");
      row.type = "button";
      row.className = "search-result";
      row.setAttribute("aria-label", `Preview ${item.title}`);
      if (item.thumbnail) {
        const image = document.createElement("img");
        image.src = item.thumbnail;
        image.alt = "";
        image.loading = "lazy";
        image.referrerPolicy = "no-referrer";
        row.append(image);
      }
      const text = document.createElement("span"), name = document.createElement("strong"), meta = document.createElement("small");
      name.textContent = item.title;
      const duration = Number.isFinite(item.duration) ? `${Math.floor(item.duration / 60)}:${String(Math.floor(item.duration % 60)).padStart(2, "0")}` : "";
      meta.textContent = [item.creator, duration].filter(Boolean).join(" · ");
      text.append(name, meta);
      row.append(text);
      row.onclick = () => preview(item.url, item.title);
      box.append(row);
    }
  }
  async function search(raw) {
    const query = raw.trim();
    cancelSearch();
    if (!query) return;
    if (query.length > 200 || /^[a-z][\w+.-]*:\/\//i.test(query)) {
      result = { query, error: "Enter a name under 200 characters, or paste an HTTP/HTTPS track link.", items: [] };
      renderResults(); return;
    }
    const url = source().template.replaceAll("{query}", encodeURIComponent(query));
    if (mounted.native?.openSourcePreview || selected !== "youtube") {
      preview(url, `${source().name} search`, true);
      return;
    }
    const current = ++serial;
    const controller = new AbortController();
    request = controller;
    const timer = setTimeout(() => controller.abort(), 20000);
    result = { query, loading: true, items: [] };
    renderResults();
    try {
      const response = await fetch("/api/search", { method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ query }), signal: controller.signal });
      const data = await response.json();
      if (!response.ok) throw new Error(data.error || "Search unavailable. Try again.");
      if (!Array.isArray(data.results)) throw new Error("Search unavailable. Try again.");
      if (current === serial) result = { query, items: data.results };
    } catch (error) {
      if (current === serial) result = { query, items: [], error: error.name === "AbortError"
        ? "Search timed out. Check your connection and try again." : error.message };
    } finally {
      clearTimeout(timer);
      if (current === serial) { request = null; renderResults(); }
    }
  }
  return { mount, search, isURL, templateURL };
})();
