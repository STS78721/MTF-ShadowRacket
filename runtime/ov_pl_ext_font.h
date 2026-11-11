// Clean-room runtime TrueType (sfnt) generator for nn::pl FontNintendoExtended
// (shared font types 5 and 6) when firmware BFTTF files are not present.
// Synthesizes crisp quadratic-Bezier vector glyphs for the Nintendo Private Use
// Area controller button and UI icon range (U+E000..U+E126).

#ifndef OV_PL_EXT_FONT_H
#define OV_PL_EXT_FONT_H

#include <math.h>
#include <stdint.h>
#include <stdlib.h>
#include <string.h>

typedef struct {
    uint8_t *buf;
    size_t len, cap;
} ExtBuf;

static void eb_reserve(ExtBuf *b, size_t add) {
    if (b->len + add <= b->cap) return;
    size_t ncap = b->cap ? b->cap * 2 : 4096;
    while (ncap < b->len + add) ncap *= 2;
    b->buf = (uint8_t *)realloc(b->buf, ncap);
    b->cap = ncap;
}
static void eb_u8(ExtBuf *b, uint8_t v) { eb_reserve(b, 1); b->buf[b->len++] = v; }
static void eb_u16(ExtBuf *b, uint16_t v) {
    eb_reserve(b, 2);
    b->buf[b->len++] = (uint8_t)(v >> 8);
    b->buf[b->len++] = (uint8_t)v;
}
static void eb_i16(ExtBuf *b, int16_t v) { eb_u16(b, (uint16_t)v); }
static void eb_u32(ExtBuf *b, uint32_t v) {
    eb_reserve(b, 4);
    b->buf[b->len++] = (uint8_t)(v >> 24);
    b->buf[b->len++] = (uint8_t)(v >> 16);
    b->buf[b->len++] = (uint8_t)(v >> 8);
    b->buf[b->len++] = (uint8_t)v;
}
static void eb_bytes(ExtBuf *b, const void *src, size_t n) {
    eb_reserve(b, n);
    memcpy(b->buf + b->len, src, n);
    b->len += n;
}
static void eb_pad4(ExtBuf *b) {
    while (b->len & 3) eb_u8(b, 0);
}

typedef struct {
    int16_t x, y;
    uint8_t on;
} ExtPt;

typedef struct {
    ExtPt pts[512];
    uint16_t ends[48];
    int npts, ncont;
    uint16_t adv;
} ExtShape;

static void es_init(ExtShape *s, uint16_t adv) {
    s->npts = 0;
    s->ncont = 0;
    s->adv = adv;
}

// Appends a closed contour, enforcing TrueType winding in Y-up coordinates:
// want_cw = 1 -> clockwise (signed area < 0, filled outer contour)
// want_cw = 0 -> counter-clockwise (signed area > 0, hole/cutout contour)
static void es_contour(ExtShape *s, const ExtPt *pts, int n, int want_cw) {
    if (n < 3 || s->ncont >= 48 || s->npts + n > 512) return;
    int64_t area2 = 0;
    for (int i = 0; i < n; i++) {
        int j = (i + 1) % n;
        area2 += (int64_t)pts[i].x * pts[j].y - (int64_t)pts[j].x * pts[i].y;
    }
    int is_cw = area2 < 0;
    if (is_cw == (want_cw != 0)) {
        for (int i = 0; i < n; i++) s->pts[s->npts++] = pts[i];
    } else {
        s->pts[s->npts++] = pts[0];
        for (int i = n - 1; i >= 1; i--) s->pts[s->npts++] = pts[i];
    }
    s->ends[s->ncont++] = (uint16_t)(s->npts - 1);
}

static void es_rect(ExtShape *s, int x0, int y0, int x1, int y1, int cw) {
    ExtPt p[4] = {
        {(int16_t)x0, (int16_t)y0, 1},
        {(int16_t)x0, (int16_t)y1, 1},
        {(int16_t)x1, (int16_t)y1, 1},
        {(int16_t)x1, (int16_t)y0, 1},
    };
    es_contour(s, p, 4, cw);
}

// 8-segment quadratic Bezier circle (16 points: 8 on-curve, 8 off-curve).
static void es_circle(ExtShape *s, double cx, double cy, double r, int cw) {
    const double pi = 3.14159265358979323846;
    const double k = r / cos(pi / 8.0);
    ExtPt p[16];
    for (int i = 0; i < 8; i++) {
        double a0 = i * (pi / 4.0);
        double a1 = a0 + (pi / 8.0);
        p[i * 2 + 0] = (ExtPt){(int16_t)lrint(cx + r * cos(a0)), (int16_t)lrint(cy + r * sin(a0)), 1};
        p[i * 2 + 1] = (ExtPt){(int16_t)lrint(cx + k * cos(a1)), (int16_t)lrint(cy + k * sin(a1)), 0};
    }
    es_contour(s, p, 16, cw);
}

// Rounded box with independent corner radii (tl, tr, br, bl).
static void es_rrect4(ExtShape *s, double x0, double y0, double x1, double y1,
                      double rtl, double rtr, double rbr, double rbl, int cw) {
    const double pi = 3.14159265358979323846;
    const double t = tan(pi / 8.0); // 0.41421356 for 45-deg octant tangents
    const double s2 = 0.7071067811865475;
    ExtPt p[24];
    int n = 0;
    // Top-left corner: (x0, y1-rtl) -> (x0+rtl, y1)
    p[n++] = (ExtPt){(int16_t)lrint(x0), (int16_t)lrint(y1 - rtl), 1};
    if (rtl > 1.0) {
        p[n++] = (ExtPt){(int16_t)lrint(x0), (int16_t)lrint(y1 - rtl * (1.0 - t)), 0};
        p[n++] = (ExtPt){(int16_t)lrint(x0 + rtl * (1.0 - s2)), (int16_t)lrint(y1 - rtl * (1.0 - s2)), 1};
        p[n++] = (ExtPt){(int16_t)lrint(x0 + rtl * (1.0 - t)), (int16_t)lrint(y1), 0};
    }
    p[n++] = (ExtPt){(int16_t)lrint(x0 + rtl), (int16_t)lrint(y1), 1};
    // Top-right corner: (x1-rtr, y1) -> (x1, y1-rtr)
    p[n++] = (ExtPt){(int16_t)lrint(x1 - rtr), (int16_t)lrint(y1), 1};
    if (rtr > 1.0) {
        p[n++] = (ExtPt){(int16_t)lrint(x1 - rtr * (1.0 - t)), (int16_t)lrint(y1), 0};
        p[n++] = (ExtPt){(int16_t)lrint(x1 - rtr * (1.0 - s2)), (int16_t)lrint(y1 - rtr * (1.0 - s2)), 1};
        p[n++] = (ExtPt){(int16_t)lrint(x1), (int16_t)lrint(y1 - rtr * (1.0 - t)), 0};
    }
    p[n++] = (ExtPt){(int16_t)lrint(x1), (int16_t)lrint(y1 - rtr), 1};
    // Bottom-right corner: (x1, y0+rbr) -> (x1-rbr, y0)
    p[n++] = (ExtPt){(int16_t)lrint(x1), (int16_t)lrint(y0 + rbr), 1};
    if (rbr > 1.0) {
        p[n++] = (ExtPt){(int16_t)lrint(x1), (int16_t)lrint(y0 + rbr * (1.0 - t)), 0};
        p[n++] = (ExtPt){(int16_t)lrint(x1 - rbr * (1.0 - s2)), (int16_t)lrint(y0 + rbr * (1.0 - s2)), 1};
        p[n++] = (ExtPt){(int16_t)lrint(x1 - rbr * (1.0 - t)), (int16_t)lrint(y0), 0};
    }
    p[n++] = (ExtPt){(int16_t)lrint(x1 - rbr), (int16_t)lrint(y0), 1};
    // Bottom-left corner: (x0+rbl, y0) -> (x0, y0+rbl)
    p[n++] = (ExtPt){(int16_t)lrint(x0 + rbl), (int16_t)lrint(y0), 1};
    if (rbl > 1.0) {
        p[n++] = (ExtPt){(int16_t)lrint(x0 + rbl * (1.0 - t)), (int16_t)lrint(y0), 0};
        p[n++] = (ExtPt){(int16_t)lrint(x0 + rbl * (1.0 - s2)), (int16_t)lrint(y0 + rbl * (1.0 - s2)), 1};
        p[n++] = (ExtPt){(int16_t)lrint(x0), (int16_t)lrint(y0 + rbl * (1.0 - t)), 0};
    }
    p[n++] = (ExtPt){(int16_t)lrint(x0), (int16_t)lrint(y0 + rbl), 1};
    es_contour(s, p, n, cw);
}

static void es_plus(ExtShape *s, int cx, int cy, int arm, int half_w, int cw) {
    ExtPt p[12] = {
        {(int16_t)(cx - half_w), (int16_t)(cy + arm), 1},
        {(int16_t)(cx + half_w), (int16_t)(cy + arm), 1},
        {(int16_t)(cx + half_w), (int16_t)(cy + half_w), 1},
        {(int16_t)(cx + arm),    (int16_t)(cy + half_w), 1},
        {(int16_t)(cx + arm),    (int16_t)(cy - half_w), 1},
        {(int16_t)(cx + half_w), (int16_t)(cy - half_w), 1},
        {(int16_t)(cx + half_w), (int16_t)(cy - arm), 1},
        {(int16_t)(cx - half_w), (int16_t)(cy - arm), 1},
        {(int16_t)(cx - half_w), (int16_t)(cy - half_w), 1},
        {(int16_t)(cx - arm),    (int16_t)(cy - half_w), 1},
        {(int16_t)(cx - arm),    (int16_t)(cy + half_w), 1},
        {(int16_t)(cx - half_w), (int16_t)(cy + half_w), 1},
    };
    es_contour(s, p, 12, cw);
}

static void es_tri(ExtShape *s, int x0, int y0, int x1, int y1, int x2, int y2, int cw) {
    ExtPt p[3] = {{(int16_t)x0, (int16_t)y0, 1}, {(int16_t)x1, (int16_t)y1, 1}, {(int16_t)x2, (int16_t)y2, 1}};
    es_contour(s, p, 3, cw);
}

// Clean geometric button letters scaled around (cx, cy) with height 2*hh.
// fg_cw = 1 draws solid letter (for outlined buttons), fg_cw = 0 cuts out letter (for filled buttons).
static void es_letter(ExtShape *s, char ch, double cx, double cy, double sc, int fg_cw) {
    #define PT(px, py, onf) (ExtPt){(int16_t)lrint(cx + (px) * sc), (int16_t)lrint(cy + (py) * sc), (onf)}
    if (ch == 'A') {
        ExtPt out[8] = {
            PT(-340, -440, 1), PT(-82, 440, 1), PT(82, 440, 1), PT(340, -440, 1),
            PT(176, -440, 1), PT(118, -225, 1), PT(-118, -225, 1), PT(-176, -440, 1)
        };
        ExtPt hole[3] = { PT(-78, -85, 1), PT(0, 225, 1), PT(78, -85, 1) };
        es_contour(s, out, 8, fg_cw);
        es_contour(s, hole, 3, !fg_cw);
    } else if (ch == 'B') {
        ExtPt out[15] = {
            PT(-280, -440, 1), PT(-280, 440, 1), PT(50, 440, 1),
            PT(265, 440, 0), PT(265, 220, 1), PT(265, 55, 0), PT(125, 15, 1),
            PT(295, -20, 0), PT(295, -205, 1), PT(295, -440, 0), PT(65, -440, 1),
            PT(-280, -440, 1)
        };
        ExtPt h_top[7] = {
            PT(-125, 75, 1), PT(-125, 305, 1), PT(30, 305, 1),
            PT(115, 305, 0), PT(115, 190, 1), PT(115, 75, 0), PT(30, 75, 1)
        };
        ExtPt h_bot[7] = {
            PT(-125, -305, 1), PT(-125, -55, 1), PT(45, -55, 1),
            PT(140, -55, 0), PT(140, -180, 1), PT(140, -305, 0), PT(45, -305, 1)
        };
        es_contour(s, out, 11, fg_cw);
        es_contour(s, h_top, 7, !fg_cw);
        es_contour(s, h_bot, 7, !fg_cw);
    } else if (ch == 'X') {
        ExtPt out[12] = {
            PT(-330, 440, 1), PT(-148, 440, 1), PT(0, 138, 1), PT(148, 440, 1),
            PT(330, 440, 1), PT(96, 0, 1), PT(340, -440, 1), PT(156, -440, 1),
            PT(0, -138, 1), PT(-156, -440, 1), PT(-340, -440, 1), PT(-96, 0, 1)
        };
        es_contour(s, out, 12, fg_cw);
    } else if (ch == 'Y') {
        ExtPt out[9] = {
            PT(-340, 440, 1), PT(-152, 440, 1), PT(0, 88, 1), PT(152, 440, 1),
            PT(340, 440, 1), PT(82, -85, 1), PT(82, -440, 1), PT(-82, -440, 1), PT(-82, -85, 1)
        };
        es_contour(s, out, 9, fg_cw);
    } else if (ch == 'L') {
        ExtPt out[6] = {
            PT(-250, -440, 1), PT(-250, 440, 1), PT(-85, 440, 1),
            PT(-85, -290, 1), PT(260, -290, 1), PT(260, -440, 1)
        };
        es_contour(s, out, 6, fg_cw);
    } else if (ch == 'R') {
        ExtPt out[11] = {
            PT(-280, -440, 1), PT(-280, 440, 1), PT(60, 440, 1),
            PT(285, 440, 0), PT(285, 175, 1), PT(285, -35, 0), PT(125, -75, 1),
            PT(305, -440, 1), PT(125, -440, 1), PT(-30, -95, 1), PT(-120, -95, 1),
        };
        ExtPt out2[12];
        for (int i = 0; i < 11; i++) out2[i] = out[i];
        out2[11] = PT(-120, -440, 1);
        ExtPt h_top[7] = {
            PT(-120, 45, 1), PT(-120, 300, 1), PT(45, 300, 1),
            PT(130, 300, 0), PT(130, 172, 1), PT(130, 45, 0), PT(45, 45, 1)
        };
        es_contour(s, out2, 12, fg_cw);
        es_contour(s, h_top, 7, !fg_cw);
    } else if (ch == 'Z') {
        ExtPt out[10] = {
            PT(-290, 440, 1), PT(290, 440, 1), PT(290, 295, 1), PT(-95, -290, 1),
            PT(300, -290, 1), PT(300, -440, 1), PT(-300, -440, 1), PT(-300, -295, 1),
            PT(85, 290, 1), PT(-290, 290, 1)
        };
        es_contour(s, out, 10, fg_cw);
    } else if (ch == 'S') {
        // Clean geometric S curve with quadratic Bezier caps
        ExtPt out[20] = {
            PT(255, 250, 1), PT(130, 210, 1),
            PT(105, 310, 0), PT(0, 310, 1),
            PT(-120, 310, 0), PT(-120, 205, 1),
            PT(-120, 120, 0), PT(30, 75, 1),
            PT(290, 0, 0), PT(290, -195, 1),
            PT(290, -455, 0), PT(10, -455, 1),
            PT(-260, -455, 0), PT(-290, -210, 1),
            PT(-145, -175, 1),
            PT(-125, -310, 0), PT(10, -310, 1),
            PT(135, -310, 0), PT(135, -195, 1),
            PT(135, -95, 0),
        };
        ExtPt out_s[24] = {
            PT(265, 235, 1), PT(125, 195, 1),
            PT(100, 305, 0), PT(-5, 305, 1),
            PT(-115, 305, 0), PT(-115, 205, 1),
            PT(-115, 120, 0), PT(35, 72, 1),
            PT(290, -8, 0), PT(290, -195, 1),
            PT(290, -450, 0), PT(10, -450, 1),
            PT(-255, -450, 0), PT(-285, -215, 1),
            PT(-135, -180, 1),
            PT(-115, -305, 0), PT(10, -305, 1),
            PT(135, -305, 0), PT(135, -195, 1),
            PT(135, -105, 0), PT(-25, -55, 1),
            PT(-270, 20, 0), PT(-270, 205, 1),
            PT(-270, 450, 0),
        };
        // Add top apex on-curve point so loop closes cleanly
        ExtPt out_s2[26];
        for (int i = 0; i < 24; i++) out_s2[i] = out_s[i];
        out_s2[24] = PT(-5, 450, 1);
        out_s2[25] = PT(235, 450, 0);
        (void)out;
        es_contour(s, out_s2, 26, fg_cw);
    }
    #undef PT
}

static void es_circle_badge(ExtShape *s, int filled) {
    es_circle(s, 1024.0, 728.0, 860.0, 1);
    if (!filled) es_circle(s, 1024.0, 728.0, 710.0, 0);
}

static void es_shoulder_badge(ExtShape *s, int is_right, int filled) {
    double rtl = is_right ? 170.0 : 580.0;
    double rtr = is_right ? 580.0 : 170.0;
    es_rrect4(s, 104.0, 88.0, 1944.0, 1368.0, rtl, rtr, 140.0, 140.0, 1);
    if (!filled) {
        double itl = is_right ? 80.0 : 450.0;
        double itr = is_right ? 450.0 : 80.0;
        es_rrect4(s, 244.0, 228.0, 1804.0, 1228.0, itl, itr, 60.0, 60.0, 0);
    }
}

static void es_trigger_badge(ExtShape *s, int filled) {
    es_rrect4(s, 104.0, 48.0, 1944.0, 1408.0, 460.0, 460.0, 170.0, 170.0, 1);
    if (!filled) es_rrect4(s, 244.0, 188.0, 1804.0, 1268.0, 330.0, 330.0, 80.0, 80.0, 0);
}

static void es_pill_badge(ExtShape *s, int filled) {
    es_rrect4(s, 104.0, 168.0, 1944.0, 1288.0, 520.0, 520.0, 520.0, 520.0, 1);
    if (!filled) es_rrect4(s, 244.0, 308.0, 1804.0, 1148.0, 380.0, 380.0, 380.0, 380.0, 0);
}

static void es_four_dots(ExtShape *s, int highlight_idx, int all_filled) {
    // 0: East (A), 1: South (B), 2: North (X), 3: West (Y)
    static const int dx[4] = { 540,    0,    0, -540};
    static const int dy[4] = {   0, -540,  540,    0};
    for (int i = 0; i < 4; i++) {
        double cx = 1024.0 + dx[i], cy = 728.0 + dy[i];
        es_circle(s, cx, cy, 265.0, 1);
        int solid = all_filled || (highlight_idx == i);
        if (!solid) es_circle(s, cx, cy, 155.0, 0);
    }
}

static void es_dir_circle(ExtShape *s, int dir, int filled) {
    // dir: 0=Up, 1=Down, 2=Left, 3=Right
    es_circle_badge(s, filled);
    int fg = !filled;
    int cx = 1024, cy = 728;
    if (dir == 0) es_tri(s, cx, cy + 430, cx - 390, cy - 270, cx + 390, cy - 270, fg);
    else if (dir == 1) es_tri(s, cx, cy - 430, cx + 390, cy + 270, cx - 390, cy + 270, fg);
    else if (dir == 2) es_tri(s, cx - 430, cy, cx + 270, cy + 390, cx + 270, cy - 390, fg);
    else es_tri(s, cx + 430, cy, cx - 270, cy - 390, cx - 270, cy + 390, fg);
}

static void es_home_badge(ExtShape *s, int filled) {
    es_circle_badge(s, filled);
    int fg = !filled;
    int cx = 1024, cy = 728;
    // House silhouette (pitched roof + walls)
    ExtPt house[7] = {
        {(int16_t)(cx),       (int16_t)(cy + 460), 1},
        {(int16_t)(cx + 470), (int16_t)(cy + 30),  1},
        {(int16_t)(cx + 320), (int16_t)(cy + 30),  1},
        {(int16_t)(cx + 320), (int16_t)(cy - 390), 1},
        {(int16_t)(cx - 320), (int16_t)(cy - 390), 1},
        {(int16_t)(cx - 320), (int16_t)(cy + 30),  1},
        {(int16_t)(cx - 470), (int16_t)(cy + 30),  1},
    };
    es_contour(s, house, 7, fg);
    es_rect(s, cx - 115, cy - 390, cx + 115, cy - 80, !fg);
}

static void es_capture_badge(ExtShape *s, int filled) {
    es_rrect4(s, 184.0, -112.0, 1864.0, 1568.0, 260.0, 260.0, 260.0, 260.0, 1);
    if (filled) {
        es_circle(s, 1024.0, 728.0, 430.0, 0);
    } else {
        es_rrect4(s, 324.0, 28.0, 1724.0, 1428.0, 150.0, 150.0, 150.0, 150.0, 0);
        es_circle(s, 1024.0, 728.0, 420.0, 1);
        es_circle(s, 1024.0, 728.0, 270.0, 0);
    }
}

static void es_power_glyph(ExtShape *s, int in_circle, int filled) {
    int fg = 1;
    double scale = 1.0;
    if (in_circle) {
        es_circle_badge(s, filled);
        fg = !filled;
        scale = 0.62;
    }
    double cx = 1024.0, cy = 728.0;
    // Open C-arc + top bar: draw outer ring - inner ring, or simplified top bar + ring with top gap
    double ro = 660.0 * scale, ri = 470.0 * scale;
    const double pi = 3.14159265358979323846;
    ExtPt arc[22];
    int n = 0;
    // Angles from 125 deg clockwise around bottom to 55 deg (290 deg sweep)
    for (int i = 0; i <= 8; i++) {
        double a = (125.0 + i * (290.0 / 8.0)) * (pi / 180.0);
        arc[n++] = (ExtPt){(int16_t)lrint(cx + ro * cos(a)), (int16_t)lrint(cy + ro * sin(a)), 1};
    }
    for (int i = 8; i >= 0; i--) {
        double a = (125.0 + i * (290.0 / 8.0)) * (pi / 180.0);
        arc[n++] = (ExtPt){(int16_t)lrint(cx + ri * cos(a)), (int16_t)lrint(cy + ri * sin(a)), 1};
    }
    es_contour(s, arc, n, fg);
    int bw = (int)lrint(95.0 * scale);
    es_rect(s, (int)cx - bw, (int)lrint(cy + 80.0 * scale), (int)cx + bw, (int)lrint(cy + 740.0 * scale), fg);
}

static void es_stick_badge(ExtShape *s, char label, int press, int rotate, int filled) {
    double cx = 1024.0, cy = press ? 590.0 : 728.0;
    double r_base = (press || rotate) ? 680.0 : 860.0;
    double r_cap  = (press || rotate) ? 480.0 : 620.0;
    // Outer base ring
    es_circle(s, cx, cy, r_base, 1);
    es_circle(s, cx, cy, r_base - 110.0, 0);
    // Inner stick cap
    es_circle(s, cx, cy, r_cap, 1);
    if (!filled) es_circle(s, cx, cy, r_cap - 120.0, 0);
    if (label) es_letter(s, label, cx, cy, press ? 0.58 : 0.72, !filled);
    if (press) {
        // Downward press arrow above stick
        es_rect(s, 944, 1420, 1104, 1650, 1);
        es_tri(s, 1024, 1230, 814, 1450, 1234, 1450, 1);
    }
    if (rotate) {
        // Directional chevrons at left and right
        es_tri(s, 64, 728, 274, 918, 274, 538, 1);
        es_tri(s, 1984, 728, 1774, 538, 1774, 918, 1);
    }
}

static void es_dpad_badge(ExtShape *s, int mask, int filled) {
    // mask bits: 1=Up, 2=Down, 4=Left, 8=Right; 0 = neutral full cross
    int cx = 1024, cy = 728;
    if (mask == 0 && filled) {
        es_plus(s, cx, cy, 840, 275, 1);
        return;
    }
    // Outlined cross frame
    es_plus(s, cx, cy, 840, 275, 1);
    es_plus(s, cx, cy, 710, 145, 0);
    // Highlighted directional arms
    if (mask & 1) es_rect(s, cx - 195, cy + 160, cx + 195, cy + 750, 1);
    if (mask & 2) es_rect(s, cx - 195, cy - 750, cx + 195, cy - 160, 1);
    if (mask & 4) es_rect(s, cx - 750, cy - 195, cx - 160, cy + 195, 1);
    if (mask & 8) es_rect(s, cx + 160, cy - 195, cx + 750, cy + 195, 1);
}

static void es_controller_icon(ExtShape *s, int kind) {
    // 1: Joy-Con L, 2: Joy-Con R, 3: Dual Grip, 4: Handheld, 5: Pro Controller
    if (kind == 1) {
        es_rrect4(s, 624.0, -80.0, 1424.0, 1536.0, 340.0, 100.0, 100.0, 340.0, 1);
        es_circle(s, 1024.0, 1080.0, 165.0, 0);
        es_plus(s, 1024, 430, 180, 65, 0);
    } else if (kind == 2) {
        es_rrect4(s, 624.0, -80.0, 1424.0, 1536.0, 100.0, 340.0, 340.0, 100.0, 1);
        es_plus(s, 1024, 1080, 180, 65, 0);
        es_circle(s, 1024.0, 430.0, 165.0, 0);
    } else if (kind == 4) {
        es_rrect4(s, 104.0, 148.0, 1944.0, 1308.0, 240.0, 240.0, 240.0, 240.0, 1);
        es_rect(s, 444, 288, 1604, 1168, 0);
    } else {
        es_rrect4(s, 164.0, 88.0, 1884.0, 1368.0, 380.0, 380.0, 380.0, 380.0, 1);
        es_circle(s, 640.0, 860.0, 160.0, 0);
        es_circle(s, 1408.0, 580.0, 160.0, 0);
    }
}

static int build_nintendo_glyph(uint16_t cp, ExtShape *s) {
    es_init(s, 2048);
    // Legacy DS/3DS/WiiU aliases U+E000..U+E006
    if (cp == 0xE000) cp = 0xE0A0;
    else if (cp == 0xE001) cp = 0xE0A1;
    else if (cp == 0xE002) cp = 0xE0A2;
    else if (cp == 0xE003) cp = 0xE0A3;
    else if (cp == 0xE004) cp = 0xE0A4;
    else if (cp == 0xE005) cp = 0xE0A5;
    else if (cp == 0xE006) cp = 0xE0D0;

    switch (cp) {
        case 0x0020: s->adv = 600; return 1;
        case 0x003F: // '?' fallback in case queried directly on type 5
            es_circle_badge(s, 0);
            es_circle(s, 1024.0, 380.0, 95.0, 1);
            es_rect(s, 944, 560, 1104, 1120, 1);
            return 1;

        // Filled & Outlined A, B, X, Y
        case 0xE0A0: case 0xE0E0: { int f = (cp == 0xE0A0); es_circle_badge(s, f); es_letter(s, 'A', 1024, 728, 1.0, !f); return 1; }
        case 0xE0A1: case 0xE0E1: { int f = (cp == 0xE0A1); es_circle_badge(s, f); es_letter(s, 'B', 1024, 728, 1.0, !f); return 1; }
        case 0xE0A2: case 0xE0E2: { int f = (cp == 0xE0A2); es_circle_badge(s, f); es_letter(s, 'X', 1024, 728, 1.0, !f); return 1; }
        case 0xE0A3: case 0xE0E3: { int f = (cp == 0xE0A3); es_circle_badge(s, f); es_letter(s, 'Y', 1024, 728, 1.0, !f); return 1; }

        // L, R, ZL, ZR, SL, SR
        case 0xE0A4: case 0xE0E4: { int f = (cp == 0xE0A4); es_shoulder_badge(s, 0, f); es_letter(s, 'L', 1044, 718, 0.88, !f); return 1; }
        case 0xE0A5: case 0xE0E5: { int f = (cp == 0xE0A5); es_shoulder_badge(s, 1, f); es_letter(s, 'R', 1004, 718, 0.88, !f); return 1; }
        case 0xE0A6: case 0xE0E6: { int f = (cp == 0xE0A6); es_trigger_badge(s, f); es_letter(s, 'Z', 710, 728, 0.78, !f); es_letter(s, 'L', 1350, 728, 0.78, !f); return 1; }
        case 0xE0A7: case 0xE0E7: { int f = (cp == 0xE0A7); es_trigger_badge(s, f); es_letter(s, 'Z', 700, 728, 0.78, !f); es_letter(s, 'R', 1345, 728, 0.78, !f); return 1; }
        case 0xE0A8: case 0xE0E8: { int f = (cp == 0xE0A8); es_pill_badge(s, f); es_letter(s, 'S', 720, 728, 0.72, !f); es_letter(s, 'L', 1345, 728, 0.72, !f); return 1; }
        case 0xE0A9: case 0xE0E9: { int f = (cp == 0xE0A9); es_pill_badge(s, f); es_letter(s, 'S', 710, 728, 0.72, !f); es_letter(s, 'R', 1340, 728, 0.72, !f); return 1; }

        // 4-button diamond group & directional highlights (nx_a, nx_b, nx_x, nx_y)
        case 0xE0AA: es_four_dots(s, -1, 1); return 1;
        case 0xE0EA: es_four_dots(s, -1, 0); return 1;
        case 0xE0AB: es_four_dots(s, 0, 0); return 1; // East (nx_a)
        case 0xE0AC: es_four_dots(s, 1, 0); return 1; // South (nx_b)
        case 0xE0AD: es_four_dots(s, 2, 0); return 1; // North (nx_x)
        case 0xE0AE: es_four_dots(s, 3, 0); return 1; // West (nx_y)

        // Directional arrow buttons
        case 0xE0AF: case 0xE0EB: es_dir_circle(s, 0, cp == 0xE0AF); return 1;
        case 0xE0B0: case 0xE0EC: es_dir_circle(s, 1, cp == 0xE0B0); return 1;
        case 0xE0B1: case 0xE0ED: es_dir_circle(s, 2, cp == 0xE0B1); return 1;
        case 0xE0B2: case 0xE0EE: es_dir_circle(s, 3, cp == 0xE0B2); return 1;

        // Plus & Minus (bare and circled)
        case 0xE0B3: es_plus(s, 1024, 728, 680, 195, 1); return 1;
        case 0xE0EF: es_plus(s, 1024, 728, 720, 235, 1); es_plus(s, 1024, 728, 595, 110, 0); return 1;
        case 0xE0B4: es_rect(s, 344, 533, 1704, 923, 1); return 1;
        case 0xE0F0: es_rect(s, 304, 493, 1744, 963, 1); es_rect(s, 434, 623, 1614, 833, 0); return 1;
        case 0xE0B5: case 0xE0F1: { int f = (cp == 0xE0B5); es_circle_badge(s, f); es_plus(s, 1024, 728, 440, 115, !f); return 1; }
        case 0xE0B6: case 0xE0F2: { int f = (cp == 0xE0B6); es_circle_badge(s, f); es_rect(s, 584, 613, 1464, 843, !f); return 1; }

        // Power, Home, Capture
        case 0xE0B7: case 0xE0F3: es_power_glyph(s, 1, cp == 0xE0B7); return 1;
        case 0xE0B8: es_power_glyph(s, 0, 1); return 1;
        case 0xE0B9: case 0xE0F4: es_home_badge(s, cp == 0xE0B9); return 1;
        case 0xE0BA: case 0xE0F5: es_capture_badge(s, cp == 0xE0BA); return 1;

        // Control Sticks
        case 0xE0C0: case 0xE100: es_stick_badge(s, 0,   0, 0, cp == 0xE0C0); return 1;
        case 0xE0C1: case 0xE101: es_stick_badge(s, 'L', 0, 0, cp == 0xE0C1); return 1;
        case 0xE0C2: case 0xE102: es_stick_badge(s, 'R', 0, 0, cp == 0xE0C2); return 1;
        case 0xE0C3: case 0xE103: es_stick_badge(s, 0,   0, 1, cp == 0xE0C3); return 1;
        case 0xE0C4: case 0xE104: es_stick_badge(s, 'L', 1, 0, cp == 0xE0C4); return 1;
        case 0xE0C5: case 0xE105: es_stick_badge(s, 'R', 1, 0, cp == 0xE0C5); return 1;

        // D-Pad / Cross-Key
        case 0xE0D0: es_dpad_badge(s, 0, 1); return 1;
        case 0xE110: es_dpad_badge(s, 0, 0); return 1;
        case 0xE0D1: case 0xE111: es_dpad_badge(s, 1, 0); return 1;
        case 0xE0D2: case 0xE112: es_dpad_badge(s, 2, 0); return 1;
        case 0xE0D3: case 0xE113: es_dpad_badge(s, 4, 0); return 1;
        case 0xE0D4: case 0xE114: es_dpad_badge(s, 8, 0); return 1;
        case 0xE0D5: case 0xE115: es_dpad_badge(s, 3, 0); return 1;
        case 0xE0D6: case 0xE116: es_dpad_badge(s, 12, 0); return 1;

        // Controller form-factor icons
        case 0xE121: es_controller_icon(s, 1); return 1;
        case 0xE122: es_controller_icon(s, 2); return 1;
        case 0xE123: case 0xE124: es_controller_icon(s, 3); return 1;
        case 0xE125: case 0xE126: es_controller_icon(s, 4); return 1;
        case 0xE127: case 0xE128: case 0xE129: case 0xE12A: case 0xE12B: case 0xE12C:
            es_controller_icon(s, 5); return 1;
        default:
            return 0;
    }
}

static uint32_t sfnt_checksum(const uint8_t *p, size_t len) {
    uint32_t sum = 0;
    size_t i = 0;
    for (; i + 4 <= len; i += 4)
        sum += ((uint32_t)p[i] << 24) | ((uint32_t)p[i + 1] << 16) | ((uint32_t)p[i + 2] << 8) | p[i + 3];
    if (i < len) {
        uint32_t tail = 0;
        for (size_t j = 0; i + j < len; j++) tail |= (uint32_t)p[i + j] << (24 - 8 * j);
        sum += tail;
    }
    return sum;
}

// Builds a complete, valid TrueType sfnt binary in a malloc'd buffer (caller frees).
static uint8_t *ov_build_nintendo_ext_ttf(size_t *out_size) {
    uint16_t cps[128];
    int ncps = 0;
    cps[ncps++] = 0x0020;
    cps[ncps++] = 0x003F;
    for (uint32_t cp = 0xE000; cp <= 0xE12C; cp++) {
        ExtShape tmp;
        if (build_nintendo_glyph((uint16_t)cp, &tmp))
            cps[ncps++] = (uint16_t)cp;
    }
    const int num_glyphs = 1 + ncps; // gid 0 = .notdef, gid 1..ncps = cps[0..ncps-1]

    ExtBuf glyf = {0}, loca = {0}, hmtx = {0};
    int16_t font_xmin = 32767, font_ymin = 32767, font_xmax = -32768, font_ymax = -32768;
    uint16_t adv_max = 0, max_pts = 0, max_cont = 0;

    for (int gid = 0; gid < num_glyphs; gid++) {
        ExtShape sh;
        if (gid == 0) {
            es_init(&sh, 1200);
            es_rect(&sh, 160, 0, 1040, 1456, 1);
            es_rect(&sh, 300, 140, 900, 1316, 0);
        } else {
            build_nintendo_glyph(cps[gid - 1], &sh);
        }
        eb_u32(&loca, (uint32_t)glyf.len);
        if (sh.adv > adv_max) adv_max = sh.adv;
        if (sh.ncont == 0) {
            eb_u16(&hmtx, sh.adv);
            eb_i16(&hmtx, 0);
            continue;
        }
        if ((uint16_t)sh.npts > max_pts) max_pts = (uint16_t)sh.npts;
        if ((uint16_t)sh.ncont > max_cont) max_cont = (uint16_t)sh.ncont;

        int16_t xmin = sh.pts[0].x, xmax = sh.pts[0].x, ymin = sh.pts[0].y, ymax = sh.pts[0].y;
        for (int i = 1; i < sh.npts; i++) {
            if (sh.pts[i].x < xmin) xmin = sh.pts[i].x;
            if (sh.pts[i].x > xmax) xmax = sh.pts[i].x;
            if (sh.pts[i].y < ymin) ymin = sh.pts[i].y;
            if (sh.pts[i].y > ymax) ymax = sh.pts[i].y;
        }
        if (xmin < font_xmin) font_xmin = xmin;
        if (ymin < font_ymin) font_ymin = ymin;
        if (xmax > font_xmax) font_xmax = xmax;
        if (ymax > font_ymax) font_ymax = ymax;

        eb_u16(&hmtx, sh.adv);
        eb_i16(&hmtx, xmin);

        eb_i16(&glyf, (int16_t)sh.ncont);
        eb_i16(&glyf, xmin);
        eb_i16(&glyf, ymin);
        eb_i16(&glyf, xmax);
        eb_i16(&glyf, ymax);
        for (int i = 0; i < sh.ncont; i++) eb_u16(&glyf, sh.ends[i]);
        eb_u16(&glyf, 0); // instructionLength = 0
        for (int i = 0; i < sh.npts; i++) eb_u8(&glyf, sh.pts[i].on ? 0x01 : 0x00);
        int16_t px = 0, py = 0;
        for (int i = 0; i < sh.npts; i++) { eb_i16(&glyf, (int16_t)(sh.pts[i].x - px)); px = sh.pts[i].x; }
        for (int i = 0; i < sh.npts; i++) { eb_i16(&glyf, (int16_t)(sh.pts[i].y - py)); py = sh.pts[i].y; }
        eb_pad4(&glyf);
    }
    eb_u32(&loca, (uint32_t)glyf.len);

    // Coalesce contiguous codepoints into cmap segments
    uint16_t seg_start[64], seg_end[64], seg_gid[64];
    int nsegs = 0;
    for (int i = 0; i < ncps; ) {
        int j = i;
        while (j + 1 < ncps && cps[j + 1] == cps[j] + 1) j++;
        seg_start[nsegs] = cps[i];
        seg_end[nsegs] = cps[j];
        seg_gid[nsegs] = (uint16_t)(1 + i);
        nsegs++;
        i = j + 1;
    }
    const int nsegs4 = nsegs + 1; // + 0xFFFF terminator

    ExtBuf cmap4 = {0};
    eb_u16(&cmap4, 4);
    eb_u16(&cmap4, (uint16_t)(16 + 8 * nsegs4));
    eb_u16(&cmap4, 0);
    eb_u16(&cmap4, (uint16_t)(nsegs4 * 2));
    uint16_t sr4 = 2, es4 = 0;
    while ((sr4 << 1) <= nsegs4 * 2) { sr4 <<= 1; es4++; }
    eb_u16(&cmap4, sr4);
    eb_u16(&cmap4, es4);
    eb_u16(&cmap4, (uint16_t)(nsegs4 * 2 - sr4));
    for (int i = 0; i < nsegs; i++) eb_u16(&cmap4, seg_end[i]);
    eb_u16(&cmap4, 0xFFFF);
    eb_u16(&cmap4, 0); // reservedPad
    for (int i = 0; i < nsegs; i++) eb_u16(&cmap4, seg_start[i]);
    eb_u16(&cmap4, 0xFFFF);
    for (int i = 0; i < nsegs; i++) eb_u16(&cmap4, (uint16_t)(seg_gid[i] - seg_start[i]));
    eb_u16(&cmap4, 1); // 0xFFFF + 1 = 0
    for (int i = 0; i < nsegs4; i++) eb_u16(&cmap4, 0);

    ExtBuf cmap12 = {0};
    eb_u16(&cmap12, 12);
    eb_u16(&cmap12, 0);
    eb_u32(&cmap12, (uint32_t)(16 + 12 * nsegs));
    eb_u32(&cmap12, 0);
    eb_u32(&cmap12, (uint32_t)nsegs);
    for (int i = 0; i < nsegs; i++) {
        eb_u32(&cmap12, seg_start[i]);
        eb_u32(&cmap12, seg_end[i]);
        eb_u32(&cmap12, seg_gid[i]);
    }

    ExtBuf cmap = {0};
    eb_u16(&cmap, 0);
    eb_u16(&cmap, 3);
    uint32_t off_fmt4 = 4 + 3 * 8;
    uint32_t off_fmt12 = off_fmt4 + (uint32_t)cmap4.len;
    eb_u16(&cmap, 0); eb_u16(&cmap, 3);  eb_u32(&cmap, off_fmt4);
    eb_u16(&cmap, 3); eb_u16(&cmap, 1);  eb_u32(&cmap, off_fmt4);
    eb_u16(&cmap, 3); eb_u16(&cmap, 10); eb_u32(&cmap, off_fmt12);
    eb_bytes(&cmap, cmap4.buf, cmap4.len);
    eb_bytes(&cmap, cmap12.buf, cmap12.len);
    free(cmap4.buf);
    free(cmap12.buf);

    // head (54 bytes)
    ExtBuf head = {0};
    eb_u32(&head, 0x00010000u); // version
    eb_u32(&head, 0x00010000u); // fontRevision
    eb_u32(&head, 0);           // checkSumAdjustment (patched at end)
    eb_u32(&head, 0x5F0F3CF5u); // magicNumber
    eb_u16(&head, 0x0003u);     // flags: baseline y=0, lsb at x=xMin
    eb_u16(&head, 2048);        // unitsPerEm
    eb_u32(&head, 0); eb_u32(&head, 0xDC65A680u); // created
    eb_u32(&head, 0); eb_u32(&head, 0xDC65A680u); // modified
    eb_i16(&head, font_xmin);
    eb_i16(&head, font_ymin);
    eb_i16(&head, font_xmax);
    eb_i16(&head, font_ymax);
    eb_u16(&head, 0);           // macStyle
    eb_u16(&head, 8);           // lowestRecPPEM
    eb_i16(&head, 2);           // fontDirectionHint
    eb_i16(&head, 1);           // indexToLocFormat = 1 (uint32_t loca)
    eb_i16(&head, 0);           // glyphDataFormat

    // hhea (36 bytes)
    ExtBuf hhea = {0};
    eb_u32(&hhea, 0x00010000u);
    eb_i16(&hhea, 1900);        // ascender (matches Roboto-Medium)
    eb_i16(&hhea, -500);        // descender
    eb_i16(&hhea, 0);           // lineGap
    eb_u16(&hhea, adv_max);
    eb_i16(&hhea, font_xmin);
    eb_i16(&hhea, 0);
    eb_i16(&hhea, font_xmax);
    eb_i16(&hhea, 1);           // caretSlopeRise
    eb_i16(&hhea, 0);           // caretSlopeRun
    eb_i16(&hhea, 0);           // caretOffset
    eb_i16(&hhea, 0); eb_i16(&hhea, 0); eb_i16(&hhea, 0); eb_i16(&hhea, 0);
    eb_i16(&hhea, 0);           // metricDataFormat
    eb_u16(&hhea, (uint16_t)num_glyphs);

    // maxp (32 bytes, version 1.0)
    ExtBuf maxp = {0};
    eb_u32(&maxp, 0x00010000u);
    eb_u16(&maxp, (uint16_t)num_glyphs);
    eb_u16(&maxp, max_pts);
    eb_u16(&maxp, max_cont);
    eb_u16(&maxp, 0); eb_u16(&maxp, 0);
    eb_u16(&maxp, 2);           // maxZones
    for (int i = 0; i < 9; i++) eb_u16(&maxp, 0);

    // OS/2 (96 bytes, version 4)
    ExtBuf os2 = {0};
    eb_u16(&os2, 4);            // version
    eb_i16(&os2, 2048);         // xAvgCharWidth
    eb_u16(&os2, 500);          // usWeightClass (Medium)
    eb_u16(&os2, 5);            // usWidthClass (Normal)
    eb_u16(&os2, 0);            // fsType
    eb_i16(&os2, 1300); eb_i16(&os2, 1400); eb_i16(&os2, 0); eb_i16(&os2, 280);
    eb_i16(&os2, 1300); eb_i16(&os2, 1400); eb_i16(&os2, 0); eb_i16(&os2, 950);
    eb_i16(&os2, 102); eb_i16(&os2, 512);
    eb_i16(&os2, 0);            // sFamilyClass
    for (int i = 0; i < 10; i++) eb_u8(&os2, 0); // panose
    eb_u32(&os2, 1); eb_u32(&os2, 0x10000000u); eb_u32(&os2, 0); eb_u32(&os2, 0); // ulUnicodeRange (PUA bit 60 -> word1 bit 28)
    eb_bytes(&os2, "UN2P", 4);  // achVendID
    eb_u16(&os2, 0x0040u);      // fsSelection (REGULAR)
    eb_u16(&os2, 0x0020u);      // usFirstCharIndex
    eb_u16(&os2, 0xE12Cu);      // usLastCharIndex
    eb_i16(&os2, 1536);         // sTypoAscender
    eb_i16(&os2, -512);         // sTypoDescender
    eb_i16(&os2, 0);            // sTypoLineGap
    eb_u16(&os2, 1946);         // usWinAscent
    eb_u16(&os2, 512);          // usWinDescent
    eb_u32(&os2, 1); eb_u32(&os2, 0); // ulCodePageRange
    eb_i16(&os2, 1082);         // sxHeight
    eb_i16(&os2, 1456);         // sCapHeight
    eb_u16(&os2, 0);            // usDefaultChar
    eb_u16(&os2, 0x0020u);      // usBreakChar
    eb_u16(&os2, 1);            // usMaxContext

    // name (minimal Format 0 with Family, Subfamily, Full, PostScript in Platform 3 UTF-16BE)
    static const char *const nstrs[4] = {"NintendoExtHost", "Regular", "NintendoExtHost Regular", "NintendoExtHost-Regular"};
    static const uint16_t nids[4] = {1, 2, 4, 6};
    ExtBuf name = {0}, nstr = {0};
    eb_u16(&name, 0);
    eb_u16(&name, 4);
    eb_u16(&name, (uint16_t)(6 + 4 * 12));
    for (int i = 0; i < 4; i++) {
        size_t slen = strlen(nstrs[i]);
        eb_u16(&name, 3); eb_u16(&name, 1); eb_u16(&name, 0x0409); eb_u16(&name, nids[i]);
        eb_u16(&name, (uint16_t)(slen * 2));
        eb_u16(&name, (uint16_t)nstr.len);
        for (size_t k = 0; k < slen; k++) eb_u16(&nstr, (uint8_t)nstrs[i][k]);
    }
    eb_bytes(&name, nstr.buf, nstr.len);
    free(nstr.buf);

    // post (32 bytes, version 3.0)
    ExtBuf post = {0};
    eb_u32(&post, 0x00030000u);
    eb_u32(&post, 0);           // italicAngle
    eb_i16(&post, -150);        // underlinePosition
    eb_i16(&post, 100);         // underlineThickness
    eb_u32(&post, 0);           // isFixedPitch
    eb_u32(&post, 0); eb_u32(&post, 0); eb_u32(&post, 0); eb_u32(&post, 0);

    // Assemble sfnt with strictly sorted 4-byte ASCII tags
    struct { const char *tag; ExtBuf *b; } tabs[10] = {
        {"OS/2", &os2},
        {"cmap", &cmap},
        {"glyf", &glyf},
        {"head", &head},
        {"hhea", &hhea},
        {"hmtx", &hmtx},
        {"loca", &loca},
        {"maxp", &maxp},
        {"name", &name},
        {"post", &post},
    };

    ExtBuf out = {0};
    eb_u32(&out, 0x00010000u);
    eb_u16(&out, 10);
    eb_u16(&out, 128); // searchRange = 8 * 16
    eb_u16(&out, 3);   // entrySelector = log2(8)
    eb_u16(&out, 32);  // rangeShift = 10 * 16 - 128

    uint32_t cur_off = 12 + 10 * 16;
    uint32_t head_off = 0;
    for (int i = 0; i < 10; i++) {
        uint32_t csum = sfnt_checksum(tabs[i].b->buf, tabs[i].b->len);
        eb_bytes(&out, tabs[i].tag, 4);
        eb_u32(&out, csum);
        eb_u32(&out, cur_off);
        eb_u32(&out, (uint32_t)tabs[i].b->len);
        if (!memcmp(tabs[i].tag, "head", 4)) head_off = cur_off;
        cur_off += ((uint32_t)tabs[i].b->len + 3u) & ~3u;
    }
    for (int i = 0; i < 10; i++) {
        eb_bytes(&out, tabs[i].b->buf, tabs[i].b->len);
        eb_pad4(&out);
        free(tabs[i].b->buf);
    }

    uint32_t adj = 0xB1B0AFBAu - sfnt_checksum(out.buf, out.len);
    out.buf[head_off + 8]  = (uint8_t)(adj >> 24);
    out.buf[head_off + 9]  = (uint8_t)(adj >> 16);
    out.buf[head_off + 10] = (uint8_t)(adj >> 8);
    out.buf[head_off + 11] = (uint8_t)adj;

    *out_size = out.len;
    return out.buf;
}

#endif
