// Screen Space Ambient Occlusion (SSAO) & Horizon-Based Ambient Occlusion (HBAO)
#pragma once
#include <stdint.h>
#include "vk.h"

#ifdef __cplusplus
extern "C" {
#endif

void vk_ao_init(void);
void vk_ao_release(void);

// Notes the active scene depth image and format from the main 3D pass
void vk_ao_note_depth(VkImage depth, VkFormat fmt, uint32_t w, uint32_t h);

// Records SSAO or HBAO passes: computes AO, blurs, and composites into scene color
VkImage vk_ao_record(VkCommandBuffer cb, unsigned slot, VkImage src, VkFormat fmt, int w, int h, const int crop[4]);

#ifdef __cplusplus
}
#endif
