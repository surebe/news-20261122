"""Sunday 22 November 2026 — the whole world of one day, on one page.

Written for the make.fun competition news-image-20261122. The program
runs on the Python 3 standard library alone: the PNG encoder, the
drawing canvas and the TrueType text renderer below are all
implemented here, and the only data files read are the small subset
fonts in fonts/ (Noto and DejaVu, openly licensed, subsetted with the
build-time tool in tools/make_fonts.py).

Every story on the page happened, or was first reported, on Sunday
22 November 2026, and was checked against the dated wire or official
source named beside it. Everything is fixed: no clock, no randomness,
no network. Two runs write byte-identical files.
"""

import math
import os
import struct
import sys
import zlib

# ---------------------------------------------------------------- PNG


def _chunk(tag, payload):
    return (
        struct.pack(">I", len(payload))
        + tag
        + payload
        + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF)
    )


def encode_png(width, height, rgb):
    """rgb is a bytearray of width*height*3 bytes. Every row uses the
    Sub filter, which suits the flat colour spans of a drawn page and
    keeps the encoding deterministic."""
    stride = width * 3
    raw = bytearray()
    for y in range(height):
        row = rgb[y * stride:(y + 1) * stride]
        filt = bytearray(stride)
        for i, b in enumerate(row):
            left = row[i - 3] if i >= 3 else 0
            filt[i] = (b - left) & 0xFF
        raw.append(1)
        raw += filt
    ihdr = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + _chunk(b"IHDR", ihdr)
        + _chunk(b"IDAT", zlib.compress(bytes(raw), 9))
        + _chunk(b"IEND", b"")
    )


# ---------------------------------------------------------------- canvas


class Canvas:
    """An RGB pixel buffer with the small set of drawing primitives
    the newspaper needs. Coordinates are integer pixels, y grows
    downward. A clip rectangle can be set so scene painters stay
    inside their box."""

    def __init__(self, width, height, bg):
        self.w = width
        self.h = height
        self.px = bytearray(width * height * 3)
        self.clip = (0, 0, width, height)
        self.fill_rect(0, 0, width, height, bg)

    # -- low level ------------------------------------------------

    def set_clip(self, x, y, w, h):
        self.clip = (x, y, x + w, y + h)

    def clear_clip(self):
        self.clip = (0, 0, self.w, self.h)

    def _clip_box(self, x, y, w, h):
        cx0, cy0, cx1, cy1 = self.clip
        x0 = max(x, cx0, 0)
        y0 = max(y, cy0, 0)
        x1 = min(x + w, cx1, self.w)
        y1 = min(y + h, cy1, self.h)
        return x0, y0, x1, y1

    def set_px(self, x, y, color):
        cx0, cy0, cx1, cy1 = self.clip
        if cx0 <= x < cx1 and cy0 <= y < cy1 and 0 <= x < self.w and 0 <= y < self.h:
            i = (y * self.w + x) * 3
            self.px[i] = color[0]
            self.px[i + 1] = color[1]
            self.px[i + 2] = color[2]

    def blend_px(self, x, y, color, alpha):
        if alpha <= 0:
            return
        if alpha >= 255:
            self.set_px(x, y, color)
            return
        cx0, cy0, cx1, cy1 = self.clip
        if not (cx0 <= x < cx1 and cy0 <= y < cy1 and 0 <= x < self.w and 0 <= y < self.h):
            return
        i = (y * self.w + x) * 3
        inv = 255 - alpha
        self.px[i] = (self.px[i] * inv + color[0] * alpha) // 255
        self.px[i + 1] = (self.px[i + 1] * inv + color[1] * alpha) // 255
        self.px[i + 2] = (self.px[i + 2] * inv + color[2] * alpha) // 255

    # -- shapes ---------------------------------------------------

    def fill_rect(self, x, y, w, h, color):
        x0, y0, x1, y1 = self._clip_box(int(x), int(y), int(w), int(h))
        if x1 <= x0 or y1 <= y0:
            return
        row = bytes(color) * (x1 - x0)
        n = (x1 - x0) * 3
        for yy in range(y0, y1):
            i = (yy * self.w + x0) * 3
            self.px[i:i + n] = row

    def frame_rect(self, x, y, w, h, color, t=1):
        self.fill_rect(x, y, w, t, color)
        self.fill_rect(x, y + h - t, w, t, color)
        self.fill_rect(x, y, t, h, color)
        self.fill_rect(x + w - t, y, t, h, color)

    def fill_polygon(self, points, color):
        """Even-odd scanline fill of a polygon given as (x, y) floats."""
        if len(points) < 3:
            return
        ys = [p[1] for p in points]
        y0 = max(int(math.floor(min(ys))), self.clip[1], 0)
        y1 = min(int(math.ceil(max(ys))), self.clip[3], self.h)
        n = len(points)
        edges = []
        for i in range(n):
            ax, ay = points[i]
            bx, by = points[(i + 1) % n]
            if ay != by:
                edges.append((ax, ay, bx, by))
        for yy in range(y0, y1):
            yc = yy + 0.5
            xs = []
            for ax, ay, bx, by in edges:
                if (ay <= yc < by) or (by <= yc < ay):
                    xs.append(ax + (yc - ay) * (bx - ax) / (by - ay))
            xs.sort()
            for k in range(0, len(xs) - 1, 2):
                xa = int(math.ceil(xs[k] - 0.5))
                xb = int(math.floor(xs[k + 1] - 0.5))
                if xb >= xa:
                    self.fill_rect(xa, yy, xb - xa + 1, 1, color)

    def fill_ellipse(self, cx, cy, rx, ry, color):
        if rx <= 0 or ry <= 0:
            return
        y0 = max(int(math.floor(cy - ry)), self.clip[1], 0)
        y1 = min(int(math.ceil(cy + ry)), self.clip[3], self.h)
        for yy in range(y0, y1):
            dy = (yy + 0.5 - cy) / ry
            if abs(dy) >= 1:
                continue
            dx = rx * math.sqrt(1.0 - dy * dy)
            xa = int(math.ceil(cx - dx - 0.5))
            xb = int(math.floor(cx + dx - 0.5))
            if xb >= xa:
                self.fill_rect(xa, yy, xb - xa + 1, 1, color)

    def fill_circle(self, cx, cy, r, color):
        self.fill_ellipse(cx, cy, r, r, color)

    def thick_line(self, x0, y0, x1, y1, width, color):
        """A line drawn by stamping filled circles along its length,
        so it has round caps and an even weight."""
        dist = math.hypot(x1 - x0, y1 - y0)
        steps = max(1, int(dist / max(1.0, width * 0.35)))
        r = width / 2.0
        for i in range(steps + 1):
            t = i / steps
            self.fill_circle(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t, r, color)

    def polyline(self, points, width, color, close=False):
        pts = list(points)
        if close and len(pts) > 2:
            pts.append(pts[0])
        for i in range(len(pts) - 1):
            self.thick_line(pts[i][0], pts[i][1], pts[i + 1][0], pts[i + 1][1],
                            width, color)

    def dashed_line(self, x0, y0, x1, y1, width, color, dash=5, gap=4):
        dist = math.hypot(x1 - x0, y1 - y0)
        if dist == 0:
            return
        ux = (x1 - x0) / dist
        uy = (y1 - y0) / dist
        pos = 0.0
        while pos < dist:
            end = min(pos + dash, dist)
            self.thick_line(x0 + ux * pos, y0 + uy * pos,
                            x0 + ux * end, y0 + uy * end, width, color)
            pos = end + gap


# ---------------------------------------------------------------- fonts


def _u16(data, off):
    return struct.unpack_from(">H", data, off)[0]


def _i16(data, off):
    return struct.unpack_from(">h", data, off)[0]


def _u32(data, off):
    return struct.unpack_from(">I", data, off)[0]


class Font:
    """A minimal TrueType reader: cmap format 4, glyf outlines
    (simple and composite), hmtx advances. Outlines are flattened to
    polygons and rasterised with 3x3 supersampling for smooth type.
    Text may be drawn with extra letter tracking (in pixels) for the
    letterspaced caps of kickers and labels."""

    SS = 3

    def __init__(self, path):
        with open(path, "rb") as fh:
            self.data = fh.read()
        data = self.data
        self.tables = {}
        count = _u16(data, 4)
        for i in range(count):
            off = 12 + i * 16
            tag = data[off:off + 4].decode("latin-1")
            self.tables[tag] = (_u32(data, off + 8), _u32(data, off + 12))
        head = self.tables["head"][0]
        self.upem = _u16(data, head + 18)
        self.loc_format = _i16(data, head + 50)
        self.num_glyphs = _u16(data, self.tables["maxp"][0] + 4)
        hhea = self.tables["hhea"][0]
        self.num_hmtx = _u16(data, hhea + 34)
        self._cmap = self._read_cmap()
        self._loca = self._read_loca()
        self._mask_cache = {}

    # -- tables ---------------------------------------------------

    def _read_cmap(self):
        base = self.tables["cmap"][0]
        subs = _u16(self.data, base + 2)
        chosen = None
        for i in range(subs):
            off = base + 4 + i * 8
            platform = _u16(self.data, off)
            sub_off = _u32(self.data, off + 4)
            fmt = _u16(self.data, base + sub_off)
            if fmt == 4 and platform in (3, 0):
                chosen = base + sub_off
                if platform == 3:
                    break
        if chosen is None:
            raise ValueError("no cmap format 4 subtable")
        d = self.data
        seg_count = _u16(d, chosen + 6) // 2
        end_off = chosen + 14
        start_off = end_off + 2 * seg_count + 2
        delta_off = start_off + 2 * seg_count
        range_off = delta_off + 2 * seg_count
        segments = []
        for i in range(seg_count):
            segments.append((
                _u16(d, start_off + 2 * i),
                _u16(d, end_off + 2 * i),
                _i16(d, delta_off + 2 * i),
                _u16(d, range_off + 2 * i),
                range_off + 2 * i,
            ))
        return segments

    def glyph_id(self, codepoint):
        for start, end, delta, roff, roff_addr in self._cmap:
            if start <= codepoint <= end:
                if roff == 0:
                    return (codepoint + delta) % 65536
                addr = roff_addr + roff + 2 * (codepoint - start)
                gid = _u16(self.data, addr)
                if gid:
                    gid = (gid + delta) % 65536
                return gid
        return 0

    def _read_loca(self):
        base, _ = self.tables["loca"]
        out = []
        if self.loc_format == 0:
            for i in range(self.num_glyphs + 1):
                out.append(_u16(self.data, base + 2 * i) * 2)
        else:
            for i in range(self.num_glyphs + 1):
                out.append(_u32(self.data, base + 4 * i))
        return out

    def advance(self, gid, scale):
        base = self.tables["hmtx"][0]
        if gid >= self.num_hmtx:
            gid = self.num_hmtx - 1
        return _u16(self.data, base + 4 * gid) * scale

    # -- outlines ---------------------------------------------------

    def _glyph_contours(self, gid, depth=0):
        """Returns a list of contours; each contour is a list of
        (x, y, on_curve) in font units."""
        if depth > 4 or gid >= self.num_glyphs:
            return []
        start = self._loca[gid]
        end = self._loca[gid + 1]
        if start == end:
            return []
        base = self.tables["glyf"][0] + start
        d = self.data
        contours = _i16(d, base)
        if contours >= 0:
            return self._simple_contours(base, contours)
        # composite glyph
        out = []
        off = base + 10
        while True:
            flags = _u16(d, off)
            comp_gid = _u16(d, off + 2)
            off += 4
            if flags & 0x0001:
                arg1 = _i16(d, off)
                arg2 = _i16(d, off + 2)
                off += 4
            else:
                arg1 = struct.unpack_from(">b", d, off)[0]
                arg2 = struct.unpack_from(">b", d, off + 1)[0]
                off += 2
            if not (flags & 0x0002):
                arg1 = 0
                arg2 = 0
            sx = 1.0
            sy = 1.0
            if flags & 0x0008:
                sx = sy = _i16(d, off) / 16384.0
                off += 2
            elif flags & 0x0040:
                sx = _i16(d, off) / 16384.0
                sy = _i16(d, off + 2) / 16384.0
                off += 4
            elif flags & 0x0080:
                off += 8
            for contour in self._glyph_contours(comp_gid, depth + 1):
                out.append([
                    (x * sx + arg1, y * sy + arg2, on) for (x, y, on) in contour
                ])
            if not (flags & 0x0020):
                break
        return out

    def _simple_contours(self, base, count):
        d = self.data
        off = base + 10
        ends = []
        for i in range(count):
            ends.append(_u16(d, off + 2 * i))
        off += 2 * count
        off += 2 + _u16(d, off)  # skip instructions
        total = ends[-1] + 1 if ends else 0
        flags = []
        while len(flags) < total:
            flag = d[off]
            off += 1
            flags.append(flag)
            if flag & 0x08:
                rep = d[off]
                off += 1
                flags.extend([flag] * rep)
        xs = []
        x = 0
        for flag in flags:
            if flag & 0x02:
                step = d[off]
                off += 1
                x += step if (flag & 0x10) else -step
            elif not (flag & 0x10):
                x += _i16(d, off)
                off += 2
            xs.append(x)
        ys = []
        y = 0
        for flag in flags:
            if flag & 0x04:
                step = d[off]
                off += 1
                y += step if (flag & 0x20) else -step
            elif not (flag & 0x20):
                y += _i16(d, off)
                off += 2
            ys.append(y)
        contours = []
        start = 0
        for end in ends:
            contour = []
            for i in range(start, end + 1):
                contour.append((xs[i], ys[i], bool(flags[i] & 0x01)))
            contours.append(contour)
            start = end + 1
        return contours

    # -- rasterising ------------------------------------------------

    def _flatten(self, contour, scale):
        """Turn one contour of on/off-curve points into a polygon in
        device pixels (y down)."""
        pts = [(x * scale, -y * scale, on) for (x, y, on) in contour]
        if not pts:
            return []
        if pts[0][2]:
            start = pts[0]
            rest = pts[1:] + [pts[0]]
        elif pts[-1][2]:
            start = pts[-1]
            rest = pts[:-1] + [pts[-1]]
        else:
            start = (
                (pts[0][0] + pts[-1][0]) / 2.0,
                (pts[0][1] + pts[-1][1]) / 2.0,
                True,
            )
            rest = pts + [start]
        out = [(start[0], start[1])]
        cur = start
        i = 0
        while i < len(rest):
            p = rest[i]
            if p[2]:
                out.append((p[0], p[1]))
                cur = p
                i += 1
            else:
                if i + 1 < len(rest):
                    nxt = rest[i + 1]
                else:
                    nxt = start
                if nxt[2]:
                    end = nxt
                    i += 2
                else:
                    end = ((p[0] + nxt[0]) / 2.0, (p[1] + nxt[1]) / 2.0, True)
                    i += 1
                self._quad(out, cur, p, end)
                cur = end
        return out

    def _quad(self, out, p0, p1, p2):
        """Recursively flatten a quadratic Bezier into out."""
        stack = [(p0[0], p0[1], p1[0], p1[1], p2[0], p2[1], 0)]
        while stack:
            x0, y0, x1, y1, x2, y2, depth = stack.pop()
            dx = x2 - x0
            dy = y2 - y0
            chord = math.hypot(dx, dy)
            if chord == 0:
                dist = math.hypot(x1 - x0, y1 - y0)
            else:
                dist = abs((x1 - x0) * dy - (y1 - y0) * dx) / chord
            if dist < 0.3 or depth >= 6:
                out.append((x2, y2))
            else:
                mx01 = (x0 + x1) / 2.0
                my01 = (y0 + y1) / 2.0
                mx12 = (x1 + x2) / 2.0
                my12 = (y1 + y2) / 2.0
                mx = (mx01 + mx12) / 2.0
                my = (my01 + my12) / 2.0
                stack.append((mx, my, mx12, my12, x2, y2, depth + 1))
                stack.append((x0, y0, mx01, my01, mx, my, depth + 1))

    def glyph_mask(self, codepoint, size):
        """(mask, w, h, xoff, yoff, advance_px): mask is a bytearray of
        alpha values; drawing position is pen + (xoff, yoff) where the
        pen sits on the baseline."""
        key = (codepoint, int(size * 4))
        if key in self._mask_cache:
            return self._mask_cache[key]
        scale = size / self.upem
        gid = self.glyph_id(codepoint)
        adv = self.advance(gid, scale)
        contours = self._glyph_contours(gid)
        polys = []
        for contour in contours:
            poly = self._flatten(contour, scale)
            if len(poly) >= 3:
                polys.append(poly)
        if not polys:
            result = (bytearray(), 0, 0, 0, 0, adv)
            self._mask_cache[key] = result
            return result
        xs = [p[0] for poly in polys for p in poly]
        ys = [p[1] for poly in polys for p in poly]
        x0 = int(math.floor(min(xs)))
        y0 = int(math.floor(min(ys)))
        x1 = int(math.ceil(max(xs)))
        y1 = int(math.ceil(max(ys)))
        w = x1 - x0
        h = y1 - y0
        ss = self.SS
        sub = bytearray(w * ss * h * ss)
        edges = []
        for poly in polys:
            for i in range(len(poly)):
                ax, ay = poly[i]
                bx, by = poly[(i + 1) % len(poly)]
                if ay != by:
                    edges.append((ax - x0, ay - y0, bx - x0, by - y0))
        for yy in range(h * ss):
            yc = (yy + 0.5) / ss
            hits = []
            for ax, ay, bx, by in edges:
                if (ay <= yc < by) or (by <= yc < ay):
                    hits.append(ax + (yc - ay) * (bx - ax) / (by - ay))
            hits.sort()
            for k in range(0, len(hits) - 1, 2):
                xa = int(math.ceil(hits[k] * ss - 0.5))
                xb = int(math.floor(hits[k + 1] * ss - 0.5))
                if xb >= xa:
                    base = yy * w * ss
                    for xx in range(max(xa, 0), min(xb, w * ss - 1) + 1):
                        sub[base + xx] = 255
        mask = bytearray(w * h)
        block = ss * ss
        for yy in range(h):
            for xx in range(w):
                total = 0
                for sy in range(ss):
                    row = (yy * ss + sy) * w * ss + xx * ss
                    for sx in range(ss):
                        total += sub[row + sx]
                mask[yy * w + xx] = total // block
        result = (mask, w, h, x0, y0, adv)
        self._mask_cache[key] = result
        return result

    # -- text -------------------------------------------------------

    def text_width(self, text, size, tracking=0.0):
        scale = size / self.upem
        total = 0.0
        for ch in text:
            total += self.advance(self.glyph_id(ord(ch)), scale)
        if tracking and len(text) > 1:
            total += tracking * (len(text) - 1)
        return total

    def draw_text(self, canvas, x, y_baseline, text, size, color, tracking=0.0):
        pen = float(x)
        last = len(text) - 1
        for i, ch in enumerate(text):
            mask, w, h, xoff, yoff, adv = self.glyph_mask(ord(ch), size)
            if w and h:
                bx = int(round(pen)) + xoff
                by = int(round(y_baseline)) + yoff
                for yy in range(h):
                    row = yy * w
                    for xx in range(w):
                        a = mask[row + xx]
                        if a:
                            canvas.blend_px(bx + xx, by + yy, color, a)
            pen += adv
            if tracking and i < last:
                pen += tracking
        return pen


def wrap_text(font, text, size, width, tracking=0.0):
    """Greedy word wrap. Returns the list of lines; a line is never
    wider than width unless it is a single word that cannot split."""
    words = text.split()
    lines = []
    cur = ""
    for word in words:
        trial = (cur + " " + word) if cur else word
        if font.text_width(trial, size, tracking) <= width or not cur:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def fit_text(font, text, width, max_lines, sizes, tracking=0.0):
    """Try the given sizes from largest down; return (size, lines) for
    the first that wraps into at most max_lines lines, or raise."""
    for size in sizes:
        lines = wrap_text(font, text, size, width, tracking)
        if len(lines) <= max_lines:
            too_wide = [ln for ln in lines
                        if font.text_width(ln, size, tracking) > width + 0.5]
            if not too_wide:
                return size, lines
    raise ValueError("text does not fit: %r" % (text[:60],))

# ---------------------------------------------------------------- palette
#
# The champions' system, measured from their pages: warm paper, warm
# ink, one red. Scene darks are warm plum or navy, used sparingly.

PAPER = (247, 242, 230)        # #F7F2E6
CARD = (253, 251, 244)
INK = (42, 35, 32)             # #2A2320
MUTED = (110, 100, 86)
RULE = (196, 186, 162)
RED = (193, 39, 45)            # #C1272D
WHITE = (255, 255, 255)
MAP_BG = (29, 42, 74)          # #1D2A4A
MAP_LAND = (217, 201, 163)     # #D9C9A3
PLUM = (51, 34, 46)            # #33222E
NAVY = (30, 42, 56)            # #1E2A38

REGION_COLORS = {
    "North America": (108, 79, 161),
    "Latin America": (87, 64, 127),
    "Europe": (46, 95, 163),
    "Africa": (62, 124, 79),
    "Asia": (200, 135, 26),
    "Oceania": (46, 140, 140),
}

# ---------------------------------------------------------------- data
#
# Every story below happened, or was first reported, on Sunday
# 22 November 2026, checked against the dated wire or official source
# named in its credit. Headlines and summaries are written for this
# page. The first three leads are the heroes of the top row; leads
# 4-13 are the card rows; the briefs are numbered on from 14.

LEADS = [
    {
        "region": "Europe", "scene": "cop31", "label": "TALKS RUN ON",
        "chip": "Reuters", "place": "ANTALYA, TÜRKIYE", "topic": "CLIMATE TALKS",
        "city": "Antalya", "lon": 30.7, "lat": 36.9,
        "headline": "Climate talks run past deadline in Antalya",
        "summary": "Nearly 200 delegations negotiated into Sunday, a day "
                   "past the deadline, over a draft to lift electricity's "
                   "share of energy to 35% by 2035. (Reuters)",
    },
    {
        "region": "Oceania", "scene": "cricket", "label": "RECORD 629-6",
        "chip": "Reuters", "place": "WELLINGTON, NEW ZEALAND", "topic": "CRICKET",
        "city": "Wellington", "lon": 174.5, "lat": -40.4,
        "headline": "Pant's century powers a record 629-6",
        "summary": "Pant's sizzling century took India to 629-6 at lunch "
                   "on day four — their highest Test total in New "
                   "Zealand, with a lead of 261. (Reuters)",
    },
    {
        "region": "Latin America", "scene": "libertadores", "label": "THE FINAL",
        "chip": "Xinhua", "place": "MONTEVIDEO, URUGUAY", "topic": "FOOTBALL",
        "city": "Montevideo", "lon": -56.2, "lat": -34.9,
        "headline": "Palmeiras face Estudiantes in the final",
        "summary": "Palmeiras meet Estudiantes in South America's "
                   "biggest club match, at the stadium that hosted the "
                   "first World Cup final. (Xinhua)",
    },
    {
        "region": "Asia", "scene": "nepal", "label": "FIRST VISIT",
        "chip": "Radio Nepal", "place": "KATHMANDU, NEPAL", "topic": "VISIT",
        "city": "Kathmandu", "lon": 85.3, "lat": 27.7,
        "headline": "Nepal's PM flies to India on first visit",
        "summary": "Shah leads 34 envoys to New Delhi.",
    },
    {
        "region": "Oceania", "scene": "aukus", "label": "SUB ROW",
        "chip": "Reuters", "place": "SYDNEY, AUSTRALIA", "topic": "AUKUS",
        "city": "Sydney", "lon": 151.2, "lat": -33.9,
        "headline": "Australia rebukes US over AUKUS warning",
        "summary": "'They are wrong,' Marles said Sunday.",
    },
    {
        "region": "Europe", "scene": "ship", "label": "SHIP HIT",
        "chip": "BBC", "place": "GULF OF FINLAND", "topic": "SHIP HIT",
        "city": "Helsinki", "lon": 24.9, "lat": 60.2,
        "headline": "Russia-bound ship hit by drones in Gulf",
        "summary": "Helsinki blames a Ukrainian strike.",
    },
    {
        "region": "North America", "scene": "fbi", "label": "FBI PROBE",
        "chip": "BBC", "place": "WASHINGTON, US", "topic": "CYBER",
        "city": "Washington", "lon": -77.0, "lat": 38.9,
        "headline": "FBI probes apparent hack of crime database",
        "summary": "Police database NCIC is the target.",
    },
    {
        "region": "North America", "scene": "gamer", "label": "GAMER'S TIP",
        "chip": "BBC", "place": "UNITED STATES", "topic": "RESCUE",
        "city": "United States", "lon": -98.5, "lat": 39.5,
        "headline": "Teen gamer's tip helps rescue missing girl",
        "summary": "He spotted her from an FBI alert.",
    },
    {
        "region": "Asia", "scene": "sumo", "label": "ONOSATO WINS",
        "chip": "JSA", "place": "FUKUOKA, JAPAN", "topic": "SUMO",
        "city": "Fukuoka", "lon": 130.4, "lat": 33.6,
        "headline": "Onosato wins the Cup in a playoff",
        "summary": "A playoff win over Wakamotoharu.",
    },
    {
        "region": "Europe", "scene": "atp", "label": "TITLE MATCH",
        "chip": "ATP", "place": "TURIN, ITALY", "topic": "TENNIS",
        "city": "Turin", "lon": 7.7, "lat": 45.1,
        "headline": "Alcaraz and Zverev meet in Turin final",
        "summary": "A new champion is certain in Turin.",
    },
    {
        "region": "Asia", "scene": "fcc", "label": "PHONE ROW",
        "chip": "Reuters", "place": "BEIJING, CHINA", "topic": "PHONES",
        "city": "Beijing", "lon": 116.4, "lat": 39.9,
        "headline": "China opposes US ban on its phone firms",
        "summary": "Commerce ministry spoke on Sunday.",
    },
    {
        "region": "Asia", "scene": "delhi", "label": "AQI 278",
        "chip": "Hindustan Times", "place": "NEW DELHI, INDIA", "topic": "SMOG",
        "city": "New Delhi", "lon": 77.2, "lat": 28.6,
        "headline": "Delhi air stays 'very poor' on Sunday",
        "summary": "AQI hit 278 on Sunday morning.",
    },
    {
        "region": "North America", "scene": "spacex", "label": "SPY SATS",
        "chip": "Vandenberg SFB", "place": "VANDENBERG, US", "topic": "SPACE",
        "city": "Vandenberg", "lon": -120.6, "lat": 34.6,
        "headline": "SpaceX to launch spy satellites Sunday",
        "summary": "NROL-136 lifts off at 12:23 UTC.",
    },
]

# One-line briefs: (region, place, headline, source). Numbered 14 up.
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

# The day in numbers: (numeral, caption). Every figure is drawn from
# a story on this page and attributed there.
STATS = [
    ("~200", "delegations still negotiating at COP31"),
    ("629-6", "India's record Test total in New Zealand"),
    ("35%", "electricity's target share of world energy, 2035"),
    ("34", "members of Nepal PM's delegation to India"),
    ("$2.41m", "prize for the ATP Finals winner"),
    ("$4,000", "paid for a lock of Washington's hair"),
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
#
# Simplified continent outlines, hand-coded as (lon, lat) polygons.
# The pin of every displayed story is tested against these polygons
# at build time: a pin that falls in the sea fails the build.

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

# --------------------------------------------------------------- scenes
#
# Thirteen flat editorial illustrations, one per displayed story.
# Rules (from the champion dissection): ONE motif per scene, drawn
# big (at least 60% of the scene height), on a light or saturated
# flat ground; flat fills only; at most five shapes besides the
# motif's own parts. The red label block and the black source chip
# are composited over every scene by the card renderer, not drawn
# here. Night grounds are the exception and appear once (the final).

FONTS = {}


def scene_cop31(cv, x, y, w, h):
    """Climate talks: a big globe, and a clock gone past midnight."""
    cv.fill_rect(x, y, w, h, (178, 216, 203))
    gx, gy, r = x + w * 0.62, y + h * 0.54, h * 0.40
    cv.fill_circle(gx, gy, r, (64, 110, 160))
    # continents, kept inside the disc
    cv.fill_polygon([(gx - r * 0.55, gy - r * 0.55), (gx - r * 0.15, gy - r * 0.72),
                     (gx - r * 0.02, gy - r * 0.38), (gx - r * 0.30, gy - r * 0.22),
                     (gx - r * 0.58, gy - r * 0.34)], MAP_LAND)
    cv.fill_polygon([(gx + r * 0.08, gy - r * 0.10), (gx + r * 0.52, gy - r * 0.28),
                     (gx + r * 0.66, gy + r * 0.06), (gx + r * 0.30, gy + r * 0.16),
                     (gx + r * 0.10, gy + r * 0.10)], MAP_LAND)
    cv.fill_polygon([(gx - r * 0.30, gy + r * 0.30), (gx - r * 0.02, gy + r * 0.24),
                     (gx + r * 0.06, gy + r * 0.58), (gx - r * 0.18, gy + r * 0.66),
                     (gx - r * 0.36, gy + r * 0.52)], MAP_LAND)
    # the clock: five past midnight
    cx, cy, cr = x + w * 0.155, y + h * 0.70, h * 0.19
    cv.fill_circle(cx, cy, cr + 2.5, INK)
    cv.fill_circle(cx, cy, cr, (253, 251, 244))
    cv.thick_line(cx, cy, cx + cr * 0.10, cy - cr * 0.78, 3.2, INK)
    cv.thick_line(cx, cy, cx + cr * 0.52, cy - cr * 0.60, 2.6, INK)
    cv.fill_circle(cx, cy, 2.6, RED)


def scene_cricket(cv, x, y, w, h):
    """A scoreboard carrying the record total, and the ball."""
    cv.fill_rect(x, y, w, h, (46, 95, 163))
    pw, ph = w * 0.80, h * 0.76
    px, py = x + w * 0.10, y + h * 0.17
    cv.fill_rect(px, py, pw, ph, INK)
    cv.fill_rect(px + 4, py + 4, pw - 8, ph - 8, (253, 251, 244))
    f = FONTS["display_b"]
    t = "INDIA"
    tw = FONTS["sans_b"].text_width(t, h * 0.105)
    FONTS["sans_b"].draw_text(cv, px + pw - 12 - tw, py + h * 0.155, t,
                              h * 0.105, RED)
    t = "629-6"
    size = h * 0.40
    tw = f.text_width(t, size)
    f.draw_text(cv, px + (pw - tw) / 2, py + h * 0.58, t, size, INK)
    t = "DAY 4 · LEAD 261"
    tw = FONTS["sans"].text_width(t, h * 0.105)
    FONTS["sans"].draw_text(cv, px + (pw - tw) / 2, py + h * 0.71, t,
                            h * 0.105, MUTED)
    # the ball, overlapping the board's lower right corner
    bx, by, br = px + pw - 2, py + ph - 2, h * 0.13
    cv.fill_circle(bx, by, br, (178, 32, 40))
    cv.polyline([(bx - br * 0.55, by - br * 0.8), (bx - br * 0.25, by),
                 (bx - br * 0.55, by + br * 0.8)], 1.8, WHITE)
    cv.polyline([(bx + br * 0.55, by - br * 0.8), (bx + br * 0.25, by),
                 (bx + br * 0.55, by + br * 0.8)], 1.8, WHITE)


def scene_libertadores(cv, x, y, w, h):
    """The Centenario tower at night, floodlit, over a split crowd."""
    cv.fill_rect(x, y, w, h, PLUM)
    # floodlight glows
    cv.fill_circle(x + w * 0.16, y + h * 0.20, h * 0.15, (120, 96, 96))
    cv.fill_circle(x + w * 0.84, y + h * 0.20, h * 0.15, (120, 96, 96))
    cv.fill_circle(x + w * 0.16, y + h * 0.20, h * 0.075, (250, 240, 200))
    cv.fill_circle(x + w * 0.84, y + h * 0.20, h * 0.075, (250, 240, 200))
    # the tower: stepped art-deco, cream against the plum
    cx = x + w * 0.5
    cream = (232, 217, 168)
    cv.fill_rect(cx - w * 0.085, y + h * 0.52, w * 0.17, h * 0.34, cream)
    cv.fill_rect(cx - w * 0.060, y + h * 0.34, w * 0.12, h * 0.20, cream)
    cv.fill_rect(cx - w * 0.038, y + h * 0.18, w * 0.076, h * 0.18, cream)
    cv.fill_rect(cx - w * 0.016, y + h * 0.06, w * 0.032, h * 0.14, cream)
    cv.fill_rect(cx - w * 0.030, y + h * 0.60, w * 0.060, h * 0.10, PLUM)
    # the crowd: green one half, red-and-white the other
    by = y + h * 0.86
    cv.fill_rect(x, by, w * 0.5, h * 0.14, (46, 124, 79))
    for i in range(6):
        col = (193, 39, 45) if i % 2 == 0 else (245, 243, 238)
        cv.fill_rect(x + w * 0.5 + i * w * 0.5 / 6, by, w * 0.5 / 6 + 1,
                     h * 0.14, col)


def scene_nepal(cv, x, y, w, h):
    """A jet over a Himalayan ridge."""
    cv.fill_rect(x, y, w, h, (207, 228, 242))
    ridge = [(x, y + h), (x, y + h * 0.78), (x + w * 0.22, y + h * 0.52),
             (x + w * 0.38, y + h * 0.74), (x + w * 0.55, y + h * 0.46),
             (x + w * 0.72, y + h * 0.72), (x + w * 0.86, y + h * 0.58),
             (x + w, y + h * 0.76), (x + w, y + h)]
    cv.fill_polygon(ridge, (110, 128, 152))
    # snow caps
    cv.fill_polygon([(x + w * 0.185, y + h * 0.575), (x + w * 0.22, y + h * 0.52),
                     (x + w * 0.255, y + h * 0.575), (x + w * 0.235, y + h * 0.60),
                     (x + w * 0.22, y + h * 0.575), (x + w * 0.205, y + h * 0.60)],
                    WHITE)
    cv.fill_polygon([(x + w * 0.515, y + h * 0.515), (x + w * 0.55, y + h * 0.46),
                     (x + w * 0.585, y + h * 0.515), (x + w * 0.565, y + h * 0.54),
                     (x + w * 0.55, y + h * 0.515), (x + w * 0.535, y + h * 0.54)],
                    WHITE)
    # the jet, side profile, nose to the right
    jy = y + h * 0.30
    body = [(x + w * 0.16, jy + h * 0.09), (x + w * 0.30, jy),
            (x + w * 0.68, jy - h * 0.02), (x + w * 0.86, jy + h * 0.05),
            (x + w * 0.88, jy + h * 0.10), (x + w * 0.74, jy + h * 0.15),
            (x + w * 0.30, jy + h * 0.16), (x + w * 0.17, jy + h * 0.14)]
    cv.fill_polygon(body, NAVY)
    cv.fill_polygon([(x + w * 0.185, jy + h * 0.03), (x + w * 0.235, jy - h * 0.13),
                     (x + w * 0.285, jy + h * 0.015)], NAVY)  # tail fin
    cv.fill_polygon([(x + w * 0.44, jy + h * 0.13), (x + w * 0.60, jy + h * 0.26),
                     (x + w * 0.50, jy + h * 0.26), (x + w * 0.36, jy + h * 0.14)],
                    NAVY)  # wing
    for i in range(6):
        cv.fill_circle(x + w * (0.40 + i * 0.065), jy + h * 0.065, 1.8,
                       (207, 228, 242))


def scene_aukus(cv, x, y, w, h):
    """A submarine breaking the surface."""
    cv.fill_rect(x, y, w, h, (127, 178, 201))
    cv.fill_rect(x, y + h * 0.62, w, h * 0.38, (64, 110, 140))
    cx, cy = x + w * 0.50, y + h * 0.60
    cv.fill_ellipse(cx, cy + h * 0.03, w * 0.40, h * 0.075, WHITE)  # foam
    cv.fill_ellipse(cx, cy, w * 0.37, h * 0.17, NAVY)               # hull
    cv.fill_rect(cx - w * 0.075, cy - h * 0.30, w * 0.13, h * 0.17, NAVY)
    cv.fill_rect(cx - w * 0.008, cy - h * 0.42, w * 0.016, h * 0.13, NAVY)
    cv.fill_rect(cx - w * 0.055, cy - h * 0.44, w * 0.07, h * 0.025, NAVY)
    cv.fill_polygon([(cx - w * 0.37, cy), (cx - w * 0.435, cy - h * 0.10),
                     (cx - w * 0.435, cy + h * 0.10)], NAVY)        # tail fin


def scene_ship(cv, x, y, w, h):
    """A cargo ship under drones on a grey northern sea."""
    cv.fill_rect(x, y, w, h, (168, 188, 196))
    cv.fill_rect(x, y + h * 0.64, w, h * 0.36, (90, 120, 135))
    hx, hy = x + w * 0.14, y + h * 0.56
    hw = w * 0.68
    cv.fill_polygon([(hx, hy), (hx + hw, hy), (hx + hw * 0.93, hy + h * 0.17),
                     (hx + hw * 0.07, hy + h * 0.17)], (176, 74, 50))
    cv.fill_rect(hx + hw * 0.16, hy - h * 0.16, hw * 0.20, h * 0.16, (70, 100, 140))
    cv.fill_rect(hx + hw * 0.38, hy - h * 0.16, hw * 0.20, h * 0.16, (200, 170, 90))
    cv.fill_rect(hx + hw * 0.60, hy - h * 0.16, hw * 0.20, h * 0.16, (84, 120, 84))
    cv.fill_rect(hx + hw * 0.84, hy - h * 0.26, hw * 0.07, h * 0.26, (60, 60, 64))
    for i, (dx, dy, r) in enumerate(((0.86, -0.34, 0.075), (0.90, -0.46, 0.10),
                                     (0.95, -0.60, 0.13))):
        cv.fill_circle(hx + hw * dx, hy + h * dy, h * r, (120, 126, 130))
    for dx, dy in ((0.80, 0.14), (0.90, 0.24)):
        px, py = x + w * dx, y + h * dy
        cv.thick_line(px - 5, py - 5, px + 5, py + 5, 2.2, (40, 44, 48))
        cv.thick_line(px - 5, py + 5, px + 5, py - 5, 2.2, (40, 44, 48))
        cv.fill_circle(px, py, 2.2, (40, 44, 48))


def scene_fbi(cv, x, y, w, h):
    """A padlock, cracked, on flat red."""
    cv.fill_rect(x, y, w, h, RED)
    cx = x + w * 0.5
    arc = []
    for i in range(13):
        t = i / 12.0
        ang = math.pi * (1 - t)
        arc.append((cx + math.cos(ang) * w * 0.115, y + h * 0.46 - math.sin(ang) * h * 0.30))
    cv.polyline(arc, 5.5, (253, 251, 244))
    bw, bh = w * 0.34, h * 0.40
    cv.fill_rect(cx - bw / 2, y + h * 0.44, bw, bh, (253, 251, 244))
    cv.fill_circle(cx, y + h * 0.60, h * 0.075, INK)
    cv.fill_polygon([(cx - h * 0.045, y + h * 0.62), (cx + h * 0.045, y + h * 0.62),
                     (cx + h * 0.02, y + h * 0.76), (cx - h * 0.02, y + h * 0.76)], INK)
    cv.polyline([(cx - bw * 0.30, y + h * 0.46), (cx - bw * 0.08, y + h * 0.60),
                 (cx + bw * 0.10, y + h * 0.52), (cx + bw * 0.28, y + h * 0.70)],
                2.6, RED)


def scene_gamer(cv, x, y, w, h):
    """A gaming monitor with a headset over it."""
    cv.fill_rect(x, y, w, h, (74, 63, 120))
    mx, my, mw, mh = x + w * 0.24, y + h * 0.20, w * 0.52, h * 0.52
    cv.fill_rect(mx, my, mw, mh, INK)
    cv.fill_rect(mx + 3, my + 3, mw - 6, mh - 6, (200, 220, 235))
    cx, cy = mx + mw / 2, my + mh / 2
    cv.fill_circle(cx, cy, h * 0.10, RED)
    cv.fill_circle(cx, cy, h * 0.045, (200, 220, 235))
    cv.thick_line(cx - h * 0.17, cy, cx - h * 0.13, cy, 2, RED)
    cv.thick_line(cx + h * 0.13, cy, cx + h * 0.17, cy, 2, RED)
    cv.thick_line(cx, cy - h * 0.17, cx, cy - h * 0.13, 2, RED)
    cv.thick_line(cx, cy + h * 0.13, cx, cy + h * 0.17, 2, RED)
    cv.fill_rect(mx + mw * 0.10, my + mh * 0.12, 5, 5, (46, 95, 163))
    cv.fill_rect(mx + mw * 0.82, my + mh * 0.70, 5, 5, (200, 135, 26))
    cv.fill_polygon([(cx - 4, my + mh), (cx + 4, my + mh),
                     (cx + 9, my + mh + h * 0.16), (cx - 9, my + mh + h * 0.16)], INK)
    arc = []
    for i in range(13):
        t = i / 12.0
        ang = math.pi * (1 - t)
        arc.append((cx + math.cos(ang) * mw * 0.56, my + mh * 0.42 - math.sin(ang) * h * 0.30))
    cv.polyline(arc, 4, (232, 217, 168))
    cv.fill_rect(mx - 6, my + mh * 0.36, 7, h * 0.20, (232, 217, 168))
    cv.fill_rect(mx + mw - 1, my + mh * 0.36, 7, h * 0.20, (232, 217, 168))


def scene_sumo(cv, x, y, w, h):
    """Two wrestlers crouched in the ring."""
    cv.fill_rect(x, y, w, h, (241, 230, 200))
    cx, cy = x + w * 0.5, y + h * 0.60
    cv.fill_ellipse(cx, cy, w * 0.44, h * 0.36, WHITE)
    cv.fill_ellipse(cx, cy, w * 0.415, h * 0.325, (196, 150, 96))
    for fx in (0.36, 0.64):
        px, py = x + w * fx, y + h * 0.52
        cv.fill_circle(px, py - h * 0.16, h * 0.085, INK)          # head
        cv.fill_polygon([(px - w * 0.075, py + h * 0.22), (px - w * 0.045, py - h * 0.10),
                         (px + w * 0.045, py - h * 0.10), (px + w * 0.075, py + h * 0.22)],
                        INK)                                       # body
        cv.fill_rect(px - w * 0.048, py + h * 0.02, w * 0.096, h * 0.055, WHITE)
    cv.thick_line(cx - w * 0.10, cy + h * 0.10, cx - w * 0.02, cy + h * 0.10, 2, WHITE)
    cv.thick_line(cx + w * 0.02, cy + h * 0.10, cx + w * 0.10, cy + h * 0.10, 2, WHITE)


def scene_atp(cv, x, y, w, h):
    """The trophy, and a ball at its foot."""
    cv.fill_rect(x, y, w, h, (46, 95, 163))
    cx = x + w * 0.46
    steel = (217, 222, 228)
    shade = (158, 166, 176)
    cv.fill_polygon([(cx - w * 0.15, y + h * 0.14), (cx + w * 0.15, y + h * 0.14),
                     (cx + w * 0.085, y + h * 0.52), (cx - w * 0.085, y + h * 0.52)],
                    steel)
    cv.fill_rect(cx - w * 0.155, y + h * 0.10, w * 0.31, h * 0.07, shade)
    arc_l = [(cx - w * 0.15 - math.sin(t / 10.0 * math.pi) * w * 0.055,
              y + h * (0.20 + t / 10.0 * 0.24)) for t in range(11)]
    arc_r = [(cx + w * 0.15 + math.sin(t / 10.0 * math.pi) * w * 0.055,
              y + h * (0.20 + t / 10.0 * 0.24)) for t in range(11)]
    cv.polyline(arc_l, 3.5, shade)
    cv.polyline(arc_r, 3.5, shade)
    cv.fill_rect(cx - w * 0.028, y + h * 0.52, w * 0.056, h * 0.14, shade)
    cv.fill_rect(cx - w * 0.10, y + h * 0.66, w * 0.20, h * 0.09, steel)
    bx, by, br = x + w * 0.76, y + h * 0.70, h * 0.16
    cv.fill_circle(bx, by, br, (196, 205, 84))
    cv.polyline([(bx - br * 0.7, by - br * 0.7), (bx, by - br * 0.2),
                 (bx - br * 0.7, by + br * 0.7)], 1.8, WHITE)


def scene_fcc(cv, x, y, w, h):
    """A telephone handset under a prohibition sign."""
    cv.fill_rect(x, y, w, h, (235, 217, 168))
    cx, cy = x + w * 0.5, y + h * 0.52
    arc = []
    for i in range(17):
        t = i / 16.0
        ang = math.pi * (0.08 + 0.84 * t)
        arc.append((cx + math.cos(ang) * w * 0.30, cy - math.sin(ang) * h * 0.26 + h * 0.10))
    cv.polyline(arc, h * 0.13, INK)
    for ex in (cx - w * 0.285, cx + w * 0.285):
        cv.fill_circle(ex, cy + h * 0.045, h * 0.115, INK)
    r = h * 0.40
    cv.fill_circle(cx, cy, r, RED)
    cv.fill_circle(cx, cy, r - 4.5, (235, 217, 168))
    cv.polyline(arc, h * 0.13, INK)
    for ex in (cx - w * 0.285, cx + w * 0.285):
        cv.fill_circle(ex, cy + h * 0.045, h * 0.115, INK)
    cv.thick_line(cx - r * 0.70, cy + r * 0.70, cx + r * 0.70, cy - r * 0.70, 5, RED)


def scene_delhi(cv, x, y, w, h):
    """India Gate dissolving into the smog."""
    cv.fill_rect(x, y, w, h, (223, 164, 92))
    cv.fill_circle(x + w * 0.70, y + h * 0.30, h * 0.20, (245, 225, 170))
    gx, gw = x + w * 0.40, w * 0.20
    gate = (74, 48, 32)
    cv.fill_rect(gx, y + h * 0.24, gw, h * 0.66, gate)
    cv.fill_rect(gx - gw * 0.10, y + h * 0.86, gw * 1.2, h * 0.06, gate)
    cv.fill_rect(gx + gw * 0.28, y + h * 0.13, gw * 0.44, h * 0.11, gate)
    cv.fill_circle(gx + gw * 0.5, y + h * 0.13, gw * 0.20, gate)
    # the arch, cut out in smog colour
    cv.fill_rect(gx + gw * 0.32, y + h * 0.52, gw * 0.36, h * 0.38, (223, 164, 92))
    cv.fill_circle(gx + gw * 0.5, y + h * 0.52, gw * 0.18, (223, 164, 92))
    cv.fill_rect(x, y + h * 0.90, w, h * 0.10, (196, 132, 66))


def scene_spacex(cv, x, y, w, h):
    """A Falcon on its coastal pad, satellites stringing away."""
    cv.fill_rect(x, y, w, h, (220, 233, 240))
    cv.fill_rect(x, y + h * 0.80, w, h * 0.20, (120, 160, 180))
    rx = x + w * 0.38
    cv.fill_rect(rx - w * 0.08, y + h * 0.78, w * 0.25, h * 0.05, (120, 126, 130))
    cv.fill_rect(rx, y + h * 0.18, w * 0.085, h * 0.61, (250, 250, 248))
    cv.fill_polygon([(rx, y + h * 0.18), (rx + w * 0.085, y + h * 0.18),
                     (rx + w * 0.0425, y + h * 0.04)], (250, 250, 248))
    cv.fill_polygon([(rx, y + h * 0.66), (rx - w * 0.04, y + h * 0.80),
                     (rx, y + h * 0.80)], NAVY)
    cv.fill_polygon([(rx + w * 0.085, y + h * 0.66), (rx + w * 0.125, y + h * 0.80),
                     (rx + w * 0.085, y + h * 0.80)], NAVY)
    cv.fill_circle(rx + w * 0.0425, y + h * 0.32, 3.0, NAVY)
    for i, (sx, sy) in enumerate(((0.64, 0.18), (0.74, 0.12), (0.84, 0.07))):
        px, py = x + w * sx, y + h * sy
        cv.fill_rect(px - 2.5, py - 2.5, 5, 5, INK)
        cv.fill_rect(px - 7, py - 1.2, 4, 2.4, (70, 100, 140))
        cv.fill_rect(px + 3, py - 1.2, 4, 2.4, (70, 100, 140))


SCENES = {
    "cop31": scene_cop31,
    "cricket": scene_cricket,
    "libertadores": scene_libertadores,
    "nepal": scene_nepal,
    "aukus": scene_aukus,
    "ship": scene_ship,
    "fbi": scene_fbi,
    "gamer": scene_gamer,
    "sumo": scene_sumo,
    "atp": scene_atp,
    "fcc": scene_fcc,
    "delhi": scene_delhi,
    "spacex": scene_spacex,
}

# --------------------------------------------------------------- layout

PAGE_W = 1024
PAGE_H = 1024
MARGIN = 16
CONTENT_W = PAGE_W - 2 * MARGIN

TOTAL_STORIES = len(LEADS) + len(BRIEFS)
REGIONS = []
for _lead in LEADS:
    if _lead["region"] not in REGIONS:
        REGIONS.append(_lead["region"])
for _b in BRIEFS:
    if _b[0] not in REGIONS:
        REGIONS.append(_b[0])
REGION_ORDER = ["North America", "Latin America", "Europe", "Africa",
                "Asia", "Oceania"]
REGION_COUNTS = {}
for _r in REGION_ORDER:
    REGION_COUNTS[_r] = (
        sum(1 for _lead in LEADS if _lead["region"] == _r)
        + sum(1 for _b in BRIEFS if _b[0] == _r)
    )

# pin nudges (pixels) for pairs that collide at map scale
PIN_NUDGES = {2: (-4, 0), 4: (5, 2), 12: (-4, -1)}


class Page:
    def __init__(self):
        here = os.path.dirname(os.path.abspath(__file__))
        fdir = os.path.join(here, "fonts")
        self.display_b = Font(os.path.join(fdir, "display_bold.ttf"))
        self.display_black = Font(os.path.join(fdir, "display_black.ttf"))
        self.display_cond = Font(os.path.join(fdir, "display_cond_black.ttf"))
        self.serif = Font(os.path.join(fdir, "serif.ttf"))
        self.serif_i = Font(os.path.join(fdir, "serif_italic.ttf"))
        self.sans_b = Font(os.path.join(fdir, "sans_bold.ttf"))
        self.sans = Font(os.path.join(fdir, "sans.ttf"))
        FONTS.update({
            "display_b": self.display_b,
            "sans_b": self.sans_b,
            "sans": self.sans,
        })
        self.cv = Canvas(PAGE_W, PAGE_H, PAPER)

    # -- shared pieces ---------------------------------------------

    def text(self, x, y_base, s, font, size, color, tracking=0.0):
        return font.draw_text(self.cv, x, y_base, s, size, color, tracking)

    def block(self, x, y_top, s, font, width, max_lines, sizes, color,
              lh_mult=1.18):
        """Fit and draw a wrapped block; returns its height."""
        size, lines = fit_text(font, s, width, max_lines, sizes)
        lh = size * lh_mult
        for i, line in enumerate(lines):
            self.text(x, y_top + size * 0.82 + i * lh, line, font, size, color)
        return len(lines) * lh

    def centred(self, y_base, s, font, size, color, tracking=0.0):
        w = font.text_width(s, size, tracking)
        self.text((PAGE_W - w) / 2, y_base, s, font, size, color, tracking)
        return w

    # -- top bands ---------------------------------------------------

    def kicker(self):
        left = "THE WHOLE WORLD · ONE SUNDAY"
        self.text(MARGIN, 20, left, self.sans_b, 10, RED, tracking=1.1)
        right = ("%d STORIES · %d REGIONS · EVERY ONE DATED SUNDAY "
                 "22 NOVEMBER 2026" % (TOTAL_STORIES, len(REGIONS)))
        w = self.sans_b.text_width(right, 10, 0.6)
        self.text(PAGE_W - MARGIN - w, 20, right, self.sans_b, 10, INK,
                  tracking=0.6)
        self.cv.fill_rect(MARGIN, 27, CONTENT_W, 1.4, INK)

    def masthead(self):
        main = "Sunday 22 November"
        year = "2026"
        chosen = None
        for s in (120, 114, 108, 102, 96, 90):
            w_main = self.display_cond.text_width(main, s, -1.0)
            w_year = self.display_black.text_width(year, s * 0.52)
            total = w_main + s * 0.16 + w_year
            if total <= CONTENT_W - 4:
                chosen = (s, w_main, w_year, total)
                break
        if chosen is None:
            raise ValueError("masthead does not fit")
        s, w_main, w_year, total = chosen
        x = (PAGE_W - total) / 2
        self.text(x, 122, main, self.display_cond, s, INK, tracking=-1.0)
        self.text(x + w_main + s * 0.16, 122, year, self.display_black,
                  s * 0.52, INK)

    def dek(self):
        for size in (16, 15, 14):
            if self.serif_i.text_width(DEK, size) <= CONTENT_W - 8:
                self.centred(166, DEK, self.serif_i, size, (74, 62, 50))
                return
        raise ValueError("dek does not fit")

    def stat_band(self, top):
        cv = self.cv
        cv.fill_rect(MARGIN, top, CONTENT_W, 1.2, INK)
        cv.fill_rect(MARGIN, top + 72, CONTENT_W, 1.2, INK)
        cell = CONTENT_W / 6.0
        for i, (num, cap) in enumerate(STATS):
            cx = MARGIN + i * cell
            if i:
                cv.fill_rect(cx, top + 10, 1, 52, RED)
            w = self.display_b.text_width(num, 42)
            self.text(cx + (cell - w) / 2, top + 42, num, self.display_b,
                      42, RED)
            size, lines = fit_text(self.sans, cap, cell - 14, 2, [10.5, 10])
            for j, line in enumerate(lines):
                lw = self.sans.text_width(line, size)
                self.text(cx + (cell - lw) / 2, top + 57 + j * 12.5, line,
                          self.sans, size, (74, 62, 50))
        return top + 72

    def region_strip(self, top):
        cv = self.cv
        present = [r for r in REGION_ORDER if REGION_COUNTS[r]]
        seg = CONTENT_W / float(len(present))
        for i, region in enumerate(present):
            x = MARGIN + i * seg
            cv.fill_rect(x, top, seg + 0.6, 20, REGION_COLORS[region])
            label = "%s %d" % (region.upper(), REGION_COUNTS[region])
            size = 9.5
            tw = self.sans_b.text_width(label, size, 0.5)
            if tw > seg - 8:
                raise ValueError("region label does not fit: " + label)
            self.text(x + (seg - tw) / 2, top + 14, label, self.sans_b,
                      size, WHITE, tracking=0.5)
        return top + 20

    # -- story cards ---------------------------------------------------

    def _label(self, x, y, w, text, target):
        size = target
        while size > 9.5 and self.sans_b.text_width(text, size, 0.4) + 14 > w - 14:
            size -= 0.5
        tw = self.sans_b.text_width(text, size, 0.4)
        self.cv.fill_rect(x + 7, y + 7, tw + 13, size * 1.36, RED)
        self.text(x + 13, y + 7 + size * 1.02, text, self.sans_b, size,
                  WHITE, tracking=0.4)

    def _chip(self, x, y, scene_h, text):
        tw = self.sans.text_width(text, 9.5)
        self.cv.fill_rect(x + 7, y + scene_h - 16, tw + 11, 15, (10, 10, 10))
        self.text(x + 12, y + scene_h - 5, text, self.sans, 9.5, WHITE)

    def _kicker_row(self, x, y, num, lead, r, avail):
        cv = self.cv
        cx = x + r
        cv.fill_circle(cx, y, r, RED)
        ns = str(num)
        nw = self.sans_b.text_width(ns, r * 1.18)
        self.text(cx - nw / 2, y + r * 0.42, ns, self.sans_b, r * 1.18, WHITE)
        tx = cx + r + 6
        place = lead["place"]
        topic = " · " + lead["topic"]
        for size, trk in ((10.5, 0.5), (10, 0.4), (9.5, 0.3), (9, 0.2),
                          (8.6, 0.1), (8.2, 0.0)):
            pw = self.sans_b.text_width(place, size, trk)
            tw = self.sans_b.text_width(topic, size, trk)
            if pw + tw <= avail:
                break
        else:
            raise ValueError("kicker does not fit: " + place + topic)
        self.text(tx, y + r * 0.42, place, self.sans_b, size, RED,
                  tracking=trk)
        self.text(tx + pw, y + r * 0.42, topic, self.sans_b, size, INK,
                  tracking=trk)
        return tx

    def story_card(self, x, y, w, h, lead, num, hero):
        cv = self.cv
        cv.fill_rect(x, y, w, h, CARD)
        cv.frame_rect(x, y, w, h, RULE, 1)
        scene_h = 126 if hero else 62
        cv.set_clip(x + 1, y + 1, w - 2, scene_h)
        SCENES[lead["scene"]](cv, x + 1, y + 1, w - 2, scene_h)
        cv.clear_clip()
        cv.frame_rect(x + 1, y + 1, w - 2, scene_h, RULE, 1)
        self._label(x, y, w, lead["label"], 23 if hero else 14)
        self._chip(x, y, scene_h, lead["chip"])
        tx = x + 10
        tw = w - 20
        r = 8.5 if hero else 7.5
        ky = y + scene_h + (15 if hero else 13)
        self._kicker_row(tx, ky, num, lead, r, w - 26 - 2 * r)
        yy = ky + (12 if hero else 10)
        if hero:
            yy += self.block(tx, yy, lead["headline"], self.display_b, tw, 2,
                             [28.5, 27, 25.5], INK, 1.10)
            yy += 3
            self.block(tx, yy, lead["summary"], self.serif, tw, 3,
                       [11.5, 11], (52, 50, 46), 1.27)
        else:
            yy += self.block(tx, yy, lead["headline"], self.display_b, tw, 2,
                             [16.5, 15.5, 14.5], INK, 1.11)
            yy += 1
            self.block(tx, yy, lead["summary"], self.serif, tw, 1,
                       [10, 9.5], (52, 50, 46), 1.2)

    def heroes(self, top):
        w = (CONTENT_W - 2 * 13) // 3
        for i, lead in enumerate(LEADS[:3]):
            self.story_card(MARGIN + i * (w + 13), top, w, 266, lead,
                            i + 1, True)
        return top + 266

    def card_row(self, top, leads, first_num):
        w = (CONTENT_W - 4 * 8) // 5
        for i, lead in enumerate(leads):
            self.story_card(MARGIN + i * (w + 8), top, w, 136, lead,
                            first_num + i, False)
        return top + 136

    # -- bottom zone ---------------------------------------------------

    def map_panel(self, top):
        cv = self.cv
        mw, mh = 380, 110
        mx = MARGIN
        cv.fill_rect(mx, top, mw, mh, MAP_BG)
        cv.frame_rect(mx, top, mw, mh, (16, 24, 44), 1)

        def proj(lon, lat):
            return (mx + (lon + 180) / 360.0 * mw,
                    top + (84 - lat) / 142.0 * mh)

        cv.set_clip(mx + 1, top + 1, mw - 2, mh - 2)
        for poly in LAND:
            pts = [proj(lon, lat) for (lon, lat) in poly]
            cv.fill_polygon(pts, MAP_LAND)
        cv.clear_clip()
        self.text(mx + 10, top + 15, "WHERE IT HAPPENED", self.sans_b, 10,
                  WHITE, tracking=1.0)
        for i, lead in enumerate(LEADS):
            num = i + 1
            if not point_in_land(lead["lon"], lead["lat"]):
                raise ValueError("pin in the sea: " + lead["city"])
            px, py = proj(lead["lon"], lead["lat"])
            dx, dy = PIN_NUDGES.get(num, (0, 0))
            px += dx
            py += dy
            cv.fill_circle(px, py, 7.4, WHITE)
            cv.fill_circle(px, py, 6.1, RED)
            ns = str(num)
            nw = self.sans_b.text_width(ns, 7.6)
            self.text(px - nw / 2, py + 2.7, ns, self.sans_b, 7.6, WHITE)
        self.text(mx, top + mh + 12,
                  "Each number is the story with that number on this page.",
                  self.sans, 8.5, MUTED)

    def briefs(self, top):
        x0 = 410
        header = ("ALSO ON SUNDAY 22 NOVEMBER — %d MORE STORIES"
                  % len(BRIEFS))
        self.text(x0, top + 12, header, self.sans_b, 11, INK, tracking=0.4)
        self.cv.fill_rect(x0, top + 18, PAGE_W - MARGIN - x0, 1, RULE)
        col_w = 291
        col_x = [x0, x0 + col_w + 16]
        per_col = (len(BRIEFS) + 1) // 2
        for i, (region, place, headline, source) in enumerate(BRIEFS):
            col = 0 if i < per_col else 1
            row = i if col == 0 else i - per_col
            bx = col_x[col]
            by = top + 29 + row * 10.0
            num = len(LEADS) + i + 1
            ns = "%d " % num
            size = 9.7
            while size > 8.6:
                w_num = self.sans_b.text_width(ns, size)
                w_place = self.sans_b.text_width(place + " ", size)
                w_head = self.sans.text_width(headline + " ", size)
                w_src = self.sans.text_width("(" + source + ")", size)
                if w_num + w_place + w_head + w_src <= col_w:
                    break
                size -= 0.3
            else:
                raise ValueError("brief does not fit: " + headline)
            x = bx
            x = self.text(x, by, ns, self.sans_b, size, RED)
            x = self.text(x, by, place + " ", self.sans_b, size, INK)
            x = self.text(x, by, headline + " ", self.sans, size,
                          (44, 42, 40))
            self.text(x, by, "(" + source + ")", self.sans, size, MUTED)

    # -- closing bands ---------------------------------------------------

    def date_check(self, top):
        cv = self.cv
        cv.frame_rect(MARGIN, top, CONTENT_W, 26, RED, 1.5)
        tab = "DATE CHECK"
        tw = self.sans_b.text_width(tab, 10.5, 0.5)
        cv.fill_rect(MARGIN, top, tw + 16, 26, RED)
        self.text(MARGIN + 8, top + 17, tab, self.sans_b, 10.5, WHITE,
                  tracking=0.5)
        tx = MARGIN + tw + 26
        width = PAGE_W - MARGIN - tx
        size, lines = fit_text(self.sans, DATE_CHECK, width, 2, [10, 9.6])
        if len(lines) > 2:
            raise ValueError("date check overflows")
        for i, line in enumerate(lines):
            self.text(tx, top + 11.5 + i * 11.5, line, self.sans, size,
                      (52, 50, 46))

    def footer(self):
        cv = self.cv
        cv.fill_rect(MARGIN, 1009, CONTENT_W, 1, INK)
        left = ("Every story here happened, or was first reported, on "
                "Sunday 22 November 2026. Officials' counts are attributed.")
        self.text(MARGIN, 1022, left, self.sans, 9.5, (90, 82, 70))
        right = "Sources named beside each story · Drawings are original"
        w = self.sans.text_width(right, 9.5)
        self.text(PAGE_W - MARGIN - w, 1022, right, self.sans, 9.5,
                  (90, 82, 70))

    # -- assembly ---------------------------------------------------

    def render(self):
        self.kicker()
        self.masthead()
        self.dek()
        y = self.stat_band(178)
        y = self.region_strip(y + 8)
        y = self.heroes(y + 14)
        y = self.card_row(y + 8, LEADS[3:8], 4)
        y = self.card_row(y + 8, LEADS[8:13], 9)
        self.map_panel(y + 8)
        self.briefs(y + 8)
        self.date_check(978)
        self.footer()
        return self.cv


def main():
    page = Page()
    cv = page.render()
    data = encode_png(PAGE_W, PAGE_H, cv.px)
    out_dir = os.environ.get("MAKEFUN_OUTPUT_DIR", "/output")
    os.makedirs(out_dir, exist_ok=True)
    path = os.path.join(out_dir, "entry.png")
    with open(path, "wb") as fh:
        fh.write(data)
    import hashlib
    print("wrote", path, len(data), "bytes sha256",
          hashlib.sha256(data).hexdigest())


if __name__ == "__main__":
    sys.exit(main())
