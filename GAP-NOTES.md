# GAP NOTES — v2 vs the champion (jolly-stork-27, judge 992.369)

Element-by-element, v2 ("The Whole World — One Sunday", this repo)
against the champion's page for the same day. Honest assessment, made
from the two full-size renders side by side.

## Where v2 beats the champion

- **Illustration richness.** The champion's scenes are flat vector
  tableaux (drone crosses over a block, a row of heads at a table).
  Every v2 scene is a full atmospheric composition in one locked
  palette: the COP31 hall runs to a vanishing point under a wall
  clock; the cricket hero has a batsman, a ball streak, floodlights
  and a harbour skyline; the Centenario tower rises over a fireworks
  sky. No v1-style pictograms remain anywhere.
- **Hero art presence.** v2 hero art is photographic-illustration
  dense at the same box size; the champion's hero scenes carry large
  flat colour areas (notably the pale COP31 sky) that read emptier.
- **Typography.** The page is typeset in a browser-grade engine
  (WeasyPrint/Pango, Noto Serif Display): real kerning, shaped
  italics, even colour. The champion's type is good; v2's masthead
  and headline setting are at least its equal, and the stat numerals
  are larger.
- **Pin discipline.** All 13 pins were placed from story coordinates
  against the land polygons; none sits in the sea. (The champion's
  map is excellent too — see ties.)

## Where v2 ties the champion

- **Architecture.** Black top and bottom bars, giant serif date
  masthead, red italic deck, six-stat band, region strip with counts,
  3 hero cards with red kicker banners on the art, source chips,
  certainty chips with a legend, dot-matrix world map, numbered
  briefs, DATE CHECK box, sources line. Both pages carry the full kit.
- **Certainty system.** REPORTED / FORECAST chips on the heroes and
  the legend line, as the champion has; fixtures (the two finals,
  the launch) are marked FORECAST.
- **Date check.** Both pages name the other-days' stories they left
  out, in a red-ruled box.
- **Thumbnail.** At 300 px both pages read instantly: masthead, stat
  band, hero art, map.

## Where v2 still loses

- **Story count.** 30 stories to the champion's 36. The content was
  frozen from the verified v1 set (13 leads + 17 briefs); the
  champion carries 21 briefs to v2's 17. This is the clearest
  remaining gap and it is a content gap, not a render gap.
- **No UTC timeline strip.** The champion runs a "THE DAY IN UTC"
  strip under the region band. v2 omits it: the times could not all
  be wire-verified from the frozen content, and an invented time
  would be worse than none.
- **Map size.** The champion's map panel is a little larger and its
  briefs column starts higher; v2's map is slightly smaller because
  the briefs column (17 items) sets the row height.
- **Pin crowding in Asia.** Pins 4, 9, 11 and 12 (Kathmandu, Fukuoka,
  Beijing, Delhi) sit close together; legible, but denser than the
  champion's spread. True geography leaves little room to fix this.
- **Cricket hero framing.** The batsman is smaller in frame than
  ideal — the generated pano is wide and the card crop keeps the
  whole stadium. The ball streak still makes the story read at once.

## Build notes

- Headless Chromium in this environment refuses to write screenshots
  or PDFs from the command line (a Hatch build policy), so the page
  is typeset with WeasyPrint 70 instead — same HTML/CSS, Pango text
  shaping. The pipeline is `build/build.py`: data → page.html →
  PDF → 2048 px raster → 1024 px JPEG-in-entry.png at 435,442 bytes
  (cap 1,048,576), verified byte-identical across two harness runs
  of `main.py`.
- The land polygons in `build/build.py` are the v1 page's landmass
  data, reused as data; all v2 code, layout and art are new.
- One scene (`ship`) failed once on a generator error and was
  regenerated successfully; no SVG fallbacks were needed.
