// Run with: node tests/check_playlists.js
const assert = require("node:assert/strict");
const lists = require("../ytmp3/web/playlist-store.js");

assert.deepEqual(lists.sanitize(null), []);
assert.deepEqual(lists.sanitize([{ id: "one", name: "One", tracks: ["a", 3, "b"] },
  { id: 2, name: "bad", tracks: [] }]), [{ id: "one", name: "One", tracks: ["a", "b"] }]);

const first = lists.create([], "  Favorites  ", ["a", "b"], "id-1");
assert.deepEqual(first, { id: "id-1", name: "Favorites", tracks: ["a", "b"] });
assert.equal(lists.create([first], "favorites", [], "id-2"), null);
lists.add(first, "b");
lists.add(first, "c");
assert.deepEqual(first.tracks, ["a", "b", "c"]);
assert.deepEqual(lists.move(first.tracks, 2, -1), ["a", "c", "b"]);
assert.deepEqual(first.tracks, ["a", "b", "c"]);
assert.deepEqual(lists.move(first.tracks, 0, -1), first.tracks);
assert.deepEqual(lists.importM3U("#EXTM3U\n#EXTINF:10,One\nMusic/one.mp3\nC:\\Music\\two.mp3\nmissing.mp3\n",
  [{ id: "one.mp3" }, { id: "@0/folder/two.mp3" }]),
  { tracks: ["one.mp3", "@0/folder/two.mp3"], missing: 1 });
assert.deepEqual(lists.importM3U("same.mp3\n", [{ id: "same.mp3" }, { id: "@0/same.mp3" }]),
  { tracks: [], missing: 1 });
console.log("playlist checks passed");
