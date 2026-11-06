#pragma once
#include <stdint.h>
#include "vk.h"

#ifdef __cplusplus
extern "C" {
#endif

void vk_xess_instance_exts(const char **ext, uint32_t *n, uint32_t max);
void vk_xess_device_exts(const VkExtensionProperties *have, uint32_t nhave, const char **ext, uint32_t *n, uint32_t max);
void vk_xess_init(void);
int vk_xess_available(void);
int vk_xess_record(VkCommandBuffer cb, unsigned slot, VkImage src, VkFormat fmt, int sw, int sh,
                   const int crop[4], VkImage dst, const int out[4]);
void vk_xess_release(void);

#ifdef __cplusplus
}
#endif
