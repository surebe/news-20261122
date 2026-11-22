"""Build-time tool: subset the display/book/sans faces this newspaper
uses and write the small results into the repo's fonts/ folder.

Faces (all Noto, OFL-licensed; subsetting for embedding is permitted):
  Noto Serif Display Bold   -> display_bold.ttf  (headlines, numerals)
  Noto Serif Display Black  -> display_black.ttf (the masthead date)
  Noto Serif                -> serif.ttf         (summaries)
  Noto Serif Italic         -> serif_italic.ttf  (the dek)
  DejaVu Sans / Sans Bold   -> sans.ttf / sans_bold.ttf (kickers, labels)

This script is NOT run by the competition harness (it needs fontTools
and the full system fonts). It is run once, here, by the author. The
entry program (main.py) carries its own TrueType parser written from
scratch and reads only the small subset files produced by this tool.
"""

import os
import sys

from fontTools import subset

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.dirname(HERE)
OUT_DIR = os.path.join(REPO, "fonts")
NOTO = "/usr/share/fonts/truetype/noto"
DEJAVU = "/usr/share/fonts/truetype/dejavu"

# Every character the newspaper can print: ASCII, the typographic
# punctuation used in the copy, and the Latin-1 letters needed for
# names such as Turkiye, Sanchez and Zurcher.
CHARSET = (
    "abcdefghijklmnopqrstuvwxyz"
    "ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    "0123456789"
    " .,;:!?'-–—'‘’“”()[]£€$%·/&+*@#~"
    "áéíóúàèìòùâêîôûäëïöüÿñçÁÉÍÓÚÀÈÌÒÙÂÊÎÔÛÄËÏÖÜŸÑÇ"
    "−×°"
)

FONTS = [
    (os.path.join(NOTO, "NotoSerifDisplay-Bold.ttf"), "display_bold.ttf"),
    (os.path.join(NOTO, "NotoSerifDisplay-Black.ttf"), "display_black.ttf"),
    (os.path.join(NOTO, "NotoSerifDisplay-CondensedBlack.ttf"), "display_cond_black.ttf"),
    (os.path.join(NOTO, "NotoSerifDisplay-CondensedBold.ttf"), "display_cond_bold.ttf"),
    (os.path.join(NOTO, "NotoSerif-Regular.ttf"), "serif.ttf"),
    (os.path.join(NOTO, "NotoSerif-Italic.ttf"), "serif_italic.ttf"),
    (os.path.join(DEJAVU, "DejaVuSans.ttf"), "sans.ttf"),
    (os.path.join(DEJAVU, "DejaVuSans-Bold.ttf"), "sans_bold.ttf"),
]


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    for src, out_name in FONTS:
        dst = os.path.join(OUT_DIR, out_name)
        opts = subset.Options()
        opts.flavor = None
        opts.layout_features = []
        opts.name_IDs = []
        opts.notdef_outline = True
        opts.recalc_bounds = True
        opts.drop_tables = [
            "GSUB", "GPOS", "GDEF", "BASE", "JSTF", "MATH", "kern",
            "morx", "mort", "kerx", "feat",
        ]
        font = subset.load_font(src, opts)
        ss = subset.Subsetter(options=opts)
        ss.populate(text=CHARSET)
        ss.subset(font)
        font.save(dst)
        print(out_name, os.path.getsize(dst), "bytes")


if __name__ == "__main__":
    sys.exit(main())
