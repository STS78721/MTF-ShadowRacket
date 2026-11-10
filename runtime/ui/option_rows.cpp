// Two-pane settings pages (option_rows.h): sleek Universal NS2 Midnight Glass cards on the left,
// and an inspector sidebar card on the right showing live/restart status badges and detailed notes.
#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "imgui.h"
#include "imgui_internal.h"   // SetKeyOwner, SetFocusID, NavCursorVisible

#include "ui/option_rows.h"

extern "C" {
#include "cfg.h"
#include "platform/platform.h"
#include "ui_text.h"
void rt_log(const char *fmt, ...) __attribute__((format(printf, 1, 2)));
}

// Switch 2 Midnight Obsidian + Electric Cyan accent palette
static const ImU32 kAccent     = IM_COL32(56, 189, 248, 255);    // Electric Switch-2 Cyan (#38BDF8)
static const ImU32 kAccentSoft = IM_COL32(56, 189, 248, 42);
static const ImU32 kAccentDim  = IM_COL32(56, 189, 248, 130);
static const ImU32 kLiveCol    = IM_COL32(52, 211, 153, 255);    // Emerald live badge (#34D399)
static const ImU32 kWarnCol    = IM_COL32(251, 191, 36, 255);    // Warm amber restart/env (#FBBF24)
static const ImU32 kTextBright = IM_COL32(241, 245, 249, 255);   // Slate 100
static const ImU32 kDim        = IM_COL32(148, 163, 184, 255);   // Slate 400
static const ImU32 kGrey       = IM_COL32(100, 116, 139, 255);   // Slate 500
static const ImU32 kCardBg     = IM_COL32(17, 25, 40, 195);
static const ImU32 kCardHover  = IM_COL32(24, 36, 58, 235);
static const ImU32 kCardBorder = IM_COL32(51, 65, 85, 160);

static float g_scale = 1;
static bool g_focus_req, g_take_first;
static char g_focus_key[64];
static bool g_held;
static float g_bottom;
static bool g_disable_next;
static UiTextId g_disable_note;

enum DescKind { DESC_LIVE = 0, DESC_RESTART = 1, DESC_ENV = 2, DESC_DISABLED = 3 };
struct Desc {
    char title[128];
    char text[UI_DESC_BYTES];
    DescKind kind;
    char key_note[96];
};
static Desc g_hover, g_focus, g_first, g_shown;

static void desc_set_raw(Desc &d, const char *title, const char *desc, const char *key, const CfgMeta *m,
                         const char *disabled) {
    snprintf(d.title, sizeof d.title, "%s", title ? title : "");
    snprintf(d.text, sizeof d.text, "%s", desc ? desc : "");
    d.key_note[0] = 0;
    if (disabled) {
        d.kind = DESC_DISABLED;
        snprintf(d.key_note, sizeof d.key_note, "%s", disabled);
    } else if (cfg_from_env(key)) {
        d.kind = DESC_ENV;
        snprintf(d.key_note, sizeof d.key_note, "%s %s", menu_text(UI_MENU_SET_BY_ENV), key);
    } else if (m && !m->live) {
        d.kind = DESC_RESTART;
        snprintf(d.key_note, sizeof d.key_note, "%s", menu_text(UI_MENU_AFTER_RESTART));
    } else {
        d.kind = DESC_LIVE;
        snprintf(d.key_note, sizeof d.key_note, "LIVE - Applies immediately");
    }
}

void opt_focus_first(void) { g_focus_req = true; }
void opt_focus_key(const char *key) { snprintf(g_focus_key, sizeof g_focus_key, "%s", key); }
void opt_reserve_bottom(float h) { g_bottom = h; }

void opt_disable_next(UiTextId note) {
    g_disable_next = true;
    g_disable_note = note;
}

void opt_begin(const char *id, float scale) {
    g_scale = scale;
    g_take_first = g_focus_req;
    g_focus_req = false;
    if (g_take_first) ImGui::NavMoveRequestCancel();
    g_hover.text[0] = g_focus.text[0] = g_first.text[0] = 0;
    ImVec2 avail = ImGui::GetContentRegionAvail();
    avail.y -= g_bottom;
    ImGui::PushID(id);
    ImGui::BeginChild("##rows", ImVec2(avail.x * 0.62f, avail.y), ImGuiChildFlags_NavFlattened);
    ImGui::PushStyleVar(ImGuiStyleVar_ItemSpacing, ImVec2(ImGui::GetStyle().ItemSpacing.x, 7 * scale));
}

void opt_end(void) {
    ImGui::PopStyleVar();
    ImGui::EndChild();
    if (g_hover.text[0]) g_shown = g_hover;
    else if (g_focus.text[0]) g_shown = g_focus;
    else if (!g_shown.text[0]) g_shown = g_first;

    ImGui::SameLine(0, 0);
    ImVec2 p = ImGui::GetCursorScreenPos(), avail = ImGui::GetContentRegionAvail();
    avail.y -= g_bottom;
    float gap = 18 * g_scale;

    // Right-hand Inspector Glass Card
    ImVec2 card_min(p.x + gap, p.y);
    ImVec2 card_max(p.x + avail.x, p.y + avail.y);
    ImDrawList *dl = ImGui::GetWindowDrawList();
    dl->AddRectFilled(card_min, card_max, IM_COL32(13, 20, 33, 215), 11 * g_scale);
    dl->AddRect(card_min, card_max, IM_COL32(56, 189, 248, 55), 11 * g_scale, 0, 1.0f * g_scale);

    ImGui::SetCursorScreenPos(card_min);
    ImGui::PushStyleVar(ImGuiStyleVar_WindowPadding, ImVec2(18 * g_scale, 16 * g_scale));
    ImGui::BeginChild("##desc", ImVec2(avail.x - gap, avail.y), ImGuiChildFlags_AlwaysUseWindowPadding,
                      ImGuiWindowFlags_NoNav);
    ImGui::PopStyleVar();

    if (g_shown.title[0]) {
        ImGui::TextColored(ImVec4(0.22f, 0.74f, 0.97f, 1.0f), "%s", g_shown.title);
        ImGui::Dummy(ImVec2(0, 4 * g_scale));

        // Status pill badge
        if (g_shown.key_note[0]) {
            ImU32 bg = (g_shown.kind == DESC_LIVE)    ? IM_COL32(16, 185, 129, 38)
                     : (g_shown.kind == DESC_RESTART) ? IM_COL32(245, 158, 11, 38)
                                                      : IM_COL32(244, 63, 94, 42);
            ImU32 fg = (g_shown.kind == DESC_LIVE)    ? kLiveCol
                     : (g_shown.kind == DESC_RESTART) ? kWarnCol
                                                      : IM_COL32(251, 113, 133, 255);
            ImFont *f = ImGui::GetFont();
            float sfs = ImGui::GetFontSize() * 0.74f;
            ImVec2 bsz = f->CalcTextSizeA(sfs, FLT_MAX, 0, g_shown.key_note);
            ImVec2 bp = ImGui::GetCursorScreenPos();
            ImVec2 bp_max(bp.x + bsz.x + 16 * g_scale, bp.y + bsz.y + 8 * g_scale);
            ImDrawList *cdl = ImGui::GetWindowDrawList();
            cdl->AddRectFilled(bp, bp_max, bg, 6 * g_scale);
            cdl->AddRect(bp, bp_max, (fg & 0x00FFFFFFu) | 0x80000000u, 6 * g_scale, 0, 1.0f);
            cdl->AddText(f, sfs, ImVec2(bp.x + 8 * g_scale, bp.y + 4 * g_scale), fg, g_shown.key_note);
            ImGui::Dummy(ImVec2(bsz.x + 16 * g_scale, bsz.y + 14 * g_scale));
        }

        ImGui::GetWindowDrawList()->AddLine(
            ImVec2(ImGui::GetCursorScreenPos().x, ImGui::GetCursorScreenPos().y),
            ImVec2(card_max.x - 18 * g_scale, ImGui::GetCursorScreenPos().y),
            IM_COL32(51, 65, 85, 140), 1.0f);
        ImGui::Dummy(ImVec2(0, 6 * g_scale));
    }

    ImGui::PushTextWrapPos(0);
    ImGui::PushStyleColor(ImGuiCol_Text, ImVec4(0.84f, 0.89f, 0.95f, 1.0f));
    ImGui::TextUnformatted(g_shown.text);
    ImGui::PopStyleColor();
    ImGui::PopTextWrapPos();
    ImGui::EndChild();
    ImGui::PopID();
}

enum RowKind { ROW_STD = 0, ROW_TOGGLE = 1, ROW_SLIDER = 2 };
struct RowView {
    const char *value;
    bool is_default;
    bool arrows;
    const char *note;
    RowKind kind;
    bool toggle_on;
    float slider_frac;
};

static int row_impl(const char *key, const char *label_str, const char *desc_str, const RowView &v) {
    const CfgMeta *m = cfg_meta(key);
    const char *disabled = g_disable_next ? menu_text(g_disable_note) : NULL;
    g_disable_next = false;
    bool off = disabled || cfg_from_env(key) != 0;
    ImGui::PushID(key);
    ImVec2 p = ImGui::GetCursorScreenPos();
    float fs = ImGui::GetFontSize(), w = ImGui::GetContentRegionAvail().x;
    float h = floorf(fs * (v.kind == ROW_SLIDER ? 2.45f : 2.25f));

    ImGui::PushStyleColor(ImGuiCol_NavCursor, ImVec4(0, 0, 0, 0));
    bool clicked = ImGui::InvisibleButton("##row", ImVec2(w, h), ImGuiButtonFlags_EnableNav);
    ImGui::PopStyleColor();

    bool to_key = g_focus_key[0] && !strcmp(key, g_focus_key);
    if (g_take_first || to_key) {
        ImGui::SetFocusID(ImGui::GetItemID(), ImGui::GetCurrentWindow());
        ImGui::SetNavCursorVisible(true);
        if (g_take_first) ImGui::SetScrollY(0);
        else ImGui::ScrollToItem(ImGuiScrollFlags_KeepVisibleEdgeY);
        g_take_first = false;
        if (to_key) g_focus_key[0] = 0;
    }
    bool hov = ImGui::IsItemHovered(), foc = ImGui::IsItemFocused() && ImGui::GetCurrentContext()->NavCursorVisible;
    int step = clicked && !off ? 2 : 0;
    g_held = false;
    if (foc && !off) {
        if (ImGui::IsKeyPressed(ImGuiKey_GamepadDpadLeft) || ImGui::IsKeyPressed(ImGuiKey_LeftArrow)) step = -1;
        if (ImGui::IsKeyPressed(ImGuiKey_GamepadDpadRight) || ImGui::IsKeyPressed(ImGuiKey_RightArrow)) step = 1;
        static const ImGuiKey steps[] = {ImGuiKey_GamepadDpadLeft, ImGuiKey_GamepadDpadRight, ImGuiKey_LeftArrow,
                                         ImGuiKey_RightArrow};
        for (ImGuiKey k : steps) {
            if (ImGui::GetKeyData(k)->DownDuration > 1.0f) g_held = true;
            ImGui::SetKeyOwner(k, ImGui::GetItemID());
        }
    }

    if (foc) desc_set_raw(g_focus, label_str, desc_str, key, m, disabled);
    if (hov) desc_set_raw(g_hover, label_str, desc_str, key, m, disabled);
    if (!g_first.text[0]) desc_set_raw(g_first, label_str, desc_str, key, m, disabled);

    ImDrawList *dl = ImGui::GetWindowDrawList();
    ImFont *font = ImGui::GetFont();
    float r = 9 * g_scale, pad = 16 * g_scale, small = fs * 0.70f;
    bool active = hov || foc;

    dl->AddRectFilled(p, ImVec2(p.x + w, p.y + h), active ? kCardHover : kCardBg, r);
    dl->AddRect(p, ImVec2(p.x + w, p.y + h),
                active ? (off ? kAccentDim : kAccent) : IM_COL32(51, 65, 85, off ? 60 : 125), r, 0,
                active ? 1.75f * g_scale : 1.0f * g_scale);
    // Glowing cyan accent stripe on left edge of active card
    if (active && !off) {
        dl->AddRectFilled(ImVec2(p.x + 2 * g_scale, p.y + 6 * g_scale),
                          ImVec2(p.x + 5.5f * g_scale, p.y + h - 6 * g_scale), kAccent, 2 * g_scale);
    }

    float ty = p.y + fs * 0.28f, ny = p.y + fs * 1.32f;
    float right = p.x + w - pad;
    float value_left = right;

    if (v.kind == ROW_TOGGLE) {
        // Modern Pill Toggle Switch
        float pw = fs * 2.1f, ph = fs * 1.05f;
        float px = right - pw, py = p.y + (h - ph) * 0.5f;
        ImU32 track_col = off ? IM_COL32(51, 65, 85, 140)
                        : v.toggle_on ? IM_COL32(14, 165, 233, 235)
                                      : IM_COL32(30, 41, 59, 255);
        ImU32 border_col = off ? kGrey : v.toggle_on ? kAccent : IM_COL32(71, 85, 105, 200);
        dl->AddRectFilled(ImVec2(px, py), ImVec2(px + pw, py + ph), track_col, ph * 0.5f);
        dl->AddRect(ImVec2(px, py), ImVec2(px + pw, py + ph), border_col, ph * 0.5f, 0, 1.2f * g_scale);
        float kr = ph * 0.36f;
        float kx = v.toggle_on ? (px + pw - ph * 0.5f) : (px + ph * 0.5f);
        dl->AddCircleFilled(ImVec2(kx, py + ph * 0.5f), kr, off ? kDim : IM_COL32(255, 255, 255, 255));
        const char *st_txt = v.value;
        float stw = font->CalcTextSizeA(small, FLT_MAX, 0, st_txt).x;
        dl->AddText(font, small, ImVec2(px - stw - 10 * g_scale, p.y + (h - small) * 0.5f),
                    off ? kGrey : v.toggle_on ? kAccent : kDim, st_txt);
        value_left = px - stw - 16 * g_scale;
    } else {
        if (v.arrows && v.value[0]) {
            float aw = fs * 0.40f, gap = fs * 0.55f, cy = ty + fs * 0.52f;
            float rx = right - aw, lx = rx - gap - ImGui::CalcTextSize(v.value).x - gap - aw;
            ImU32 ac = off ? kGrey : active ? kAccent : kDim;
            dl->AddTriangleFilled(ImVec2(lx, cy), ImVec2(lx + aw, cy - aw * 0.72f), ImVec2(lx + aw, cy + aw * 0.72f), ac);
            dl->AddTriangleFilled(ImVec2(rx + aw, cy), ImVec2(rx, cy - aw * 0.72f), ImVec2(rx, cy + aw * 0.72f), ac);
            if (clicked && !off) {
                float mx = ImGui::GetIO().MousePos.x;
                if (mx >= lx - gap && mx <= lx + aw + gap) step = -1;
                else if (mx >= rx - gap && mx <= rx + aw + gap) step = 1;
            }
            right = rx - gap;
            value_left = lx;
        }
        if (v.value[0]) {
            float vx = right - ImGui::CalcTextSize(v.value).x;
            dl->AddText(ImVec2(vx, ty), off ? kGrey : v.is_default ? IM_COL32(203, 213, 225, 255) : kTextBright,
                        v.value);
            if (!v.arrows) value_left = vx;
        }
        if (v.kind == ROW_SLIDER) {
            float bw = fs * 6.2f, bh = 5.0f * g_scale;
            float bx = p.x + w - pad - bw, by = p.y + h - 10.0f * g_scale - bh;
            dl->AddRectFilled(ImVec2(bx, by), ImVec2(bx + bw, by + bh), IM_COL32(30, 41, 59, 255), bh * 0.5f);
            float f = v.slider_frac < 0 ? 0 : v.slider_frac > 1 ? 1 : v.slider_frac;
            if (f > 0.01f) {
                dl->AddRectFilled(ImVec2(bx, by), ImVec2(bx + bw * f, by + bh), off ? kGrey : kAccent, bh * 0.5f);
            }
            dl->AddCircleFilled(ImVec2(bx + bw * f, by + bh * 0.5f), bh * 0.95f, off ? kDim : kTextBright);
        } else if (v.note || v.is_default) {
            const char *t = v.note ? v.note : menu_text(UI_MENU_DEFAULT_MARK);
            float tw = font->CalcTextSizeA(small, FLT_MAX, 0, t).x;
            dl->AddText(font, small, ImVec2(right - tw, ny), v.note ? kAccent : kDim, t);
        }
    }

    ImVec4 clip(p.x, p.y, value_left - fs * 0.6f, p.y + h);
    dl->AddText(font, fs, ImVec2(p.x + pad, ty), off ? kGrey : kTextBright, label_str, NULL, 0, &clip);

    const char *note = disabled        ? disabled
                     : off             ? menu_text(UI_MENU_SET_BY_ENV)
                     : m && !m->live   ? menu_text(UI_MENU_AFTER_RESTART)
                                       : "Live setting";
    ImU32 note_col = (disabled || off) ? IM_COL32(251, 113, 133, 220)
                   : (m && !m->live)   ? IM_COL32(251, 191, 36, 200)
                                       : IM_COL32(52, 211, 153, 185);
    dl->AddText(font, small, ImVec2(p.x + pad, ny), note_col, note);
    ImGui::PopID();
    return off ? 0 : step;
}

static int row(const char *key, UiTextId label, UiTextId desc, const RowView &v) {
    return row_impl(key, menu_text(label), menu_text(desc), v);
}

static uint64_t g_save_at;
static bool g_save_logged;

static void apply(const char *key, const char *value) {
    if (*value) {
        cfg_set(key, value);
    } else {
        const char *k = key;
        cfg_reset(&k, 1);
    }
    opt_save_soon();
}

void opt_save_soon(void) { g_save_at = plat_now_ns() + 400000000ull; }

int opt_save_tick(int force) {
    if (!g_save_at || (!force && plat_now_ns() < g_save_at)) return g_save_at != 0;
    g_save_at = 0;
    if (!cfg_save() && !g_save_logged) {
        g_save_logged = true;
        rt_log("menu: could not write settings file; changed settings apply for this session");
    }
    return 0;
}

bool opt_toggle(const char *key, UiTextId label, UiTextId desc, bool inverted) {
    return opt_toggle_text(key, menu_text(label), menu_text(desc), inverted);
}

bool opt_toggle_text(const char *key, const char *label, const char *desc, bool inverted) {
    const CfgMeta *m = cfg_meta(key);
    bool set = cfg_bool(key) != 0, def = m && strcmp(m->def, "0") != 0;
    bool on = set != inverted;
    RowView v = {menu_text(on ? UI_MENU_ON : UI_MENU_OFF), set == def, false, NULL, ROW_TOGGLE, on, 0.0f};
    if (!row_impl(key, label, desc, v)) return false;
    apply(key, set ? "0" : "1");
    return true;
}

bool opt_button(const char *id, UiTextId label, UiTextId desc, const char *value) {
    RowView v = {value ? value : "", false, false, NULL, ROW_STD, false, 0.0f};
    return row(id, label, desc, v) == 2;
}

void opt_group(UiTextId title) {
    opt_group_text(menu_text(title));
}

void opt_group_text(const char *title) {
    ImGui::Dummy(ImVec2(0, 8 * g_scale));
    ImVec2 p = ImGui::GetCursorScreenPos();
    ImGui::TextColored(ImVec4(0.22f, 0.74f, 0.97f, 1.0f), "%s", title);
    ImGui::GetWindowDrawList()->AddLine(
        ImVec2(p.x, ImGui::GetCursorScreenPos().y - 2 * g_scale),
        ImVec2(p.x + ImGui::GetContentRegionAvail().x * 0.45f, ImGui::GetCursorScreenPos().y - 2 * g_scale),
        IM_COL32(56, 189, 248, 70), 1.0f);
    ImGui::Dummy(ImVec2(0, 2 * g_scale));
}

void opt_text(UiTextId text, bool warn) {
    ImGui::PushTextWrapPos(0);
    if (warn) ImGui::TextColored(ImVec4(0.98f, 0.75f, 0.24f, 1), "%s", menu_text(text));
    else ImGui::TextUnformatted(menu_text(text));
    ImGui::PopTextWrapPos();
}

bool opt_choice_list(const char *key, UiTextId label, const char *const *values, const char *const *names, int n,
                     UiTextId desc, int cur, const char *note) {
    const CfgMeta *m = cfg_meta(key);
    const char *now = cfg_value(key);
    if (cur < 0)
        for (int i = 0; i < n; i++)
            if (!strcmp(values[i], now)) cur = i;
    int def = -1;
    for (int i = 0; m && i < n; i++)
        if (!strcmp(values[i], m->def)) def = i;
    RowView v = {cur >= 0 ? names[cur] : now, cur == def, true, note, ROW_STD, false, 0.0f};
    int step = row(key, label, desc, v);
    if (!step || n <= 0) return false;
    int nv;
    if (cur < 0) nv = 0;
    else if (step == 2) nv = (cur + 1) % n;
    else nv = cur + step < 0 ? 0 : cur + step >= n ? n - 1 : cur + step;
    if (nv == cur) return false;
    apply(key, values[nv]);
    return true;
}

bool opt_choice(const char *key, UiTextId label, const UiTextId *names, int n, UiTextId desc, const char *note) {
    enum { MAX = 32 };
    const CfgMeta *m = cfg_meta(key);
    const char *values[MAX], *shown[MAX];
    char buf[256];
    int k = 0;
    if (m && !m->def[0]) values[k++] = "";
    snprintf(buf, sizeof buf, "%s", m && m->values ? m->values : "");
    for (char *s = buf, *e; *s && k < MAX; s = e) {
        e = strchr(s, '|');
        if (e) *e++ = 0;
        else e = s + strlen(s);
        values[k++] = s;
    }
    if (n > k) n = k;
    for (int i = 0; i < n; i++) shown[i] = menu_text(names[i]);
    return opt_choice_list(key, label, values, shown, n, desc, -1, note);
}

bool opt_slider(const char *key, UiTextId label, float lo, float hi, UiTextId desc, float step, const char *fmt) {
    const CfgMeta *m = cfg_meta(key);
    double v = cfg_double(key), def = m ? strtod(m->def, NULL) : lo;
    char shown[48];
    snprintf(shown, sizeof shown, fmt, v);
    float frac = (hi > lo) ? (float)((v - lo) / (hi - lo)) : 0.0f;
    RowView rv = {shown, fabs(v - def) < step * 0.01, true, NULL, ROW_SLIDER, false, frac};
    int s = row(key, label, desc, rv);
    if (!s) return false;
    int steps = g_held && (hi - lo) > 40 * step ? 10 : 1;
    double n = round(v / step) * step + (s == 2 ? step : s * step * steps);
    if (s == 2 && n > hi + step * 0.01) n = lo;
    n = n < lo ? lo : n > hi ? hi : n;
    if (fabs(n - v) < step * 0.01) return false;
    char out[32];
    if (step >= 1) snprintf(out, sizeof out, "%d", (int)lround(n));
    else snprintf(out, sizeof out, "%g", round(n / step) * step);
    apply(key, out);
    return true;
}

static void fit_text(ImDrawList *dl, float x0, float x1, float y, float h, ImU32 col, const char *t, bool centred) {
    ImFont *font = ImGui::GetFont();
    float fs = ImGui::GetFontSize(), room = x1 - x0, tw = font->CalcTextSizeA(fs, FLT_MAX, 0, t).x;
    if (tw > room) {
        fs = fmaxf(fs * room / tw, fs * 0.65f);
        tw = font->CalcTextSizeA(fs, FLT_MAX, 0, t).x;
    }
    float x = centred && tw < room ? x0 + (room - tw) * 0.5f : x0;
    ImVec4 clip(x0, y, x1, y + h);
    dl->AddText(font, fs, ImVec2(x, y + (h - fs) * 0.5f), col, t, NULL, 0, &clip);
}

static void bind_columns(float x, float w, float cx[3], float *cw) {
    float lw = floorf(w * 0.34f), gap = floorf(8 * g_scale);
    *cw = floorf((w - lw - gap * 3) / 3);
    for (int c = 0; c < 3; c++) cx[c] = x + lw + gap + c * (*cw + gap);
}

void opt_bind_header(UiTextId c0, UiTextId c1, UiTextId c2) {
    ImVec2 p = ImGui::GetCursorScreenPos();
    float w = ImGui::GetContentRegionAvail().x, cx[3], cw, fs = ImGui::GetFontSize() * 0.8f;
    bind_columns(p.x, w, cx, &cw);
    const UiTextId cols[3] = {c0, c1, c2};
    ImFont *font = ImGui::GetFont();
    for (int c = 0; c < 3; c++) {
        const char *t = menu_text(cols[c]);
        float tw = font->CalcTextSizeA(fs, FLT_MAX, 0, t).x;
        ImGui::GetWindowDrawList()->AddText(font, fs, ImVec2(cx[c] + (cw - tw) * 0.5f, p.y), kDim, t);
    }
    ImGui::Dummy(ImVec2(w, fs * 1.2f));
}

int opt_bind_row(const char *key, const char *label, UiTextId desc, const char *const cells[3], const bool enabled[3],
                 const char *note) {
    ImGui::PushID(key);
    ImVec2 p = ImGui::GetCursorScreenPos();
    float fs = ImGui::GetFontSize(), w = ImGui::GetContentRegionAvail().x, h = floorf(fs * 1.9f), cx[3], cw;
    bind_columns(p.x, w, cx, &cw);
    ImDrawList *dl = ImGui::GetWindowDrawList();
    float r = 8 * g_scale, pad = 6 * g_scale;
    fit_text(dl, p.x + 16 * g_scale, cx[0] - fs * 0.3f, p.y, h, kTextBright, label, false);
    int result = -1;
    bool row_foc = false, row_hov = false;
    for (int c = 0; c < 3; c++) {
        ImVec2 a(cx[c], p.y), b(cx[c] + cw, p.y + h);
        const char *t = cells[c] && cells[c][0] ? cells[c] : "-";
        if (!enabled[c]) {
            dl->AddRect(a, b, IM_COL32(51, 65, 85, 65), r);
            fit_text(dl, a.x + pad, b.x - pad, a.y, h, kGrey, t, true);
            continue;
        }
        ImGui::SetCursorScreenPos(a);
        ImGui::PushID(c);
        ImGui::PushStyleColor(ImGuiCol_NavCursor, ImVec4(0, 0, 0, 0));
        bool clicked = ImGui::InvisibleButton("##cell", ImVec2(cw, h), ImGuiButtonFlags_EnableNav);
        ImGui::PopStyleColor();
        char id[80];
        snprintf(id, sizeof id, "%s#%d", key, c);
        bool to_key = g_focus_key[0] && !strcmp(id, g_focus_key);
        if (g_take_first || to_key) {
            ImGui::SetFocusID(ImGui::GetItemID(), ImGui::GetCurrentWindow());
            ImGui::SetNavCursorVisible(true);
            if (g_take_first) ImGui::SetScrollY(0);
            else ImGui::ScrollToItem(ImGuiScrollFlags_KeepVisibleEdgeY);
            g_take_first = false;
            if (to_key) g_focus_key[0] = 0;
        }
        bool hov = ImGui::IsItemHovered(), foc = ImGui::IsItemFocused() && ImGui::GetCurrentContext()->NavCursorVisible;
        row_foc |= foc;
        row_hov |= hov;
        if (clicked) result = c;
        if (foc && (ImGui::IsKeyPressed(ImGuiKey_Delete, false) || ImGui::IsKeyPressed(ImGuiKey_Backspace, false) ||
                    ImGui::IsKeyPressed(ImGuiKey_GamepadFaceUp, false)))
            result = 10 + c;
        dl->AddRectFilled(a, b, hov || foc ? kCardHover : kCardBg, r);
        dl->AddRect(a, b, hov || foc ? kAccent : kCardBorder, r, 0, hov || foc ? 1.8f : 1.0f);
        fit_text(dl, a.x + pad, b.x - pad, a.y, h, kTextBright, t, true);
        ImGui::PopID();
    }
    char k[64];
    snprintf(k, sizeof k, "NS2_%s", key);
    if (row_foc) desc_set_raw(g_focus, label, menu_text(desc), k, NULL, note);
    if (row_hov) desc_set_raw(g_hover, label, menu_text(desc), k, NULL, note);
    if (!g_first.text[0]) desc_set_raw(g_first, label, menu_text(desc), k, NULL, note);
    ImGui::SetCursorScreenPos(p);
    ImGui::Dummy(ImVec2(w, h));
    ImGui::PopID();
    return result;
}
