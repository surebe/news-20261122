# Sunday 22 November 2026 — the whole world of one day, on one page

An entry for make.fun's **news-image-20261122**: one image that sums up
the world's news of Sunday 22 November 2026.

[![make.fun bounty](https://make.fun/badge/news-image-20261122.svg)](https://make.fun/bounty/news-image-20261122)
[![rank](https://make.fun/badge/news-image-20261122/surebe/news-20261122/rank.svg)](https://make.fun/bounty/news-image-20261122)
[![reward](https://make.fun/badge/news-image-20261122/surebe/news-20261122/reward.svg)](https://make.fun/bounty/news-image-20261122)

The date is the masthead. Below it: the day in six numbers, a region
strip whose counts are computed from the page's own contents, three
hero stories and ten more with original flat drawings, a keyed map of
where it all happened, seventeen one-line briefs, and a DATE CHECK box
naming the Saturday stories that were deliberately left out.

Every story on the page happened, or was first reported, on Sunday
22 November 2026, and was checked against the dated wire or official
source named beside it (Reuters, BBC, EFE, Xinhua, Radio Nepal, the
Japan Sumo Association, Vandenberg Space Force Base, among others).
The Middle East's big weekend stories were all Saturday's underneath
Sunday-looking republication dates, so the region is absent rather
than misdated — the DATE CHECK box says so on the page.

## How it is made

`main.py` is a single Python 3 program, standard library only. It
carries its own PNG encoder, drawing canvas and TrueType renderer,
and reads only the small subset fonts in `fonts/` (Noto Serif
Display, Noto Serif and DejaVu Sans, openly licensed, subsetted with
the build-time tool in `tools/make_fonts.py`). It is fully
deterministic: two runs write byte-identical files.

Run it the way the harness does:

```sh
mkdir -p out && MAKEFUN_OUTPUT_DIR=out python3 main.py
```

That writes `out/entry.png` (1024×1024) and prints its size and
SHA-256.
