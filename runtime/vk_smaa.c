// Subpixel Morphological Anti-Aliasing (SMAA 1x) - Post-processing edge smoothing
// Reference implementation adapted from Jorge Jimenez et al. (MIT License)
#include "vk.h"
#include "vk_smaa.h"

#include <string.h>
#include <stdio.h>
#include <stdlib.h>

#include "cfg.h"
#include "host.h"
#include "smaa_lut.h"
#include "smaa_edge_spv.h"
#include "smaa_blend_spv.h"
#include "smaa_neighborhood_spv.h"

#define SLOTS 8

static struct {
    int tried, ok;
    int lut_uploaded;
    PFN_vkCmdPushDescriptorSetKHR push;

    // Static Lookup Textures
    VkImage search_img;
    VmaAllocation search_alloc;
    VkImageView search_view;
    VkBuffer search_stg;
    VmaAllocation search_stg_alloc;

    VkImage area_img;
    VmaAllocation area_alloc;
    VkImageView area_view;
    VkBuffer area_stg;
    VmaAllocation area_stg_alloc;

    VkSampler sampler_linear;
    VkSampler sampler_point;

    // Pass 1: Edge Detection
    VkDescriptorSetLayout edge_dsl;
    VkPipelineLayout edge_layout;
    VkPipeline edge_pipe;

    // Pass 2: Blending Weights
    VkDescriptorSetLayout blend_dsl;
    VkPipelineLayout blend_layout;
    VkPipeline blend_pipe;

    // Pass 3: Neighborhood Blending
    VkDescriptorSetLayout neigh_dsl;
    VkPipelineLayout neigh_layout;
    VkPipeline neigh_pipe;

    // Dynamic intermediate images
    uint32_t w, h;
    VkImage edges_img;
    VmaAllocation edges_alloc;
    VkImageView edges_view;

    VkImage blend_img;
    VmaAllocation blend_alloc;
    VkImageView blend_view;

    VkImage out_img;
    VmaAllocation out_alloc;
    VkImageView out_view;

    VkImageView src_view[SLOTS];
} S;

static void free_dynamic_images(VkCtx *c) {
    if (S.edges_view) vkDestroyImageView(c->device, S.edges_view, NULL);
    if (S.edges_img) vmaDestroyImage(c->vma, S.edges_img, S.edges_alloc);
    if (S.blend_view) vkDestroyImageView(c->device, S.blend_view, NULL);
    if (S.blend_img) vmaDestroyImage(c->vma, S.blend_img, S.blend_alloc);
    if (S.out_view) vkDestroyImageView(c->device, S.out_view, NULL);
    if (S.out_img) vmaDestroyImage(c->vma, S.out_img, S.out_alloc);
    S.edges_view = S.blend_view = S.out_view = VK_NULL_HANDLE;
    S.edges_img = S.blend_img = S.out_img = VK_NULL_HANDLE;
    S.w = S.h = 0;
}

static int ensure_dynamic_images(VkCtx *c, uint32_t w, uint32_t h) {
    if (S.out_img && S.w == w && S.h == h) return 1;
    vk_queue_lock();
    vkDeviceWaitIdle(c->device);
    vk_queue_unlock();
    free_dynamic_images(c);

    VmaAllocationCreateInfo ai = {.usage = VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE};

    // 1. Edges texture (RG8_UNORM)
    VkImageCreateInfo eci = {.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO, .imageType = VK_IMAGE_TYPE_2D,
                             .format = VK_FORMAT_R8G8_UNORM, .extent = {w, h, 1}, .mipLevels = 1, .arrayLayers = 1,
                             .samples = VK_SAMPLE_COUNT_1_BIT, .tiling = VK_IMAGE_TILING_OPTIMAL,
                             .usage = VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_SAMPLED_BIT};
    if (vmaCreateImage(c->vma, &eci, &ai, &S.edges_img, &S.edges_alloc, NULL) != VK_SUCCESS) return 0;
    VkImageViewCreateInfo evi = {.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO, .image = S.edges_img,
                                 .viewType = VK_IMAGE_VIEW_TYPE_2D, .format = VK_FORMAT_R8G8_UNORM,
                                 .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}};
    if (vkCreateImageView(c->device, &evi, NULL, &S.edges_view) != VK_SUCCESS) return 0;

    // 2. Blending weights texture (RGBA8_UNORM)
    VkImageCreateInfo bci = {.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO, .imageType = VK_IMAGE_TYPE_2D,
                             .format = VK_FORMAT_R8G8B8A8_UNORM, .extent = {w, h, 1}, .mipLevels = 1, .arrayLayers = 1,
                             .samples = VK_SAMPLE_COUNT_1_BIT, .tiling = VK_IMAGE_TILING_OPTIMAL,
                             .usage = VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_SAMPLED_BIT};
    if (vmaCreateImage(c->vma, &bci, &ai, &S.blend_img, &S.blend_alloc, NULL) != VK_SUCCESS) return 0;
    VkImageViewCreateInfo bvi = {.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO, .image = S.blend_img,
                                 .viewType = VK_IMAGE_VIEW_TYPE_2D, .format = VK_FORMAT_R8G8B8A8_UNORM,
                                 .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}};
    if (vkCreateImageView(c->device, &bvi, NULL, &S.blend_view) != VK_SUCCESS) return 0;

    // 3. Anti-aliased output image (RGBA16F)
    VkImageCreateInfo oci = {.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO, .imageType = VK_IMAGE_TYPE_2D,
                             .format = VK_FORMAT_R16G16B16A16_SFLOAT, .extent = {w, h, 1}, .mipLevels = 1, .arrayLayers = 1,
                             .samples = VK_SAMPLE_COUNT_1_BIT, .tiling = VK_IMAGE_TILING_OPTIMAL,
                             .usage = VK_IMAGE_USAGE_STORAGE_BIT | VK_IMAGE_USAGE_SAMPLED_BIT | VK_IMAGE_USAGE_TRANSFER_SRC_BIT};
    if (vmaCreateImage(c->vma, &oci, &ai, &S.out_img, &S.out_alloc, NULL) != VK_SUCCESS) return 0;
    VkImageViewCreateInfo ovi = {.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO, .image = S.out_img,
                                 .viewType = VK_IMAGE_VIEW_TYPE_2D, .format = VK_FORMAT_R16G16B16A16_SFLOAT,
                                 .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}};
    if (vkCreateImageView(c->device, &ovi, NULL, &S.out_view) != VK_SUCCESS) return 0;

    S.w = w; S.h = h;
    return 1;
}

static int init_luts(VkCtx *c) {
    VmaAllocationCreateInfo dai = {.usage = VMA_MEMORY_USAGE_AUTO_PREFER_DEVICE};
    VmaAllocationCreateInfo sai = {.usage = VMA_MEMORY_USAGE_AUTO,
                                   .flags = VMA_ALLOCATION_CREATE_HOST_ACCESS_SEQUENTIAL_WRITE_BIT |
                                            VMA_ALLOCATION_CREATE_MAPPED_BIT};

    // 1. SearchTex (64x16, R8_UNORM)
    VkImageCreateInfo sci = {.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO, .imageType = VK_IMAGE_TYPE_2D,
                             .format = VK_FORMAT_R8_UNORM, .extent = {SMAA_SEARCHTEX_WIDTH, SMAA_SEARCHTEX_HEIGHT, 1},
                             .mipLevels = 1, .arrayLayers = 1, .samples = VK_SAMPLE_COUNT_1_BIT,
                             .tiling = VK_IMAGE_TILING_OPTIMAL,
                             .usage = VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_SAMPLED_BIT};
    if (vmaCreateImage(c->vma, &sci, &dai, &S.search_img, &S.search_alloc, NULL) != VK_SUCCESS) return 0;
    VkImageViewCreateInfo svi = {.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO, .image = S.search_img,
                                 .viewType = VK_IMAGE_VIEW_TYPE_2D, .format = VK_FORMAT_R8_UNORM,
                                 .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}};
    if (vkCreateImageView(c->device, &svi, NULL, &S.search_view) != VK_SUCCESS) return 0;

    VkBufferCreateInfo sbi = {.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, .size = sizeof(smaa_search_tex),
                              .usage = VK_BUFFER_USAGE_TRANSFER_SRC_BIT};
    VmaAllocationInfo sinfo;
    if (vmaCreateBuffer(c->vma, &sbi, &sai, &S.search_stg, &S.search_stg_alloc, &sinfo) != VK_SUCCESS) return 0;
    memcpy(sinfo.pMappedData, smaa_search_tex, sizeof(smaa_search_tex));

    // 2. AreaTex (160x560, R8G8_UNORM)
    VkImageCreateInfo aci = {.sType = VK_STRUCTURE_TYPE_IMAGE_CREATE_INFO, .imageType = VK_IMAGE_TYPE_2D,
                             .format = VK_FORMAT_R8G8_UNORM, .extent = {SMAA_AREATEX_WIDTH, SMAA_AREATEX_HEIGHT, 1},
                             .mipLevels = 1, .arrayLayers = 1, .samples = VK_SAMPLE_COUNT_1_BIT,
                             .tiling = VK_IMAGE_TILING_OPTIMAL,
                             .usage = VK_IMAGE_USAGE_TRANSFER_DST_BIT | VK_IMAGE_USAGE_SAMPLED_BIT};
    if (vmaCreateImage(c->vma, &aci, &dai, &S.area_img, &S.area_alloc, NULL) != VK_SUCCESS) return 0;
    VkImageViewCreateInfo avi = {.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO, .image = S.area_img,
                                 .viewType = VK_IMAGE_VIEW_TYPE_2D, .format = VK_FORMAT_R8G8_UNORM,
                                 .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}};
    if (vkCreateImageView(c->device, &avi, NULL, &S.area_view) != VK_SUCCESS) return 0;

    VkBufferCreateInfo abi = {.sType = VK_STRUCTURE_TYPE_BUFFER_CREATE_INFO, .size = sizeof(smaa_area_tex),
                              .usage = VK_BUFFER_USAGE_TRANSFER_SRC_BIT};
    VmaAllocationInfo ainfo;
    if (vmaCreateBuffer(c->vma, &abi, &sai, &S.area_stg, &S.area_stg_alloc, &ainfo) != VK_SUCCESS) return 0;
    memcpy(ainfo.pMappedData, smaa_area_tex, sizeof(smaa_area_tex));

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

void vk_smaa_init(void) {
    S.tried = 1;
    VkCtx *c = vk_ctx();
    S.push = (PFN_vkCmdPushDescriptorSetKHR)vkGetDeviceProcAddr(c->device, "vkCmdPushDescriptorSetKHR");
    if (!S.push) {
        rt_log("vk_smaa: push descriptors not supported; SMAA disabled");
        return;
    }

    // Samplers
    VkSamplerCreateInfo sli = {.sType = VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO, .magFilter = VK_FILTER_LINEAR,
                               .minFilter = VK_FILTER_LINEAR, .mipmapMode = VK_SAMPLER_MIPMAP_MODE_NEAREST,
                               .addressModeU = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,
                               .addressModeV = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,
                               .addressModeW = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE, .maxLod = 0};
    if (vkCreateSampler(c->device, &sli, NULL, &S.sampler_linear) != VK_SUCCESS) return;

    VkSamplerCreateInfo spi = {.sType = VK_STRUCTURE_TYPE_SAMPLER_CREATE_INFO, .magFilter = VK_FILTER_NEAREST,
                               .minFilter = VK_FILTER_NEAREST, .mipmapMode = VK_SAMPLER_MIPMAP_MODE_NEAREST,
                               .addressModeU = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,
                               .addressModeV = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE,
                               .addressModeW = VK_SAMPLER_ADDRESS_MODE_CLAMP_TO_EDGE, .maxLod = 0};
    if (vkCreateSampler(c->device, &spi, NULL, &S.sampler_point) != VK_SUCCESS) return;

    if (!init_luts(c)) {
        rt_log("vk_smaa: failed to initialize AreaTex/SearchTex LUTs");
        return;
    }

    // 1. Edge Pass Pipeline
    VkDescriptorSetLayoutBinding eb[2] = {
        {.binding = 0, .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT},
        {.binding = 1, .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT}};
    VkDescriptorSetLayoutCreateInfo edci = {.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
                                            .flags = VK_DESCRIPTOR_SET_LAYOUT_CREATE_PUSH_DESCRIPTOR_BIT_KHR,
                                            .bindingCount = 2, .pBindings = eb};
    VkPushConstantRange epr = {VK_SHADER_STAGE_COMPUTE_BIT, 0, 16};
    if (vkCreateDescriptorSetLayout(c->device, &edci, NULL, &S.edge_dsl) != VK_SUCCESS) return;
    VkPipelineLayoutCreateInfo eli = {.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO, .setLayoutCount = 1,
                                      .pSetLayouts = &S.edge_dsl, .pushConstantRangeCount = 1, .pPushConstantRanges = &epr};
    if (vkCreatePipelineLayout(c->device, &eli, NULL, &S.edge_layout) != VK_SUCCESS) return;
    S.edge_pipe = make_compute_pipe(c, S.edge_layout, smaa_edge_spv, sizeof(smaa_edge_spv));

    // 2. Blend Pass Pipeline
    VkDescriptorSetLayoutBinding bb[4] = {
        {.binding = 0, .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT},
        {.binding = 1, .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT},
        {.binding = 2, .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT},
        {.binding = 3, .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT}};
    VkDescriptorSetLayoutCreateInfo bdci = {.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
                                            .flags = VK_DESCRIPTOR_SET_LAYOUT_CREATE_PUSH_DESCRIPTOR_BIT_KHR,
                                            .bindingCount = 4, .pBindings = bb};
    VkPushConstantRange bpr = {VK_SHADER_STAGE_COMPUTE_BIT, 0, 24};
    if (vkCreateDescriptorSetLayout(c->device, &bdci, NULL, &S.blend_dsl) != VK_SUCCESS) return;
    VkPipelineLayoutCreateInfo bli = {.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO, .setLayoutCount = 1,
                                      .pSetLayouts = &S.blend_dsl, .pushConstantRangeCount = 1, .pPushConstantRanges = &bpr};
    if (vkCreatePipelineLayout(c->device, &bli, NULL, &S.blend_layout) != VK_SUCCESS) return;
    S.blend_pipe = make_compute_pipe(c, S.blend_layout, smaa_blend_spv, sizeof(smaa_blend_spv));

    // 3. Neighborhood Blending Pipeline
    VkDescriptorSetLayoutBinding nb[3] = {
        {.binding = 0, .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT},
        {.binding = 1, .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT},
        {.binding = 2, .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, .descriptorCount = 1, .stageFlags = VK_SHADER_STAGE_COMPUTE_BIT}};
    VkDescriptorSetLayoutCreateInfo ndci = {.sType = VK_STRUCTURE_TYPE_DESCRIPTOR_SET_LAYOUT_CREATE_INFO,
                                            .flags = VK_DESCRIPTOR_SET_LAYOUT_CREATE_PUSH_DESCRIPTOR_BIT_KHR,
                                            .bindingCount = 3, .pBindings = nb};
    VkPushConstantRange npr = {VK_SHADER_STAGE_COMPUTE_BIT, 0, 24};
    if (vkCreateDescriptorSetLayout(c->device, &ndci, NULL, &S.neigh_dsl) != VK_SUCCESS) return;
    VkPipelineLayoutCreateInfo nli = {.sType = VK_STRUCTURE_TYPE_PIPELINE_LAYOUT_CREATE_INFO, .setLayoutCount = 1,
                                      .pSetLayouts = &S.neigh_dsl, .pushConstantRangeCount = 1, .pPushConstantRanges = &npr};
    if (vkCreatePipelineLayout(c->device, &nli, NULL, &S.neigh_layout) != VK_SUCCESS) return;
    S.neigh_pipe = make_compute_pipe(c, S.neigh_layout, smaa_neighborhood_spv, sizeof(smaa_neighborhood_spv));

    if (S.edge_pipe && S.blend_pipe && S.neigh_pipe) {
        S.ok = 1;
        rt_log("vk_smaa: SMAA 1x compute pipelines initialized successfully");
    }
}

static void barrier(VkCommandBuffer cb, VkImage img, VkImageLayout from, VkImageLayout to,
                    VkPipelineStageFlags2 ss, VkAccessFlags2 sa, VkPipelineStageFlags2 ds, VkAccessFlags2 da) {
    VkImageMemoryBarrier2 b = {.sType = VK_STRUCTURE_TYPE_IMAGE_MEMORY_BARRIER_2,
                               .srcStageMask = ss, .srcAccessMask = sa,
                               .dstStageMask = ds, .dstAccessMask = da,
                               .oldLayout = from, .newLayout = to,
                               .srcQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                               .dstQueueFamilyIndex = VK_QUEUE_FAMILY_IGNORED,
                               .image = img, .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}};
    VkDependencyInfo d = {.sType = VK_STRUCTURE_TYPE_DEPENDENCY_INFO, .imageMemoryBarrierCount = 1, .pImageMemoryBarriers = &b};
    vkCmdPipelineBarrier2(cb, &d);
}

static void upload_luts(VkCommandBuffer cb, VkCtx *c) {
    if (S.lut_uploaded) return;
    barrier(cb, S.search_img, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
            VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT, 0, VK_PIPELINE_STAGE_2_TRANSFER_BIT, VK_ACCESS_2_TRANSFER_WRITE_BIT);
    VkBufferImageCopy scp = {.imageSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1},
                             .imageExtent = {SMAA_SEARCHTEX_WIDTH, SMAA_SEARCHTEX_HEIGHT, 1}};
    vkCmdCopyBufferToImage(cb, S.search_stg, S.search_img, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &scp);
    barrier(cb, S.search_img, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, VK_IMAGE_LAYOUT_GENERAL,
            VK_PIPELINE_STAGE_2_TRANSFER_BIT, VK_ACCESS_2_TRANSFER_WRITE_BIT,
            VK_PIPELINE_STAGE_2_COMPUTE_SHADER_BIT, VK_ACCESS_2_SHADER_SAMPLED_READ_BIT);

    barrier(cb, S.area_img, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL,
            VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT, 0, VK_PIPELINE_STAGE_2_TRANSFER_BIT, VK_ACCESS_2_TRANSFER_WRITE_BIT);
    VkBufferImageCopy acp = {.imageSubresource = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 0, 1},
                             .imageExtent = {SMAA_AREATEX_WIDTH, SMAA_AREATEX_HEIGHT, 1}};
    vkCmdCopyBufferToImage(cb, S.area_stg, S.area_img, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, 1, &acp);
    barrier(cb, S.area_img, VK_IMAGE_LAYOUT_TRANSFER_DST_OPTIMAL, VK_IMAGE_LAYOUT_GENERAL,
            VK_PIPELINE_STAGE_2_TRANSFER_BIT, VK_ACCESS_2_TRANSFER_WRITE_BIT,
            VK_PIPELINE_STAGE_2_COMPUTE_SHADER_BIT, VK_ACCESS_2_SHADER_SAMPLED_READ_BIT);

    S.lut_uploaded = 1;
}

VkImage vk_smaa_record(VkCommandBuffer cb, unsigned slot, VkImage src, VkFormat fmt, int w, int h, const int crop[4]) {
    const char *cfg_smaa = cfg_value("DKB_SMAA");
    if (!cfg_smaa || !strcmp(cfg_smaa, "0") || !*cfg_smaa) return VK_NULL_HANDLE;

    VkCtx *c = vk_ctx();
    if (!S.tried) vk_smaa_init();
    if (!S.ok) return VK_NULL_HANDLE;

    uint32_t cw = (uint32_t)(crop ? crop[2] : w);
    uint32_t ch = (uint32_t)(crop ? crop[3] : h);
    if (!ensure_dynamic_images(c, cw, ch)) return VK_NULL_HANDLE;

    upload_luts(cb, c);

    slot %= SLOTS;
    if (S.src_view[slot]) vkDestroyImageView(c->device, S.src_view[slot], NULL);
    VkImageViewCreateInfo vi = {.sType = VK_STRUCTURE_TYPE_IMAGE_VIEW_CREATE_INFO, .image = src,
                                .viewType = VK_IMAGE_VIEW_TYPE_2D, .format = fmt,
                                .subresourceRange = {VK_IMAGE_ASPECT_COLOR_BIT, 0, 1, 0, 1}};
    if (vkCreateImageView(c->device, &vi, NULL, &S.src_view[slot]) != VK_SUCCESS) return VK_NULL_HANDLE;

    const VkPipelineStageFlags2 CS = VK_PIPELINE_STAGE_2_COMPUTE_SHADER_BIT;
    const VkPipelineStageFlags2 ALL = VK_PIPELINE_STAGE_2_ALL_COMMANDS_BIT;

    // --- Pass 1: Edge Detection ---
    barrier(cb, src, VK_IMAGE_LAYOUT_GENERAL, VK_IMAGE_LAYOUT_GENERAL,
            ALL, VK_ACCESS_2_MEMORY_WRITE_BIT, CS, VK_ACCESS_2_SHADER_SAMPLED_READ_BIT);
    barrier(cb, S.edges_img, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_GENERAL,
            ALL, 0, CS, VK_ACCESS_2_SHADER_STORAGE_WRITE_BIT);

    VkDescriptorImageInfo edge_src = {S.sampler_linear, S.src_view[slot], VK_IMAGE_LAYOUT_GENERAL};
    VkDescriptorImageInfo edge_dst = {VK_NULL_HANDLE, S.edges_view, VK_IMAGE_LAYOUT_GENERAL};
    VkWriteDescriptorSet ew[2] = {
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstBinding = 0, .descriptorCount = 1,
         .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, .pImageInfo = &edge_src},
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstBinding = 1, .descriptorCount = 1,
         .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, .pImageInfo = &edge_dst}};
    vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_COMPUTE, S.edge_pipe);
    rec_push(S.push, cb, VK_PIPELINE_BIND_POINT_COMPUTE, S.edge_layout, 0, 2, ew);

    struct { int32_t size[2]; float threshold, dummy; } edge_pc = {{(int32_t)cw, (int32_t)ch}, 0.1f, 0.0f};
    vkCmdPushConstants(cb, S.edge_layout, VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(edge_pc), &edge_pc);
    vkCmdDispatch(cb, (cw + 7) / 8, (ch + 7) / 8, 1);

    // --- Pass 2: Blending Weights ---
    barrier(cb, S.edges_img, VK_IMAGE_LAYOUT_GENERAL, VK_IMAGE_LAYOUT_GENERAL,
            CS, VK_ACCESS_2_SHADER_STORAGE_WRITE_BIT, CS, VK_ACCESS_2_SHADER_SAMPLED_READ_BIT);
    barrier(cb, S.blend_img, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_GENERAL,
            ALL, 0, CS, VK_ACCESS_2_SHADER_STORAGE_WRITE_BIT);

    VkDescriptorImageInfo bl_edge = {S.sampler_point, S.edges_view, VK_IMAGE_LAYOUT_GENERAL};
    VkDescriptorImageInfo bl_area = {S.sampler_linear, S.area_view, VK_IMAGE_LAYOUT_GENERAL};
    VkDescriptorImageInfo bl_search = {S.sampler_point, S.search_view, VK_IMAGE_LAYOUT_GENERAL};
    VkDescriptorImageInfo bl_dst = {VK_NULL_HANDLE, S.blend_view, VK_IMAGE_LAYOUT_GENERAL};
    VkWriteDescriptorSet bw[4] = {
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstBinding = 0, .descriptorCount = 1,
         .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, .pImageInfo = &bl_edge},
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstBinding = 1, .descriptorCount = 1,
         .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, .pImageInfo = &bl_area},
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstBinding = 2, .descriptorCount = 1,
         .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, .pImageInfo = &bl_search},
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstBinding = 3, .descriptorCount = 1,
         .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, .pImageInfo = &bl_dst}};
    vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_COMPUTE, S.blend_pipe);
    rec_push(S.push, cb, VK_PIPELINE_BIND_POINT_COMPUTE, S.blend_layout, 0, 4, bw);

    struct { int32_t size[2]; float metrics[4]; } bl_pc = {{(int32_t)cw, (int32_t)ch},
                                                           {1.0f / (float)cw, 1.0f / (float)ch, (float)cw, (float)ch}};
    vkCmdPushConstants(cb, S.blend_layout, VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(bl_pc), &bl_pc);
    vkCmdDispatch(cb, (cw + 7) / 8, (ch + 7) / 8, 1);

    // --- Pass 3: Neighborhood Blending ---
    barrier(cb, S.blend_img, VK_IMAGE_LAYOUT_GENERAL, VK_IMAGE_LAYOUT_GENERAL,
            CS, VK_ACCESS_2_SHADER_STORAGE_WRITE_BIT, CS, VK_ACCESS_2_SHADER_SAMPLED_READ_BIT);
    barrier(cb, S.out_img, VK_IMAGE_LAYOUT_UNDEFINED, VK_IMAGE_LAYOUT_GENERAL,
            ALL, 0, CS, VK_ACCESS_2_SHADER_STORAGE_WRITE_BIT);

    VkDescriptorImageInfo nb_src = {S.sampler_linear, S.src_view[slot], VK_IMAGE_LAYOUT_GENERAL};
    VkDescriptorImageInfo nb_blend = {S.sampler_point, S.blend_view, VK_IMAGE_LAYOUT_GENERAL};
    VkDescriptorImageInfo nb_dst = {VK_NULL_HANDLE, S.out_view, VK_IMAGE_LAYOUT_GENERAL};
    VkWriteDescriptorSet nw[3] = {
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstBinding = 0, .descriptorCount = 1,
         .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, .pImageInfo = &nb_src},
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstBinding = 1, .descriptorCount = 1,
         .descriptorType = VK_DESCRIPTOR_TYPE_COMBINED_IMAGE_SAMPLER, .pImageInfo = &nb_blend},
        {.sType = VK_STRUCTURE_TYPE_WRITE_DESCRIPTOR_SET, .dstBinding = 2, .descriptorCount = 1,
         .descriptorType = VK_DESCRIPTOR_TYPE_STORAGE_IMAGE, .pImageInfo = &nb_dst}};
    vkCmdBindPipeline(cb, VK_PIPELINE_BIND_POINT_COMPUTE, S.neigh_pipe);
    rec_push(S.push, cb, VK_PIPELINE_BIND_POINT_COMPUTE, S.neigh_layout, 0, 3, nw);

    vkCmdPushConstants(cb, S.neigh_layout, VK_SHADER_STAGE_COMPUTE_BIT, 0, sizeof(bl_pc), &bl_pc);
    vkCmdDispatch(cb, (cw + 7) / 8, (ch + 7) / 8, 1);

    barrier(cb, S.out_img, VK_IMAGE_LAYOUT_GENERAL, VK_IMAGE_LAYOUT_GENERAL,
            CS, VK_ACCESS_2_SHADER_STORAGE_WRITE_BIT, ALL, VK_ACCESS_2_MEMORY_READ_BIT);

    return S.out_img;
}

void vk_smaa_release(void) {
    VkCtx *c = vk_ctx();
    for (int i = 0; i < SLOTS; i++) {
        if (S.src_view[i]) vkDestroyImageView(c->device, S.src_view[i], NULL);
        S.src_view[i] = VK_NULL_HANDLE;
    }
    free_dynamic_images(c);

    if (S.search_view) vkDestroyImageView(c->device, S.search_view, NULL);
    if (S.search_img) vmaDestroyImage(c->vma, S.search_img, S.search_alloc);
    if (S.search_stg) vmaDestroyBuffer(c->vma, S.search_stg, S.search_stg_alloc);

    if (S.area_view) vkDestroyImageView(c->device, S.area_view, NULL);
    if (S.area_img) vmaDestroyImage(c->vma, S.area_img, S.area_alloc);
    if (S.area_stg) vmaDestroyBuffer(c->vma, S.area_stg, S.area_stg_alloc);

    if (S.sampler_linear) vkDestroySampler(c->device, S.sampler_linear, NULL);
    if (S.sampler_point) vkDestroySampler(c->device, S.sampler_point, NULL);

    if (S.edge_pipe) vkDestroyPipeline(c->device, S.edge_pipe, NULL);
    if (S.edge_layout) vkDestroyPipelineLayout(c->device, S.edge_layout, NULL);
    if (S.edge_dsl) vkDestroyDescriptorSetLayout(c->device, S.edge_dsl, NULL);

    if (S.blend_pipe) vkDestroyPipeline(c->device, S.blend_pipe, NULL);
    if (S.blend_layout) vkDestroyPipelineLayout(c->device, S.blend_layout, NULL);
    if (S.blend_dsl) vkDestroyDescriptorSetLayout(c->device, S.blend_dsl, NULL);

    if (S.neigh_pipe) vkDestroyPipeline(c->device, S.neigh_pipe, NULL);
    if (S.neigh_layout) vkDestroyPipelineLayout(c->device, S.neigh_layout, NULL);
    if (S.neigh_dsl) vkDestroyDescriptorSetLayout(c->device, S.neigh_dsl, NULL);

    memset(&S, 0, sizeof(S));
}
