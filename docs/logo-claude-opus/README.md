# ytmp3 logo exploration: Claude Opus

Four new concepts for the app icon, the favicon and the navigation symbol. They
follow [DESIGN.md](../DESIGN.md): a personal local audio library and URL
downloader, with a clear, capable, quiet tone.

[Contact sheet](contact-sheet.svg) shows each tile at 128, 48 and 24 px, plus a
single-colour 24 px navigation glyph, on the app's light (`#f2f5f3`) and dark
(`#101819`) backgrounds.

## How this set departs from the rejected one

All three [earlier drafts](../logo-concepts/) share a mint tile with dark ink
and use a play triangle, list lines, a record or a letter. None of the concepts
below uses any of those. None sits on a mint tile, either: mint appears only as
an accent inside a darker tile. There are no letters, triangles, discs or list
lines, and nothing refers to YouTube, Spotify or VLC.

## Palette

No new colours. Every fill is an existing token from `web/app.css`: dark ink
`#102822`, mint `#70d7b4`, light-theme teal `#146d54`, ink `#f0f6f4`, surface
`#172123`, light surfaces `#dce7e1` / `#cad7d0`, and light ink `#15221e`. I kept
them because the app already has one teal accent, and a launcher icon in a
different hue would make the app feel like two products. Each concept pairs the
tokens differently, so the four tiles don't read as recolours of one another.

## Concepts

All geometry sits on a 512 grid. Each mark covers about 50–60% of the tile and
is centred optically, so it survives Android's circle and squircle masks.
Every mark reduces to a single colour for Android 13 themed icons and the nav
bar.

### A · Drop: recommended

[a-drop.svg](a-drop.svg). A mint teardrop on the dark-green tile, cut by one
sine period. The idea: the app distils audio out of a link. The drop is what
remains, and the cut shows that what remains is sound. The wave's nodes meet
the drop's edges at its widest line, so the cut looks deliberate instead of
decorative.

- **Small sizes:** the teardrop silhouette carries it. At 24 px the cut is about
  1.2 px and its curve flattens to a near-straight notch, so the mark reads as
  "a drop with a line through it". The wave becomes legible from about 48 px.
- **Tradeoff:** the least literal of the four about music. A drop is also used
  by water, weather and some bookmark apps (Raindrop.io, for example). The
  sound cut is the only thing that separates it from those.

### B · Fork

[b-fork.svg](b-fork.svg). One continuous white stroke on the deep-teal tile. A
link loop opens to the right, and its two strands oscillate in antiphase, the
way a struck tuning fork's tines move. One shape says both "a URL" and "it
rings".

- **Small sizes:** a 40-unit stroke comes out at about 1.9 px on a 24 px tile
  and 2.7 px as a nav glyph. The two strands stay about 3.75 px apart, so they
  never merge.
- **Tradeoff:** the most linear and delicate of the four. The loop could also
  read as a hairpin or a sideways magnet. Green plus curved lines is also
  closer to Spotify's territory than I'd like, although the forms are
  different: a connected U, not stacked arcs.

### C · Shelf

[c-shelf.svg](c-shelf.svg). Three dark books and one teal book leaning against
them, on a shelf, on a pale tile. The uneven heights double as a level meter.
It is the only concept that says *library*, the part of the app used every
day.

- **Small sizes:** at 24 px the books are about 1.9 px wide with roughly 0.9 px
  gaps, so they read as a comb of uneven bars. The leaning book is what stops it
  looking like a bar chart. At 48 px it is clearly books.
- **Tradeoff:** it sits nearest to generic "library" and analytics glyphs. The
  pale tile has low contrast against light launchers and pages, so it depends on
  its hairline border there.

### D · Grille

[d-grille.svg](d-grille.svg). Six holes in a hexagon around a larger mint
centre, on the dark surface tile: a quiet piece of audio hardware. It also
reads as a collection with one item playing.

- **Small sizes:** the strongest at 16–24 px. It is made only of dots, with gaps
  of 1.5 px or more, so nothing closes up, and the lit centre stays distinct at
  any size.
- **Tradeoff:** the most abstract. It says nothing about downloading or links.
  Out of context it could be a flower, a molecule or a loading indicator.

## Recommendation

**A · Drop.** It has the most distinctive silhouette in a launcher row, it holds
at favicon size, and a single shape tells the app's story: a link goes in and
sound stays. It also has no internal detail that must survive at 24 px, so the
cut can fade there without the mark failing. As a nav glyph it stays a solid,
calm shape beside the app's other symbols. If Drop reads as too
water-like, Grille is the safest fallback for small sizes. Shelf communicates
"library" most directly.

## Files

| File | Contents |
| --- | --- |
| `a-drop.svg`, `b-fork.svg`, `c-shelf.svg`, `d-grille.svg` | 512 × 512 launcher tiles. Standard SVG with no scripts, fonts or external assets. |
| `contact-sheet.svg` | All four at 128 / 48 / 24 px and as 24 px nav glyphs, on light and dark. It uses system fonts for labels only. |

Nothing here changes the app's installed icon. The nav glyphs in the contact
sheet show each mark without its tile, with `viewBox="80 80 352 352"` and
`currentColor`. That is how a chosen concept would enter the app's symbol set.

The [PNG contact sheet](contact-sheet.png) was rendered in Edge and visually checked after Claude's session. Drop was chosen for the current app icon; the other three remain alternatives.
