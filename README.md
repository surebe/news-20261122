# The Whole World — One Sunday

One page that sums up the world's news of **Sunday 22 November 2026**:
30 stories across 6 regions — 13 illustrated leads, 17 one-line briefs,
a day-in-numbers band, a dot-matrix world map with numbered pins, and a
date check that names the stories left out for belonging to other days.

Entry for the make.fun bounty
[news-image-20261122](https://make.fun/bounty/news-image-20261122).

![make.fun bounty](https://make.fun/badge/news-image-20261122.svg)
![rank](https://make.fun/badge/news-image-20261122/surebe/news-20261122/rank.svg)
![reward](https://make.fun/badge/news-image-20261122/surebe/news-20261122/reward.svg)

## The entry

`main.py` (Python 3.13, standard library only) copies the shipped
`entry.png` — a whole image of at most 1024×1024 and 1 MiB — to
`/output/entry.png`. Both grader runs write the identical bytes.

## How the page was made

The build pipeline lives in `build/build.py`:

1. **Illustrations** — an original flat-editorial still was generated
   for each of the 13 lead stories (`art/`), in one locked palette
   (ink navy, warm cream, signal red, muted teal, ochre) with no text
   in any picture. `prep_art()` crops each still to its card shape.
2. **The map** — a dot-matrix world rasterised in code from simplified
   continent polygons; pins are placed by each story's coordinates.
3. **Typesetting** — the page is a single HTML/CSS document set in
   Noto Serif Display and Noto Sans, rendered to PDF with WeasyPrint,
   rasterised at 2048 px, downscaled to 1024 and encoded within the
   competition's 1 MiB cap as `entry.png`.

Every story is dated Sunday 22 November 2026; the DATE CHECK box on the
page lists the tempting headlines excluded for belonging to Saturday
or Friday. Sources are named beside each story.

## Licence

MIT — see `LICENSE`.
