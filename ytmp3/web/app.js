const $ = (selector) => document.querySelector(selector);
const main = $("#main");
const audio = $("#audio");
const native = window.Ytmp3Android || null;
const iconPaths = {
  play: '<path d="m8 5 11 7-11 7z" fill="currentColor" stroke="none"/>',
  mix: '<path d="M3 7h3c4 0 8 10 12 10h3M3 17h3c4 0 8-10 12-10h3M18 4l3 3-3 3M18 14l3 3-3 3"/>',
  loop: '<path d="M4 10V7a3 3 0 0 1 3-3h11l-3-3M18 4l-3 3M20 14v3a3 3 0 0 1-3 3H6l3 3M6 20l3-3"/>',
  download: '<path d="M12 3v12m-4-4 4 4 4-4M4 18v2h16v-2"/>',
  add: '<path d="M12 4v16M4 12h16"/>',
  select: '<rect x="3.5" y="3.5" width="17" height="17" rx="2"/><path d="m8 12 3 3 5-6"/>',
  all: '<rect x="5" y="5" width="16" height="16" rx="2"/><path d="M2 16V5a3 3 0 0 1 3-3h11m-7 11 3 3 5-6"/>',
  queue: '<path d="M3 6h13M3 12h13M3 18h10M19 15v6m-3-3h6"/>',
  playlist: '<path d="M5 6h10M5 10h10m-9 7a2 2 0 1 0 2 2V13l7-2v4m4-4v8m-4-4h8"/>',
  star: '<path d="m12 2 3 6.5 7 .9-5.1 5 1.2 7-6.1-3.3-6.1 3.3 1.2-7L2 9.4l7-.9z"/>',
  share: '<path d="M12 15V3m-4 4 4-4 4 4M5 13v6a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-6"/>',
  remove: '<circle cx="12" cy="12" r="9"/><path d="M7 12h10"/>',
  close: '<path d="M5 5l14 14M19 5 5 19"/>',
  edit: '<path d="m4 20 4-.8L20 7.2 16.8 4 4.8 16zM14.5 6.3l3.2 3.2"/>',
  refresh: '<path d="M20 11a8 8 0 1 0-2.3 6.7M20 4v7h-7"/>'
};
function icon(name) {
  return `<svg class="action-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true" focusable="false">${iconPaths[name]}</svg>`;
}
function iconize(root) {
  root.querySelectorAll("[data-icon]").forEach((button) => {
    if (!iconPaths[button.dataset.icon] || button.dataset.iconReady) return;
    button.innerHTML = icon(button.dataset.icon);
    button.dataset.iconReady = "true";
  });
}
iconize(document);
function stored(key, fallback) {
  try { return JSON.parse(localStorage.getItem(key)) ?? fallback; }
  catch { return fallback; }
}
const savedPlaylists = stored("ytmp3_playlists", []);
const savedQueue = stored("ytmp3_queue", []);
const savedFavorites = stored("ytmp3_favorites", []);
const savedHidden = stored("ytmp3_hidden_tracks", []);
const savedSettings = stored("ytmp3_settings", {});
function routeView(hash) {
  const view = hash.replace(/^#/, "");
  return ({ library: "audio", settings: "more", about: "more", queue: "audio" })[view]
    || (["browse", "audio", "playlists", "more"].includes(view) ? view : "audio");
}
const state = {
  tracks: [],
  trackById: new Map(),
  visibleLimit: 100,
  queue: Array.isArray(savedQueue) ? savedQueue.filter((id) => typeof id === "string") : [],
  playlists: Ytmp3Playlists.sanitize(savedPlaylists),
  favorites: Array.isArray(savedFavorites) ? savedFavorites.filter((id) => typeof id === "string") : [],
  hiddenTracks: new Set(Array.isArray(savedHidden) ? savedHidden.filter((id) => typeof id === "string") : []),
  selectedTracks: new Set(),
  selectionMode: false,
  layout: ["list", "tiles", "compact"].includes(savedSettings.libraryView)
    ? savedSettings.libraryView : savedSettings.dense ? "compact" : "list",
  selectedPlaylist: null,
  settings: { theme: "dark", speed: 1, ...savedSettings },
  nativePlayback: {},
  current: -1,
  view: routeView(location.hash),
  filter: "",
  folder: "",
  favoritesOnly: false,
  sort: savedSettings.sort || "recent",
  artVersion: 0,
  update: null,
  updateChecking: false,
  updateCheckSilent: true,
  updateJob: null,
  urlDraft: "",
  browseFolder: "",
  browseQuery: "",
  browseLimit: 100,
  repeat: "off",
  shuffle: false,
  job: null,
  snapshotAt: 0,
  trackJson: "[]",
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
function trackArt(track, className = "track-art") {
  const art = document.createElement("div");
  art.className = className;
  art.setAttribute("aria-hidden", "true");
  if (track?.artwork) {
    const image = document.createElement("img");
    image.src = `/cover/${encodeURIComponent(track.id)}?v=${state.artVersion}`;
    image.alt = "";
    image.loading = className === "track-art" ? "lazy" : "eager";
    image.addEventListener("error", () => { art.textContent = "♪"; });
    art.append(image);
  } else art.textContent = "♪";
  return art;
}
function inFolder(track, id) {
  return !id || track.folderId === id || (id.endsWith(":")
    ? track.folderId?.startsWith(id)
    : track.folderId?.startsWith(`${id}/`));
}
function visibleTracks() {
  const query = state.filter.toLocaleLowerCase();
  const favorites = state.favoritesOnly ? new Set(state.favorites) : null;
  const result = state.tracks.filter((track) =>
    !state.hiddenTracks.has(track.id) &&
    inFolder(track, state.folder) &&
    (!favorites || favorites.has(track.id)) &&
    [titleOf(track), track.artist, track.album, track.folder, track.id].some((value) =>
      (value || "").toLocaleLowerCase().includes(query)));
  const compare = (a, b) => String(a || "").localeCompare(String(b || ""), undefined, { numeric: true, sensitivity: "base" });
  result.sort((a, b) => {
    if (state.sort === "title") return compare(titleOf(a), titleOf(b));
    if (state.sort === "artist") return compare(a.artist, b.artist) || compare(titleOf(a), titleOf(b));
    if (state.sort === "album") return compare(a.album, b.album) || compare(titleOf(a), titleOf(b));
    if (state.sort === "duration") return (a.duration || 0) - (b.duration || 0) || compare(titleOf(a), titleOf(b));
    if (state.sort === "oldest") return a.modified - b.modified;
    return b.modified - a.modified;
  });
  return result;
}
function currentTrack() {
  return state.trackById.get(state.queue[state.current]);
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
function applyTracks(data) {
  if (!Array.isArray(data?.tracks)) throw new Error("Invalid library response");
  const trackJson = JSON.stringify(data.tracks);
  const changed = trackJson !== state.trackJson;
  state.tracks = data.tracks;
  state.trackJson = trackJson;
  state.trackById = new Map(state.tracks.map((track) => [track.id, track]));
  state.snapshotAt = Date.now();
  try {
    localStorage.setItem("ytmp3_snapshot", JSON.stringify({ tracks: state.tracks, at: state.snapshotAt }));
  } catch { /* Large libraries can exceed browser storage; the in-memory list still works. */ }
  $("#connection").textContent = native ? "On this device" : "Connected";
  $("#connection").classList.remove("offline");
  $("#offline-banner").hidden = true;
  if (changed) render();
}
let nativeRefreshWaiters = [];
window.ytmp3TracksReady = (ok) => {
  try {
    if (!ok) throw new Error("Library scan failed");
    applyTracks(JSON.parse(native.cachedTracks()));
  } catch { toast("Could not refresh library."); }
  nativeRefreshWaiters.splice(0).forEach((resolve) => resolve());
};
async function refresh() {
  if (native) {
    return new Promise((resolve) => {
      nativeRefreshWaiters.push(resolve);
      native.refreshTracks();
    });
  }
  try {
    const response = await fetch("/api/tracks", { cache: "no-store" });
    if (!response.ok) throw new Error("Library unavailable");
    applyTracks(await response.json());
  } catch {
    showOffline();
    render();
  }
}

const views = ["browse", "audio", "playlists", "more"];
const viewScroll = new Map();
history.scrollRestoration = "manual";
let viewSlide = null;
function stopViewSlide() {
  if (!viewSlide) return;
  viewSlide.incoming.cancel();
  viewSlide.outgoing.cancel();
  viewSlide.frame.remove();
  viewSlide = null;
}
function setView(view, push = true, startX = 0) {
  if (!views.includes(view) || state.view === view) return;
  stopViewSlide();
  main.getAnimations().forEach((animation) => animation.cancel());
  const direction = Math.sign(views.indexOf(view) - views.indexOf(state.view));
  const motion = !matchMedia("(prefers-reduced-motion: reduce)").matches;
  let frame, old;
  if (motion) {
    const rect = main.getBoundingClientRect();
    frame = document.createElement("div");
    frame.className = "view-slide-frame";
    frame.style.left = `${rect.left - startX}px`;
    old = document.createElement("div");
    old.className = "view-slide-old";
    old.style.top = `${rect.top}px`;
    old.style.width = `${rect.width}px`;
    old.append(...main.childNodes);
    frame.append(old);
  }
  main.style.transform = "";
  main.style.willChange = "";
  viewScroll.set(state.view, scrollY);
  state.selectedTracks.clear();
  state.selectionMode = false;
  state.view = view;
  if (push) history.pushState({ view }, "", view === "audio" ? "/" : `#${view}`);
  render(false);
  main.focus({ preventScroll: true });
  scrollTo({ top: viewScroll.get(view) || 0, behavior: "instant" });
  if (frame) {
    old.querySelectorAll("[id]").forEach((node) => node.removeAttribute("id"));
    old.inert = true;
    old.setAttribute("aria-hidden", "true");
    document.body.append(frame);
    const timing = { duration: 290, easing: "cubic-bezier(.22,.75,.2,1)" };
    const distance = main.getBoundingClientRect().width * direction;
    const outgoing = old.animate([
      { transform: `translateX(${startX}px)` }, { transform: `translateX(${-distance}px)` }
    ], timing);
    const incoming = main.animate([
      { transform: `translateX(${distance}px)` }, { transform: "translateX(0)" }
    ], timing);
    viewSlide = { frame, incoming, outgoing };
    incoming.onfinish = () => { if (viewSlide?.frame === frame) stopViewSlide(); };
  }
}
addEventListener("popstate", () => {
  if (state.playerOpen) animatePlayerExit();
  state.playerOpen = false;
  document.body.classList.remove("player-open");
  $("#player").dataset.panel = "queue";
  $("#expand-player").setAttribute("aria-expanded", "false");
  $("#expand-player").setAttribute("aria-label", "Open player");
  setView(routeView(location.hash), false);
});
document.querySelectorAll(".nav-item").forEach((button) =>
  button.addEventListener("click", () => setView(button.dataset.view))
);
function canSwipeView(target) {
  return !state.playerOpen && !state.selectionMode && !document.querySelector("dialog[open]") &&
    target instanceof Element && !target.closest("input, select, textarea, button, a, summary, " +
      ".drag-handle, .tile-menu, .playlist-list, .selection-bar, [contenteditable]");
}
function adjacentView(direction, startX = 0) {
  const next = views[views.indexOf(state.view) + direction];
  if (next) setView(next, true, startX);
  else settleViewDrag(startX);
}
function settleViewDrag(x) {
  main.style.transform = "";
  main.style.willChange = "";
  if (x && !matchMedia("(prefers-reduced-motion: reduce)").matches)
    main.animate([{ transform: `translateX(${x}px)` }, { transform: "translateX(0)" }],
      { duration: 180, easing: "ease-out" });
}
let viewTouch = null;
$(".workspace").addEventListener("touchstart", (event) => {
  viewTouch = null;
  if (event.touches.length !== 1 || !canSwipeView(event.target)) return;
  const { clientX: x, clientY: y } = event.touches[0];
  if (x < 24 || x > innerWidth - 24) return;
  viewTouch = { x, y, axis: null, dragX: 0 };
}, { passive: true });
$(".workspace").addEventListener("touchmove", (event) => {
  if (!viewTouch || event.touches.length !== 1) return;
  const dx = event.touches[0].clientX - viewTouch.x;
  const dy = event.touches[0].clientY - viewTouch.y;
  if (!viewTouch.axis && Math.max(Math.abs(dx), Math.abs(dy)) > 18)
    viewTouch.axis = Math.abs(dx) > Math.abs(dy) * 1.3 ? "horizontal" : "vertical";
  if (viewTouch.axis === "horizontal") {
    event.preventDefault();
    const next = views[views.indexOf(state.view) + (dx < 0 ? 1 : -1)];
    viewTouch.dragX = Math.max(-innerWidth * .35, Math.min(innerWidth * .35,
      dx * (next ? .65 : .15)));
    main.style.willChange = "transform";
    main.style.transform = `translateX(${viewTouch.dragX}px)`;
  }
}, { passive: false });
$(".workspace").addEventListener("touchend", (event) => {
  if (!viewTouch || event.changedTouches.length !== 1) return;
  const { x, y, axis, dragX } = viewTouch;
  viewTouch = null;
  const dx = event.changedTouches[0].clientX - x;
  const dy = event.changedTouches[0].clientY - y;
  if (axis !== "horizontal" || state.selectionMode || Math.abs(dx) < 80 ||
      Math.abs(dx) < Math.abs(dy) * 1.3) { settleViewDrag(dragX); return; }
  event.preventDefault();
  adjacentView(dx < 0 ? 1 : -1, dragX);
}, { passive: false });
$(".workspace").addEventListener("touchcancel", () => {
  settleViewDrag(viewTouch?.dragX || 0);
  viewTouch = null;
});
let wheelTravel = 0;
let wheelAt = 0;
let wheelCooldown = 0;
$(".workspace").addEventListener("wheel", (event) => {
  if (!canSwipeView(event.target) || event.ctrlKey || event.altKey || event.shiftKey ||
      event.metaKey || Math.abs(event.deltaX) < Math.abs(event.deltaY) * 1.4) return;
  const now = Date.now();
  if (now < wheelCooldown) return;
  if (now - wheelAt > 350 || Math.sign(wheelTravel) !== Math.sign(event.deltaX)) wheelTravel = 0;
  wheelAt = now;
  wheelTravel += event.deltaX * (event.deltaMode === 1 ? 16 : event.deltaMode === 2 ? innerWidth : 1);
  if (Math.abs(wheelTravel) < 100) return;
  event.preventDefault();
  adjacentView(wheelTravel > 0 ? 1 : -1);
  wheelTravel = 0;
  wheelCooldown = now + 550;
}, { passive: false });

function render(includeQueue = true) {
  document.querySelectorAll(".nav-item").forEach((button) => {
    button.classList.toggle("active", button.dataset.view === state.view);
    button.setAttribute("aria-current", button.dataset.view === state.view ? "page" : "false");
  });
  $("#page-title").textContent = state.view[0].toUpperCase() + state.view.slice(1);
  if (state.view === "browse") renderBrowse();
  else if (state.view === "audio") renderAudio();
  else if (state.view === "playlists") renderPlaylists();
  else renderMore();
  updatePlayer();
  if (includeQueue) renderQueue();
  iconize(main);
}

function renderBrowse() {
  main.innerHTML = `<div class="content">
    <section class="download-panel" aria-labelledby="add-heading">
      <form id="url-form"><label id="add-heading" for="url-input">Add from link</label>
        <div class="url-form"><input id="url-input" class="url-input" type="url" required
          inputmode="url" autocomplete="url" placeholder="Track or playlist URL"
          aria-label="Track or playlist URL"><button class="primary-button symbol-button" data-icon="download" type="submit" aria-label="Save MP3 from link" title="Save MP3">Save MP3</button></div>
      </form><div id="job-container"></div>
      <div id="link-preview" class="link-preview" role="status" hidden></div>
    </section>
    <section class="browse-library" aria-labelledby="browse-heading">
      <div class="browse-heading"><h2 id="browse-heading">All media</h2><span id="browse-count"></span></div>
      <div class="browse-controls"><label for="browse-folder">Folders</label>
        <select id="browse-folder"></select>
        <input id="browse-search" class="search-input" type="search" placeholder="Find a file" aria-label="Find a file"></div>
      <div id="browse-tracks" class="track-list" data-layout="compact"></div>
    </section>
  </div>`;
  const input = $("#url-input");
  const shared = sessionStorage.getItem("ytmp3_shared_url");
  if (shared) {
    state.urlDraft = shared;
    sessionStorage.removeItem("ytmp3_shared_url");
  }
  input.value = state.urlDraft;
  input.addEventListener("input", (event) => { state.urlDraft = event.target.value; scheduleLinkPreview(); });
  $("#url-form").addEventListener("submit", submitURL);
  renderJob();
  scheduleLinkPreview();
  const tracks = state.tracks.filter((track) => !state.hiddenTracks.has(track.id));
  const folders = [...new Map(tracks.flatMap((track) => [
    [track.rootFolderId, track.rootFolder], [track.folderId, track.folder]
  ]).filter(([id]) => id)).entries()].sort((a, b) => a[1].localeCompare(b[1]));
  const folderSelect = $("#browse-folder");
  folderSelect.add(new Option("All folders", ""));
  folders.forEach(([id, name]) => folderSelect.add(new Option(name, id)));
  if (folders.some(([id]) => id === state.browseFolder)) folderSelect.value = state.browseFolder;
  else state.browseFolder = "";
  folderSelect.addEventListener("change", (event) => {
    state.browseFolder = event.target.value; state.browseLimit = 100; renderBrowseTracks();
  });
  $("#browse-search").value = state.browseQuery;
  $("#browse-search").addEventListener("input", (event) => {
    state.browseQuery = event.target.value; state.browseLimit = 100; renderBrowseTracks();
  });
  renderBrowseTracks();
}

function renderBrowseTracks() {
  const list = $("#browse-tracks");
  if (!list) return;
  list.replaceChildren();
  const tracks = browseTracks();
  $("#browse-count").textContent = `${tracks.length} ${tracks.length === 1 ? "file" : "files"}`;
  if (!tracks.length) {
    list.innerHTML = '<div class="empty"><strong>No media here</strong><p>Add a music folder in More or save a link above.</p></div>';
    return;
  }
  for (const track of tracks.slice(0, state.browseLimit)) {
    const row = trackRow(track, "browse");
    row.classList.add("browse-track");
    row.querySelector(".track-meta span").textContent = [track.folder, track.duration ? formatTime(track.duration) : null].filter(Boolean).join(" · ");
    row.addEventListener("click", (event) => {
      if (!event.target.closest("button, summary, details, input")) {
        state.queue = tracks.map((item) => item.id);
        playTrack(track.id);
      }
    });
    list.append(row);
  }
  if (tracks.length > state.browseLimit) {
    const more = document.createElement("button");
    more.className = "row-button show-more";
    more.textContent = `Show ${Math.min(100, tracks.length - state.browseLimit)} more`;
    more.addEventListener("click", () => { state.browseLimit += 100; renderBrowseTracks(); });
    list.append(more);
  }
}

function browseTracks() {
  const query = state.browseQuery.toLocaleLowerCase();
  return state.tracks.filter((track) => !state.hiddenTracks.has(track.id)
    && inFolder(track, state.browseFolder)
    && [titleOf(track), track.artist, track.album, track.folder, track.id].some((value) =>
      (value || "").toLocaleLowerCase().includes(query)))
    .sort((a, b) => (a.folder || "").localeCompare(b.folder || "")
      || titleOf(a).localeCompare(titleOf(b), undefined, { numeric: true }));
}

let previewTimer;
let previewSerial = 0;
function scheduleLinkPreview() {
  clearTimeout(previewTimer);
  const serial = ++previewSerial;
  const box = $("#link-preview");
  const input = $("#url-input");
  if (!box || !input) return;
  box.hidden = true;
  const url = input.value.trim();
  try {
    const parsed = new URL(url);
    if (!["http:", "https:"].includes(parsed.protocol) || !parsed.hostname
        || parsed.username || parsed.password || url.length > 4096) return;
  } catch { return; }
  previewTimer = setTimeout(() => loadLinkPreview(url, serial), 650);
}

async function loadLinkPreview(url, serial) {
  const current = () => serial === previewSerial && state.view === "browse"
    && $("#url-input")?.value.trim() === url;
  if (!current()) return;
  const box = $("#link-preview");
  box.textContent = "Checking link…";
  box.hidden = false;
  let data;
  try {
    if (native) {
      const started = JSON.parse(native.preview(url));
      if (!started.job) throw new Error();
      for (let attempt = 0; attempt < 30 && current(); attempt++) {
        await new Promise((resolve) => setTimeout(resolve, 700));
        data = JSON.parse(native.previewJob(started.job));
        if (data?.state === "done" || data?.state === "error") break;
      }
    } else {
      const controller = new AbortController();
      const timeout = setTimeout(() => controller.abort(), 15000);
      try {
        const response = await fetch("/api/preview", {
          method: "POST", headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url }), signal: controller.signal
        });
        data = response.ok ? await response.json() : null;
      } finally { clearTimeout(timeout); }
    }
  } catch { data = null; }
  if (!current()) return;
  box.replaceChildren();
  const parsed = new URL(url);
  const text = document.createElement("div");
  const title = document.createElement("strong");
  title.textContent = data?.title || parsed.hostname;
  const subtitle = document.createElement("span");
  subtitle.textContent = data?.title
    ? [data.site || parsed.hostname, data.kind === "playlist"
      ? data.count ? `${data.count} tracks` : "Playlist" : data.creator].filter(Boolean).join(" · ")
    : "Link ready to try";
  text.append(title, subtitle);
  if (data?.thumbnail) {
    const image = document.createElement("img");
    image.src = data.thumbnail;
    image.alt = "";
    image.referrerPolicy = "no-referrer";
    image.addEventListener("error", () => image.remove());
    box.append(image);
  }
  box.append(text);
}

function renderAudio() {
  main.innerHTML = `<div class="content">
    <div class="library-controls">
      <input id="filter" class="search-input" type="search" placeholder="Search title, artist, album, folder" aria-label="Search library">
      <select id="folder-filter" aria-label="Choose folder"></select>
      <select id="sort-tracks" aria-label="Sort tracks">
        <option value="recent">Recently added</option><option value="title">Title A–Z</option>
        <option value="artist">Artist A–Z</option><option value="album">Album A–Z</option>
        <option value="duration">Shortest first</option><option value="oldest">Oldest first</option>
      </select>
      <button class="row-button symbol-button" id="play-selection" data-icon="play" type="button" aria-label="Play visible tracks" title="Play">Play</button>
      <button class="row-button symbol-button" id="mix-selection" data-icon="mix" type="button" aria-label="Mix visible tracks" title="Mix">Mix</button>
      <button class="row-button symbol-button" id="favorites-filter" data-icon="star" type="button" aria-label="Favorites only" title="Favorites" aria-pressed="false">☆</button>
      <div id="layout-mode" class="layout-switch" role="group" aria-label="Library layout">
        <span class="layout-thumb" aria-hidden="true"></span>
        <button type="button" data-layout="compact" aria-label="Compact view" title="Compact view">☷</button>
        <button type="button" data-layout="list" aria-label="List view" title="List view">≡</button>
        <button type="button" data-layout="tiles" aria-label="Tile view" title="Tile view">▦</button>
      </div>
      <button class="row-button symbol-button" id="select-mode" data-icon="select" type="button" aria-label="Select tracks" title="Select tracks" aria-pressed="false">Select</button>
    </div>
    <p class="result-count" id="library-count"></p>
    <div id="selection-bar" class="selection-bar" hidden>
      <button class="row-button symbol-button" id="clear-selection" data-icon="close" type="button" aria-label="Cancel selection" title="Cancel selection">Close</button>
      <strong id="selected-count"></strong>
      <button class="row-button symbol-button" id="select-all" data-icon="all" type="button" aria-label="Select all visible tracks" title="Select all visible">Select visible</button>
      <button class="row-button symbol-button" id="selected-play" data-icon="play" type="button" aria-label="Play selected tracks" title="Play selected">Play</button>
      <button class="row-button symbol-button" id="selected-mix" data-icon="mix" type="button" aria-label="Mix selected tracks" title="Mix selected">Mix</button>
      <button class="row-button symbol-button" id="selected-queue" data-icon="queue" type="button" aria-label="Add selected tracks to queue" title="Add to queue">Queue</button>
      <button class="row-button symbol-button" id="selected-playlist" data-icon="playlist" type="button" aria-label="Add selected tracks to playlist" title="Add to playlist">Playlist</button>
      <button class="row-button symbol-button" id="selected-favorite" data-icon="star" type="button" aria-label="Favorite selected tracks" title="Favorite">Favorite</button>
      <button class="row-button symbol-button" id="selected-share" data-icon="share" type="button" aria-label="Share selected tracks" title="Share" ${native ? "" : "hidden"}>Share</button>
      <button class="row-button symbol-button" id="selected-hide" data-icon="remove" type="button" aria-label="Remove selected tracks from Audio" title="Remove from Audio">Remove</button>
    </div>
    <div id="track-list" class="track-list"></div>
  </div>`;
  $("#filter").value = state.filter;
  $("#filter").addEventListener("input", (event) => {
    state.filter = event.target.value;
    state.visibleLimit = 100;
    renderTracks();
  });
  const folders = [...new Map(state.tracks.flatMap((track) => [
    [track.rootFolderId, track.rootFolder], [track.folderId, track.folder]
  ]).filter(([id]) => id)).entries()]
    .sort((a, b) => a[1].localeCompare(b[1]));
  const folderSelect = $("#folder-filter");
  folderSelect.add(new Option("All folders", ""));
  folders.forEach(([id, name]) => folderSelect.add(new Option(name, id)));
  if (folders.some(([id]) => id === state.folder)) folderSelect.value = state.folder;
  else state.folder = "";
  folderSelect.addEventListener("change", (event) => {
    state.folder = event.target.value; state.visibleLimit = 100; renderTracks();
  });
  $("#sort-tracks").value = state.sort;
  $("#sort-tracks").addEventListener("change", (event) => {
    state.sort = event.target.value; state.settings.sort = state.sort;
    state.visibleLimit = 100; persistSettings(); renderTracks();
  });
  $("#play-selection").addEventListener("click", () => playCollection(visibleTracks().map((track) => track.id)));
  $("#mix-selection").addEventListener("click", () => playCollection(visibleTracks().map((track) => track.id), true));
  $("#favorites-filter").setAttribute("aria-pressed", String(state.favoritesOnly));
  $("#favorites-filter").addEventListener("click", () => {
    state.favoritesOnly = !state.favoritesOnly;
    state.visibleLimit = 100;
    $("#favorites-filter").setAttribute("aria-pressed", String(state.favoritesOnly));
    renderTracks();
  });
  const layoutSwitch = $("#layout-mode");
  layoutSwitch.dataset.layout = state.layout;
  layoutSwitch.querySelectorAll("button").forEach((button) => {
    button.setAttribute("aria-pressed", String(button.dataset.layout === state.layout));
    button.addEventListener("click", () => {
      state.layout = button.dataset.layout;
      state.settings.libraryView = state.layout;
      layoutSwitch.dataset.layout = state.layout;
      layoutSwitch.querySelectorAll("button").forEach((item) =>
        item.setAttribute("aria-pressed", String(item === button)));
      persistSettings(); renderTracks();
    });
  });
  $("#select-mode").addEventListener("click", () => {
    state.selectionMode = !state.selectionMode;
    if (!state.selectionMode) state.selectedTracks.clear();
    renderTracks();
  });
  $("#select-all").addEventListener("click", () => {
    visibleTracks().forEach((track) => state.selectedTracks.add(track.id)); renderTracks();
  });
  $("#selected-play").addEventListener("click", () => playCollection(selectedIds()));
  $("#selected-mix").addEventListener("click", () => playCollection(selectedIds(), true));
  $("#selected-queue").addEventListener("click", () => {
    state.queue.push(...selectedIds()); persistLists(); syncNativeQueue(); render(); toast("Added to queue");
  });
  $("#selected-playlist").addEventListener("click", () => openPlaylistPicker(selectedIds()));
  $("#selected-favorite").addEventListener("click", () => {
    state.favorites = [...new Set([...state.favorites, ...selectedIds()])];
    localStorage.setItem("ytmp3_favorites", JSON.stringify(state.favorites));
    renderTracks(); toast("Added to favorites");
  });
  if (native) $("#selected-share").addEventListener("click", () => native.shareTracks(JSON.stringify(selectedIds())));
  $("#selected-hide").addEventListener("click", () => confirmHideTracks(selectedIds()));
  $("#clear-selection").addEventListener("click", () => {
    state.selectedTracks.clear(); state.selectionMode = false; renderTracks();
  });
  renderTracks();
}

function renderTracks() {
  const list = $("#track-list");
  if (!list) return;
  const filtered = visibleTracks();
  list.dataset.layout = state.layout;
  $("#selection-bar").hidden = !state.selectionMode;
  $("#select-mode").setAttribute("aria-pressed", String(state.selectionMode));
  $("#selected-count").textContent = `${state.selectedTracks.size} selected`;
  for (const id of ["selected-play", "selected-mix", "selected-queue", "selected-playlist",
    "selected-favorite", "selected-share", "selected-hide"]) {
    const button = $("#" + id);
    if (button) button.disabled = !state.selectedTracks.size;
  }
  $("#library-count").textContent = `${filtered.length} of ${state.tracks.length} tracks`;
  $("#play-selection").disabled = !filtered.length;
  $("#mix-selection").disabled = !filtered.length;
  list.replaceChildren();
  if (!filtered.length) {
    const box = document.createElement("div");
    box.className = "empty";
    const strong = document.createElement("strong");
    strong.textContent = state.tracks.length ? "No matching files" : "No audio yet";
    const note = document.createElement("p");
    note.textContent = state.tracks.length ? "Try a different filter."
      : "Add a music folder or save a link in Browse.";
    box.append(strong, note);
    list.append(box);
    return;
  }
  const showCount = Math.min(state.visibleLimit, filtered.length);
  filtered.slice(0, showCount).forEach((track) => list.append(trackRow(track)));
  // Render 100 more rows per action; a virtual list is the upgrade for huge libraries.
  const showMore = () => {
    if (state.visibleLimit >= filtered.length) return;
    const button = document.createElement("button");
    button.className = "row-button show-more";
    button.type = "button";
    button.textContent = `Show ${Math.min(100, filtered.length - state.visibleLimit)} more tracks`;
    button.addEventListener("click", () => {
      button.remove();
      const start = state.visibleLimit;
      state.visibleLimit = Math.min(filtered.length, start + 100);
      filtered.slice(start, state.visibleLimit).forEach((track) => list.append(trackRow(track)));
      showMore();
    });
    list.append(button);
  };
  showMore();
}

function selectedIds() {
  return [...state.selectedTracks].filter((id) => state.trackById.has(id));
}
function toggleTrackSelection(id) {
  if (state.selectedTracks.has(id)) state.selectedTracks.delete(id);
  else state.selectedTracks.add(id);
  renderTracks();
}
function confirmHideTracks(ids) {
  state.pendingHideIds = ids.filter((id) => state.trackById.has(id));
  if (!state.pendingHideIds.length) return;
  $("#hide-text").textContent = state.pendingHideIds.length === 1
    ? `Hide “${titleOf(state.trackById.get(state.pendingHideIds[0]))}” from Library?`
    : `Hide ${state.pendingHideIds.length} tracks from Library?`;
  $("#hide-dialog").showModal();
}
$("#cancel-hide").addEventListener("click", () => $("#hide-dialog").close());
$("#confirm-hide").addEventListener("click", () => {
  state.pendingHideIds.forEach((id) => {
    state.hiddenTracks.add(id);
    state.selectedTracks.delete(id);
  });
  localStorage.setItem("ytmp3_hidden_tracks", JSON.stringify([...state.hiddenTracks]));
  $("#hide-dialog").close();
  if (state.view === "audio") renderTracks();
  else if (state.view === "browse") renderBrowse();
  toast("Removed from Library. Restore in More.");
});

function toggleFavorite(id) {
  state.favorites = state.favorites.includes(id)
    ? state.favorites.filter((item) => item !== id) : [...state.favorites, id];
  localStorage.setItem("ytmp3_favorites", JSON.stringify(state.favorites));
  if (state.view === "audio") renderTracks();
  else if (state.view === "browse") renderBrowseTracks();
  else if (state.view === "playlists") renderPlaylists();
  renderQueue();
}

function reorderQueue(from, to) {
  if (to < 0 || to >= state.queue.length || from === to) return;
  state.queue = Ytmp3Playlists.move(state.queue, from, to - from);
  if (state.current === from) state.current = to;
  else if (from < state.current && to >= state.current) state.current--;
  else if (from > state.current && to <= state.current) state.current++;
  persistLists(); syncNativeQueue(); renderQueue();
}
function removeQueueIndex(index) {
  const wasCurrent = index === state.current;
  state.queue.splice(index, 1);
  if (!state.queue.length) {
    state.current = -1; audio.pause();
    if (native) native.command("stop", 0);
  } else if (wasCurrent) {
    state.current = Math.min(index, state.queue.length - 1);
    playTrack(state.queue[state.current], state.current);
    return;
  } else if (index < state.current) state.current--;
  persistLists(); syncNativeQueue(); renderQueue(); updatePlayer();
}

function reorderPlaylist(list, from, to) {
  if (to < 0 || to >= list.tracks.length || from === to) return;
  list.tracks = Ytmp3Playlists.move(list.tracks, from, to - from);
  persistLists(); renderPlaylists();
}

function dragHandle(row, index, onDrop, label) {
  const handle = document.createElement("button");
  handle.type = "button";
  handle.className = "drag-handle";
  handle.textContent = "⠿";
  handle.setAttribute("aria-label", `Drag to reorder ${label}; arrow keys also work`);
  let pointer = null;
  let target = index;
  const clear = () => {
    row.classList.remove("dragging");
    document.querySelectorAll(".drop-target").forEach((item) => item.classList.remove("drop-target"));
    pointer = null;
  };
  handle.addEventListener("pointerdown", (event) => {
    if (event.button !== 0) return;
    pointer = event.pointerId;
    target = index;
    handle.setPointerCapture(pointer);
    row.classList.add("dragging");
    event.preventDefault();
  });
  handle.addEventListener("pointermove", (event) => {
    if (pointer !== event.pointerId) return;
    const hovered = document.elementFromPoint(event.clientX, event.clientY)?.closest("[data-reorder-index]");
    if (!hovered || hovered.parentElement !== row.parentElement) return;
    target = Number(hovered.dataset.reorderIndex);
    document.querySelectorAll(".drop-target").forEach((item) => item.classList.remove("drop-target"));
    if (hovered !== row) hovered.classList.add("drop-target");
  });
  handle.addEventListener("pointerup", (event) => {
    if (pointer !== event.pointerId) return;
    clear();
    onDrop(index, target);
  });
  handle.addEventListener("pointercancel", clear);
  handle.addEventListener("keydown", (event) => {
    if (!["ArrowUp", "ArrowDown"].includes(event.key)) return;
    event.preventDefault();
    onDrop(index, index + (event.key === "ArrowUp" ? -1 : 1));
  });
  return handle;
}

function showTrackInfo(track) {
  const dialog = $("#info-dialog");
  $("#info-art").replaceChildren(trackArt(track));
  $("#info-title").textContent = titleOf(track);
  const details = $("#info-details");
  details.replaceChildren();
  for (const [label, value] of [
    ["Artist", track.artist || "Unknown"], ["Album", track.album || "Unknown"],
    ["Duration", track.duration ? formatTime(track.duration) : "Unknown"],
    ["Folder", track.folder || "Library"], ["File", track.id.split("/").pop()],
    ["Size", `${(track.size / 1048576).toFixed(1)} MB`]
  ]) {
    const term = document.createElement("dt"); term.textContent = label;
    const description = document.createElement("dd"); description.textContent = value;
    details.append(term, description);
  }
  dialog.showModal();
}
$("#close-info").addEventListener("click", () => $("#info-dialog").close());

document.addEventListener("pointerdown", (event) => {
  document.querySelectorAll(".tile-menu[open], .queue-options[open]").forEach((menu) => {
    if (!menu.contains(event.target)) menu.open = false;
  });
}, true);
document.addEventListener("keydown", (event) => {
  if (event.key !== "Escape" || document.querySelector("dialog[open]")) return;
  const menus = document.querySelectorAll(".tile-menu[open], .queue-options[open]");
  if (menus.length) {
    menus.forEach((menu) => { menu.open = false; });
    event.preventDefault();
  } else if (state.selectionMode && state.view === "audio") {
    state.selectedTracks.clear();
    state.selectionMode = false;
    renderTracks();
    event.preventDefault();
  }
});

function trackMenu(track, context, index, list) {
  const menu = document.createElement("details");
  menu.className = "tile-menu";
  const summary = document.createElement("summary");
  summary.textContent = "⋮";
  summary.setAttribute("aria-label", `Actions for ${titleOf(track)}`);
  const options = document.createElement("div");
  options.className = "tile-options";
  menu.append(summary, options);
  menu.addEventListener("toggle", () => {
    if (!menu.open) return;
    const rect = summary.getBoundingClientRect();
    const bounds = context === "queue" && state.playerOpen ? $("#queue-list").getBoundingClientRect() : null;
    const below = (bounds ? bounds.bottom : state.playerOpen ? innerHeight - 16 : $("#player").getBoundingClientRect().top) - rect.bottom;
    const above = rect.top - (bounds ? bounds.top : state.playerOpen ? 16 : document.querySelector(".topbar").getBoundingClientRect().bottom);
    const height = Math.min(options.scrollHeight, 440, innerHeight * .62);
    const width = Math.min(220, innerWidth - 32);
    menu.classList.toggle("align-left", rect.right - width < 8 && rect.left + width <= innerWidth - 8);
    const openUp = below < height && above > below;
    menu.classList.toggle("open-up", openUp);
    options.style.maxHeight = `${Math.max(80, Math.min(height, openUp ? above : below) - 8)}px`;
  });
  const addAction = (label, run) => {
    const button = document.createElement("button");
    button.type = "button";
    button.textContent = label;
    button.addEventListener("click", () => { menu.open = false; run(); });
    options.append(button);
  };
  addAction("Play", () => {
    if (context === "library") state.queue = visibleTracks().map((item) => item.id);
    if (context === "browse") state.queue = browseTracks().map((item) => item.id);
    if (context === "playlist") state.queue = list.tracks.filter((id) => state.trackById.has(id));
    playTrack(track.id, context === "queue" ? index : undefined);
  });
  addAction("View info", () => showTrackInfo(track));
  addAction("Add to playlist", () => openPlaylistPicker(track.id));
  addAction(state.favorites.includes(track.id) ? "Remove favorite" : "Add to favorites",
    () => toggleFavorite(track.id));
  if (context === "library" || context === "browse") {
    addAction("Play next", () => {
      state.queue.splice(Math.max(0, state.current + 1), 0, track.id);
      persistLists(); syncNativeQueue(); renderQueue(); toast("Added next");
    });
    addAction("Add to queue", () => {
      state.queue.push(track.id); persistLists(); syncNativeQueue();
      renderQueue(); toast("Added to queue");
    });
    addAction("Remove from Library", () => confirmHideTracks([track.id]));
  }
  addAction("Edit details and cover", () => openTrackEditor(track));
  if (native) {
    addAction("Share file", () => native.shareTrack(track.id));
    addAction("Set as ringtone", () => native.setRingtone(track.id));
  } else addAction("Share file", () => shareTrack(track));
  if (context === "queue") addAction("Remove from queue", () => removeQueueIndex(index));
  if (context === "playlist") addAction("Remove from playlist", () => {
    list.tracks.splice(index, 1); persistLists(); renderPlaylists();
  });
  if (!track.external) addAction("Save file", () => {
    if (native) {
      const result = JSON.parse(native.exportTrack(track.id));
      toast(result.error || "Saving to Music on this phone…");
    } else location.href = `/export/${encodeURIComponent(track.id)}`;
  });
  return menu;
}

async function shareTrack(track) {
  try {
    const response = await fetch(`/media/${encodeURIComponent(track.id)}`);
    if (!response.ok) throw new Error();
    const file = new File([await response.blob()], `${titleOf(track)}.mp3`, { type: "audio/mpeg" });
    if (!navigator.canShare?.({ files: [file] })) {
      location.href = `/export/${encodeURIComponent(track.id)}`;
      toast("File downloaded for sharing");
      return;
    }
    await navigator.share({ files: [file], title: titleOf(track) });
  } catch (error) {
    if (error.name !== "AbortError") toast("Could not share this file.");
  }
}

function trackRow(track, context = "library", index = -1, list = null) {
  const row = document.createElement("div");
  row.className = "track-row";
  if (context === "queue" ? index === state.current : currentTrack()?.id === track.id) row.classList.add("current");
  if (context !== "library" && context !== "browse") {
    row.classList.add("reorderable");
    row.dataset.reorderIndex = String(index);
    row.append(dragHandle(row, index, context === "queue"
      ? reorderQueue : (from, to) => reorderPlaylist(list, from, to), titleOf(track)));
  } else if (context === "library" && state.selectionMode) {
    row.classList.add("selectable");
    const check = document.createElement("input");
    check.type = "checkbox"; check.className = "track-select";
    check.checked = state.selectedTracks.has(track.id);
    check.setAttribute("aria-label", `Select ${titleOf(track)}`);
    check.addEventListener("change", () => toggleTrackSelection(track.id));
    row.append(check);
    row.classList.toggle("selected", check.checked);
  }
  row.append(trackArt(track));
  const meta = document.createElement(context === "queue" ? "button" : "div"); meta.className = "track-meta";
  if (context === "queue") {
    meta.type = "button"; meta.classList.add("queue-play");
    meta.setAttribute("aria-label", `Play ${titleOf(track)} at position ${index + 1}`);
    meta.addEventListener("click", () => playTrack(track.id, index));
  }
  const title = document.createElement("strong"); title.textContent = titleOf(track);
  const sub = document.createElement("span");
  sub.textContent = [context === "queue" && index === state.current ? "Now playing" : null,
    track.artist, track.album, track.duration ? formatTime(track.duration) : null]
    .filter(Boolean).join(" · ") || track.folder || "MP3";
  meta.append(title, sub);
  row.append(meta, trackMenu(track, context, index, list));
  if (context === "library") {
    let timer, startX, startY, longPressed = false;
    row.addEventListener("pointerdown", (event) => {
      if (event.target.closest("button,summary,details,input,a")) return;
      startX = event.clientX; startY = event.clientY; longPressed = false;
      timer = setTimeout(() => {
        state.selectionMode = true; longPressed = true;
        state.selectedTracks.add(track.id);
        renderTracks();
      }, 550);
    });
    row.addEventListener("pointermove", (event) => {
      if (Math.abs(event.clientX - startX) > 12 || Math.abs(event.clientY - startY) > 12)
        clearTimeout(timer);
    });
    row.addEventListener("pointerup", () => clearTimeout(timer));
    row.addEventListener("pointercancel", () => clearTimeout(timer));
    row.addEventListener("click", (event) => {
      if (longPressed) { longPressed = false; return; }
      if (state.selectionMode && !event.target.closest("button,summary,details,input,a"))
        toggleTrackSelection(track.id);
    });
  }
  return row;
}

function openTrackEditor(track) {
  const dialog = $("#track-dialog");
  dialog.dataset.track = track.id;
  $("#edit-title").value = titleOf(track);
  $("#edit-artist").value = track.artist || "";
  $("#edit-album").value = track.album || "";
  $("#edit-cover").value = "";
  $("#edit-cover").hidden = !!native;
  $("#pick-cover").hidden = !native;
  $("#edit-art").replaceChildren(trackArt(track));
  dialog.showModal();
  $("#edit-title").focus();
}
async function saveTrackEdit(removeCover = false) {
  const dialog = $("#track-dialog");
  const id = dialog.dataset.track;
  const body = { id, title: $("#edit-title").value.trim(),
    artist: $("#edit-artist").value.trim(), album: $("#edit-album").value.trim() };
  if (!body.title) { toast("Enter a track title."); return; }
  try {
    if (native) {
      const result = JSON.parse(native.editTrack(id, body.title, body.artist, body.album));
      if (result.error) throw new Error(result.error);
      if (removeCover) {
        const removed = JSON.parse(native.removeCover(id));
        if (removed.error) throw new Error(removed.error);
      }
    } else {
      const file = $("#edit-cover").files?.[0];
      if (file && !removeCover) {
        if (file.size > 1024 * 1024 || !["image/jpeg", "image/png"].includes(file.type))
          throw new Error("Choose a JPEG or PNG cover under 1 MB.");
        body.cover = await new Promise((resolve, reject) => {
          const reader = new FileReader();
          reader.onload = () => resolve(String(reader.result).split(",", 2)[1]);
          reader.onerror = () => reject(new Error("Could not read cover image."));
          reader.readAsDataURL(file);
        });
      }
      if (removeCover) body.removeCover = true;
      const response = await fetch("/api/tracks/edit", { method: "POST",
        headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
      if (!response.ok) throw new Error((await response.json()).error || "Could not save track details.");
    }
    state.artVersion++;
    dialog.close();
    await refresh();
    toast(removeCover ? "Chosen cover removed" : "Track details saved");
    if (native) syncNativeQueue();
  } catch (error) { toast(error.message || "Could not save track details."); }
}
$("#cancel-edit").addEventListener("click", () => $("#track-dialog").close());
$("#track-editor").addEventListener("submit", (event) => { event.preventDefault(); saveTrackEdit(); });
$("#remove-cover").addEventListener("click", () => saveTrackEdit(true));
$("#pick-cover").addEventListener("click", () => native.pickCover($("#track-dialog").dataset.track));
window.ytmp3CoverChanged = async (result) => {
  if (result.error) { toast(result.error); return; }
  state.artVersion++;
  $("#track-dialog").close();
  await refresh();
  syncNativeQueue();
  toast("Cover saved");
};
window.ytmp3RingtoneResult = (result) => toast(result.error || "Ringtone set");

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

function openPlaylistPicker(ids) {
  const dialog = $("#playlist-dialog");
  state.pickerIds = Array.isArray(ids) ? ids : [ids];
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
  state.pickerIds.forEach((id) => Ytmp3Playlists.add(list, id));
  persistLists();
  $("#playlist-dialog").close();
  toast(`${state.pickerIds.length} added to ${list.name}`);
  if (state.view === "playlists") renderPlaylists();
});

function renderPlaylists() {
  main.innerHTML = `<div class="content"><div class="section-head compact-head">
    <div class="section-actions"><button class="row-button symbol-button" id="new-playlist" data-icon="add" type="button" aria-label="New playlist" title="New playlist">New</button>
      <button class="row-button symbol-button" id="import-playlist" data-icon="download" type="button" aria-label="Import M3U playlist" title="Import M3U">Import M3U</button></div></div>
      <input id="playlist-file" type="file" accept=".m3u,.m3u8" hidden>
    <div id="playlist-list" class="playlist-list"></div><div id="playlist-detail"></div></div>`;
  iconize(main);
  $("#new-playlist").addEventListener("click", () => {
    $("#create-playlist-dialog").showModal();
    $("#new-playlist-name").focus();
  });
  $("#import-playlist").addEventListener("click", () => native ? native.pickPlaylist() : $("#playlist-file").click());
  $("#playlist-file").addEventListener("change", async (event) => {
    const file = event.target.files?.[0];
    if (file) importPlaylistFile(file.name, await file.text());
  });
  const listBox = $("#playlist-list");
  if (!state.playlists.length) listBox.innerHTML = '<div class="empty"><strong>No playlists yet</strong><p>Create one with New.</p></div>';
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
    <div class="section-actions"><button class="row-button symbol-button" id="playlist-play" data-icon="play" type="button" aria-label="Play playlist" title="Play playlist">Play</button>
    <button class="row-button symbol-button" id="playlist-queue" data-icon="queue" type="button" aria-label="Add playlist to queue" title="Add to queue">Queue</button>
    <details class="playlist-options"><summary class="row-button symbol-button" data-icon="edit" aria-label="Edit playlist" title="Edit playlist">Edit</summary>
      <form id="rename-playlist" class="inline-form"><input id="rename-value" class="url-input" maxlength="80" aria-label="Rename playlist" required>
        <button class="row-button" type="submit">Rename</button><button class="row-button" id="delete-playlist" type="button">Delete</button></form>
    </details></div></div>
    <div class="track-list" id="playlist-tracks"></div>`;
  iconize(detail);
  $("#selected-name").textContent = selected.name;
  $("#selected-count").textContent = `${selected.tracks.length} tracks`;
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
  $("#playlist-play").disabled = !selected.tracks.some((id) => state.trackById.has(id));
  $("#playlist-play").addEventListener("click", () => {
    state.queue = selected.tracks.filter((id) => state.trackById.has(id));
    state.current = 0; persistLists();
    if (state.queue.length) playTrack(state.queue[0]);
  });
  $("#playlist-queue").addEventListener("click", () => {
    state.queue.push(...selected.tracks.filter((id) => state.trackById.has(id)));
    persistLists(); syncNativeQueue(); render(); toast("Playlist added to queue");
  });
  const songs = $("#playlist-tracks");
  if (!selected.tracks.length) songs.innerHTML = '<div class="empty"><strong>Nothing here yet</strong><p>Add tracks from Audio.</p></div>';
  selected.tracks.forEach((id, index) => {
    const track = state.trackById.get(id);
    if (track) songs.append(trackRow(track, "playlist", index, selected));
    else {
      const row = document.createElement("div"); row.className = "playlist-track";
      const label = document.createElement("span"); label.textContent = "Unavailable track";
      const remove = document.createElement("button"); remove.className = "row-button";
      remove.type = "button"; remove.textContent = "Remove";
      remove.addEventListener("click", () => {
        selected.tracks.splice(index, 1); persistLists(); renderPlaylists();
      });
      row.append(label, remove); songs.append(row);
    }
  });
}

$("#cancel-create-playlist").addEventListener("click", () => $("#create-playlist-dialog").close());
$("#create-playlist").addEventListener("submit", (event) => {
  event.preventDefault();
  if (!createPlaylist($("#new-playlist-name").value)) return;
  $("#create-playlist-dialog").close();
  $("#new-playlist-name").value = "";
  if (state.view === "playlists") renderPlaylists();
});

function renderQueue() {
  const list = $("#queue-list");
  $("#queue-count").textContent = `${state.queue.length} ${state.queue.length === 1 ? "track" : "tracks"}`;
  $("#clear-queue").disabled = !state.queue.length;
  $("#save-queue").disabled = !state.queue.length;
  $("#queue-mix").disabled = !state.queue.length;
  $("#queue-loop").disabled = !state.queue.length;
  $("#queue-mix").setAttribute("aria-pressed", String(state.shuffle));
  $("#queue-loop").setAttribute("aria-pressed", String(state.repeat === "all"));
  list.replaceChildren();
  if (!state.queue.length) {
    list.innerHTML = '<div class="empty"><strong>Queue is empty</strong><p>Play a track from Audio.</p></div>';
    return;
  }
  state.queue.forEach((id, index) => {
    const track = state.trackById.get(id);
    if (track) list.append(trackRow(track, "queue", index));
    else {
      const missing = document.createElement("div"); missing.className = "playlist-track";
      missing.textContent = "Unavailable track ";
      const remove = document.createElement("button"); remove.type = "button"; remove.className = "row-button";
      remove.textContent = "Remove";
      remove.addEventListener("click", () => removeQueueIndex(index));
      missing.append(remove); list.append(missing);
    }
  });
}
$("#clear-queue").addEventListener("click", () => {
  state.queue = []; state.current = -1; audio.pause();
  if (native) native.command("stop", 0);
  persistLists(); renderQueue(); updatePlayer();
  $("#queue-options").open = false;
});
$("#save-queue").addEventListener("click", () => {
  $("#save-queue-dialog").showModal();
  $("#queue-name").focus();
});
$("#cancel-save-queue").addEventListener("click", () => $("#save-queue-dialog").close());
$("#save-queue-form").addEventListener("submit", (event) => {
  event.preventDefault();
  if (createPlaylist($("#queue-name").value, state.queue)) {
    $("#save-queue-dialog").close();
    $("#queue-name").value = "";
    toast("Queue saved as playlist");
  }
});
$("#queue-mix").addEventListener("click", () => {
  if (!state.queue.length) return;
  setShuffle(true);
  if (state.current < 0 || state.queue.length === 1)
    playTrack(state.queue[Math.floor(Math.random() * state.queue.length)]);
  else move(1);
});
$("#queue-loop").addEventListener("click", () => setRepeat(state.repeat === "all" ? "off" : "all"));

function renderMore() {
  main.innerHTML = `<div class="content">
    <section class="settings-card"><h2>Interface</h2>
      <label class="setting-row">Appearance <select id="theme-setting"><option value="system">Follow device</option>
        <option value="dark">Dark</option><option value="light">Light</option></select></label>
      <label class="setting-row">Default playback speed <select id="speed-setting">
        <option value="0.75">0.75×</option><option value="1">1×</option><option value="1.25">1.25×</option>
        <option value="1.5">1.5×</option><option value="2">2×</option></select></label>
    </section><section class="settings-card"><h2>Media library</h2>
      <div class="section-actions"><button id="add-folder" class="row-button symbol-button" data-icon="add" type="button" aria-label="Add music folder" title="Add folder" ${native ? "" : "hidden"}>Add folder</button>
        <button id="rescan" class="row-button symbol-button" data-icon="refresh" type="button" aria-label="Rescan library" title="Rescan library">Rescan library</button></div>
      <div id="folder-list"></div>
      ${state.hiddenTracks.size ? '<h3>Hidden tracks</h3><div id="hidden-tracks"></div>' : ''}</section>
    <section class="settings-card"><h2>App updates</h2>
      <p id="update-status">Check for a newer ytmp3 app version.</p>
      <p id="update-notes" hidden></p>
      <div class="section-actions"><button id="check-update" class="row-button symbol-button" data-icon="refresh" type="button" aria-label="Check for app updates" title="Check for updates">Check now</button>
        <button id="install-update" class="primary-button" type="button" hidden></button></div>
    </section><details class="settings-card about-details"><summary><h2>About ytmp3</h2></summary>
      <p>Downloads use <a href="https://github.com/yt-dlp/yt-dlp" target="_blank" rel="noopener noreferrer">yt-dlp</a> and ffmpeg. ytmp3 provides the library and player.</p>
      <p>Save content you are authorized to copy.</p>
      ${native ? '<p>Android includes <a href="https://github.com/yausername/youtubedl-android">youtubedl-android</a> (<a href="/licenses/youtubedl-android-GPL-3.0.txt">GPL-3.0 license</a>).</p>' : ''}
    </details></div>`;
  iconize(main);
  $("#theme-setting").value = state.settings.theme;
  $("#speed-setting").value = String(state.settings.speed);
  $("#theme-setting").addEventListener("change", (event) => {
    state.settings.theme = event.target.value; persistSettings();
  });
  $("#speed-setting").addEventListener("change", (event) => {
    state.settings.speed = Number(event.target.value); persistSettings();
    if (native) native.command("speed", state.settings.speed);
    else audio.playbackRate = state.settings.speed;
    $("#speed").textContent = `${state.settings.speed}×`;
  });
  $("#rescan").addEventListener("click", () => refresh());
  $("#check-update").addEventListener("click", () => checkAppUpdate(false));
  $("#install-update").addEventListener("click", installAppUpdate);
  renderUpdateCard();
  if (native) {
    $("#add-folder").addEventListener("click", () => native.pickFolder());
    const folders = JSON.parse(native.folders());
    for (const folder of folders) {
      const row = document.createElement("div"); row.className = "folder-row";
      const name = document.createElement("span"); name.textContent = folder.name;
      const remove = document.createElement("button"); remove.type = "button"; remove.className = "row-button";
      remove.textContent = "Remove"; remove.setAttribute("aria-label", `Remove folder ${folder.name}`);
      remove.addEventListener("click", () => {
        native.removeFolder(folder.uri); refresh(); renderMore();
      });
      row.append(name, remove); $("#folder-list").append(row);
    }
  }
  for (const id of state.hiddenTracks) {
    const track = state.trackById.get(id);
    const row = document.createElement("div"); row.className = "folder-row";
    const name = document.createElement("span"); name.textContent = track ? titleOf(track) : id;
    const restore = document.createElement("button"); restore.type = "button";
    restore.className = "row-button"; restore.textContent = "Restore";
    restore.addEventListener("click", () => {
      state.hiddenTracks.delete(id);
      localStorage.setItem("ytmp3_hidden_tracks", JSON.stringify([...state.hiddenTracks]));
      renderMore();
    });
    row.append(name, restore); $("#hidden-tracks").append(row);
  }
}
window.ytmp3FoldersChanged = () => { refresh(); if (state.view === "more") renderMore(); };

function renderUpdateCard() {
  const status = $("#update-status");
  if (!status) return;
  status.textContent = state.updateJob?.state === "working" ? "Installing update…"
    : state.updateJob?.state === "done" ? "Update installed. Restart the PC app."
    : state.updateJob?.state === "error" ? "Could not install the update. Try again later."
    : state.updateChecking ? "Checking for updates…"
    : state.update?.error ? state.update.error
    : state.update?.available ? `Version ${state.update.version} is available. You have ${state.update.current}.`
    : state.update ? `Up to date (version ${state.update.current}).`
    : "Check for a newer ytmp3 app version.";
  const notes = $("#update-notes");
  notes.hidden = !state.update?.available || !state.update.notes;
  notes.textContent = state.update?.notes || "";
  $("#check-update").disabled = state.updateChecking || state.updateJob?.state === "working";
  const install = $("#install-update");
  install.hidden = !state.update?.available || state.updateJob?.state === "done";
  install.disabled = state.updateJob?.state === "working";
  install.textContent = native ? "Open APK in Drive" : "Install update";
}

function receiveAppUpdate(result) {
  state.updateChecking = false;
  state.update = result;
  if (!result.error) localStorage.setItem("ytmp3_update_checked_at", String(Date.now()));
  renderUpdateCard();
  if (result.error) {
    if (!state.updateCheckSilent) toast(result.error);
  } else if (result.available) toast(`ytmp3 ${result.version} is available in More`);
  else if (!state.updateCheckSilent) toast("ytmp3 is up to date");
}
window.ytmp3UpdateResult = receiveAppUpdate;

async function checkAppUpdate(silent = true) {
  if (state.updateChecking) return;
  state.updateChecking = true;
  state.updateCheckSilent = silent;
  renderUpdateCard();
  if (native) { native.checkAppUpdate(); return; }
  try {
    const response = await fetch("/api/update", { cache: "no-store" });
    receiveAppUpdate(response.ok ? await response.json() : { error: "Could not check for updates." });
  } catch { receiveAppUpdate({ error: "Could not check for updates." }); }
}

async function installAppUpdate() {
  if (!state.update?.available) return;
  if (native) { native.openAppUpdate(); return; }
  try {
    const response = await fetch("/api/update/install", { method: "POST",
      headers: { "Content-Type": "application/json" }, body: "{}" });
    if (!response.ok) throw new Error();
    state.updateJob = await response.json();
    renderUpdateCard();
    pollAppUpdate();
  } catch { toast("Could not start the update."); }
}

async function pollAppUpdate() {
  try {
    const response = await fetch("/api/update/job", { cache: "no-store" });
    if (!response.ok) throw new Error();
    state.updateJob = await response.json();
    renderUpdateCard();
    if (state.updateJob.state === "working") setTimeout(pollAppUpdate, 2000);
    else toast(state.updateJob.state === "done" ? "Update installed. Restart ytmp3." : "Update failed. Try again later.");
  } catch { toast("Could not check update progress."); }
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
        const ids = state.job.tracks.filter((track) => state.trackById.has(track));
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

function playCollection(ids, mix = false) {
  if (!ids.length) return;
  state.queue = [...ids];
  if (mix) {
    for (let i = state.queue.length - 1; i > 0; i--) {
      const j = Math.floor(Math.random() * (i + 1));
      [state.queue[i], state.queue[j]] = [state.queue[j], state.queue[i]];
    }
  }
  setShuffle(false);
  playTrack(state.queue[0]);
}
function playTrack(id, index) {
  if (!state.queue.includes(id)) state.queue = state.tracks.map((item) => item.id);
  state.queue = state.queue.filter((item) => state.trackById.has(item));
  state.current = state.queue[index] === id ? index : state.queue.indexOf(id);
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
      title: titleOf(track), artist: track.artist || "", album: track.album || "",
      artwork: track.artwork ? [{ src: `/cover/${encodeURIComponent(track.id)}?v=${state.artVersion}` }] : []
    });
  }
  render();
}
function queueItems() {
  return state.queue.map((id) => state.trackById.get(id))
    .filter(Boolean).map((track) => ({ id: track.id, title: titleOf(track),
      artist: track.artist || "", album: track.album || "", artwork: !!track.artwork }));
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
    if (!state.nativePlayback.id && (state.queue.length || state.tracks.length))
      return playTrack(state.queue[0] || state.tracks[0].id, 0);
    native.command(state.nativePlayback.playing ? "pause" : "play", 0);
    return;
  }
  if (!audio.src && (state.queue.length || state.tracks.length))
    return playTrack(state.queue[0] || state.tracks[0].id, 0);
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
  playTrack(state.queue[next], next);
}
function updatePlayer() {
  const track = currentTrack();
  $("#player-title").textContent = track ? titleOf(track) : "Nothing playing";
  $("#player-subtitle").textContent = track ? [track.artist, track.album].filter(Boolean).join(" · ") || track.folder || "Personal library"
    : "Choose a file from your library";
  const playerArt = $(".player-art");
  const artKey = `${track?.id || ""}:${state.artVersion}`;
  if (playerArt.dataset.key !== artKey) {
    playerArt.dataset.key = artKey;
    playerArt.replaceChildren(...trackArt(track, "player-art").childNodes);
  }
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
  if (state.playerOpen) return;
  state.playerOpen = true;
  document.body.classList.add("player-open");
  setPlayerPanel("queue", false);
  $("#queue-list").scrollTop = 0;
  history.pushState({ view: state.view, player: true }, "", "#player");
  if (!matchMedia("(prefers-reduced-motion: reduce)").matches)
    $("#player").animate([
      { transform: "translateY(100%)" }, { transform: "translateY(0)" }
    ], { duration: 300, easing: "cubic-bezier(.22,.75,.2,1)" });
  $("#close-player").focus();
}
let panelSlide = null;
function stopPanelSlide() {
  if (!panelSlide) return;
  panelSlide.animation.cancel();
  panelSlide.ghost.remove();
  panelSlide = null;
}
function playerGhost() {
  const ghost = $("#player").cloneNode(true);
  ghost.querySelector("#audio")?.remove();
  ghost.querySelectorAll("[id]").forEach((node) => node.removeAttribute("id"));
  ghost.removeAttribute("id");
  ghost.classList.add("player-panel-ghost");
  ghost.inert = true;
  ghost.setAttribute("aria-hidden", "true");
  return ghost;
}
function animatePlayerExit() {
  stopPanelSlide();
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const exit = document.createElement("div");
  exit.className = "player-exit player-open";
  exit.append(playerGhost());
  document.body.append(exit);
  const animation = exit.animate([
    { transform: "translateY(0)" }, { transform: "translateY(100%)" }
  ], { duration: 310, easing: "cubic-bezier(.4,0,.8,.3)" });
  animation.onfinish = () => exit.remove();
}
function setPlayerPanel(panel, animate = true) {
  const player = $("#player");
  if (player.dataset.panel === panel) return;
  stopPanelSlide();
  player.getAnimations().forEach((animation) => animation.cancel());
  const motion = animate && state.playerOpen &&
    !matchMedia("(prefers-reduced-motion: reduce)").matches;
  const ghost = motion ? playerGhost() : null;
  const queueScroll = $("#queue-list").scrollTop;
  player.dataset.panel = panel;
  $("#expand-player").setAttribute("aria-expanded", String(panel === "song"));
  $("#expand-player").setAttribute("aria-label", panel === "song" ? "Back to queue" : "Open song view");
  $("#back-to-queue").hidden = panel !== "song";
  if (ghost) {
    ghost.style.zIndex = panel === "song" ? "9" : "11";
    document.body.append(ghost);
    ghost.querySelector(".queue-list").scrollTop = queueScroll;
    const timing = { duration: 310, easing: "cubic-bezier(.22,.75,.2,1)" };
    const animation = panel === "song"
      ? player.animate([{ transform: "translateY(100%)" }, { transform: "translateY(0)" }], timing)
      : ghost.animate([{ transform: "translateY(0)" }, { transform: "translateY(100%)" }], timing);
    panelSlide = { animation, ghost };
    animation.onfinish = () => { if (panelSlide?.ghost === ghost) stopPanelSlide(); };
  }
}
function closePlayer() {
  if (state.playerOpen) history.back();
}
$("#expand-player").addEventListener("click", () => {
  if (!state.playerOpen) openPlayer();
  else setPlayerPanel($("#player").dataset.panel === "queue" ? "song" : "queue");
});
$("#back-to-queue").addEventListener("click", () => setPlayerPanel("queue"));
$("#close-player").addEventListener("click", closePlayer);
let pullDistance = 0;
let pullTime = 0;
let pullCooldown = 0;
function playerCanScroll() {
  const player = $("#player");
  return ["auto", "scroll"].includes(getComputedStyle(player).overflowY) &&
    player.scrollHeight > player.clientHeight + 1;
}
$("#player").addEventListener("wheel", (event) => {
  if (!state.playerOpen || event.target.closest("input, button:not(#expand-player), .drag-handle, .tile-menu")) return;
  const panel = $("#player").dataset.panel;
  const list = $("#queue-list");
  let action;
  if (panel === "queue") {
    if (event.deltaY < 0 && (event.target.closest("#expand-player") ||
        (event.target.closest("#queue-list") && list.scrollTop <= 1))) action = "song";
    else if (event.deltaY > 0 && event.target.closest("#expand-player")) action = "close";
  } else {
    const player = $("#player");
    const limit = player.scrollHeight - player.clientHeight;
    if (event.deltaY > 0 && (!playerCanScroll() || player.scrollTop >= limit - 1)) action = "queue";
    else if (event.deltaY < 0 && (!playerCanScroll() || player.scrollTop <= 1)) action = "close";
  }
  if (!action) { pullDistance = 0; return; }
  const now = Date.now();
  if (now < pullCooldown) return;
  if (now - pullTime > 450) pullDistance = 0;
  pullTime = now;
  pullDistance += Math.abs(event.deltaY);
  if (pullDistance < 90) return;
  event.preventDefault();
  pullDistance = 0;
  pullCooldown = now + 600;
  if (action === "close") closePlayer();
  else setPlayerPanel(action);
}, { passive: false });
let touchStart = null;
$("#player").addEventListener("touchstart", (event) => {
  touchStart = null;
  if (!state.playerOpen || event.touches.length !== 1 ||
      event.target.closest("input, .drag-handle, .tile-menu")) return;
  const panel = $("#player").dataset.panel;
  const list = $("#queue-list");
  const banner = !!event.target.closest("#expand-player");
  if (panel === "queue" && !banner && !event.target.closest("#queue-list")) return;
  if (panel === "song" && event.target.closest("button:not(#expand-player)")) return;
  touchStart = { x: event.touches[0].clientX, y: event.touches[0].clientY,
    scrollTop: list.scrollTop, scrollBottom: list.scrollHeight - list.clientHeight - list.scrollTop,
    panel, banner };
}, { passive: true });
$("#player").addEventListener("touchend", (event) => {
  if (!touchStart || event.changedTouches.length !== 1) return;
  const { x, y, scrollTop, scrollBottom, panel, banner } = touchStart;
  touchStart = null;
  const across = event.changedTouches[0].clientX - x;
  const distance = event.changedTouches[0].clientY - y;
  if (Math.abs(across) > Math.abs(distance) * 1.3) {
    if (panel === "song" && Math.abs(across) > 90) {
      event.preventDefault();
      move(across < 0 ? 1 : -1);
    }
    return;
  }
  if (panel === "queue") {
    const list = $("#queue-list");
    if ((banner && distance < -80) ||
        (!banner && -distance - scrollBottom > 90 &&
          list.scrollTop >= list.scrollHeight - list.clientHeight - 1)) {
      event.preventDefault();
      setPlayerPanel("song");
    } else if ((banner && distance > 90) ||
        (!banner && distance - scrollTop > 90 && list.scrollTop <= 1)) {
      event.preventDefault();
      closePlayer();
    }
  } else if (distance > 100 && (!playerCanScroll() || $("#player").scrollTop <= 1)) {
    event.preventDefault();
    setPlayerPanel("queue");
  } else if (distance < -110 && (!playerCanScroll() || $("#player").scrollTop >=
      $("#player").scrollHeight - $("#player").clientHeight - 1)) {
    event.preventDefault();
    closePlayer();
  }
}, { passive: false });
$("#player").addEventListener("touchcancel", () => { touchStart = null; });
$("#play").addEventListener("click", togglePlay);
$("#previous").addEventListener("click", () => move(-1));
$("#next").addEventListener("click", () => move(1));
function updatePlaybackModes() {
  $("#shuffle").setAttribute("aria-pressed", String(state.shuffle));
  $("#shuffle").setAttribute("aria-label", state.shuffle ? "Shuffle on" : "Shuffle off");
  $("#repeat").dataset.active = String(state.repeat !== "off");
  $("#repeat").setAttribute("aria-label", `Repeat ${state.repeat}`);
  $("#queue-mix").setAttribute("aria-pressed", String(state.shuffle));
  $("#queue-loop").setAttribute("aria-pressed", String(state.repeat === "all"));
}
function setShuffle(enabled) {
  state.shuffle = enabled;
  if (native) native.command("shuffle", enabled ? 1 : 0);
  updatePlaybackModes();
}
function setRepeat(mode) {
  state.repeat = mode;
  if (native) native.command("repeat", { off: 0, one: 1, all: 2 }[mode]);
  updatePlaybackModes();
  toast(`Repeat ${state.repeat}`);
}
$("#shuffle").addEventListener("click", () => setShuffle(!state.shuffle));
$("#repeat").addEventListener("click", () =>
  setRepeat({ off: "all", all: "one", one: "off" }[state.repeat]));
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
    const changed = playback.id !== state.nativePlayback.id ||
      (playback.id && playback.index !== state.current);
    state.nativePlayback = playback;
    if (playback.id) state.current = playback.index;
    if (typeof playback.shuffle === "boolean") state.shuffle = playback.shuffle;
    if ([0, 1, 2].includes(playback.repeat)) state.repeat = ["off", "one", "all"][playback.repeat];
    updatePlaybackModes();
    updatePlayer();
    if (changed && state.view === "audio") renderTracks();
    if (changed && state.view === "browse") renderBrowseTracks();
    if (changed) renderQueue();
  } catch { /* The controller is reconnecting. */ }
}, 500);

$("#theme-button").addEventListener("click", () => {
  const theme = document.documentElement.dataset.theme === "dark" ? "light" : "dark";
  state.settings.theme = theme;
  persistSettings();
  if (state.view === "more") renderMore();
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
  state.view = "browse";
  history.replaceState(null, "", "#browse");
  render();
  $("#url-input").focus();
  toast("Shared link ready to save");
}
window.ytmp3Receive = receiveShared;
const shared = new URLSearchParams(location.search);
const received = shared.get("url") || shared.get("text")?.match(/https?:\/\/\S+/)?.[0];
if (received) {
  sessionStorage.setItem("ytmp3_shared_url", received);
  history.replaceState(null, "", "#browse");
  state.view = "browse";
  toast("Shared link ready to save");
}
const lastUpdateCheck = Number(localStorage.getItem("ytmp3_update_checked_at") || 0);
if (Date.now() - lastUpdateCheck > 86400000) setTimeout(() => checkAppUpdate(true), 2000);
try {
  const snapshot = JSON.parse(localStorage.getItem("ytmp3_snapshot")
    || sessionStorage.getItem("ytmp3_snapshot") || "null");
  if (snapshot?.tracks && Array.isArray(snapshot.tracks)) {
    state.tracks = snapshot.tracks;
    state.trackJson = JSON.stringify(state.tracks);
    state.trackById = new Map(state.tracks.map((track) => [track.id, track]));
    state.snapshotAt = Number.isFinite(snapshot.at) ? snapshot.at : 0;
  }
} catch { /* Ignore an invalid old snapshot. */ }
render();
refresh();
