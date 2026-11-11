// Game resolution: the size the game composes its frame in (its output: canvas, UI and swapchain) and the size of its
// 3D scene, above the shipped 1920x1080 and 1600x900. The game does the rendering itself, as with the community
// resolution mods (UltraCam, Visual Fixes): the patch sets output and scene (recomp/patches-v121.txt,
// patches-v143.txt; MacNativeGames games/totk/runtime/game_patches.c and game_patches_v143.c, MIT, Copyright (c) 2026
// MacNativeGames contributors) make the game read both sizes from the patch page, and the texture heap that holds the
// output- and scene-sized render targets grows with them.
//
// Settings, read at start: TOTK_OUTPUT_RES = <w>x<h> (default 1920x1080, the game's own), TOTK_RENDER_SCALE = the
// scene's size relative to the output: "game" (default, 5/6, the game's 1600x900 at 1080p) or a percentage; above 100
// the game supersamples its scene, which smooths edges (anti-aliasing) at the cost of GPU time. The game's own final
// pass (FSR 1 EASU) scales the scene to the output; the present scales the output to the window (vk_fsr.c).
//
// Patch page: +16 the scene size {w, h} as floats, +32 the output size and +48 the swapchain size as {w, h} in one
// 64-bit word, +40 the renderer (1.2.1) or display configuration (1.4.3) the patched code stores there.
// +56 the camera's aspect ratio as a float when the output is not 16:9 (set aspect), +60 the field-of-view factor
// (set fov, res_fov_live).
// 1.4.3 scales the scene it reads by output width / 1920 (a 2560x1440 output renders its 1600x900 scene at 2128x1200;
// MacNativeGames measured the same), so its page holds the wanted size divided by that factor and the game's 5/6 needs
// no scene patch. 1.2.1 renders the size it reads (1600x900 on a 2560x1440 output): its page holds the wanted size, and
// the scene set is on whenever the output differs from 1920x1080.
//
// Heap: agl's DynamicTextureAllocator is one fixed heap, "DynamicTextureAllocatorMem" in
// System/HeapSize/Product.Nin_NX_NVN.HeapDef.byml.zs (113664 KiB, carved from "Graphics", 201728 KiB). At 2560x1440
// the shipped size runs out at the title screen. Both heaps grow by the same amount: the shipped size times the output's
// pixel ratio above 1920x1080 plus the scene's above 1600x900 (MacNativeGames' measurement: a 3440x1440 canvas with a
// 4620x1935 scene crashed at +258 MiB and loaded at +400 MiB; this formula gives +750 MiB there). romfs.c serves the
// rewritten table (res_heapdef_build) in place of the original; memory.c adds the amount to the application pool, so
// no other heap shrinks. Without the rewritten table (a RomFS that lacks it, a format this code does not know) the
// patch sets stay off and the game keeps its own sizes.
#include <math.h>
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <zstd.h>

#include "cfg.h"
#include "game_profile.h"
#include "host.h"

#define BASE_W 1920
#define BASE_H 1080
#define SCENE_W 1600
#define SCENE_H 900
#define DTA_KIB 113664u      // DynamicTextureAllocatorMem, shipped
#define SCENE_MAX 16384      // per side, up to 16K on modern PC GPUs

static struct {
    int decided;
    unsigned ow, oh, sw, sh;   // output and scene
    int scene_set;             // the scene differs from the game's 5/6 of the output
    int heapdef_ok;            // romfs.c serves the grown HeapDef
    int on;                    // res_init switched the patch sets on
} R;

static volatile uint32_t g_live_win_w, g_live_win_h, g_live_crop_w, g_live_crop_h;

void res_record_game_surface(uint32_t win_w, uint32_t win_h, int cx, int cy, int cw, int ch) {
    (void)cx;
    (void)cy;
    if (win_w > 0 && win_h > 0) {
        __atomic_store_n(&g_live_win_w, win_w, __ATOMIC_RELAXED);
        __atomic_store_n(&g_live_win_h, win_h, __ATOMIC_RELAXED);
    }
    if (cw > 0 && ch > 0) {
        __atomic_store_n(&g_live_crop_w, (uint32_t)cw, __ATOMIC_RELAXED);
        __atomic_store_n(&g_live_crop_h, (uint32_t)ch, __ATOMIC_RELAXED);
    } else if (win_w > 0 && win_h > 0) {
        __atomic_store_n(&g_live_crop_w, win_w, __ATOMIC_RELAXED);
        __atomic_store_n(&g_live_crop_h, win_h, __ATOMIC_RELAXED);
    }
}

static void decide(void) {
    static char last_out[64] = {0};
    static char last_scale[64] = {0};

    const char *o = cfg_value("TOTK_OUTPUT_RES");
    const char *s = cfg_value("TOTK_RENDER_SCALE");
    if (!o) o = "1920x1080";
    if (!s) s = "game";

    if (R.decided && !strcmp(o, last_out) && !strcmp(s, last_scale))
        return;
    R.decided = 1;
    snprintf(last_out, sizeof last_out, "%s", o);
    snprintf(last_scale, sizeof last_scale, "%s", s);

    R.ow = BASE_W;
    R.oh = BASE_H;
    unsigned w = 0, h = 0;
    char tail;
    if (sscanf(o, "%ux%u%c", &w, &h, &tail) == 2 && w >= 1280 && h >= 720 && w <= 7680 && h <= 4320) {
        R.ow = w & ~1u;
        R.oh = h & ~1u;
    } else {
        rt_log("resolution: TOTK_OUTPUT_RES=%s is not <width>x<height> in 1280x720..7680x4320; 1920x1080", o);
    }

    double k = 1.0;
    if (strcmp(s, "game")) {
        char *end = NULL;
        double val = strtod(s, &end);
        if (end && (*end == 'x' || *end == 'X')) {
            k = (R.ow >= 3840) ? (val * 0.5) : val; // 1x = 1080p, 2x = 4K, 3x = 6K, 4x = 8K
            R.scene_set = 1;
        } else if (val >= 1.0 && val <= 8.0 && val == (int)val && end != s && !*end) {
            k = (R.ow >= 3840) ? (val * 0.5) : val;
            R.scene_set = 1;
        } else if (end != s && !*end && val >= 25 && val <= 800) {
            k = val / 100.0;
            R.scene_set = 1;
        } else {
            rt_log("resolution: TOTK_RENDER_SCALE=%s is not game or a percentage/multiplier; using game", s);
        }
    }
    double sw = R.ow * k, sh = R.oh * k;
    double fit = fmin(1.0, fmin(SCENE_MAX / sw, SCENE_MAX / sh));
    if (fit < 1.0) R.scene_set = 1;
    R.sw = (unsigned)(sw * fit + 0.5) & ~1u;
    R.sh = (unsigned)(sh * fit + 0.5) & ~1u;
}

static int bigger(void) {
    decide();
    return R.ow != BASE_W || R.oh != BASE_H || R.scene_set;
}

uint64_t res_heap_extra_kib(void) {
    if (!bigger()) return 0;
    double grow = fmax(0.0, (double)R.ow * R.oh / (BASE_W * BASE_H) - 1.0) +
                  fmax(0.0, (double)R.sw * R.sh / (SCENE_W * SCENE_H) - 1.0);
    if (grow <= 0) return 0;
    return (uint64_t)ceil(DTA_KIB * (1.0 + grow) / 1024.0) * 1024 - DTA_KIB;
}

uint64_t res_heap_extra_bytes(void) { return ((res_heap_extra_kib() << 10) + 0x1fffff) & ~0x1fffffull; }

// ---- the HeapDef table. BYML version 2..7, little endian ("YB"): a hash node is {u8 0xC1, u24 count} and count
// entries {u24 key index, u8 type, u32 value}; an int (type 0xD1) is stored in the entry, so a size changes in place.
typedef struct { uint8_t *p; size_t n; uint32_t keys; } Byml;

static int u32_at(const Byml *b, size_t off, uint32_t *v) {
    if (off + 4 > b->n) return 0;
    memcpy(v, b->p + off, 4);
    return 1;
}

static const char *key_name(const Byml *b, uint32_t k) {
    uint32_t head, at;
    if (!u32_at(b, b->keys, &head) || (head & 0xff) != 0xc2 || k >= head >> 8 || !u32_at(b, b->keys + 4 + 4 * k, &at) ||
        b->keys + at >= b->n || !memchr(b->p + b->keys + at, 0, b->n - b->keys - at))
        return NULL;
    return (const char *)b->p + b->keys + at;
}

// The offset of the value of hash node `node`'s entry `name`, which must have type `type`; 0 when there is none.
static size_t field(const Byml *b, uint32_t node, const char *name, uint8_t type) {
    uint32_t head;
    if (!u32_at(b, node, &head) || (head & 0xff) != 0xc1) return 0;
    for (uint32_t i = 0; i < head >> 8; i++) {
        uint32_t e;
        if (!u32_at(b, node + 4 + 8 * (size_t)i, &e)) return 0;
        const char *k = key_name(b, e & 0xffffff);
        if (k && !strcmp(k, name)) return e >> 24 == type ? node + 8 + 8 * (size_t)i : 0;
    }
    return 0;
}

static size_t heap_size_field(const Byml *b, uint32_t heaps, const char *heap) {
    size_t at = field(b, heaps, heap, 0xc1);
    uint32_t node;
    return at && u32_at(b, at, &node) ? field(b, node, "Size", 0xd1) : 0;
}

int res_heapdef_build(const void *in, size_t n, void **out, size_t *out_n) {
    uint64_t extra = res_heap_extra_kib();
    *out = NULL;
    if (!extra) return 0;
    if (ZSTD_getDictID_fromFrame(in, n)) {
        rt_log("resolution: the HeapDef table needs a zstd dictionary; the game keeps its own resolution");
        return 0;
    }
    unsigned long long raw = ZSTD_getFrameContentSize(in, n);
    if (raw == ZSTD_CONTENTSIZE_UNKNOWN || raw == ZSTD_CONTENTSIZE_ERROR || raw > (64u << 20)) {
        rt_log("resolution: the HeapDef table is not a zstd frame with a size; the game keeps its own resolution");
        return 0;
    }
    Byml b = {malloc((size_t)raw), (size_t)raw, 0};
    if (!b.p) return 0;
    size_t got = ZSTD_decompress(b.p, b.n, in, n);
    uint32_t root, heaps = 0;
    uint16_t ver = 0;
    if (!ZSTD_isError(got) && got == b.n && b.n >= 16) memcpy(&ver, b.p + 2, 2);
    size_t heaps_at = 0, dta_at = 0, gfx_at = 0;
    if (ver >= 2 && ver <= 7 && !memcmp(b.p, "YB", 2) && u32_at(&b, 4, &b.keys) && u32_at(&b, 12, &root) &&
        (heaps_at = field(&b, root, "Heaps", 0xc1)) && u32_at(&b, heaps_at, &heaps)) {
        dta_at = heap_size_field(&b, heaps, "DynamicTextureAllocatorMem");
        gfx_at = heap_size_field(&b, heaps, "Graphics");
    }
    if (!dta_at || !gfx_at) {
        rt_log("resolution: the HeapDef table has no DynamicTextureAllocatorMem / Graphics sizes; the game keeps its own "
               "resolution");
        free(b.p);
        return 0;
    }
    int32_t dta, gfx;
    memcpy(&dta, b.p + dta_at, 4);
    memcpy(&gfx, b.p + gfx_at, 4);
    int32_t dta2 = dta + (int32_t)extra, gfx2 = gfx + (int32_t)extra;
    memcpy(b.p + dta_at, &dta2, 4);
    memcpy(b.p + gfx_at, &gfx2, 4);
    size_t cap = ZSTD_compressBound(b.n);
    void *z = malloc(cap);
    size_t zn = z ? ZSTD_compress(z, cap, b.p, b.n, 9) : 0;
    free(b.p);
    if (!z || ZSTD_isError(zn)) {
        free(z);
        return 0;
    }
    *out = z;
    *out_n = zn;
    rt_log("resolution: HeapDef DynamicTextureAllocatorMem %d -> %d KiB, Graphics %d -> %d KiB", dta, dta2, gfx, gfx2);
    return 1;
}

void res_heapdef_served(void) { R.heapdef_ok = 1; }

// ---- start: the patch page and the sets
static uint64_t pack(unsigned w, unsigned h) { return (uint64_t)h << 32 | w; }

void res_init(void) {
    if (!game_profile_has(GAME_QUIRK_TOTK_PATCH_RES)) {
        const RtGameProfile *gp = game_profile();
        rt_log("resolution: Universal NS2 live hooks active for %s (Docked %ux%u, Handheld %ux%u)",
               gp->display_name, gp->docked_w, gp->docked_h, gp->handheld_w, gp->handheld_h);
        return;
    }
    if (!bigger()) {
        rt_log("resolution: the game's own (output 1920x1080, scene 1600x900)");
        return;
    }
    int output = rt_patch_set("output"), scene = rt_patch_set("scene");
    if (output < 0 || scene < 0) {
        rt_log("resolution: the generated C has no output and scene patch sets; the game keeps its own resolution");
        return;
    }
    fs_init();   // romfs.c serves the grown HeapDef from here on (res_heapdef_served)
    if (res_heap_extra_kib() && !R.heapdef_ok) {   // sizes at or below the shipped ones fit the shipped heaps
        rt_log("resolution: no grown HeapDef table; the game keeps its own resolution");
        return;
    }
    uint8_t *page = rt_patch_page();
    double k = RT_V143 ? (double)R.ow / BASE_W : 1.0;   // 1.4.3's own scaling of the scene with the output width
    int scene_on = R.scene_set || (!RT_V143 && (R.ow != BASE_W || R.oh != BASE_H));
    float sc[2] = {(float)(R.sw / k), (float)(R.sh / k)};
    uint64_t out = pack(R.ow, R.oh), none = 0;
    memcpy(page + 16, sc, sizeof sc);
    memcpy(page + 32, &out, 8);
    memcpy(page + 40, &none, 8);
    memcpy(page + 48, &out, 8);
    rt_patch_switch(output, R.ow != BASE_W || R.oh != BASE_H);
    rt_patch_switch(scene, scene_on);
    R.on = 1;
    // Another shape than 16:9 (more than 1% off): the camera takes the output's ratio (recomp/patches-v121.txt and
    // patches-v143.txt, set aspect), so a 21:9 output shows more of the world at the sides instead of a stretched 16:9 view. The HUD's layouts
    // for that shape come from romfs-patches-<w>x<h> (romfs.c overlay_init, tools/make_romfs_patches.py --aspect).
    double ratio = (double)R.ow / R.oh, game = (double)BASE_W / BASE_H;
    int aspect = rt_patch_set("aspect");
    if (!res_is_16x9(R.ow, R.oh)) {
        if (aspect < 0) {
            rt_log("resolution: output %ux%u is not 16:9 and this game version has no camera aspect patch; the view "
                   "is stretched", R.ow, R.oh);
        } else {
            float r = (float)ratio;
            memcpy(page + 56, &r, sizeof r);
            rt_patch_switch(aspect, 1);
            rt_log("resolution: camera aspect ratio %.4f (16:9 is %.4f)", ratio, game);
        }
    } else {
        rt_patch_switch(aspect, 0);   // the page holds no ratio
    }
    rt_log("resolution: output %ux%u, scene %ux%u%s; texture heap +%llu KiB", R.ow, R.oh, R.sw, R.sh,
           scene_on ? "" : " (the game's own 5/6 of the output)", (unsigned long long)res_heap_extra_kib());
}

// 16:9 within 1% (1366x768 counts): the shape the game's own layouts and camera are made for.
int res_is_16x9(unsigned w, unsigned h) {
    double rel = ((double)w / h) / ((double)BASE_W / BASE_H);
    return rel >= 0.99 && rel <= 1.01;
}

// The game resolution asks for a romfs-patches-<w>x<h> overlay: it is not 16:9 and the game version has the camera
// aspect patch (set aspect); the UI layouts of another shape only fit a camera that follows the same shape.
int res_wants_wide_overlay(const unsigned out[2]) {
    return !res_is_16x9(out[0], out[1]) && rt_patch_set("aspect") >= 0;
}

// Field of view (TOTK_FOV, percent of the game's own, 70..140, live): the camera's vertical view angle times the
// factor on page +60 (recomp/patches-v143.txt, set fov). The horizontal angle follows through the aspect ratio. 100
// switches the set off, so the camera code is the game's own. Runs on a settings change (gfx_present.c
// window_settings_live), the first time at the first present.
#define FOV_MIN 70
#define FOV_MAX 140
void res_fov_live(void) {
    static int set = -2, shown = 100;
    if (set == -2) set = rt_patch_set("fov");
    int pct = cfg_int("TOTK_FOV");
    pct = pct < FOV_MIN ? FOV_MIN : pct > FOV_MAX ? FOV_MAX : pct;
    if (pct == shown) return;
    shown = pct;
    if (set < 0) {
        if (game_profile_has(GAME_QUIRK_TOTK_PATCH_RES))
            rt_log("resolution: this game version has no field-of-view patch; TOTK_FOV=%d does nothing", pct);
        return;
    }
    float k = pct / 100.0f;
    memcpy((uint8_t *)rt_patch_page() + 60, &k, sizeof k);   // before the switch: a site that sees it on reads k
    rt_patch_switch(set, pct != 100);
    rt_log("resolution: field of view %d%% of the game's", pct);
}

void res_wanted(unsigned out[2]) {
    decide();
    out[0] = R.ow, out[1] = R.oh;
}

void res_sizes(unsigned out[2], unsigned scene[2]) {
    decide();
    out[0] = R.ow ? R.ow : BASE_W;
    out[1] = R.oh ? R.oh : BASE_H;
    scene[0] = R.sw ? R.sw : SCENE_W;
    scene[1] = R.sh ? R.sh : SCENE_H;
}

void res_apply_live(void) {
    static int init = 0;
    static int prev_handheld = -1;
    static char prev_out[64] = {0};

    const char *op = cfg_value("NS2_OPERATION_MODE");
    int hh = (op && !strcmp(op, "handheld")) ? 1 : 0;
    const char *out_res = cfg_value("NS2_OUTPUT_RES");

    if (!init) {
        init = 1;
        prev_handheld = hh;
        if (out_res) snprintf(prev_out, sizeof prev_out, "%s", out_res);
        decide();
        // Synchronize window size on initial startup if set
        if (out_res && !cfg_bool("NS2_FULLSCREEN") && strcmp(cfg_value("NS2_WINDOW_SIZE"), out_res) != 0) {
            cfg_set("NS2_WINDOW_SIZE", out_res);
        }
        return;
    }

    int notify_mode = (hh != prev_handheld);
    if (notify_mode) prev_handheld = hh;

    int out_changed = out_res && strcmp(out_res, prev_out) != 0;
    if (out_changed) {
        snprintf(prev_out, sizeof prev_out, "%s", out_res);
        R.decided = 0;
        decide();
        // Keep host window swapchain synchronized with Output Resolution when windowed
        if (!cfg_bool("NS2_FULLSCREEN") && strcmp(cfg_value("NS2_WINDOW_SIZE"), out_res) != 0) {
            cfg_set("NS2_WINDOW_SIZE", out_res);
        }
        notify_mode = 1;
    }
    if (notify_mode) ov_notify_operation_mode_changed();
}

void res_live_snapshot(unsigned win_sz[2], unsigned crop_sz[2], unsigned out_tgt[2], int *handheld) {
    uint32_t ww = __atomic_load_n(&g_live_win_w, __ATOMIC_RELAXED);
    uint32_t wh = __atomic_load_n(&g_live_win_h, __ATOMIC_RELAXED);
    uint32_t cw = __atomic_load_n(&g_live_crop_w, __ATOMIC_RELAXED);
    uint32_t ch = __atomic_load_n(&g_live_crop_h, __ATOMIC_RELAXED);
    if (win_sz) {
        win_sz[0] = ww ? ww : game_profile()->docked_w;
        win_sz[1] = wh ? wh : game_profile()->docked_h;
    }
    if (crop_sz) {
        crop_sz[0] = cw ? cw : (ww ? ww : game_profile()->docked_w);
        crop_sz[1] = ch ? ch : (wh ? wh : game_profile()->docked_h);
    }
    if (out_tgt) {
        decide();
        out_tgt[0] = R.ow;
        out_tgt[1] = R.oh;
    }
    if (handheld) {
        const char *op = cfg_value("NS2_OPERATION_MODE");
        *handheld = (op && !strcmp(op, "handheld")) ? 1 : 0;
    }
}

// ---- Fast Fusion Resolution Scaling Hooks
// Fast Fusion uses a Display/Configuration singleton at *(uint64_t*)0x700071beb8.
// - f_700011ff04 sets the Output Canvas resolution (shipped 3840x2160 docked, 1920x1080 handheld)
// - f_700011ff1c sets the Internal 3D scene rendering resolution (shipped 1920x1080 docked, 1280x720 handheld)
// - f_7000075cc0 sets the dynamic sub-viewport projection scale (1.0 = full render target)
extern void __real_f_700011ff04(Cpu *c) __attribute__((weak));
extern void __real_f_700011ff1c(Cpu *c) __attribute__((weak));
extern void __real_f_7000075cc0(Cpu *c) __attribute__((weak));

void ff_get_target_resolutions(uint32_t *canvas_w, uint32_t *canvas_h, uint32_t *scene_w, uint32_t *scene_h) {
    const char *o = cfg_value("TOTK_OUTPUT_RES");
    const char *s = cfg_value("TOTK_RENDER_SCALE");
    if (!o || !*o) o = "3840x2160";
    if (!s || !*s) s = "200";

    uint32_t cw = 3840, ch = 2160;
    unsigned w = 0, h = 0;
    char tail;
    if (sscanf(o, "%ux%u%c", &w, &h, &tail) == 2 && w >= 640 && h >= 360 && w <= 16384 && h <= 16384) {
        cw = w & ~1u;
        ch = h & ~1u;
    }

    // Determine scale multiplier:
    // Emulator-style: 1x = 1080p, 2x = 3840x2160 (Native 4K), 3x = 5760x3240, 4x = 7680x4320 (8K).
    // Percentage-style: 50 = 1080p, 100 = Native 4K (or 1080p if output 1080p), 200 = 2x Native 4K, etc.
    double mult = 2.0; // default to native 4K
    if (!strcmp(s, "game")) {
        mult = 1.0;
    } else if (!strcmp(s, "native") || !strcmp(s, "4k") || !strcmp(s, "4K")) {
        mult = 2.0; // 2x of 1080p = 3840x2160
    } else {
        char *end = NULL;
        double val = strtod(s, &end);
        if (end && (*end == 'x' || *end == 'X')) {
            mult = val;
        } else if (val >= 1.0 && val <= 8.0 && val == (int)val) {
            mult = val;
        } else if (val >= 25.0 && val <= 800.0) {
            if (cw >= 3840 && val == 100.0) mult = 2.0; // 100% of 4K canvas = 4K scene
            else if (val == 200.0) mult = 2.0;          // 200 = 2x = 4K scene
            else if (val == 300.0) mult = 3.0;          // 300 = 3x = 6K scene
            else if (val == 400.0) mult = 4.0;          // 400 = 4x = 8K scene
            else mult = (val / 100.0) * (cw >= 3840 ? 2.0 : 1.0);
        }
    }

    if (mult < 0.25) mult = 0.25;
    if (mult > 8.0) mult = 8.0;

    uint32_t sw = (uint32_t)(1920.0 * mult + 0.5) & ~1u;
    uint32_t sh = (uint32_t)(1080.0 * mult + 0.5) & ~1u;

    if (canvas_w) *canvas_w = cw;
    if (canvas_h) *canvas_h = ch;
    if (scene_w) *scene_w = sw;
    if (scene_h) *scene_h = sh;
}

void __wrap_f_700011ff04(Cpu *c) {
    uint64_t *disp_cfg_ptr = (uint64_t *)(uintptr_t)0x700071beb8;
    uint64_t disp_cfg = disp_cfg_ptr ? *disp_cfg_ptr : 0;
    int is_res_call = (disp_cfg && c->x[0] == disp_cfg) || (c->x[1] >= 640 && c->x[2] >= 360);

    if (is_res_call) {
        uint32_t cw = 0, ch = 0;
        ff_get_target_resolutions(&cw, &ch, NULL, NULL);
        rt_log("ff: resolution hook: canvas set to %ux%u (was %ux%u)", cw, ch, (unsigned)c->x[1], (unsigned)c->x[2]);
        c->x[1] = cw;
        c->x[2] = ch;
    }
    if (__real_f_700011ff04) __real_f_700011ff04(c);
    else {
        GuestFn orig = rt_dispatch_lookup(0x700011ff04ull);
        if (orig) orig(c);
    }
}

void __wrap_f_700011ff1c(Cpu *c) {
    uint64_t *disp_cfg_ptr = (uint64_t *)(uintptr_t)0x700071beb8;
    uint64_t disp_cfg = disp_cfg_ptr ? *disp_cfg_ptr : 0;
    int is_res_call = (disp_cfg && c->x[0] == disp_cfg) || (c->x[1] >= 640 && c->x[2] >= 360);

    if (is_res_call) {
        uint32_t sw = 0, sh = 0;
        ff_get_target_resolutions(NULL, NULL, &sw, &sh);
        rt_log("ff: resolution hook: internal 3D scene set to %ux%u (was %ux%u)", sw, sh, (unsigned)c->x[1], (unsigned)c->x[2]);
        c->x[1] = sw;
        c->x[2] = sh;
    }
    if (__real_f_700011ff1c) __real_f_700011ff1c(c);
    else {
        GuestFn orig = rt_dispatch_lookup(0x700011ff1cull);
        if (orig) orig(c);
    }
}

void __wrap_f_7000075cc0(Cpu *c) {
    uint64_t x21 = c->x[0];
    if (x21) {
        float *scale_x = (float *)(uintptr_t)(x21 + 0xb0);
        float *scale_y = (float *)(uintptr_t)(x21 + 0xb4);
        *scale_x = 1.0f;
        *scale_y = 1.0f;
        static int logged = 0;
        if (!logged) {
            logged = 1;
            rt_log("ff: resolution hook: 3D scene scale locked to 1.0x (full native resolution)");
        }
    }
    if (__real_f_7000075cc0) __real_f_7000075cc0(c);
    else {
        GuestFn orig = rt_dispatch_lookup(0x7000075cc0ull);
        if (orig) orig(c);
    }
}
