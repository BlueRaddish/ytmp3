const $ = (selector) => document.querySelector(selector);
const main = $("#main");
const audio = $("#audio");
const native = window.Ytmp3Android || null;
function stored(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; }
  catch { return fallback; }
}
const savedPlaylists = stored("ytmp3_playlists", []);
const savedQueue = stored("ytmp3_queue", []);
const savedSettings = stored("ytmp3_settings", {});
const state = {
  tracks: [],
  queue: Array.isArray(savedQueue) ? savedQueue.filter((id) => typeof id === "string") : [],
  playlists: Ytmp3Playlists.sanitize(savedPlaylists),
  selectedPlaylist: null,
  settings: { theme: "dark", dense: false, speed: 1, ...savedSettings },
  nativePlayback: {},
  current: -1,
  view: ["library", "playlists", "queue", "settings", "about"].includes(location.hash.slice(1))
    ? location.hash.slice(1) : "library",
  filter: "",
  urlDraft: "",
  repeat: "off",
  shuffle: false,
  job: null,
  snapshotAt: 0,
  keyboardConfirmed: false,
  playerOpen: false
};
const keys = {
  " ": () => togglePlay(),
  ArrowRight: () => seekBy(10),
  ArrowLeft: () => seekBy(-10)
};

function persistLists() {
  localStorage.setItem("ytmp3_playlists", JSON.stringify(state.playlists));
  localStorage.setItem("ytmp3_queue", JSON.stringify(state.queue));
}
function persistSettings() {
  localStorage.setItem("ytmp3_settings", JSON.stringify(state.settings));
  document.documentElement.dataset.dense = String(state.settings.dense);
  document.documentElement.dataset.theme = state.settings.theme === "system"
    ? (matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark") : state.settings.theme;
}
persistSettings();

function capabilities() {
  const root = document.documentElement;
  const mq = (query) => matchMedia(query).matches;
  const width = innerWidth;
  const height = innerHeight;
  root.dataset.pointer = mq("(pointer: fine)") ? "fine" : "coarse";
  root.dataset.hover = mq("(hover: hover)") ? "hover" : "none";
  root.dataset.keyboard = state.keyboardConfirmed ? "present" : "absent";
  root.dataset.size = width < 600 ? "compact" : width < 840 ? "medium"
    : width < 1200 ? "expanded" : width < 1600 ? "large" : "extra-large";
  root.dataset.height = height < 480 ? "compact" : height < 900 ? "medium" : "expanded";
  root.dataset.shell = mq("(display-mode: standalone)") ? "pwa" : "browser";
  root.dataset.online = navigator.onLine ? "online" : "offline";
}
for (const query of ["(pointer: fine)", "(hover: hover)", "(any-pointer: coarse)",
  "(display-mode: standalone)", "(min-width: 600px)", "(min-width: 840px)",
  "(min-width: 1200px)", "(min-width: 1600px)", "(min-height: 480px)",
  "(min-height: 900px)"]) {
  matchMedia(query).addEventListener("change", capabilities);
}
addEventListener("resize", capabilities);
addEventListener("online", () => { capabilities(); refresh(); });
addEventListener("offline", () => { capabilities(); if (!native) showOffline(); });
addEventListener("keydown", (event) => {
  if (!event.altKey && !event.ctrlKey && !event.metaKey
      && !["INPUT", "TEXTAREA", "SELECT"].includes(document.activeElement.tagName)) {
    state.keyboardConfirmed = true;
    capabilities();
    if (keys[event.key]) { event.preventDefault(); keys[event.key](); }
  }
});
capabilities();

function formatTime(seconds) {
  if (!Number.isFinite(seconds)) return "0:00";
  const rounded = Math.floor(seconds);
  return `${Math.floor(rounded / 60)}:${String(rounded % 60).padStart(2, "0")}`;
}
function age(timestamp) {
  const mins = Math.max(0, Math.round((Date.now() - timestamp) / 60000));
  return mins < 1 ? "just now" : mins < 60 ? `${mins} min ago`
    : `${Math.round(mins / 60)} h ago`;
}
function titleOf(track) {
  return track.title || track.id.replace(/\.mp3$/i, "");
}
function currentTrack() {
  return state.tracks.find((item) => item.id === state.queue[state.current]);
}
function toast(message) {
  const box = $("#toast");
  box.textContent = message;
  box.hidden = false;
  clearTimeout(toast.timer);
  toast.timer = setTimeout(() => { box.hidden = true; }, 5000);
}
function showOffline() {
  $("#connection").textContent = "Unavailable";
  $("#connection").classList.add("offline");
  const banner = $("#offline-banner");
  banner.textContent = state.snapshotAt
    ? `Library unavailable. Showing files seen ${age(state.snapshotAt)}. Reconnect to play or save.`
    : "Library unavailable. Check that the ytmp3 app server is running.";
  banner.hidden = false;
}
async function refresh() {
  try {
    let data;
    if (native) data = JSON.parse(native.tracks());
    else {
      const response = await fetch("/api/tracks", { cache: "no-store" });
      if (!response.ok) throw new Error("Library unavailable");
      data = await response.json();
    }
    state.tracks = data.tracks;
    state.snapshotAt = Date.now();
    sessionStorage.setItem("ytmp3_snapshot", JSON.stringify({
      tracks: state.tracks, at: state.snapshotAt
    }));
    $("#connection").textContent = native ? "On this device" : "Connected";
    $("#connection").classList.remove("offline");
    $("#offline-banner").hidden = true;
    render();
  } catch {
    showOffline();
    render();
  }
}

function setView(view, push = true) {
  if (!["library", "playlists", "queue", "settings", "about"].includes(view)) return;
  if (push && state.view === view) return;
  state.view = view;
  if (push) history.pushState({ view }, "", view === "library" ? "/" : `#${view}`);
  render();
  main.focus({ preventScroll: true });
  scrollTo({ top: 0, behavior: "instant" });
}
addEventListener("popstate", () => {
  state.playerOpen = false;
  document.body.classList.remove("player-open");
  $("#expand-player").setAttribute("aria-expanded", "false");
  setView(["playlists", "queue", "settings", "about"].includes(location.hash.slice(1))
    ? location.hash.slice(1) : "library", false);
});
document.querySelectorAll(".nav-item").forEach((button) =>
  button.addEventListener("click", () => setView(button.dataset.view))
);

function render() {
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === state.view);
    button.setAttribute("aria-current", button.dataset.view === state.view ? "page" : "false");
  });
  $("#queue-count").textContent = String(state.queue.length);
  $("#page-title").textContent = state.view[0].toUpperCase() + state.view.slice(1);
  if (state.view === "library") renderLibrary();
  else if (state.view === "playlists") renderPlaylists();
  else if (state.view === "queue") renderQueue();
  else if (state.view === "settings") renderSettings();
  else renderAbout();
  updatePlayer();
}

function renderLibrary() {
  main.innerHTML = `<div class="content">
    <p class="eyebrow">Your space for sound</p>
    <h1>Your audio, in one place.</h1>
    <p class="intro">Save from a link you supply, then play from your personal library on ${native ? "this phone" : "this PC or a connected device"}.</p>
    <section class="download-panel" aria-labelledby="add-heading">
      <form id="url-form"><label id="add-heading" for="url-input">Add from URL or playlist</label>
        <div class="url-form"><input id="url-input" class="url-input" type="url" required
          inputmode="url" autocomplete="url" placeholder="https://example.org/recording"
          aria-describedby="url-note"><button class="primary-button" type="submit">Save as MP3</button></div>
        <p class="form-note" id="url-note">Downloads use yt-dlp. Playlists are limited to 100 items. Save only content you have permission to copy.</p>
      </form><div id="job-container"></div>
    </section>
    <div class="section-head"><div><h2>Library</h2><p id="library-count"></p></div>
      <input id="filter" class="search-input" type="search" placeholder="Filter files" aria-label="Filter files"></div>
    <div id="track-list" class="track-list"></div>
  </div>`;
  $("#filter").value = state.filter;
  $("#url-input").value = state.urlDraft;
  $("#url-input").addEventListener("input", (event) => { state.urlDraft = event.target.value; });
  $("#filter").addEventListener("input", (event) => {
    state.filter = event.target.value;
    renderTracks();
  });
  $("#url-form").addEventListener("submit", submitURL);
  const shared = sessionStorage.getItem("ytmp3_shared_url");
  if (shared) {
    state.urlDraft = shared;
    $("#url-input").value = shared;
    sessionStorage.removeItem("ytmp3_shared_url");
  }
  renderJob();
  renderTracks();
}

function renderTracks() {
  const list = $("#track-list");
  if (!list) return;
  const filtered = state.tracks.filter((track) =>
    titleOf(track).toLocaleLowerCase().includes(state.filter.toLocaleLowerCase()));
  $("#library-count").textContent = `${state.tracks.length} ${state.tracks.length === 1 ? "file" : "files"}`;
  list.replaceChildren();
  if (!filtered.length) {
    const box = document.createElement("div");
    box.className = "empty";
    const strong = document.createElement("strong");
    strong.textContent = state.tracks.length ? "No matching files" : "Your library is ready";
    const note = document.createElement("p");
    note.textContent = state.tracks.length ? "Try a different filter."
      : "Supply a URL above to save your first MP3.";
    box.append(strong, note);
    list.append(box);
    return;
  }
  filtered.forEach((track) => list.append(trackRow(track)));
}

function trackRow(track, inQueue = false, index = -1) {
  const row = document.createElement("div");
  row.className = "track-row";
  if (currentTrack()?.id === track.id) row.classList.add("current");
  const art = document.createElement("div");
  art.className = "track-art";
  art.setAttribute("aria-hidden", "true");
  art.textContent = "♪";
  const meta = document.createElement("div");
  meta.className = "track-meta";
  const name = document.createElement("strong");
  name.textContent = titleOf(track);
  const sub = document.createElement("span");
  sub.textContent = `${(track.size / 1048576).toFixed(1)} MB · MP3`;
  meta.append(name, sub);
  const actions = document.createElement("div");
  actions.className = "track-actions";
  const play = document.createElement("button");
  play.className = "row-button";
  play.type = "button";
  play.textContent = "Play";
  play.setAttribute("aria-label", `Play ${titleOf(track)}`);
  play.addEventListener("click", () => playTrack(track.id));
  actions.append(play);
  if (inQueue) {
    for (const [label, change] of [["↑", -1], ["↓", 1]]) {
      const moveButton = document.createElement("button");
      moveButton.className = "row-button";
      moveButton.type = "button";
      moveButton.textContent = label;
      moveButton.disabled = index + change < 0 || index + change >= state.queue.length;
      moveButton.setAttribute("aria-label", `${change < 0 ? "Move up" : "Move down"} ${titleOf(track)}`);
      moveButton.addEventListener("click", () => {
        state.queue = Ytmp3Playlists.move(state.queue, index, change);
        if (state.current === index) state.current = index + change;
        else if (state.current === index + change) state.current = index;
        persistLists();
        syncNativeQueue();
        renderQueue();
      });
      actions.append(moveButton);
    }
    const remove = document.createElement("button");
    remove.className = "row-button";
    remove.type = "button";
    remove.textContent = "Remove";
    remove.setAttribute("aria-label", `Remove ${titleOf(track)} from queue`);
    remove.addEventListener("click", () => {
      state.queue.splice(index, 1);
      if (state.current >= index) state.current--;
      persistLists();
      syncNativeQueue();
      render();
    });
    actions.append(remove);
  } else {
    const next = document.createElement("button");
    next.className = "row-button";
    next.type = "button";
    next.textContent = "Next";
    next.setAttribute("aria-label", `Play ${titleOf(track)} next`);
    next.addEventListener("click", () => {
      state.queue.splice(Math.max(0, state.current + 1), 0, track.id);
      persistLists(); syncNativeQueue(); render(); toast("Added next");
    });
    actions.append(next);
    const add = document.createElement("button");
    add.className = "row-button";
    add.type = "button";
    add.textContent = "Queue";
    add.setAttribute("aria-label", `Add ${titleOf(track)} to queue`);
    add.addEventListener("click", () => {
      state.queue.push(track.id);
      persistLists(); syncNativeQueue();
      $("#queue-count").textContent = String(state.queue.length);
      toast("Added to queue");
    });
    actions.append(add);
    const playlist = document.createElement("button");
    playlist.className = "row-button";
    playlist.type = "button";
    playlist.textContent = "Playlist";
    playlist.setAttribute("aria-label", `Add ${titleOf(track)} to playlist`);
    playlist.addEventListener("click", () => openPlaylistPicker(track.id));
    actions.append(playlist);
    if (!track.external) {
    const save = document.createElement("a");
    save.className = "button-link";
    save.href = native ? "#" : `/export/${encodeURIComponent(track.id)}`;
    if (!native) save.download = track.id;
    save.textContent = "Save file";
    save.setAttribute("aria-label", `Save ${titleOf(track)} to this device`);
    if (native) save.addEventListener("click", (event) => {
      event.preventDefault();
      const result = JSON.parse(native.exportTrack(track.id));
      toast(result.error || "Saving to Music on this phone…");
    });
    actions.append(save);
    }
  }
  row.append(art, meta, actions);
  return row;
}

function createPlaylist(name, ids = []) {
  const list = Ytmp3Playlists.create(state.playlists, name, ids);
  if (!list) { toast("Enter a unique playlist name."); return null; }
  state.playlists.push(list);
  state.selectedPlaylist = list.id;
  persistLists();
  return list;
}

function uniquePlaylistName(raw) {
  const base = (raw.trim() || "Imported playlist").slice(0, 80);
  let label = base;
  for (let number = 2; state.playlists.some((list) => list.name.toLocaleLowerCase() === label.toLocaleLowerCase()); number++) {
    label = `${base.slice(0, 75)} (${number})`;
  }
  return label;
}

function openPlaylistPicker(id) {
  const dialog = $("#playlist-dialog");
  dialog.dataset.track = id;
  const choice = $("#playlist-choice");
  choice.replaceChildren();
  for (const list of state.playlists) choice.add(new Option(list.name, list.id));
  choice.disabled = !state.playlists.length;
  $("#playlist-new").value = "";
  dialog.showModal();
  (choice.disabled ? $("#playlist-new") : choice).focus();
}
$("#playlist-cancel").addEventListener("click", () => $("#playlist-dialog").close());
$("#playlist-picker").addEventListener("submit", (event) => {
  event.preventDefault();
  const name = $("#playlist-new").value;
  const list = name.trim() ? createPlaylist(name) : state.playlists.find((item) => item.id === $("#playlist-choice").value);
  if (!list) { if (!name.trim()) toast("Create or choose a playlist."); return; }
  Ytmp3Playlists.add(list, $("#playlist-dialog").dataset.track);
  persistLists();
  $("#playlist-dialog").close();
  toast(`Added to ${list.name}`);
  if (state.view === "playlists") renderPlaylists();
});

function renderPlaylists() {
  main.innerHTML = `<div class="content"><p class="eyebrow">Your collections</p><h1>Playlists</h1>
    <p class="intro">Keep collections on this device. Add tracks from Library, save the queue, or import an M3U file of tracks already in this library.</p>
    <form id="create-playlist" class="inline-form"><input id="new-playlist-name" class="url-input" type="text"
      maxlength="80" placeholder="New playlist name" aria-label="New playlist name" required>
      <button class="primary-button" type="submit">Create</button></form>
    <div class="section-actions"><button class="row-button" id="import-playlist" type="button">Import M3U playlist</button>
      <input id="playlist-file" type="file" accept=".m3u,.m3u8" hidden></div>
    <div id="playlist-list" class="playlist-list"></div><div id="playlist-detail"></div></div>`;
  $("#create-playlist").addEventListener("submit", (event) => {
    event.preventDefault();
    if (createPlaylist($("#new-playlist-name").value)) renderPlaylists();
  });
  $("#import-playlist").addEventListener("click", () => native ? native.pickPlaylist() : $("#playlist-file").click());
  $("#playlist-file").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (file) importPlaylistFile(file.name, await file.text());
  });
  const listBox = $("#playlist-list");
  if (!state.playlists.length) listBox.innerHTML = '<div class="empty"><strong>No playlists yet</strong><p>Create one above or add a library track.</p></div>';
  for (const list of state.playlists) {
    const button = document.createElement("button");
    button.type = "button";
    button.className = "playlist-card" + (state.selectedPlaylist === list.id ? " selected" : "");
    button.textContent = `${list.name} · ${list.tracks.length} tracks`;
    button.addEventListener("click", () => { state.selectedPlaylist = list.id; renderPlaylists(); });
    listBox.append(button);
  }
  const selected = state.playlists.find((list) => list.id === state.selectedPlaylist) || state.playlists[0];
  if (!selected) return;
  state.selectedPlaylist = selected.id;
  const detail = $("#playlist-detail");
  detail.innerHTML = `<div class="section-head"><div><h2 id="selected-name"></h2><p id="selected-count"></p></div>
    <div class="section-actions"><button class="row-button" id="playlist-play" type="button">Play</button>
    <button class="row-button" id="playlist-queue" type="button">Add to queue</button></div></div>
    <form id="rename-playlist" class="inline-form"><input id="rename-value" class="url-input" maxlength="80" aria-label="Rename playlist" required>
      <button class="row-button" type="submit">Rename</button><button class="row-button" id="delete-playlist" type="button">Delete</button></form>
    <div class="track-list" id="playlist-tracks"></div>`;
  $("#selected-name").textContent = selected.name;
  $("#selected-count").textContent = `${selected.tracks.length} tracks · use arrows to reorder`;
  $("#rename-value").value = selected.name;
  $("#rename-playlist").addEventListener("submit", (event) => {
    event.preventDefault();
    const value = $("#rename-value").value.trim();
    if (!value || state.playlists.some((item) => item.id !== selected.id && item.name.toLowerCase() === value.toLowerCase())) {
      toast("Choose a unique playlist name."); return;
    }
    selected.name = value; persistLists(); renderPlaylists();
  });
  $("#delete-playlist").addEventListener("click", () => {
    const dialog = $("#confirm-dialog");
    $("#confirm-text").textContent = `Delete “${selected.name}”? The audio files stay in Library.`;
    dialog.returnValue = "";
    dialog.addEventListener("close", () => {
      if (dialog.returnValue !== "delete") return;
      state.playlists = state.playlists.filter((item) => item.id !== selected.id);
      state.selectedPlaylist = null; persistLists(); renderPlaylists();
    }, { once: true });
    dialog.showModal();
  });
  $("#playlist-play").disabled = !selected.tracks.some((id) => state.tracks.some((item) => item.id === id));
  $("#playlist-play").addEventListener("click", () => {
    state.queue = selected.tracks.filter((id) => state.tracks.some((item) => item.id === id));
    state.current = 0; persistLists();
    if (state.queue.length) playTrack(state.queue[0]);
  });
  $("#playlist-queue").addEventListener("click", () => {
    state.queue.push(...selected.tracks.filter((id) => state.tracks.some((item) => item.id === id)));
    persistLists(); syncNativeQueue(); render(); toast("Playlist added to queue");
  });
  const songs = $("#playlist-tracks");
  if (!selected.tracks.length) songs.innerHTML = '<div class="empty"><strong>Nothing here yet</strong><p>Add tracks from Library.</p></div>';
  selected.tracks.forEach((id, index) => {
    const track = state.tracks.find((item) => item.id === id);
    const row = document.createElement("div"); row.className = "playlist-track";
    const title = document.createElement("span"); title.textContent = track ? titleOf(track) : "Unavailable track";
    row.append(title);
    for (const [label, change] of [["↑", -1], ["↓", 1]]) {
      const button = document.createElement("button"); button.type = "button"; button.className = "row-button";
      button.textContent = label; button.disabled = index + change < 0 || index + change >= selected.tracks.length;
      button.setAttribute("aria-label", `${change < 0 ? "Move up" : "Move down"} ${title.textContent}`);
      button.addEventListener("click", () => {
        selected.tracks = Ytmp3Playlists.move(selected.tracks, index, change);
        persistLists(); renderPlaylists();
      }); row.append(button);
    }
    const remove = document.createElement("button"); remove.type = "button"; remove.className = "row-button";
    remove.textContent = "Remove"; remove.setAttribute("aria-label", `Remove ${title.textContent}`);
    remove.addEventListener("click", () => { selected.tracks.splice(index, 1); persistLists(); renderPlaylists(); });
    row.append(remove); songs.append(row);
  });
}

function renderQueue() {
  main.innerHTML = `<div class="content"><p class="eyebrow">Coming up</p><h1>Queue</h1>
    <p class="intro">Play through the files you chose. Shuffle and repeat are in the player controls.</p>
    <div class="section-actions"><button id="clear-queue" class="row-button" type="button">Clear queue</button></div>
    <form id="save-queue" class="inline-form"><input id="queue-name" class="url-input" type="text" maxlength="80"
      placeholder="Name this queue" aria-label="Playlist name" required><button class="row-button" type="submit">Save as playlist</button></form>
    <div id="queue-list" class="track-list"></div></div>`;
  $("#clear-queue").disabled = !state.queue.length;
  $("#clear-queue").addEventListener("click", () => {
    state.queue = []; state.current = -1; audio.pause();
    if (native) native.command("stop", 0);
    persistLists(); render();
  });
  $("#save-queue").addEventListener("submit", (event) => {
    event.preventDefault();
    if (createPlaylist($("#queue-name").value, state.queue)) {
      toast("Queue saved as playlist"); setView("playlists");
    }
  });
  const list = $("#queue-list");
  if (!state.queue.length) {
    list.innerHTML = '<div class="empty"><strong>Nothing queued yet</strong><p>Play a library file or add it to the queue.</p></div>';
    return;
  }
  state.queue.forEach((id, index) => {
    const track = state.tracks.find((item) => item.id === id);
    if (track) list.append(trackRow(track, true, index));
    else {
      const missing = document.createElement("div"); missing.className = "playlist-track";
      missing.textContent = "Unavailable track ";
      const remove = document.createElement("button"); remove.type = "button"; remove.className = "row-button";
      remove.textContent = "Remove";
      remove.addEventListener("click", () => { state.queue.splice(index, 1); persistLists(); renderQueue(); });
      missing.append(remove); list.append(missing);
    }
  });
}

function renderSettings() {
  main.innerHTML = `<div class="content"><p class="eyebrow">Make it yours</p><h1>Settings</h1>
    <p class="intro">These preferences stay on this device.</p>
    <section class="settings-card"><h2>Interface</h2>
      <label class="setting-row">Appearance <select id="theme-setting"><option value="system">Follow device</option>
        <option value="dark">Dark</option><option value="light">Light</option></select></label>
      <label class="setting-row">Compact library rows <input id="dense-setting" type="checkbox"></label>
      <label class="setting-row">Default playback speed <select id="speed-setting">
        <option value="0.75">0.75×</option><option value="1">1×</option><option value="1.25">1.25×</option>
        <option value="1.5">1.5×</option><option value="2">2×</option></select></label>
    </section><section class="settings-card"><h2>Media library</h2>
      <p>${native ? "Choose folders whose MP3 files should appear alongside downloads. Subfolders are included." : "Start the PC app with --include FOLDER for each additional media folder. Subfolders are included; --library PATH changes the download folder."}</p>
      <div class="section-actions"><button id="add-folder" class="row-button" type="button" ${native ? "" : "hidden"}>Add folder</button>
        <button id="rescan" class="row-button" type="button">Rescan library</button></div>
      <div id="folder-list"></div></section></div>`;
  $("#theme-setting").value = state.settings.theme;
  $("#dense-setting").checked = !!state.settings.dense;
  $("#speed-setting").value = String(state.settings.speed);
  $("#theme-setting").addEventListener("change", (event) => {
    state.settings.theme = event.target.value; persistSettings();
  });
  $("#dense-setting").addEventListener("change", (event) => {
    state.settings.dense = event.target.checked; persistSettings();
  });
  $("#speed-setting").addEventListener("change", (event) => {
    state.settings.speed = Number(event.target.value); persistSettings();
    if (native) native.command("speed", state.settings.speed);
    else audio.playbackRate = state.settings.speed;
    $("#speed").textContent = `${state.settings.speed}×`;
  });
  $("#rescan").addEventListener("click", () => refresh());
  if (native) {
    $("#add-folder").addEventListener("click", () => native.pickFolder());
    const folders = JSON.parse(native.folders());
    for (const folder of folders) {
      const row = document.createElement("div"); row.className = "folder-row";
      const name = document.createElement("span"); name.textContent = folder.name;
      const remove = document.createElement("button"); remove.type = "button"; remove.className = "row-button";
      remove.textContent = "Remove"; remove.setAttribute("aria-label", `Remove folder ${folder.name}`);
      remove.addEventListener("click", () => {
        native.removeFolder(folder.uri); refresh(); renderSettings();
      });
      row.append(name, remove); $("#folder-list").append(row);
    }
  }
}
window.ytmp3FoldersChanged = () => { refresh(); if (state.view === "settings") renderSettings(); };

function renderAbout() {
  main.innerHTML = `<div class="content"><p class="eyebrow">Under the hood</p><h1>About ytmp3</h1>
    <p class="intro">A URL-to-MP3 wrapper and a personal player.</p>
    <div class="about-card"><h2>Powered by yt-dlp</h2>
      <p><a href="https://github.com/yt-dlp/yt-dlp" target="_blank" rel="noopener noreferrer">yt-dlp</a>
      performs site extraction and downloading. ffmpeg converts audio to MP3. ytmp3 adds the
      personal library, interface, player and file handling.</p>
      <p>Only download content you are authorized to copy. This app does not supply a media catalog or licenses.</p>
      ${native ? '<p>Android bundles <a href="https://github.com/yausername/youtubedl-android">youtubedl-android</a>. <a href="/licenses/youtubedl-android-GPL-3.0.txt">Read its GPL-3.0 license</a>.</p>' : ''}
      <h2>Player controls</h2>
      <ul><li>Play and pause, next and previous</li><li>Seek, volume and speed</li>
      <li>Shuffle and repeat</li><li>Save a library file to the current device</li></ul>
      <p>${native ? "Files are stored on this phone. Save file exports a copy to your Music folder." : "Files are stored on the computer running the ytmp3 server. Keep that computer running for phone playback."}</p>
    </div></div>`;
}

function importPlaylistFile(name, text) {
  if (!/\.m3u8?$/i.test(name) || text.length > 1024 * 1024) { toast("Choose an M3U playlist under 1 MB."); return; }
  let result;
  try { result = Ytmp3Playlists.importM3U(text, state.tracks); }
  catch { toast("Could not read this playlist."); return; }
  if (!result.tracks.length) { toast(`No library tracks matched; ${result.missing} entries skipped.`); return; }
  const list = createPlaylist(uniquePlaylistName(name.replace(/\.m3u8?$/i, "")), result.tracks);
  if (!list) { toast("Could not create the playlist."); return; }
  state.selectedPlaylist = list.id;
  renderPlaylists();
  toast(`Imported ${result.tracks.length} tracks; ${result.missing} unmatched.`);
}
window.ytmp3PlaylistFile = importPlaylistFile;

async function submitURL(event) {
  event.preventDefault();
  const input = $("#url-input");
  const button = $("#url-form button[type=submit]");
  const url = input.value.trim();
  if (!url) return;
  button.disabled = true;
  try {
    let data;
    if (native) data = JSON.parse(native.submit(url));
    else {
      const response = await fetch("/api/download", {
        method: "POST", headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url })
      });
      data = await response.json();
      if (!response.ok) throw new Error(data.error || "Could not start download.");
    }
    if (data.error) throw new Error(data.error);
    state.job = { id: data.job, state: "queued" };
    renderJob();
    pollJob(data.job);
  } catch (error) {
    toast(error.message);
  } finally {
    button.disabled = false;
  }
}

function renderJob() {
  const container = $("#job-container");
  if (!container) return;
  container.replaceChildren();
  if (!state.job) return;
  const box = document.createElement("div");
  box.className = `job ${state.job.state === "error" ? "error" : ""}`;
  const dot = document.createElement("span");
  dot.className = "job-indicator";
  dot.setAttribute("aria-hidden", "true");
  const message = document.createElement("span");
  const total = state.job.total || 0;
  message.textContent = state.job.state === "queued" ? "Waiting to download…"
    : state.job.state === "working" ? total > 1
      ? `Processing ${state.job.completed || 0} of ${total}… ${state.job.saved || 0} saved`
      : "Downloading and converting…"
    : state.job.state === "error" ? state.job.error
    : `Saved ${state.job.saved || 1} of ${total || 1} to your library${state.job.failed ? `; ${state.job.failed} skipped` : ""}.`;
  box.append(dot, message);
  container.append(box);
}

async function pollJob(id) {
  try {
    if (native) state.job = JSON.parse(native.job(id));
    else {
      const response = await fetch(`/api/jobs/${encodeURIComponent(id)}`, { cache: "no-store" });
      if (!response.ok) throw new Error("Cannot check the download.");
      state.job = await response.json();
    }
    if (!state.job) throw new Error("Cannot check the download.");
    renderJob();
    if (state.job.state === "done") {
      toast(state.job.failed ? `${state.job.saved} saved; ${state.job.failed} skipped.` : "Saved to your library");
      state.urlDraft = "";
      if ($("#url-input")) $("#url-input").value = "";
      await refresh();
      if (state.job.playlist && Array.isArray(state.job.tracks)) {
        const ids = state.job.tracks.filter((track) => state.tracks.some((item) => item.id === track));
        if (ids.length) createPlaylist(uniquePlaylistName(state.job.playlist), ids);
      }
      return;
    }
    if (state.job.state === "error") return;
    setTimeout(() => pollJob(id), 1000);
  } catch {
    showOffline();
    setTimeout(() => pollJob(id), 3000);
  }
}

function playTrack(id) {
  if (!state.queue.includes(id)) state.queue = state.tracks.map((item) => item.id);
  state.queue = state.queue.filter((item) => state.tracks.some((track) => track.id === item));
  state.current = state.queue.indexOf(id);
  const track = currentTrack();
  if (!track) return;
  persistLists();
  if (native) {
    native.playQueue(JSON.stringify(queueItems()), state.current);
    native.command("speed", state.settings.speed);
    render();
    return;
  }
  audio.src = `/media/${encodeURIComponent(track.id)}`;
  audio.playbackRate = state.settings.speed;
  audio.play().catch(() => toast("Tap Play to start audio."));
  if ("mediaSession" in navigator) {
    navigator.mediaSession.metadata = new MediaMetadata({
      title: titleOf(track), artist: "ytmp3 library"
    });
  }
  render();
}
function queueItems() {
  return state.queue.map((id) => state.tracks.find((item) => item.id === id))
    .filter(Boolean).map((track) => ({ id: track.id, title: titleOf(track) }));
}
function syncNativeQueue() {
  if (native) native.replaceQueue(JSON.stringify(queueItems()), Math.max(0, state.current));
}
function seekBy(seconds) {
  if (native) native.command("seek", Math.max(0, (state.nativePlayback.position || 0) + seconds * 1000));
  else if (audio.duration) audio.currentTime = Math.max(0, Math.min(audio.duration, audio.currentTime + seconds));
}
function togglePlay() {
  if (native) {
    if (!state.nativePlayback.id && state.tracks.length) return playTrack(state.tracks[0].id);
    native.command(state.nativePlayback.playing ? "pause" : "play", 0);
    return;
  }
  if (!audio.src && state.tracks.length) return playTrack(state.tracks[0].id);
  if (audio.paused) audio.play().catch(() => toast("Playback could not start."));
  else audio.pause();
}
function move(direction, fromEnd = false) {
  if (native) { native.command(direction > 0 ? "next" : "previous", 0); return; }
  if (!state.queue.length) return;
  if (direction < 0 && audio.currentTime > 3 && !fromEnd) {
    audio.currentTime = 0;
    return;
  }
  let next = state.current + direction;
  if (state.shuffle && state.queue.length > 1 && direction > 0) {
    do { next = Math.floor(Math.random() * state.queue.length); }
    while (next === state.current);
  }
  if (next >= state.queue.length || next < 0) {
    if (state.repeat === "all") next = direction > 0 ? 0 : state.queue.length - 1;
    else { audio.pause(); if (fromEnd) audio.currentTime = 0; return; }
  }
  state.current = next;
  persistLists();
  playTrack(state.queue[next]);
}
function updatePlayer() {
  const track = currentTrack();
  $("#player-title").textContent = track ? titleOf(track) : "Nothing playing";
  $("#player-subtitle").textContent = track ? "Personal library" : "Choose a file from your library";
  const playing = native ? state.nativePlayback.playing : !audio.paused;
  const duration = native ? Math.ceil((state.nativePlayback.duration || 0) / 1000) : audio.duration;
  const position = Math.min(duration || Infinity,
    native ? (state.nativePlayback.position || 0) / 1000 : audio.currentTime);
  $("#play").textContent = playing ? "Ⅱ" : "▶";
  $("#play").setAttribute("aria-label", playing ? "Pause" : "Play");
  $("#elapsed").textContent = formatTime(position);
  $("#duration").textContent = formatTime(duration);
  $("#seek").value = duration ? Math.round(position / duration * 1000) : 0;
}
function openPlayer() {
  if (!matchMedia("(max-width: 839px)").matches || state.playerOpen) return;
  state.playerOpen = true;
  document.body.classList.add("player-open");
  $("#expand-player").setAttribute("aria-expanded", "true");
  history.pushState({ view: state.view, player: true }, "", "#player");
  $("#close-player").focus();
}
function closePlayer() {
  if (state.playerOpen) history.back();
}
$("#expand-player").addEventListener("click", openPlayer);
$("#close-player").addEventListener("click", closePlayer);
$("#play").addEventListener("click", togglePlay);
$("#previous").addEventListener("click", () => move(-1));
$("#next").addEventListener("click", () => move(1));
$("#shuffle").addEventListener("click", () => {
  state.shuffle = !state.shuffle;
  if (native) native.command("shuffle", state.shuffle ? 1 : 0);
  $("#shuffle").setAttribute("aria-pressed", String(state.shuffle));
  $("#shuffle").setAttribute("aria-label", state.shuffle ? "Shuffle on" : "Shuffle off");
});
$("#repeat").addEventListener("click", () => {
  state.repeat = { off: "all", all: "one", one: "off" }[state.repeat];
  if (native) native.command("repeat", { off: 0, one: 1, all: 2 }[state.repeat]);
  $("#repeat").dataset.active = String(state.repeat !== "off");
  $("#repeat").setAttribute("aria-label", `Repeat ${state.repeat}`);
  toast(`Repeat ${state.repeat}`);
});
$("#speed").addEventListener("click", () => {
  const speeds = [1, 1.25, 1.5, 2, 0.75];
  state.settings.speed = speeds[(speeds.indexOf(state.settings.speed) + 1) % speeds.length];
  persistSettings();
  if (native) native.command("speed", state.settings.speed);
  else audio.playbackRate = state.settings.speed;
  $("#speed").textContent = `${state.settings.speed}×`;
});
$("#volume").addEventListener("input", (event) => {
  if (native) native.command("volume", Number(event.target.value) / 100);
  else audio.volume = Number(event.target.value) / 100;
});
$("#seek").addEventListener("input", (event) => {
  if (native) native.command("seek", Number(event.target.value) / 1000 * (state.nativePlayback.duration || 0));
  else if (audio.duration) audio.currentTime = Number(event.target.value) / 1000 * audio.duration;
});
audio.addEventListener("timeupdate", updatePlayer);
audio.addEventListener("loadedmetadata", updatePlayer);
audio.addEventListener("play", updatePlayer);
audio.addEventListener("pause", updatePlayer);
audio.addEventListener("ended", () => {
  if (state.repeat === "one") { audio.currentTime = 0; audio.play(); }
  else move(1, true);
});
audio.addEventListener("error", () => toast(native ? "This file could not be played." : "This file could not be played. Check the server connection."));
if (!native && "mediaSession" in navigator) {
  navigator.mediaSession.setActionHandler("play", () => audio.play());
  navigator.mediaSession.setActionHandler("pause", () => audio.pause());
  navigator.mediaSession.setActionHandler("previoustrack", () => move(-1));
  navigator.mediaSession.setActionHandler("nexttrack", () => move(1));
}

if (native) setInterval(() => {
  try {
    const playback = JSON.parse(native.playback());
    if (!playback.id && !state.nativePlayback.id) return;
    const changed = playback.id !== state.nativePlayback.id;
    state.nativePlayback = playback;
    if (playback.id) state.current = playback.index;
    if (typeof playback.shuffle === "boolean") {
      state.shuffle = playback.shuffle;
      $("#shuffle").setAttribute("aria-pressed", String(state.shuffle));
      $("#shuffle").setAttribute("aria-label", state.shuffle ? "Shuffle on" : "Shuffle off");
    }
    if ([0, 1, 2].includes(playback.repeat)) {
      state.repeat = ["off", "one", "all"][playback.repeat];
      $("#repeat").dataset.active = String(state.repeat !== "off");
      $("#repeat").setAttribute("aria-label", `Repeat ${state.repeat}`);
    }
    updatePlayer();
    if (changed && state.view === "library") renderTracks();
    if (changed && state.view === "queue") renderQueue();
  } catch { /* The controller is reconnecting. */ }
}, 500);

$("#theme-button").addEventListener("click", () => {
  const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  state.settings.theme = theme;
  persistSettings();
  if (state.view === "settings") renderSettings();
});
matchMedia("(prefers-color-scheme: light)").addEventListener("change", () => {
  if (state.settings.theme === "system") persistSettings();
});
$("#speed").textContent = `${state.settings.speed}×`;
if (!native) audio.playbackRate = state.settings.speed;
function receiveShared(text) {
  const received = text?.match(/https?:\/\/\S+/)?.[0];
  if (!received) return;
  state.urlDraft = received;
  state.view = "library";
  history.replaceState(null, "", "/");
  render();
  $("#url-input").focus();
  toast("Shared link ready to save");
}
window.ytmp3Receive = receiveShared;
const shared = new URLSearchParams(location.search);
const received = shared.get("url") || shared.get("text")?.match(/https?:\/\/\S+/)?.[0];
if (received) {
  sessionStorage.setItem("ytmp3_shared_url", received);
  history.replaceState(null, "", "/");
  state.view = "library";
  toast("Shared link ready to save");
}
try {
  const snapshot = JSON.parse(sessionStorage.getItem("ytmp3_snapshot") || "null");
  if (snapshot?.tracks && Array.isArray(snapshot.tracks)) {
    state.tracks = snapshot.tracks;
    state.snapshotAt = snapshot.at;
  }
} catch { /* Ignore an invalid old snapshot. */ }
render();
refresh();
