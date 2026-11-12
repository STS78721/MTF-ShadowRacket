#include "game_profile.h"

#include <stdio.h>
#include <string.h>

#include "host.h"

// Embedded weakly so older/partial link tests still compile without modules.c edits
extern const char rt_game_short_name[] __attribute__((weak));
extern const char rt_game_display_name[] __attribute__((weak));

static const RtGameProfile kProfiles[] = {
    {0x040074a01bf12000ull, "dkb",  "Donkey Kong Bananza",                "dkb.ini",  1920, 1080, 1280, 720, GAME_QUIRK_PT_BR},
    {0x0400C3F00006E000ull, "mkw",  "Mario Kart World",                   "mkw.ini",  1920, 1080, 1280, 720, GAME_QUIRK_MKW_HEAP_FALLBACK | GAME_QUIRK_MKW_VTABLES},
    {0x0400D4201C6EA000ull, "mtf",  "Mario Tennis Fever",                 "mtf.ini",  1920, 1080, 1280, 720, GAME_QUIRK_MTF_WORKER_ARGS},
    {0x040041E0212AE000ull, "ff",   "Fast Fusion",                        "ff.ini",   1920, 1080, 1280, 720, GAME_QUIRK_NONE},
    {0x0100F2C0115B6000ull, "totk", "Zelda: Tears of the Kingdom",        "totk.ini", 1920, 1080, 1280, 720, GAME_QUIRK_TOTK_PATCH_RES},
    {0x0400486024DEC000ull, "oot",  "Zelda: Ocarina of Time (Switch 2)",  "oot.ini",  1920, 1080, 1280, 720, GAME_QUIRK_NONE},
};

static RtGameProfile g_resolved;
static int g_resolved_ok;
static char g_ini_buf[48];

const RtGameProfile *game_profile(void) {
    if (g_resolved_ok) return &g_resolved;
    for (size_t i = 0; i < sizeof kProfiles / sizeof *kProfiles; i++) {
        if (kProfiles[i].title_id == rt_application_id) {
            g_resolved = kProfiles[i];
            g_resolved_ok = 1;
            return &g_resolved;
        }
    }
    const char *sn = (rt_game_short_name && rt_game_short_name[0]) ? rt_game_short_name : "ns2";
    const char *dn = (rt_game_display_name && rt_game_display_name[0]) ? rt_game_display_name : "Universal NS2 Title";
    snprintf(g_ini_buf, sizeof g_ini_buf, "%s.ini", sn);
    g_resolved = (RtGameProfile){
        .title_id = rt_application_id,
        .short_name = sn,
        .display_name = dn,
        .ini_name = g_ini_buf,
        .docked_w = 1920,
        .docked_h = 1080,
        .handheld_w = 1280,
        .handheld_h = 720,
        .quirks = GAME_QUIRK_NONE,
    };
    g_resolved_ok = 1;
    return &g_resolved;
}

int game_profile_has(uint32_t quirk) {
    return (game_profile()->quirks & quirk) != 0;
}

void game_profile_log(void) {
    const RtGameProfile *p = game_profile();
    rt_log("profile: '%s' (%s, title_id=%016llx, quirks=%#x)",
           p->display_name, p->short_name, (unsigned long long)p->title_id, p->quirks);
}
