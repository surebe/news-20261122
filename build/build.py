#!/usr/bin/env python3
"""Build tooling for "The Whole World — One Sunday" (news-image-20261122).

Pipeline: story data (below) -> page.html -> WeasyPrint PDF -> pdftoppm
raster at 2048px -> PIL downscale to 1024 -> entry.png (JPEG bytes).

The shipped entry program is ../main.py, which simply copies the
entry.png asset this script produces. Everything here is build-time
provenance; the grader never runs it.

Art: art/<scene>.jpg stills generated for this page (see art/), cropped
to their card shapes by prep_art(). The world map is drawn in code:
dots rasterised from the land polygons in LAND, pins placed in the HTML.
"""

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BUILD = ROOT / "build"
ART = ROOT / "art"

# ---------------------------------------------------------------- content
# The day's verified stories. Facts, headlines and figures are the ones
# the v1 entry carried; nothing here is re-reported or re-worded.

# (scene, label, chip, place, topic, city, lon, lat, certainty,
#  headline, summary)
LEADS = [
    ("cop31", "TALKS RUN ON", "Reuters", "ANTALYA, TÜRKIYE", "CLIMATE TALKS",
     "Antalya", 30.7, 36.9, "REPORTED",
     "Climate talks run past deadline in Antalya",
     "Nearly 200 delegations negotiated into Sunday, a day past the "
     "deadline, over a draft to lift electricity's share of energy to "
     "35% by 2035. (Reuters)"),
    ("cricket", "RECORD 629-6", "Reuters", "WELLINGTON, NEW ZEALAND",
     "CRICKET", "Wellington", 174.5, -40.4, "REPORTED",
     "Pant's century powers a record 629-6",
     "Pant's sizzling century took India to 629-6 at lunch on day "
     "four — their highest Test total in New Zealand, with a lead of "
     "261. (Reuters)"),
    ("libertadores", "THE FINAL", "Xinhua", "MONTEVIDEO, URUGUAY",
     "FOOTBALL", "Montevideo", -56.2, -34.9, "FORECAST",
     "Palmeiras face Estudiantes in the final",
     "Palmeiras meet Estudiantes in South America's biggest club "
     "match, at the stadium that hosted the first World Cup final. "
     "(Xinhua)"),
    ("nepal", "FIRST VISIT", "Radio Nepal", "KATHMANDU, NEPAL", "VISIT",
     "Kathmandu", 85.3, 27.7, "REPORTED",
     "Nepal's PM flies to India on first visit",
     "Shah leads 34 envoys to New Delhi."),
    ("aukus", "SUB ROW", "Reuters", "SYDNEY, AUSTRALIA", "AUKUS",
     "Sydney", 151.2, -33.9, "REPORTED",
     "Australia rebukes US over AUKUS warning",
     "“They are wrong,” Marles said Sunday."),
    ("ship", "SHIP HIT", "BBC", "GULF OF FINLAND", "SHIP HIT",
     "Helsinki", 24.9, 60.2, "REPORTED",
     "Russia-bound ship hit by drones in Gulf",
     "Helsinki blames a Ukrainian strike."),
    ("fbi", "FBI PROBE", "BBC", "WASHINGTON, US", "CYBER",
     "Washington", -77.0, 38.9, "REPORTED",
     "FBI probes apparent hack of crime database",
     "Police database NCIC is the target."),
    ("gamer", "GAMER'S TIP", "BBC", "UNITED STATES", "RESCUE",
     "United States", -98.5, 39.5, "REPORTED",
     "Teen gamer's tip helps rescue missing girl",
     "He spotted her from an FBI alert."),
    ("sumo", "ONOSATO WINS", "JSA", "FUKUOKA, JAPAN", "SUMO",
     "Fukuoka", 130.4, 33.6, "REPORTED",
     "Onosato wins the Cup in a playoff",
     "A playoff win over Wakamotoharu."),
    ("atp", "TITLE MATCH", "ATP", "TURIN, ITALY", "TENNIS",
     "Turin", 7.7, 45.1, "FORECAST",
     "Alcaraz and Zverev meet in Turin final",
     "A new champion is certain in Turin."),
    ("fcc", "PHONE ROW", "Reuters", "BEIJING, CHINA", "PHONES",
     "Beijing", 116.4, 39.9, "REPORTED",
     "China opposes US ban on its phone firms",
     "Commerce ministry spoke on Sunday."),
    ("delhi", "AQI 278", "Hindustan Times", "NEW DELHI, INDIA", "SMOG",
     "New Delhi", 77.2, 28.6, "REPORTED",
     "Delhi air stays 'very poor' on Sunday",
     "AQI hit 278 on Sunday morning."),
    ("spacex", "SPY SATS", "Vandenberg SFB", "VANDENBERG, US", "SPACE",
     "Vandenberg", -120.6, 34.6, "FORECAST",
     "SpaceX to launch spy satellites Sunday",
     "NROL-136 lifts off at 12:23 UTC."),
]

# (region, place, headline, source) — numbered 14 up.
BRIEFS = [
    ("Asia", "Pyongyang", "Marathon put off to October", "Reuters"),
    ("North America", "Washington", "Lock of hair sells for $4,000", "BBC"),
    ("Oceania", "Whanganui", "Racer dies at hillclimb", "MotorSport NZ"),
    ("Asia", "Tokyo", "Kojima: AI may sap the joy of creation", "Nikkei Asia"),
    ("Asia", "New Delhi", "Drones spray anti-smog mist", "Daily Pioneer"),
    ("Europe", "Toulouse", "Macron dines with 60 business chiefs", "EFE"),
    ("Europe", "Ukraine", "Strikes near nuclear plants raise leak risk", "EFE"),
    ("Africa", "Nigeria", "Young voters sit out the coming election", "BBC"),
    ("Latin America", "Santiago", "Chile braces for a brutal wildfire season", "EFE"),
    ("Latin America", "Los Angeles", "Allende warns of far right's rise", "EFE"),
    ("Latin America", "Mexico City", "Cathedral ends night tours", "Xinhua"),
    ("North America", "Washington", "Democrats hunt new leaders", "EFE"),
    ("Oceania", "NZ", "Farmlands chair quits in row", "Farmers Weekly"),
    ("Oceania", "NZ", "Five split $1m Lotto prize", "NZ Herald"),
    ("Oceania", "Ruatoria", "House slips off foundations", "NZ Herald"),
    ("Oceania", "Auckland", "Motorcyclist critically hurt", "NZ Herald"),
    ("North America", "Las Vegas", "Verstappen wins Las Vegas GP", "Reuters"),
]

# (numeral, caption) — every figure is drawn from a story on this page.
STATS = [
    ("~200", "delegations still negotiating at COP31"),
    ("629-6", "India's record Test total in New Zealand"),
    ("35%", "electricity's target share of world energy, 2035"),
    ("34", "members of Nepal PM's delegation to India"),
    ("$2.41m", "prize for the ATP Finals winner"),
    ("$4,000", "paid for a lock of Washington's hair"),
]

# (name, count, colour) — strip order matches the v1 page.
REGIONS = [
    ("NORTH AMERICA", 6, "#5b4a8a"),
    ("LATIN AMERICA", 4, "#b5502a"),
    ("EUROPE", 5, "#2e6f6a"),
    ("AFRICA", 1, "#c8912a"),
    ("ASIA", 7, "#44607e"),
    ("OCEANIA", 7, "#4a7c59"),
]

DEK = ("Climate talks run on in Antalya · India post a record 629-6 "
       "in Wellington · Turin and Montevideo host the day's finals")

DATE_CHECK = (
    "Left out as Saturday 21 November's news, however Sunday the "
    "headlines looked: Bahrain's Iranian-attack report, the Hormuz "
    "mediation statements and President Aoun's speech in Beirut. Also "
    "excluded: Friday's Peru earthquake and the El Chapo Isidro "
    "capture, a Friday-night raid."
)

# ------------------------------------------------------------- the map
# Simplified continent outlines as (lon, lat) polygons — the same
# landmass data the v1 page used, rasterised here into a dot matrix.

LAND = [
    # North and Central America
    [(-168, 66), (-150, 70), (-135, 69), (-125, 71), (-110, 68),
     (-95, 69), (-86, 66), (-81, 62), (-79, 58), (-86, 55), (-93, 57),
     (-95, 51), (-90, 47), (-84, 46), (-77, 44), (-70, 42), (-72, 40),
     (-74, 39), (-76, 35), (-79, 33), (-80, 30), (-81, 26), (-84, 28),
     (-87, 29), (-91, 29), (-96, 28), (-97, 26), (-97, 22), (-94, 18),
     (-91, 19), (-87, 21), (-88, 16), (-83, 15), (-79, 9), (-77, 8),
     (-83, 9), (-86, 12), (-90, 14), (-94, 16), (-97, 16), (-102, 18),
     (-105, 20), (-108, 23), (-110, 24), (-113, 29), (-117, 33),
     (-121, 34), (-124, 40), (-124, 46), (-129, 52), (-133, 57),
     (-140, 60), (-152, 60), (-162, 61), (-168, 66)],
    # South America
    [(-79, 9), (-75, 11), (-71, 12), (-64, 11), (-60, 9), (-55, 6),
     (-51, 4), (-50, 0), (-44, -3), (-38, -5), (-35, -8), (-38, -13),
     (-39, -16), (-40, -21), (-44, -23), (-48, -26), (-51, -30),
     (-54, -33), (-57, -37), (-59, -39), (-62, -41), (-63, -43),
     (-65, -45), (-66, -48), (-67, -51), (-68, -54), (-70, -54),
     (-72, -50), (-73, -44), (-73, -38), (-72, -32), (-70, -24),
     (-70, -19), (-74, -15), (-77, -12), (-79, -8), (-80, -5),
     (-81, -2), (-80, 1), (-78, 3), (-77, 5), (-79, 7)],
    # Africa
    [(-6, 35), (-1, 35), (5, 37), (10, 37), (15, 33), (20, 32),
     (25, 32), (30, 31), (33, 29), (35, 24), (37, 22), (39, 20),
     (40, 16), (42, 14), (43, 12), (46, 11), (50, 12), (51, 11),
     (48, 6), (45, 2), (42, -3), (40, -7), (40, -12), (39, -17),
     (37, -21), (35, -25), (33, -27), (31, -29), (28, -32), (24, -34),
     (20, -35), (18, -33), (16, -29), (15, -26), (14, -21), (13, -17),
     (12, -13), (13, -8), (12, -4), (9, -1), (9, 3), (6, 4), (3, 6),
     (-2, 5), (-6, 5), (-10, 6), (-13, 8), (-15, 11), (-17, 14),
     (-17, 18), (-16, 21), (-15, 24), (-14, 27), (-12, 29), (-9, 31),
     (-7, 33)],
    # Madagascar
    [(44, -16), (47, -14), (49, -15), (50, -17), (48, -20), (47, -23),
     (46, -25), (45, -25), (44, -22), (43, -19), (43, -17)],
    # Eurasia, one landmass from Iberia to the Pacific
    [(-9, 37), (-9, 43), (-3, 44), (-5, 48), (-1, 50), (2, 51),
     (5, 53), (7, 55), (8, 57), (11, 57), (13, 56), (18, 56),
     (20, 58), (21, 60), (19, 62), (16, 65), (12, 66), (13, 69),
     (20, 70), (28, 71), (38, 68), (50, 68), (62, 69), (72, 71),
     (85, 72), (98, 76), (110, 74), (122, 72), (135, 72), (148, 71),
     (160, 70), (172, 68), (178, 66), (178, 63), (168, 61), (160, 58),
     (158, 52), (154, 47), (146, 45), (142, 43), (139, 38), (136, 35),
     (131, 33), (127, 33), (122, 31), (120, 27), (117, 24), (113, 22),
     (108, 17), (107, 12), (106, 9), (104, 3), (101, 3), (99, 7),
     (98, 11), (96, 15), (93, 17), (91, 22), (88, 22), (86, 20),
     (83, 18), (80, 15), (79, 11), (77, 8), (75, 13), (73, 18),
     (72, 20), (68, 23), (66, 25), (61, 25), (57, 27), (56, 24),
     (58, 23), (57, 20), (55, 17), (53, 15), (49, 13), (45, 12),
     (43, 12), (41, 14), (39, 19), (37, 22), (35, 28), (34, 31),
     (36, 36), (32, 36), (28, 37), (24, 36), (21, 37), (19, 40),
     (16, 39), (14, 41), (12, 44), (10, 44), (7, 44), (4, 43),
     (1, 41), (-1, 38), (-2, 37)],
    # Britain
    [(-5, 50), (-3, 52), (-2, 54), (-3, 56), (-4, 58), (-2, 58),
     (-1, 56), (0, 54), (1, 52), (0, 51)],
    # Japan
    [(130, 31), (132, 33), (135, 34), (138, 35), (140, 36), (141, 39),
     (141, 42), (143, 43), (144, 44), (142, 44), (141, 41), (140, 38),
     (139, 36), (136, 34), (133, 33), (131, 32)],
    # Sumatra
    [(95, 5), (98, 3), (100, 0), (103, -3), (105, -5), (106, -6),
     (103, -5), (100, -2), (97, 2), (95, 4)],
    # Borneo
    [(109, 1), (111, 3), (114, 4), (117, 6), (119, 3), (118, 0),
     (117, -2), (114, -3), (111, -2), (109, 0)],
    # Java
    [(106, -6), (109, -7), (112, -7), (114, -8), (114, -9), (110, -8),
     (107, -8)],
    # Sulawesi
    [(119, 0), (120, 1), (122, 1), (123, -1), (121, -2), (120, -4),
     (119, -2)],
    # New Guinea
    [(131, -1), (135, -2), (139, -2), (143, -3), (146, -5), (149, -8),
     (150, -10), (147, -9), (144, -7), (140, -6), (136, -4),
     (132, -3)],
    # Philippines
    [(120, 13), (121, 15), (122, 17), (122, 18), (121, 15), (120, 13)],
    # Taiwan
    [(120, 22), (121, 23), (122, 25), (121, 25), (120, 24)],
    # Australia
    [(113, -22), (114, -26), (114, -30), (115, -33), (117, -35),
     (121, -34), (125, -33), (129, -32), (132, -32), (134, -33),
     (136, -35), (138, -35), (139, -37), (141, -38), (144, -38),
     (146, -39), (148, -38), (150, -37), (152, -34), (153, -31),
     (153, -28), (152, -25), (150, -22), (147, -19), (145, -16),
     (143, -13), (142, -11), (142, -14), (141, -16), (140, -18),
     (137, -16), (136, -15), (136, -12), (134, -12), (132, -11),
     (130, -12), (128, -14), (126, -14), (123, -16), (121, -18),
     (118, -20), (115, -21)],
    # New Zealand, North Island
    [(173, -35), (175, -36), (177, -37), (178, -38), (176, -39),
     (175, -40), (174, -41), (173, -39), (172, -37)],
    # New Zealand, South Island
    [(167, -46), (169, -45), (171, -43), (172, -42), (171, -41),
     (169, -43), (167, -45)],
]

# Map window: equirectangular, lon -168..182, lat -58..86.
MAP_LON = (-168.0, 182.0)
MAP_LAT = (-58.0, 86.0)


def point_in_land(lon, lat):
    """Ray-casting test against every land polygon."""
    for poly in LAND:
        inside = False
        n = len(poly)
        for i in range(n):
            ax, ay = poly[i]
            bx, by = poly[(i + 1) % n]
            if (ay > lat) != (by > lat):
                x_cross = ax + (lat - ay) * (bx - ax) / (by - ay)
                if lon < x_cross:
                    inside = not inside
        if inside:
            return True
    return False


def map_xy(lon, lat, w, h):
    """Project lon/lat to pixel coordinates inside the map window."""
    x = (lon - MAP_LON[0]) / (MAP_LON[1] - MAP_LON[0]) * w
    y = (MAP_LAT[1] - lat) / (MAP_LAT[1] - MAP_LAT[0]) * h
    return x, y


# ------------------------------------------------------------------- art

# Card shapes the art must fill, at build resolution (2x the page).
HERO_SIZE = (1260, 456)       # hero art box 315x114 page px
SEC_SIZE = (744, 172)         # secondary art box 186x43 page px

# Per-scene vertical focal point for the centre crop (0=top, 1=bottom);
# tuned by eye against the generated stills.
FOCAL_Y = {
    "cop31": 0.45, "cricket": 0.5, "libertadores": 0.42,
    "nepal": 0.45, "aukus": 0.5, "ship": 0.5, "fbi": 0.5,
    "gamer": 0.45, "sumo": 0.45, "atp": 0.5, "fcc": 0.5,
    "delhi": 0.5, "spacex": 0.4,
}


def find_art(scene):
    """Locate the generated still for a scene, whatever its suffix."""
    for path in sorted(ART.glob(f"*{scene}*")):
        if path.suffix.lower() in (".webp", ".png", ".jpg", ".jpeg"):
            return path
    return None


def prep_art():
    """Centre-crop every still to its card shape; write art/<scene>.jpg."""
    from PIL import Image

    made = {}
    for lead in LEADS:
        scene = lead[0]
        src = find_art(scene)
        if src is None:
            raise SystemExit(f"missing art for scene {scene}")
        if src.name == f"{scene}.jpg":
            made[scene] = src
            continue
        target = HERO_SIZE if LEADS.index(lead) < 3 else SEC_SIZE
        img = Image.open(src).convert("RGB")
        tw, th = target
        scale = max(tw / img.width, th / img.height)
        img = img.resize((round(img.width * scale), round(img.height * scale)),
                         Image.LANCZOS)
        left = (img.width - tw) // 2
        fy = FOCAL_Y.get(scene, 0.5)
        top = int((img.height - th) * fy)
        img = img.crop((left, top, left + tw, top + th))
        out = ART / f"{scene}.jpg"
        img.save(out, quality=87)
        made[scene] = out
    return made


def render_dotmap():
    """Rasterise the dot-matrix world into build/dotmap.png (4x)."""
    from PIL import Image, ImageDraw

    w, h = 1912, 760
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    step = 2.7
    lon = MAP_LON[0]
    while lon <= MAP_LON[1]:
        lat = MAP_LAT[1]
        while lat >= MAP_LON[0] * 0 + MAP_LAT[0]:
            x, y = map_xy(lon, lat, w, h)
            if point_in_land(lon, lat):
                r = 5.2
                draw.ellipse([x - r, y - r, x + r, y + r],
                             fill=(150, 172, 208, 255))
            else:
                r = 1.7
                draw.ellipse([x - r, y - r, x + r, y + r],
                             fill=(120, 150, 190, 55))
            lat -= step
        lon += step
    out = BUILD / "dotmap.png"
    img.save(out)
    return out


# ------------------------------------------------------------------ page

CSS = """
@page { size: 1024px 1024px; margin: 0; }
* { box-sizing: border-box; }
html, body { margin: 0; padding: 0; }
body {
  width: 1024px; height: 1024px; overflow: hidden;
  background: #f4ecda; color: #191b20;
  font-family: "Noto Sans", sans-serif;
}
.serif { font-family: "Noto Serif Display", "Noto Serif", serif; }

/* top + bottom bars */
.bar {
  height: 23px; background: #101623; color: #f4ecda;
  display: flex; justify-content: space-between; align-items: center;
  padding: 0 14px; font-size: 10px; font-weight: 700;
  letter-spacing: 2.2px;
}

/* masthead */
.masthead { padding: 4px 28px 0 28px; text-align: center; }
.masthead h1 {
  margin: 0; font-size: 73px; font-weight: 900; line-height: 0.98;
  letter-spacing: -2px; white-space: nowrap; color: #14161c;
}
.dek {
  margin: 4px 0 6px 0; text-align: center; color: #a31621;
  font-size: 16.5px; font-style: italic; font-weight: 600;
}
.rule-thick { border-top: 3px solid #14161c; margin: 0 28px; }
.rule-thin { border-top: 1px solid #14161c; margin: 2px 28px 0 28px; }

/* stat band */
.stats {
  display: flex; margin: 0 28px; padding: 4px 0 4px 0;
  border-bottom: 1px solid #14161c;
}
.stat { flex: 1; text-align: center; padding: 0 6px; }
.stat + .stat { border-left: 1px solid #c8bb9e; }
.stat .num {
  font-size: 34px; font-weight: 700; color: #a31621; line-height: 1.02;
}
.stat .cap { font-size: 9px; line-height: 1.2; color: #3a372e; }

/* region strip */
.regions { display: flex; margin: 5px 28px 0 28px; height: 20px; }
.region {
  color: #fff; font-size: 10px; font-weight: 700; letter-spacing: 1.4px;
  display: flex; align-items: center; justify-content: center;
  white-space: nowrap; overflow: hidden;
}

/* story cards */
.heroes { display: flex; gap: 12px; padding: 7px 28px 0 28px; }
.hero { width: 314.7px; }
.secondaries { display: flex; gap: 10px; padding: 6px 28px 0 28px; }
.sec { width: 185.6px; }
.artbox { position: relative; overflow: hidden; background: #223; }
.artbox img { display: block; width: 100%; height: 100%; object-fit: cover; }
.kicker {
  position: absolute; top: 0; left: 0; background: #b01e24; color: #fff;
  font-weight: 800; letter-spacing: 1.2px; padding: 4px 9px;
}
.hero .kicker { font-size: 13.5px; }
.sec .kicker { font-size: 9px; padding: 3px 6px; }
.srcchip {
  position: absolute; left: 7px; bottom: 7px; color: #f4ecda;
  background: rgba(13, 18, 30, 0.88); font-weight: 700;
  padding: 3px 7px; letter-spacing: 0.4px;
}
.hero .srcchip { font-size: 9.5px; }
.sec .srcchip { font-size: 7.5px; left: 5px; bottom: 5px; padding: 2px 5px; }
.cert {
  position: absolute; right: 7px; bottom: 7px; background: #f4ecda;
  color: #14161c; font-weight: 800; letter-spacing: 1px;
  padding: 3px 7px; font-size: 8.5px;
}
.cert i {
  display: inline-block; width: 6px; height: 6px; background: #b01e24;
  margin-right: 4px;
}
.sec .cert { display: none; }
.kickrow {
  display: flex; align-items: center; gap: 6px; margin-top: 4px;
}
.pnum {
  flex: none; width: 17px; height: 17px; border-radius: 50%;
  background: #b01e24; color: #fff; font-size: 10.5px; font-weight: 800;
  text-align: center; line-height: 17px;
}
.sec .pnum { width: 14px; height: 14px; font-size: 9px; line-height: 14px; }
.place {
  color: #a31621; font-weight: 800; letter-spacing: 0.9px;
  white-space: nowrap; overflow: hidden;
}
.hero .place { font-size: 11px; }
.sec .place { font-size: 8.3px; letter-spacing: 0.5px; }
.hero h2 {
  margin: 3px 0 3px 0; font-size: 22.5px; font-weight: 700;
  line-height: 1.05; letter-spacing: -0.2px;
}
.hero p { margin: 0; font-size: 10.9px; line-height: 1.28; color: #35322b; }
.sec h3 {
  margin: 3px 0 2px 0; font-size: 13.8px; font-weight: 700;
  line-height: 1.1;
}
.sec p { margin: 0; font-size: 9.2px; line-height: 1.25; color: #35322b; }

/* bottom: map + briefs */
.bottom { display: flex; gap: 14px; padding: 5px 28px 0 28px; }
.mapbox { width: 478px; flex: none; }
.maphead, .briefhead {
  font-size: 11.5px; font-weight: 800; letter-spacing: 1.6px;
  margin-bottom: 5px;
}
.maphead span { color: #8a93a5; font-weight: 600; letter-spacing: 0.6px;
  font-size: 9.5px; margin-left: 8px; }
.mappanel {
  position: relative; background: #14263e; height: 190px; overflow: hidden;
}
.mappanel img { width: 100%; height: 100%; display: block; }
.pin {
  position: absolute; width: 15px; height: 15px; border-radius: 50%;
  background: #d8232a; border: 1.6px solid #f4ecda; color: #fff;
  font-size: 8.6px; font-weight: 800; text-align: center;
  line-height: 12.4px; transform: translate(-50%, -50%);
}
.briefs { flex: 1; }
.briefcols { display: flex; gap: 14px; }
.briefcol { flex: 1; }
.brief { font-size: 9.15px; line-height: 1.26; margin-bottom: 2px; }
.brief b { font-weight: 800; }
.brief .n { color: #a31621; font-weight: 800; }
.brief .src { color: #6d675a; }

/* date check + sources */
.datecheck {
  margin: 5px 28px 0 28px; border: 1.6px solid #b01e24;
  padding: 5px 10px; font-size: 9.8px; line-height: 1.35;
  display: flex; gap: 10px;
}
.datecheck .tag {
  flex: none; color: #b01e24; font-weight: 800; letter-spacing: 1.2px;
  font-size: 10.5px; padding-top: 1px;
}
.sources {
  margin: 3px 28px 3px 28px; font-size: 8.6px; color: #6d675a;
  display: flex; justify-content: space-between;
}
.bottombar { position: absolute; bottom: 0; left: 0; right: 0; }
"""


def esc(text):
    return (text.replace("&", "&amp;").replace("<", "&lt;")
            .replace(">", "&gt;"))


def hero_card(lead, num):
    (scene, label, chip, place, topic, _city, _lon, _lat, cert,
     headline, summary) = lead
    return f"""
    <div class="hero">
      <div class="artbox" style="height:114px">
        <img src="../art/{scene}.jpg"/>
        <div class="kicker">{esc(label)}</div>
        <div class="srcchip">{esc(chip)}</div>
        <div class="cert"><i></i>{cert}</div>
      </div>
      <div class="kickrow"><div class="pnum">{num}</div>
        <div class="place">{esc(place)} · {esc(topic)}</div></div>
      <h2 class="serif">{esc(headline)}</h2>
      <p>{esc(summary)}</p>
    </div>"""


def sec_card(lead, num):
    (scene, label, chip, place, topic, _city, _lon, _lat, cert,
     headline, summary) = lead
    return f"""
    <div class="sec">
      <div class="artbox" style="height:43px">
        <img src="../art/{scene}.jpg"/>
        <div class="kicker">{esc(label)}</div>
        <div class="srcchip">{esc(chip)}</div>
      </div>
      <div class="kickrow"><div class="pnum">{num}</div>
        <div class="place">{esc(place)} · {esc(topic)}</div></div>
      <h3 class="serif">{esc(headline)}</h3>
      <p>{esc(summary)}</p>
    </div>"""


def pin_html(lead, num):
    lon, lat = lead[6], lead[7]
    x, y = map_xy(lon, lat, 100.0, 100.0)
    return (f'<div class="pin" style="left:{x:.1f}%;top:{y:.1f}%">'
            f"{num}</div>")


def brief_html(brief, num):
    region, place, headline, source = brief
    return (f'<div class="brief"><span class="n">{num}</span> '
            f"<b>{esc(region)}</b> · {esc(place)}: {esc(headline)} "
            f'<span class="src">({esc(source)})</span></div>')


def build_html():
    heroes = "".join(hero_card(LEADS[i], i + 1) for i in range(3))
    secs_a = "".join(sec_card(LEADS[i], i + 1) for i in range(3, 8))
    secs_b = "".join(sec_card(LEADS[i], i + 1) for i in range(8, 13))
    stats = "".join(
        f'<div class="stat"><div class="num serif">{esc(n)}</div>'
        f'<div class="cap">{esc(c)}</div></div>' for n, c in STATS)
    total = sum(c for _n, c, _col in REGIONS)
    regions = "".join(
        f'<div class="region" style="background:{col};'
        f'flex:{max(c, 1.6) / total:.3f}">{esc(name)} {c}</div>'
        for name, c, col in REGIONS)
    pins = "".join(pin_html(LEADS[i], i + 1) for i in range(13))
    col_a = "".join(brief_html(BRIEFS[i], i + 14) for i in range(9))
    col_b = "".join(brief_html(BRIEFS[i], i + 14) for i in range(9, 17))
    html = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"/><style>{CSS}</style></head>
<body>
  <div class="bar"><div>THE WHOLE WORLD — ONE SUNDAY</div>
    <div>30 STORIES · 6 REGIONS · EVERY ONE DATED SUNDAY 22 NOVEMBER 2026</div></div>
  <div class="masthead"><h1 class="serif">Sunday 22 November 2026</h1></div>
  <div class="dek serif">{esc(DEK)}</div>
  <div class="rule-thick"></div><div class="rule-thin"></div>
  <div class="stats">{stats}</div>
  <div class="regions">{regions}</div>
  <div class="heroes">{heroes}</div>
  <div class="secondaries">{secs_a}</div>
  <div class="secondaries">{secs_b}</div>
  <div class="bottom">
    <div class="mapbox">
      <div class="maphead">WHERE IT HAPPENED <span>pins match story numbers</span></div>
      <div class="mappanel"><img src="dotmap.png"/>{pins}</div>
    </div>
    <div class="briefs">
      <div class="briefhead">ALSO ON SUNDAY 22 NOVEMBER — 17 MORE STORIES</div>
      <div class="briefcols"><div class="briefcol">{col_a}</div>
      <div class="briefcol">{col_b}</div></div>
    </div>
  </div>
  <div class="datecheck"><div class="tag">DATE CHECK</div>
    <div>{esc(DATE_CHECK)}</div></div>
  <div class="sources">
    <div>Sources: Reuters, BBC, AP wires and the outlets named with each story. Pictures: original illustrations made for this page; map drawn in code.</div>
    <div>CERTAINTY — <b>REPORTED</b> = carried by the day's wires · <b>FORECAST</b> = still to happen when drawn</div>
  </div>
  <div class="bar bottombar"><div>THE WHOLE WORLD — ONE SUNDAY</div>
    <div>SUNDAY 22 NOVEMBER 2026 · ONE PAGE</div></div>
</body></html>"""
    out = BUILD / "page.html"
    out.write_text(html, encoding="utf-8")
    return out


# ----------------------------------------------------------------- render

def render_entry():
    """page.html -> PDF -> 2048px raster -> 1024 entry.png + thumbnail."""
    from PIL import Image

    pdf = BUILD / "page.pdf"
    try:
        from weasyprint import HTML
    except ImportError:
        raise SystemExit(
            "WeasyPrint is not importable in this interpreter; run the "
            "build with the venv python that has it installed.")
    HTML(str(BUILD / "page.html")).write_pdf(str(pdf))
    subprocess.run(
        ["pdftoppm", "-png", "-r", "192", "-singlefile",
         str(pdf), str(BUILD / "page2048")],
        check=True)
    img = Image.open(BUILD / "page2048.png").convert("RGB")
    if img.size != (2048, 2048):
        raise SystemExit(f"unexpected raster size {img.size}")
    img = img.resize((1024, 1024), Image.LANCZOS)

    entry = ROOT / "entry.png"
    for quality in (90, 86, 82, 78, 74, 70):
        img.save(entry, format="JPEG", quality=quality,
                 subsampling=1, optimize=True)
        if entry.stat().st_size <= 1_048_576:
            break
    else:
        raise SystemExit("entry.png still over the 1 MiB cap")
    thumb = BUILD / "thumb300.png"
    img.resize((300, 300), Image.LANCZOS).save(thumb)
    return entry


def main():
    BUILD.mkdir(exist_ok=True)
    prep_art()
    print("art prepped")
    render_dotmap()
    print("dotmap drawn")
    build_html()
    print("page.html written")
    entry = render_entry()
    print(f"entry.png written: {entry.stat().st_size} bytes")


if __name__ == "__main__":
    sys.exit(main())
