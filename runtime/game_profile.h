// Universal NS2 to PC: central game identity & per-title runtime quirks registry.
// Looks up rt_application_id at startup so game-specific fixes live in one table
// instead of scattered magic constants across kernel/system/graphics files.
#pragma once
#include <stdint.h>

#ifdef __cplusplus
extern "C" {
#endif

enum {
    GAME_QUIRK_NONE             = 0,
    GAME_QUIRK_PT_BR            = 1u << 0, // Ship PT-BR when locale is "pt" (DKB)
    GAME_QUIRK_MTF_WORKER_ARGS  = 1u << 1, // ThreadType doubly-indirect worker arg fix (MTF)
    GAME_QUIRK_MKW_HEAP_FALLBACK= 1u << 2, // Wrap sead::ExpHeap::alloc / camera / delegate checks (MKW)
    GAME_QUIRK_MKW_VTABLES      = 1u << 3, // Patch ExpHeap / dispose guest vtables after init_array (MKW)
    GAME_QUIRK_TOTK_PATCH_RES   = 1u << 4, // Game uses TotK-style output/scene/aspect assembly patches
};

typedef struct {
    uint64_t title_id;
    const char *short_name;     // e.g. "dkb", "mkw", "mtf", "totk", "ns2"
    const char *display_name;   // Human-readable title
    const char *ini_name;       // Preferred config filename, e.g. "mkw.ini"
    uint32_t docked_w, docked_h;
    uint32_t handheld_w, handheld_h;
    uint32_t quirks;
} RtGameProfile;

const RtGameProfile *game_profile(void);
int game_profile_has(uint32_t quirk);
void game_profile_log(void);

#ifdef __cplusplus
}
#endif
