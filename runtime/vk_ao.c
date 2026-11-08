// Screen Space Ambient Occlusion (SSAO) & Horizon-Based Ambient Occlusion (HBAO)
#include "vk.h"
#include "vk_ao.h"

#include <math.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "cfg.h"
#include "host.h"
#include "nvn_api.h"
#include "ssao_spv.h"
#include "hbao_spv.h"
#include "ao_blur_spv.h"
#include "ao_composite_spv.h"

#define SLOTS 8

static struct {
    int tried, ok;
    PFN_vkCmdPushDescriptorSetKHR push;

    // Last recorded scene depth image
    VkImage last_depth;
    VkFormat last_depth_fmt;
    uint32_t last_depth_w, last_depth_h;
    uint64_t last_depth_frame;

    VkSampler sampler_linear;
    VkSampler sampler_point;

    // SSAO Pipeline
    VkDescriptorSetLayout ssao_dsl;
    VkPipelineLayout ssao_layout;
    VkPipeline ssao_pipe;

    // HBAO Pipeline
    VkDescriptorSetLayout hbao_dsl;
    VkPipelineLayout hbao_layout;
    VkPipeline hbao_pipe;

    // Bilateral Blur Pipeline
    VkDescriptorSetLayout blur_dsl;
    VkPipelineLayout blur_layout;
    VkPipeline blur_pipe;

    // Composite Pipeline
    VkDescriptorSetLayout comp_dsl;
    VkPipelineLayout comp_layout;
    VkPipeline comp_pipe;

    // Dynamic Images
    uint32_t w, h;
    VkImage raw_ao_img;
    VmaAllocation raw_ao_alloc;
    VkImageView raw_ao_view;

    VkImage blur_ao_img;
    VmaAllocation blur_ao_alloc;
    VkImageView blur_ao_view;

    VkImage out_img;
    VmaAllocation out_alloc;
    VkImageView out_view;

    VkImageView src_view[SLOTS];
    VkImageView depth_view[SLOTS];
} A;

void vk_ao_note_depth(VkImage depth, VkFormat fmt, uint32_t w, uint32_t h) {
    if (!depth) return;
    A.last_depth = depth;
    A.last_depth_fmt = fmt;
    A.last_depth_w = w;
    A.last_depth_h = h;
    A.last_depth_frame = __atomic_load_n(&gfx_counters.frames, __ATOMIC_RELAXED);
}

int vk_ao_get_depth(VkImage *out_depth, VkFormat *out_fmt, uint32_t *out_w, uint32_t *out_h) {
    uint64_t cur = __atomic_load_n(&gfx_counters.frames, __ATOMIC_RELAXED);
    if (!A.last_depth || cur > A.last_depth_frame + 2) return 0;
    if (out_depth) *out_depth = A.last_depth;
    if (out_fmt) *out_fmt = A.last_depth_fmt;
    if (out_w) *out_w = A.last_depth_w;
    if (out_h) *out_h = A.last_depth_h;
    return 1;
}

static void free_dynamic_images(VkCtx *c) {
    if (A.raw_ao_view) vkDestroyImageView(c->device, A.raw_ao_view, NULL);
    if (A.raw_ao_img) vmaDestroyImage(c->vma, A.raw_ao_img, A.raw_ao_alloc);
    if (A.blur_ao_view) vkDestroyImageView(c->device, A.blur_ao_view, NULL);
    if (A.blur_ao_img) vmaDestroyImage(c->vma, A.blur_ao_img, A.blur_ao_alloc);
    if (A.out_view) vkDestroyImageView(c->device, A.out_view, NULL);
    if (A.out_img) vmaDestroyImage(c->vma, A.out_img, A.out_alloc);
    A.raw_ao_view = A.blur_ao_view = A.out_view = VK_NULL_HANDLE;
    A.raw_ao_img = A.blur_ao_img = A.out_img = VK_NULL_HANDLE;
    A.w = A.h = 0;
}

static int ensure_dynamic_images(VkCtx *c, uint32_t w, uint32_t h) {
    if (A.out_img && A.w == w && A.h == h) return 1;
    vk_queue_lock();
    vkDeviceWaitIdle(c->device);
    vk_queue_unlock();
    free_dynamic_images(c);

    VmaAllocationCreateInfo ai = {.usage = VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE};

    // 1. Raw AO texture (R8_UNORM)
    VkImageCreateInfo rci = {.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO, .imageType = VK_IMAGE_TYPE_2D,
                             .format = VK_FORMAT_R8_UNORM, .extent = {w, h, 1}, .mipLevels = 1, .arrayLayers = 1,
                             .samples = VK_SAMPLE_COUNT_1_BIT, .tiling = VK_IMAGE_TILING_OPTIMAL,
                             .usage = VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_SAMPLED_BIT};
    if (vmaCreateImage(c->vma, &rci, &ai, &A.raw_ao_img, &A.raw_ao_alloc, NULL) != VK_SUCCESS) return 0;
    VkImageViewCreateInfo rvi = {.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO, .image = A.raw_ao_img,
                                 .viewType = VK_IMAGE_VIEW_TYPE_2D, .format = VK_FORMAT_R8_UNORM,
                                 .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}};
    if (vkCreateImageView(c->device, &rvi, NULL, &A.raw_ao_view) != VK_SUCCESS) return 0;

    // 2. Blurred AO texture (R8_UNORM)
    VkImageCreateInfo bci = {.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO, .imageType = VK_IMAGE_TYPE_2D,
                             .format = VK_FORMAT_R8_UNORM, .extent = {w, h, 1}, .mipLevels = 1, .arrayLayers = 1,
                             .samples = VK_SAMPLE_COUNT_1_BIT, .tiling = VK_IMAGE_TILING_OPTIMAL,
                             .usage = VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_SAMPLED_BIT};
    if (vmaCreateImage(c->vma, &bci, &ai, &A.blur_ao_img, &A.blur_ao_alloc, NULL) != VK_SUCCESS) return 0;
    VkImageViewCreateInfo bvi = {.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO, .image = A.blur_ao_img,
                                 .viewType = VK_IMAGE_VIEW_TYPE_2D, .format = VK_FORMAT_R8_UNORM,
                                 .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}};
    if (vkCreateImageView(c->device, &bvi, NULL, &A.blur_ao_view) != VK_SUCCESS) return 0;

    // 3. Composite output image (RGBA16F)
    VkImageCreateInfo oci = {.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO, .imageType = VK_IMAGE_TYPE_2D,
                             .format = VK_FORMAT_R16G16B16A16_SFLOAT, .extent = {w, h, 1}, .mipLevels = 1, .arrayLayers = 1,
                             .samples = VK_SAMPLE_COUNT_1_BIT, .tiling = VK_IMAGE_TILING_OPTIMAL,
                             .usage = VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT};
    if (vmaCreateImage(c->vma, &oci, &ai, &A.out_img, &A.out_alloc, NULL) != VK_SUCCESS) return 0;
    VkImageViewCreateInfo ovi = {.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO, .image = A.out_img,
                                 .viewType = VK_IMAGE_VIEW_TYPE_2D, .format = VK_FORMAT_R16G16B16A16_SFLOAT,
                                 .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}};
    if (vkCreateImageView(c->device, &ovi, NULL, &A.out_view) != VK_SUCCESS) return 0;

    A.w = w; A.h = h;
    return 1;
}

static VkPipeline make_compute_pipe(VkCtx *c, VkPipelineLayout layout, const uint32_t *spv, size_t spv_bytes) {
    VkShaderModuleCreateInfo mi = {.sType = VK_STRUCTURE_TYPE_SHADER_MODULE_CREATE_INFO, .codeSize = spv_bytes,
                                   .pCode = spv};
    VkShaderModule m = VK_NULL_HANDLE;
    if (vkCreateShaderModule(c->device, &mi, NULL, &m) != VK_SUCCESS) return VK_NULL_HANDLE;
    VkComputePipelineCreateInfo ci = {.sType = VK_STRUCTURE_TYPE_COMPUTE_PIPELINE_CREATE_INFO,
                                      .stage = {.sType = VK_STRUCTURE_TYPE_PIPELINE_SHADER_STAGE_CREATE_INFO,
                                                .stage = VK_SHADER_STAGE_COMPUTE_BIT, .module = m, .pName = "main"},
                                      .layout = layout};
    VkPipeline pipe = VK_NULL_HANDLE;
    vkCreateComputePipelines(c->device, VK_NULL_HANDLE, 1, &ci, NULL, &pipe);
    vkDestroyShaderModule(c->device, m, NULL);
    return pipe;
}

void vk_ao_init(void) {
    A.tried = 1;
    VkCtx *c = vk_ctx();
    A.push = (PFN_vkCmdPushDescriptorSetKHR)vkGetDeviceProcAddr(c->device, "vkCmdPushDescriptorSetKHR");
    if (!A.push) {
        rt_log("vk_ao: push descriptors not supported; AO disabled");
        return;
    }

    // Samplers
    VkSamplerCreateInfo sli = {.sType = VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO, .magFilter = VK_FILTER_LINEAR,
                               .minFilter = VK_FILTER_LINEAR, .mipmapMode = VK_SAMPLER_MIPMAP_MODE_NEAREST,
                               .addressModeU = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,
                               .addressModeV = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,
                               .addressModeW = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE, .maxLod = 0};
    if (vkCreateSampler(c->device, &sli, NULL, &A.sampler_linear) != VK_SUCCESS) return;

    VkSamplerCreateInfo spi = {.sType = VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO, .magFilter = VK_FILTER_NEAREST,
                               .minFilter = VK_FILTER_NEAREST, .mipmapMode = VK_SAMPLER_MIPMAP_MODE_NEAREST,
                               .addressModeU = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,
                               .addressModeV = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,
                               .addressModeW = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE, .maxLod = 0};
    if (vkCreateSampler(c->device, &spi, NULL, &A.sampler_point) != VK_SUCCESS) return;

    // SSAO / HBAO Layout (binding 0: depth, binding 1: dstAO)
    VkDescriptorSetLayoutBinding aob[2] = {
        {.binding = 0, .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT},
        {.binding = 1, .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT}};
    VkDescriptorSetLayoutCreateInfo aodci = {.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
                                             .flags = VK_DESCRIPTOR_SET_LAYOUT_CREATE_PUSH_DESCRIPTOR_BIT_KHR,
                                             .bindingCount = 2, .pBindings = aob};
    VkPushConstantRange aopr = {VK_SHADER_STAGE_COMPUTE_BIT, 0, 48};
    if (vkCreateDescriptorSetLayout(c->device, &aodci, NULL, &A.ssao_dsl) != VK_SUCCESS) return;
    VkPipelineLayoutCreateInfo aoli = {.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO, .setLayoutCount = 1,
                                       .pSetLayouts = &A.ssao_dsl, .pushConstantRangeCount = 1, .pPushConstantRanges = &aopr};
    if (vkCreatePipelineLayout(c->device, &aoli, NULL, &A.ssao_layout) != VK_SUCCESS) return;
    A.ssao_pipe = make_compute_pipe(c, A.ssao_layout, ssao_spv, sizeof(ssao_spv));

    A.hbao_dsl = A.ssao_dsl;
    A.hbao_layout = A.ssao_layout;
    A.hbao_pipe = make_compute_pipe(c, A.hbao_layout, hbao_spv, sizeof(hbao_spv));

    // Blur Pipeline (binding 0: aoTex, binding 1: depthTex, binding 2: dstAO)
    VkDescriptorSetLayoutBinding blb[3] = {
        {.binding = 0, .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT},
        {.binding = 1, .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT},
        {.binding = 2, .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT}};
    VkDescriptorSetLayoutCreateInfo bldci = {.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
                                             .flags = VK_DESCRIPTOR_SET_LAYOUT_CREATE_PUSH_DESCRIPTOR_BIT_KHR,
                                             .bindingCount = 3, .pBindings = blb};
    VkPushConstantRange blpr = {VK_SHADER_STAGE_COMPUTE_BIT, 0, 32};
    if (vkCreateDescriptorSetLayout(c->device, &bldci, NULL, &A.blur_dsl) != VK_SUCCESS) return;
    VkPipelineLayoutCreateInfo blli = {.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO, .setLayoutCount = 1,
                                       .pSetLayouts = &A.blur_dsl, .pushConstantRangeCount = 1, .pPushConstantRanges = &blpr};
    if (vkCreatePipelineLayout(c->device, &blli, NULL, &A.blur_layout) != VK_SUCCESS) return;
    A.blur_pipe = make_compute_pipe(c, A.blur_layout, ao_blur_spv, sizeof(ao_blur_spv));

    // Composite Pipeline (binding 0: srcColor, binding 1: aoTex, binding 2: dstColor)
    VkDescriptorSetLayoutBinding cpb[3] = {
        {.binding = 0, .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT},
        {.binding = 1, .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT},
        {.binding = 2, .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT}};
    VkDescriptorSetLayoutCreateInfo cpdci = {.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
                                             .flags = VK_DESCRIPTOR_SET_LAYOUT_CREATE_PUSH_DESCRIPTOR_BIT_KHR,
                                             .bindingCount = 3, .pBindings = cpb};
    VkPushConstantRange cppr = {VK_SHADER_STAGE_COMPUTE_BIT, 0, 24};
    if (vkCreateDescriptorSetLayout(c->device, &cpdci, NULL, &A.comp_dsl) != VK_SUCCESS) return;
    VkPipelineLayoutCreateInfo cpli = {.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO, .setLayoutCount = 1,
                                       .pSetLayouts = &A.comp_dsl, .pushConstantRangeCount = 1, .pPushConstantRanges = &cppr};
    if (vkCreatePipelineLayout(c->device, &cpli, NULL, &A.comp_layout) != VK_SUCCESS) return;
    A.comp_pipe = make_compute_pipe(c, A.comp_layout, ao_composite_spv, sizeof(ao_composite_spv));

    if (A.ssao_pipe && A.hbao_pipe && A.blur_pipe && A.comp_pipe) {
        A.ok = 1;
        rt_log("vk_ao: SSAO & HBAO ambient occlusion pipelines initialized successfully");
    }
}

static void barrier(VkCommandBuffer cb, VkImage img, VkImageLayout from, VkImageLayout to,
                    VkPipelineStageFlags2 ss, VkAccessFlags2 sa, VkPipelineStageFlags2 ds, VkAccessFlags2 da,
                    VkImageAspectFlags aspect) {
    VkImageMemoryBarrier2 b = {.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER_2,
                               .srcStageMask = ss, .srcAccessMask = sa,
                               .dstStageMask = ds, .dstAccessMask = da,
                               .oldLayout = from, .newLayout = to,
                               .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                               .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                               .image = img, .subresourceRange = {aspect, 0, 1, 0, 1}};
    VkDependencyInfo d = {.sType = VK_STRUCTURE_TYPE_DEPENDENCY_INFO, .imageMemoryBarrierCount = 1, .pImageMemoryBarriers = &b};
    vkCmdPipelineBarrier2(cb, &d);
}

VkImage vk_ao_record(VkCommandBuffer cb, unsigned slot, VkImage src, VkFormat fmt, int w, int h, const int crop[4]) {
    const char *cfg_ao = cfg_value("DKB_AO");
    if (!cfg_ao || !strcmp(cfg_ao, "off") || !strcmp(cfg_ao, "0") || !*cfg_ao) return VK_NULL_HANDLE;

    // Must have a valid active scene depth buffer
    if (!A.last_depth) return VK_NULL_HANDLE;
    uint64_t cur_frame = __atomic_load_n(&gfx_counters.frames, __ATOMIC_RELAXED);
    if (cur_frame > A.last_depth_frame + 2) return VK_NULL_HANDLE; // stale depth buffer

    VkCtx *c = vk_ctx();
    if (!A.tried) vk_ao_init();
    if (!A.ok) return VK_NULL_HANDLE;

    uint32_t cw = (uint32_t)(crop ? crop[2] : w);
    uint32_t ch = (uint32_t)(crop ? crop[3] : h);
    if (!ensure_dynamic_images(c, cw, ch)) return VK_NULL_HANDLE;

    slot %= SLOTS;
    if (A.src_view[slot]) vkDestroyImageView(c->device, A.src_view[slot], NULL);
    VkImageViewCreateInfo cvi = {.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO, .image = src,
                                 .viewType = VK_IMAGE_VIEW_TYPE_2D, .format = fmt,
                                 .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}};
    if (vkCreateImageView(c->device, &cvi, NULL, &A.src_view[slot]) != VK_SUCCESS) return VK_NULL_HANDLE;

    if (A.depth_view[slot]) vkDestroyImageView(c->device, A.depth_view[slot], NULL);
    VkImageViewCreateInfo dvi = {.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO, .image = A.last_depth,
                                 .viewType = VK_IMAGE_VIEW_TYPE_2D, .format = A.last_depth_fmt,
                                 .subresourceRange = {VK_IMAGE_ASPECT_DEPTH_BIT, 0, 1, 0, 1}};
    if (vkCreateImageView(c->device, &dvi, NULL, &A.depth_view[slot]) != VK_SUCCESS) return VK_NULL_HANDLE;

    const VkPipelineStageFlags2 CS = VK_PIPELINE_STAGE_2_COMPUTE_SHADER_BIT;
    const VkPipelineStageFlags2 ALL = VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT;

    // --- Pass 1: SSAO or HBAO Generation ---
    int is_hbao = !strcmp(cfg_ao, "hbao");
    VkPipeline ao_pipe = is_hbao ? A.hbao_pipe : A.ssao_pipe;
    VkPipelineLayout ao_layout = is_hbao ? A.hbao_layout : A.ssao_layout;

    barrier(cb, A.last_depth, VK_IMAGE_LAYOUT_GENERAL, VK_IMAGE_LAYOUT_GENERAL,
            ALL, VK_ACCESS_2_MEMORY_WRITE_BIT, CS, VK_ACCESS_2_SHADER_SAMPLED_READ_BIT, VK_IMAGE_ASPECT_DEPTH_BIT);
    barrier(cb, A.raw_ao_img, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_GENERAL,
            ALL, 0, CS, VK_ACCESS_2_SHADER_STORAGE_WRITE_BIT, VK_IMAGE_ASPECT_COLOR_BIT);

    VkDescriptorImageInfo d_info = {A.sampler_linear, A.depth_view[slot], VK_IMAGE_LAYOUT_GENERAL};
    VkDescriptorImageInfo r_info = {VK_NULL_HANDLE, A.raw_ao_view, VK_IMAGE_LAYOUT_GENERAL};
    VkWriteDescriptorSet aow[2] = {
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstBinding = 0, .descriptorCount = 1,
         .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, .pImageInfo = &d_info},
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstBinding = 1, .descriptorCount = 1,
         .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, .pImageInfo = &r_info}};

    vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_COMPUTE, ao_pipe);
    rec_push(A.push, cb, VK_PIPELINE_BIND_POINT_COMPUTE, ao_layout, 0, 2, aow);

    // Camera projection constants (standard 60 deg vertical FOV)
    float fov_rad = 60.0f * 3.14159265f / 180.0f;
    float tan_half_fov = tanf(fov_rad * 0.5f);
    float p00 = 1.0f / (tan_half_fov * ((float)cw / (float)ch));
    float p11 = 1.0f / tan_half_fov;

    double cfg_intensity = cfg_double("DKB_AO_INTENSITY");
    float intensity = cfg_intensity > 0.0 ? (float)cfg_intensity : 1.0f;

    struct {
        int32_t size[2];
        float pad[2];
        float proj_info[4];
        float params[4]; // radius, bias, intensity, reverse_z
    } ao_pc = {
        {(int32_t)cw, (int32_t)ch}, {0},
        {2.0f / p00, 2.0f / p11, -1.0f / p00, -1.0f / p11},
        {is_hbao ? 1.5f : 1.2f, 0.05f, intensity, 1.0f} // Bananza uses reverse-Z
    };

    vkCmdPushConstants(cb, ao_layout, VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(ao_pc), &ao_pc);
    vkCmdDispatch(cb, (cw + 7) / 8, (ch + 7) / 8, 1);

    // --- Pass 2: Bilateral Depth-Aware Blur ---
    barrier(cb, A.raw_ao_img, VK_IMAGE_LAYOUT_GENERAL, VK_IMAGE_LAYOUT_GENERAL,
            CS, VK_ACCESS_2_SHADER_STORAGE_WRITE_BIT, CS, VK_ACCESS_2_SHADER_SAMPLED_READ_BIT, VK_IMAGE_ASPECT_COLOR_BIT);
    barrier(cb, A.blur_ao_img, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_GENERAL,
            ALL, 0, CS, VK_ACCESS_2_SHADER_STORAGE_WRITE_BIT, VK_IMAGE_ASPECT_COLOR_BIT);

    VkDescriptorImageInfo bl_raw = {A.sampler_point, A.raw_ao_view, VK_IMAGE_LAYOUT_GENERAL};
    VkDescriptorImageInfo bl_dep = {A.sampler_point, A.depth_view[slot], VK_IMAGE_LAYOUT_GENERAL};
    VkDescriptorImageInfo bl_dst = {VK_NULL_HANDLE, A.blur_ao_view, VK_IMAGE_LAYOUT_GENERAL};
    VkWriteDescriptorSet blw[3] = {
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstBinding = 0, .descriptorCount = 1,
         .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, .pImageInfo = &bl_raw},
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstBinding = 1, .descriptorCount = 1,
         .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, .pImageInfo = &bl_dep},
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstBinding = 2, .descriptorCount = 1,
         .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, .pImageInfo = &bl_dst}};

    vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_COMPUTE, A.blur_pipe);
    rec_push(A.push, cb, VK_PIPELINE_BIND_POINT_COMPUTE, A.blur_layout, 0, 3, blw);

    struct { int32_t size[2]; float step[2]; float sharpness; float dummy[3]; } blur_pc = {
        {(int32_t)cw, (int32_t)ch}, {1.0f / (float)cw, 1.0f / (float)ch}, 2.0f, {0}
    };
    vkCmdPushConstants(cb, A.blur_layout, VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(blur_pc), &blur_pc);
    vkCmdDispatch(cb, (cw + 7) / 8, (ch + 7) / 8, 1);

    // --- Pass 3: Composite (Color * AO) ---
    barrier(cb, A.blur_ao_img, VK_IMAGE_LAYOUT_GENERAL, VK_IMAGE_LAYOUT_GENERAL,
            CS, VK_ACCESS_2_SHADER_STORAGE_WRITE_BIT, CS, VK_ACCESS_2_SHADER_SAMPLED_READ_BIT, VK_IMAGE_ASPECT_COLOR_BIT);
    barrier(cb, src, VK_IMAGE_LAYOUT_GENERAL, VK_IMAGE_LAYOUT_GENERAL,
            ALL, VK_ACCESS_2_MEMORY_WRITE_BIT, CS, VK_ACCESS_2_SHADER_SAMPLED_READ_BIT, VK_IMAGE_ASPECT_COLOR_BIT);
    barrier(cb, A.out_img, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_GENERAL,
            ALL, 0, CS, VK_ACCESS_2_SHADER_STORAGE_WRITE_BIT, VK_IMAGE_ASPECT_COLOR_BIT);

    VkDescriptorImageInfo cp_col = {A.sampler_linear, A.src_view[slot], VK_IMAGE_LAYOUT_GENERAL};
    VkDescriptorImageInfo cp_ao = {A.sampler_linear, A.blur_ao_view, VK_IMAGE_LAYOUT_GENERAL};
    VkDescriptorImageInfo cp_dst = {VK_NULL_HANDLE, A.out_view, VK_IMAGE_LAYOUT_GENERAL};
    VkWriteDescriptorSet cpw[3] = {
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstBinding = 0, .descriptorCount = 1,
         .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, .pImageInfo = &cp_col},
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstBinding = 1, .descriptorCount = 1,
         .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, .pImageInfo = &cp_ao},
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstBinding = 2, .descriptorCount = 1,
         .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, .pImageInfo = &cp_dst}};

    vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_COMPUTE, A.comp_pipe);
    rec_push(A.push, cb, VK_PIPELINE_BIND_POINT_COMPUTE, A.comp_layout, 0, 3, cpw);

    struct { int32_t size[2]; float intensity; float dummy; } comp_pc = {
        {(int32_t)cw, (int32_t)ch}, intensity, 0.0f
    };
    vkCmdPushConstants(cb, A.comp_layout, VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(comp_pc), &comp_pc);
    vkCmdDispatch(cb, (cw + 7) / 8, (ch + 7) / 8, 1);

    barrier(cb, A.out_img, VK_IMAGE_LAYOUT_GENERAL, VK_IMAGE_LAYOUT_GENERAL,
            CS, VK_ACCESS_2_SHADER_STORAGE_WRITE_BIT, ALL, VK_ACCESS_2_MEMORY_READ_BIT, VK_IMAGE_ASPECT_COLOR_BIT);

    return A.out_img;
}

void vk_ao_release(void) {
    VkCtx *c = vk_ctx();
    for (int i = 0; i < SLOTS; i++) {
        if (A.src_view[i]) vkDestroyImageView(c->device, A.src_view[i], NULL);
        if (A.depth_view[i]) vkDestroyImageView(c->device, A.depth_view[i], NULL);
        A.src_view[i] = A.depth_view[i] = VK_NULL_HANDLE;
    }
    free_dynamic_images(c);

    if (A.sampler_linear) vkDestroySampler(c->device, A.sampler_linear, NULL);
    if (A.sampler_point) vkDestroySampler(c->device, A.sampler_point, NULL);

    if (A.ssao_pipe) vkDestroyPipeline(c->device, A.ssao_pipe, NULL);
    if (A.ssao_layout) vkDestroyPipelineLayout(c->device, A.ssao_layout, NULL);
    if (A.ssao_dsl) vkDestroyDescriptorSetLayout(c->device, A.ssao_dsl, NULL);

    if (A.hbao_pipe && A.hbao_pipe != A.ssao_pipe) vkDestroyPipeline(c->device, A.hbao_pipe, NULL);
    if (A.blur_pipe) vkDestroyPipeline(c->device, A.blur_pipe, NULL);
    if (A.blur_layout) vkDestroyPipelineLayout(c->device, A.blur_layout, NULL);
    if (A.blur_dsl) vkDestroyDescriptorSetLayout(c->device, A.blur_dsl, NULL);

    if (A.comp_pipe) vkDestroyPipeline(c->device, A.comp_pipe, NULL);
    if (A.comp_layout) vkDestroyPipelineLayout(c->device, A.comp_layout, NULL);
    if (A.comp_dsl) vkDestroyDescriptorSetLayout(c->device, A.comp_dsl, NULL);

    memset(&A, 0, sizeof(A));
}
