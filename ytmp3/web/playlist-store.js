/* Small data operations shared by the player UI and its runnable check. */
globalThis.Ytmp3Playlists = (() => {
  function sanitize(value) {
    if (!Array.isArray(value)) return [];
    return value.filter((list) => typeof list?.id === "string" && typeof list.name === "string"
      && Array.isArray(list.tracks)).map((list) => ({
      id: list.id, name: list.name,
      tracks: list.tracks.filter((id) => typeof id === "string")
    }));
  }
  function create(lists, name, ids = [], id = crypto.randomUUID()) {
    const clean = name.trim();
    if (!clean || lists.some((list) => list.name.toLocaleLowerCase() === clean.toLocaleLowerCase())) return null;
    return { id, name: clean, tracks: ids.filter((track) => typeof track === "string") };
  }
  function add(list, id) {
    if (!list.tracks.includes(id)) list.tracks.push(id);
  }
  function move(items, index, change) {
    const target = index + change;
    if (index < 0 || target < 0 || target >= items.length) return items;
    const reordered = [...items];
    const [item] = reordered.splice(index, 1);
    reordered.splice(target, 0, item);
    return reordered;
  }
  function importM3U(text, library) {
    const byName = new Map();
    for (const track of library) {
      let path = track.id;
      try { path = decodeURIComponent(path); } catch { /* Keep literal filenames containing %. */ }
      const name = path.replaceAll("\\", "/").split("/").pop().toLocaleLowerCase();
      byName.set(name, byName.has(name) ? null : track.id);
    }
    const found = [];
    let missing = 0;
    for (const raw of text.replace(/^\uFEFF/, "").split(/\r?\n/)) {
      const line = raw.trim();
      if (!line || line.startsWith("#")) continue;
      let path = line;
      try { path = decodeURIComponent(path); } catch { /* Keep literal paths containing %. */ }
      const name = path.replaceAll("\\", "/").split("/").pop().toLocaleLowerCase();
      const id = byName.get(name);
      if (id) found.push(id);
      else missing++;
    }
    return { tracks: found, missing };
  }
  return { sanitize, create, add, move, importM3U };
})();
if (typeof module !== "undefined") module.exports = globalThis.Ytmp3Playlists;
