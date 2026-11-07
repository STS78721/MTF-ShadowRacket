// Subpixel Morphological Anti-Aliasing (SMAA 1x) - Post-processing edge smoothing
#pragma once
#include <stdint.h>
#include "vk.h"

#ifdef __cplusplus
extern "C" {
#endif

void vk_smaa_init(void);
void vk_smaa_release(void);

// Runs the 3 SMAA passes (edge detection, blend weights, neighborhood blending)
// Returns an anti-aliased RGBA16F image of the crop rectangle, or VK_NULL_HANDLE if SMAA is off or uninitialized.
VkImage vk_smaa_record(VkCommandBuffer cb, unsigned slot, VkImage src, VkFormat fmt, int w, int h, const int crop[4]);

#ifdef __cplusplus
}
#endif
