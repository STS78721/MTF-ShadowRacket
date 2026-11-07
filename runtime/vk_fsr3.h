#pragma once
#include <stdint.h>
#include "vk.h"

#ifdef __cplusplus
extern "C" {
#endif

// AMD FidelityFX Super Resolution 3.1 (FSR 3.1)
// Provides FSR 3.1 Super Resolution (Upscaling) & Decoupled Frame Generation
int vk_fsr3_wanted(void);
int vk_fsr3_available(void);
int vk_fsr3_fg_available(void);
const char *vk_fsr3_version_string(void);
uint64_t vk_fsr3_dispatches(void);

void vk_fsr3_init(void);
void vk_fsr3_release(void);

// Record FSR 3.1 Super Resolution pass. Returns 1 if recorded, 0 if bypassed/fallback.
int vk_fsr3_record(VkCommandBuffer cb, unsigned slot, VkImage src, VkFormat fmt, int sw, int sh, const int crop[4],
                   VkImage dst, const int out[4]);

#ifdef __cplusplus
}
#endif
