// NVN 2 procs Donkey Kong Bananza asks for beyond TotK's NVN (runtime/nvn_procs_nvn2.inc). Only the calls whose effect
// the host can honour without knowing a new NVN 2 structure layout are here; the rest stop with their name
// (nvn_procs.c) until a call shows what they need.
#include <stdint.h>
#include <string.h>

#include "gfx.h"
#include "host.h"
#include "nvn_api.h"
#include "nvn_mode_trace.h"
#include "nvn_obj.h"
#include "platform/platform.h"

// ---- Queues. The host has one queue model: a queue's primary queue and its ray-tracing memory change nothing.
// void nvnQueueBuilderSetPrimaryQueue(NVNqueueBuilder *b, NVNqueue *primary)
NVN_API(nvnQueueBuilderSetPrimaryQueue) { NVN_LOG("QueueBuilderSetPrimaryQueue %p", arg_p(c, 1)); }
// void nvnQueueBuilderSetRayTracingMemorySize(NVNqueueBuilder *b, size_t n)
NVN_API(nvnQueueBuilderSetRayTracingMemorySize) { (void)c; }
// size_t nvnQueueBuilderGetRayTracingMemorySize(const NVNqueueBuilder *b)
NVN_API(nvnQueueBuilderGetRayTracingMemorySize) { ret_x(c, 0); }
// size_t nvnQueueGetTotalRayTracingMemoryUsed(const NVNqueue *q)
NVN_API(nvnQueueGetTotalRayTracingMemoryUsed) { ret_x(c, 0); }

// ---- Device
// int nvnDeviceGetFlags(const NVNdevice *d): the flags the device was initialized with
NVN_API(nvnDeviceGetFlags) { ret_x(c, ((const dev_t_ *)arg_p(c, 0))->flags); }
// size_t nvnDeviceGetCommandHandleMemorySize(const NVNdevice *d): host command handles fit in 64 bytes
NVN_API(nvnDeviceGetCommandHandleMemorySize) { ret_x(c, 64); }
// NVNbufferAddress nvnDeviceGetUniformBufferHandle(const NVNdevice *d, NVNbufferAddress addr, size_t size): GPU address
NVN_API(nvnDeviceGetUniformBufferHandle) { ret_x(c, arg_x(c, 1)); }
// Device command buffer builder/handle stubs (Begin/End/SubmitDeviceCommands are NVN2_NOT_RECORDED below)
NVN_API(nvnDeviceCommandBufferSetDefaults) { (void)c; }
NVN_API(nvnDeviceCommandBufferSetDevice) { (void)c; }
NVN_API(nvnDeviceCommandBufferSetStorage) { (void)c; }
NVN_API(nvnDeviceCommandBufferSetCommandMemorySize) { (void)c; }
NVN_API(nvnDeviceCommandBufferSetComputeMemorySize) { (void)c; }
NVN_API(nvnDeviceCommandBufferGetHandle) { ret_x(c, 0); }
// Device-level ray-tracing acceleration structure helpers (ray tracing is off on the host; zero memory requirements)
NVN_API(nvnDeviceCalculateAccelerationStructureMemoryRequirements) {
    static volatile int32_t logged;
    if (!__atomic_exchange_n(&logged, 1, __ATOMIC_RELAXED))
        rt_log("nvn2: nvnDeviceCalculateAccelerationStructureMemoryRequirements ignored (ray tracing off)");
    void *out = arg_p(c, 2);
    if (out) memset(out, 0, 32);
}
NVN_API(nvnDeviceCompactAccelerationStructure) { (void)c; }
NVN_API(nvnDeviceCopyAccelerationStructure) { (void)c; }
NVN_API(nvnDeviceRelocateAccelerationStructure) { (void)c; }
// NVNboolean nvnDeviceRegisterFastClear{Color,Colori,Colorui}Index(NVNdevice *, const T *color, NVNformat, int index),
// ...Stencil(NVNdevice *, int value): like the NVN 1 forms (nvn_api_core.c), "not registered" keeps the normal clear
NVN_API(nvnDeviceRegisterFastClearColorIndex) { ret_x(c, 0); }
NVN_API(nvnDeviceRegisterFastClearColoriIndex) { ret_x(c, 0); }
NVN_API(nvnDeviceRegisterFastClearColoruiIndex) { ret_x(c, 0); }
NVN_API(nvnDeviceRegisterFastClearStencil) { ret_x(c, 0); }
// Depth/stencil fast-clear indexes (NVN 2): "not registered" keeps the normal clear path.
NVN_API(nvnDeviceRegisterFastClearDepthIndex) { ret_x(c, 0); }
NVN_API(nvnDeviceRegisterFastClearStencilIndex) { ret_x(c, 0); }

// ---- Device message buffer (driver debug messages): the host driver writes none
NVN_API(nvnDeviceMessageBufferSetDefaults) { (void)c; }
NVN_API(nvnDeviceMessageBufferSetDevice) { (void)c; }
NVN_API(nvnDeviceMessageBufferSetStorage) { (void)c; }
NVN_API(nvnDeviceMessageBufferBeginMessages) { (void)c; }
NVN_API(nvnDeviceMessageBufferEndMessages) { (void)c; }
NVN_API(nvnDeviceMessageBufferReset) { (void)c; }
// const NVNdeviceMessage *nvnDeviceMessageBufferGetNextMessage(...): no message
NVN_API(nvnDeviceMessageBufferGetNextMessage) { ret_x(c, 0); }

// ---- Multisample state: coverage truncation is a hint the Vulkan back end has no switch for
NVN_API(nvnMultisampleStateSetCoverageTruncationEnable) { (void)c; }
NVN_API(nvnMultisampleStateGetCoverageTruncationEnable) { ret_x(c, 0); }

// ---- Window colour space and HDR metadata: the host presents SDR sRGB
// void nvnWindowBuilderSetColorSpace(NVNwindowBuilder *, NVNcolorSpace), NVNcolorSpace ...GetColorSpace(...): 0, sRGB
NVN_API(nvnWindowBuilderSetColorSpace) { NVN_LOG("WindowBuilderSetColorSpace %d", (int)arg_x(c, 1)); }
NVN_API(nvnWindowBuilderGetColorSpace) { ret_x(c, 0); }
// void ...Set{Hdr}Display/ContentMetadata(obj, const metadata *): kept by no one; getters write 0 floats (SDR)
NVN_API(nvnWindowBuilderSetHdrDisplayMetadata) { (void)c; }
NVN_API(nvnWindowBuilderSetHdrContentMetadata) { (void)c; }
NVN_API(nvnWindowSetHdrDisplayMetadata) { (void)c; }
NVN_API(nvnWindowSetHdrContentMetadata) { (void)c; }
static void nvn2_zero_float_outs(Cpu *c, int first, int count) {
    for (int i = first; i < first + count; i++) {
        float *p = arg_p(c, i);
        if (p) *p = 0.0f;
    }
}
NVN_API(nvnWindowBuilderGetHdrContentMetadata) { nvn2_zero_float_outs(c, 1, 2); }
NVN_API(nvnWindowGetHdrContentMetadata) { nvn2_zero_float_outs(c, 1, 2); }
NVN_API(nvnWindowBuilderGetHdrDisplayMetadata) { nvn2_zero_float_outs(c, 1, 10); }
NVN_API(nvnWindowGetHdrDisplayMetadata) { nvn2_zero_float_outs(c, 1, 10); }

// void nvnCommandBufferSetComputeOverlapMode(NVNcommandBuffer *cmd, uint32_t mode)
// NVN 2 changes compute/graphics scheduling, not shader or resource state (docs/nvn2-command-modes.md).
// Our dispatch and graphics-pass boundaries already insert full barriers on one queue, so both scheduling modes
// retain that conservative ordering. Allowing overlap does not require the host to execute work concurrently.
NVN_API(nvnCommandBufferSetComputeOverlapMode) { (void)c; }

// ---- Command buffer calls new in NVN 2. Until the Vulkan back end learns them (mesh shaders, ray tracing, DLSS,
// variable-rate shading, conditional enables, device command buffers), they are accepted and
// recorded nowhere, and the first call of each is logged, so a run lists what the back end still has to do. None of
// them returns a value.
#define NVN2_NOT_RECORDED(n)                                                                                         \
    NVN_API(n) {                                                                                                     \
        static volatile int32_t logged;                                                                              \
        (void)c;                                                                                                     \
        if (!__atomic_exchange_n(&logged, 1, __ATOMIC_RELAXED)) rt_log("nvn2: " #n " accepted, not recorded yet");   \
    }
// A mode call whose values up to `ok` are handled by doing nothing, with the reason in docs/nvn2-command-modes.md; a
// larger value is logged once with its number, so a scene that needs more than the host gives shows up in the log.
#define NVN2_MODE_HANDLED(n, kind, ok)                                                                                \
    NVN_API(n) {                                                                                                    \
        static volatile int32_t logged;                                                                             \
        uint32_t mode = (uint32_t)arg_x(c, 1);                                                                      \
        nvn_mode_trace(kind, arg_x(c, 0), 0, mode, 0);                                                              \
        if (mode > (ok) && !__atomic_exchange_n(&logged, 1, __ATOMIC_RELAXED))                                      \
            rt_log("nvn2: " #n " mode %u is not supported (handled: 0..%u); accepted, not recorded", mode, (unsigned)(ok)); \
    }
// Recording mode: 0 and 1 are what the tutorial and cave call. 1 selects the SDK's compute synchronization path,
// which the host's barriers around dispatches and passes already cover. 2 (copy fence) to 4 (packing) are not.
NVN2_MODE_HANDLED(nvnCommandBufferSetRecordingMode, NVN_MODE_RECORDING, 1)
NVN2_NOT_RECORDED(nvnCommandBufferBeginDeviceCommands)
NVN2_NOT_RECORDED(nvnCommandBufferEndDeviceCommands)
NVN2_NOT_RECORDED(nvnCommandBufferSubmitDeviceCommands)
NVN2_NOT_RECORDED(nvnCommandBufferBindAccelerationStructure)
NVN2_NOT_RECORDED(nvnCommandBufferBindAccelerationStructures)
NVN2_NOT_RECORDED(nvnCommandBufferBindAccelerationStructuresDeferred)
NVN2_NOT_RECORDED(nvnCommandBufferBuildAccelerationStructures)
NVN2_NOT_RECORDED(nvnCommandBufferCompactAccelerationStructure)
NVN2_NOT_RECORDED(nvnCommandBufferCopyAccelerationStructure)
NVN2_NOT_RECORDED(nvnCommandBufferRelocateAccelerationStructure)
NVN2_NOT_RECORDED(nvnCommandBufferDispatchRays)
NVN2_NOT_RECORDED(nvnCommandBufferDispatchRaysIndirect)
NVN2_NOT_RECORDED(nvnCommandBufferBindDeviceMessageBuffer)
NVN2_NOT_RECORDED(nvnCommandBufferBindDeviceMessageBufferDeferred)
NVN2_NOT_RECORDED(nvnCommandBufferResetDeviceMessageBuffer)
NVN2_NOT_RECORDED(nvnCommandBufferResetDeviceMessageBufferDeferred)
NVN2_NOT_RECORDED(nvnCommandBufferBindShadingRateImage)
NVN2_NOT_RECORDED(nvnCommandBufferSetShadingRatePaletteMode)
NVN2_NOT_RECORDED(nvnCommandBufferShadingRateImagePalette)
// Dirty-tile map: Mario Tennis Fever's deferred court lighting. GetProc must not be NULL (that left
// the tile buffer untouched and drew the black half-quad grid over the court). Until the Vulkan
// replay can classify tiles from the G-buffer, keep Set/Get coherent in a host-side table and on
// Compute fill the destination texture with 0xff so every tile counts as dirty (full lighting).
typedef struct {
    void *key;
    tex_t *texture;
    uint32_t inputs, outputs, expand_footprint, depth_stencil_mask;
    void *constant_color_table;
} dirty_tile_params_t;
enum { DIRTY_TILE_PARAMS_CAP = 8 };
static dirty_tile_params_t dirty_tile_params[DIRTY_TILE_PARAMS_CAP];
static dirty_tile_params_t *dirty_tile_params_of(void *key) {
    if (!key) return NULL;
    dirty_tile_params_t *free = NULL;
    for (int i = 0; i < DIRTY_TILE_PARAMS_CAP; i++) {
        if (dirty_tile_params[i].key == key) return &dirty_tile_params[i];
        if (!free && !dirty_tile_params[i].key) free = &dirty_tile_params[i];
    }
    if (!free) {
        static int once;
        if (!once++) rt_log("nvn: DirtyTileMapParameters table full; reusing slot 0");
        free = &dirty_tile_params[0];
    }
    memset(free, 0, sizeof *free);
    free->key = key;
    return free;
}
static void dirty_tile_fill_all_dirty(tex_t *tex) {
    if (!tex || tex->magic != NVN_TEX_MAGIC || !tex->mem || !tex->L.size) return;
    size_t n = tex->L.size > 0x1000000ull ? 0x1000000ull : (size_t)tex->L.size; // 16 MiB cap
    memset(tex->mem, 0xff, n);
    nvn_guest_written((uint64_t)(uintptr_t)tex->mem, n);
}
static void compute_dirty_tile_map(Cpu *c, const char *name) {
    static volatile int32_t logged;
    dirty_tile_params_t *p = dirty_tile_params_of(arg_p(c, 1));
    if (!__atomic_exchange_n(&logged, 1, __ATOMIC_RELAXED))
        rt_log("nvn2: %s: fill tile map all-dirty (tex=%p size=%llu)", name, (void *)(p ? p->texture : NULL),
               p && p->texture ? (unsigned long long)p->texture->L.size : 0ull);
    if (p) dirty_tile_fill_all_dirty(p->texture);
}
NVN_API(nvnCommandBufferComputeDirtyTileMap) { compute_dirty_tile_map(c, "ComputeDirtyTileMap"); }
NVN_API(nvnCommandBufferComputeDirtyTileMapEx) { compute_dirty_tile_map(c, "ComputeDirtyTileMapEx"); }
NVN_API(nvnDirtyTileMapParametersSetDefaults) {
    dirty_tile_params_t *p = dirty_tile_params_of(arg_p(c, 0));
    if (p) {
        void *key = p->key;
        memset(p, 0, sizeof *p);
        p->key = key;
    }
}
NVN_API(nvnDirtyTileMapParametersSetTexture) {
    dirty_tile_params_t *p = dirty_tile_params_of(arg_p(c, 0));
    if (p) p->texture = arg_p(c, 1);
}
NVN_API(nvnDirtyTileMapParametersSetInputs) {
    dirty_tile_params_t *p = dirty_tile_params_of(arg_p(c, 0));
    if (p) p->inputs = (uint32_t)arg_x(c, 1);
}
NVN_API(nvnDirtyTileMapParametersSetOutputs) {
    dirty_tile_params_t *p = dirty_tile_params_of(arg_p(c, 0));
    if (p) p->outputs = (uint32_t)arg_x(c, 1);
}
NVN_API(nvnDirtyTileMapParametersSetExpandFootprint) {
    dirty_tile_params_t *p = dirty_tile_params_of(arg_p(c, 0));
    if (p) p->expand_footprint = (uint32_t)arg_x(c, 1);
}
NVN_API(nvnDirtyTileMapParametersSetDepthStencilMask) {
    dirty_tile_params_t *p = dirty_tile_params_of(arg_p(c, 0));
    if (p) p->depth_stencil_mask = (uint32_t)arg_x(c, 1);
}
NVN_API(nvnDirtyTileMapParametersSetConstantColorTable) {
    dirty_tile_params_t *p = dirty_tile_params_of(arg_p(c, 0));
    if (p) p->constant_color_table = arg_p(c, 1);
}
NVN_API(nvnDirtyTileMapParametersGetTexture) {
    dirty_tile_params_t *p = dirty_tile_params_of(arg_p(c, 0));
    ret_x(c, (uint64_t)(uintptr_t)(p ? p->texture : NULL));
}
NVN_API(nvnDirtyTileMapParametersGetInputs) {
    dirty_tile_params_t *p = dirty_tile_params_of(arg_p(c, 0));
    ret_x(c, p ? p->inputs : 0);
}
NVN_API(nvnDirtyTileMapParametersGetOutputs) {
    dirty_tile_params_t *p = dirty_tile_params_of(arg_p(c, 0));
    ret_x(c, p ? p->outputs : 0);
}
NVN_API(nvnDirtyTileMapParametersGetExpandFootprint) {
    dirty_tile_params_t *p = dirty_tile_params_of(arg_p(c, 0));
    ret_x(c, p ? p->expand_footprint : 0);
}
NVN_API(nvnDirtyTileMapParametersGetDepthStencilMask) {
    dirty_tile_params_t *p = dirty_tile_params_of(arg_p(c, 0));
    ret_x(c, p ? p->depth_stencil_mask : 0);
}
NVN_API(nvnDirtyTileMapParametersGetConstantColorTable) {
    dirty_tile_params_t *p = dirty_tile_params_of(arg_p(c, 0));
    ret_x(c, (uint64_t)(uintptr_t)(p ? p->constant_color_table : NULL));
}
NVN2_NOT_RECORDED(nvnCommandBufferSetGraphicsWorkloadPriority)
NVN2_NOT_RECORDED(nvnCommandBufferSetComputeWorkloadPriority)
NVN2_NOT_RECORDED(nvnCommandBufferSetResourceOccupancy)
NVN2_NOT_RECORDED(nvnCommandBufferSetFloatBlendClamp)
NVN_API(nvnQueueBuilderGetPrimaryQueue) { ret_x(c, 0); }
NVN_API(nvnMultisampleStateGetSampleLocations) { ret_x(c, 0); }
NVN_API(nvnTexturePoolWriteDescriptorTableData) { (void)c; }
NVN_API(nvnSamplerPoolWriteDescriptorTableData) { (void)c; }
// Bare-bones Switch 2 NVN2 DLSS API compatibility (no neural DLSS upscaling: passthrough resolution + linear color blit).
typedef struct { const void *tex, *view; } dlss_texref_t;
typedef struct {
    const void *key;
    void *dev, *mem, *tex_pool;
    uint32_t flags, method, preset, out_w, out_h, max_evals;
    uint64_t size;
    uint32_t tex_ids[32];
} dlss_builder_t;
typedef struct { const void *key; uint32_t out_w, out_h; } dlss_net_t;
typedef struct {
    const void *key;
    dlss_texref_t in_color, out_color, motion_vecs, depth, exposure, bias_mask;
    uint32_t in_w, in_h, in_color_x, in_color_y, depth_x, depth_y, mv_x, mv_y, bias_x, bias_y, out_x, out_y;
    uint32_t eval_index, dbg_layer, dbg_full, dbg_nans, dbg_jitter;
    float jitter_x, jitter_y, mv_scale_x, mv_scale_y, pre_exposure;
    uint8_t history_reset;
} dlss_params_t;

enum { DLSS_SLOTS = 32 };
static PlatMutex dlss_lock = PLAT_MUTEX_INIT;
static dlss_builder_t dlss_builders[DLSS_SLOTS];
static dlss_net_t dlss_nets[DLSS_SLOTS];
static dlss_params_t dlss_params[DLSS_SLOTS];

// Lookup/allocate/reset a slot keyed by its leading `const void *key` pointer.
// op: 0 = lookup-or-create, 1 = reset payload preserving key, -1 = release slot.
static void *dlss_slot_of(void *arr, size_t stride, const void *key, int op) {
    if (!key) return NULL;
    plat_mutex_lock(&dlss_lock);
    uint8_t *base = (uint8_t *)arr;
    uint8_t *empty = NULL;
    for (int i = 0; i < DLSS_SLOTS; i++) {
        uint8_t *e = base + (size_t)i * stride;
        const void *k = *(const void **)e;
        if (k == key) {
            if (op < 0) {
                memset(e, 0, stride);
                plat_mutex_unlock(&dlss_lock);
                return NULL;
            }
            if (op > 0) memset(e + sizeof(const void *), 0, stride - sizeof(const void *));
            plat_mutex_unlock(&dlss_lock);
            return e;
        }
        if (!empty && !k) empty = e;
    }
    if (op < 0) {
        plat_mutex_unlock(&dlss_lock);
        return NULL;
    }
    if (!empty) empty = base;
    memset(empty, 0, stride);
    *(const void **)empty = key;
    plat_mutex_unlock(&dlss_lock);
    return empty;
}

static inline dlss_builder_t *dlss_builder_of(const void *k, int op) {
    return (dlss_builder_t *)dlss_slot_of(dlss_builders, sizeof *dlss_builders, k, op);
}
static inline dlss_net_t *dlss_net_of(const void *k, int op) {
    return (dlss_net_t *)dlss_slot_of(dlss_nets, sizeof *dlss_nets, k, op);
}
static inline dlss_params_t *dlss_params_of(const void *k, int op) {
    return (dlss_params_t *)dlss_slot_of(dlss_params, sizeof *dlss_params, k, op);
}

static inline void dlss_write_u32(Cpu *c, int arg_idx, uint32_t v) {
    uint32_t *out = (uint32_t *)arg_p(c, arg_idx);
    if (out) *out = v;
}
static inline void dlss_write_f32(Cpu *c, int arg_idx, float v) {
    float *out = (float *)arg_p(c, arg_idx);
    if (out) *out = v;
}

NVN_API(nvnDlssNetworkBuilderSetDefaults) {
    dlss_builder_t *b = dlss_builder_of(arg_p(c, 0), 1);
    if (b) b->max_evals = 1;
}
NVN_API(nvnDlssNetworkBuilderSetDevice) { dlss_builder_t *b = dlss_builder_of(arg_p(c, 0), 0); if (b) b->dev = arg_p(c, 1); }
NVN_API(nvnDlssNetworkBuilderGetDevice) { dlss_builder_t *b = dlss_builder_of(arg_p(c, 0), 0); ret_x(c, b ? (uintptr_t)b->dev : 0); }
NVN_API(nvnDlssNetworkBuilderSetFlags) { dlss_builder_t *b = dlss_builder_of(arg_p(c, 0), 0); if (b) b->flags = (uint32_t)arg_x(c, 1); }
NVN_API(nvnDlssNetworkBuilderGetFlags) { dlss_builder_t *b = dlss_builder_of(arg_p(c, 0), 0); ret_x(c, b ? b->flags : 0); }
NVN_API(nvnDlssNetworkBuilderSetOutputResolution) {
    dlss_builder_t *b = dlss_builder_of(arg_p(c, 0), 0);
    uint32_t in_w = (uint32_t)arg_x(c, 1);
    uint32_t in_h = (uint32_t)arg_x(c, 2);
    uint32_t cw = 0, ch = 0;
    ff_get_target_resolutions(&cw, &ch, NULL, NULL);
    if (b) {
        b->out_w = (cw > 0) ? cw : in_w;
        b->out_h = (ch > 0) ? ch : in_h;
    }
    rt_log("dlss: SetOutputResolution %ux%u -> %ux%u (lr=%#llx)", in_w, in_h, b ? b->out_w : 0, b ? b->out_h : 0, (unsigned long long)c->x[30]);
}
NVN_API(nvnDlssNetworkBuilderGetOutputResolution) {
    dlss_builder_t *b = dlss_builder_of(arg_p(c, 0), 0);
    uint32_t cw = 0, ch = 0;
    ff_get_target_resolutions(&cw, &ch, NULL, NULL);
    uint32_t w = (b && b->out_w) ? b->out_w : cw;
    uint32_t h = (b && b->out_h) ? b->out_h : ch;
    dlss_write_u32(c, 1, w);
    dlss_write_u32(c, 2, h);
}
NVN_API(nvnDlssNetworkBuilderSetMethod) { dlss_builder_t *b = dlss_builder_of(arg_p(c, 0), 0); if (b) b->method = (uint32_t)arg_x(c, 1); }
NVN_API(nvnDlssNetworkBuilderGetMethod) { dlss_builder_t *b = dlss_builder_of(arg_p(c, 0), 0); ret_x(c, b ? b->method : 0); }
NVN_API(nvnDlssNetworkBuilderSetPreset) { dlss_builder_t *b = dlss_builder_of(arg_p(c, 0), 0); if (b) b->preset = (uint32_t)arg_x(c, 1); }
NVN_API(nvnDlssNetworkBuilderGetPreset) { dlss_builder_t *b = dlss_builder_of(arg_p(c, 0), 0); ret_x(c, b ? b->preset : 0); }
NVN_API(nvnDlssNetworkBuilderGetOptimalSettings) {
    dlss_builder_t *b = dlss_builder_of(arg_p(c, 0), 0);
    uint32_t cw = 0, ch = 0, sw = 0, sh = 0;
    ff_get_target_resolutions(&cw, &ch, &sw, &sh);
    uint32_t w = (sw > 0) ? sw : ((b && b->out_w) ? b->out_w : 1920u);
    uint32_t h = (sh > 0) ? sh : ((b && b->out_h) ? b->out_h : 1080u);
    rt_log("dlss: GetOptimalSettings out=%ux%u optimal_scene=%ux%u method=%u preset=%u (lr=%#llx)",
           b ? b->out_w : cw, b ? b->out_h : ch, w, h, b ? b->method : 0, b ? b->preset : 0, (unsigned long long)c->x[30]);
    dlss_write_u32(c, 1, w);
    dlss_write_u32(c, 2, h);
    dlss_write_u32(c, 3, w);
    dlss_write_u32(c, 4, h);
    dlss_write_u32(c, 5, w);
    dlss_write_u32(c, 6, h);
    ret_x(c, 1);
}
NVN_API(nvnDlssNetworkBuilderGetStorageSize) { (void)c; ret_x(c, 4096ull); }
NVN_API(nvnDlssNetworkBuilderGetMemorySize) { dlss_builder_t *b = dlss_builder_of(arg_p(c, 0), 0); ret_x(c, (b && b->size) ? b->size : 4096ull); }
NVN_API(nvnDlssNetworkBuilderSetStorage) {
    dlss_builder_t *b = dlss_builder_of(arg_p(c, 0), 0);
    if (b) { b->mem = arg_p(c, 1); b->size = arg_x(c, 2); }
}
NVN_API(nvnDlssNetworkBuilderGetMemory) { dlss_builder_t *b = dlss_builder_of(arg_p(c, 0), 0); ret_x(c, b ? (uintptr_t)b->mem : 0); }
NVN_API(nvnDlssNetworkBuilderSetTextureIDs) {
    dlss_builder_t *b = dlss_builder_of(arg_p(c, 0), 0);
    if (!b) return;
    b->tex_pool = arg_p(c, 1);
    const void *ids = arg_p(c, 2);
    if (ids) memcpy(b->tex_ids, ids, sizeof b->tex_ids);
}
NVN_API(nvnDlssNetworkBuilderGetTexturePool) { dlss_builder_t *b = dlss_builder_of(arg_p(c, 0), 0); ret_x(c, b ? (uintptr_t)b->tex_pool : 0); }
NVN_API(nvnDlssNetworkBuilderGetTextureIDs) {
    dlss_builder_t *b = dlss_builder_of(arg_p(c, 0), 0);
    void *out = arg_p(c, 1);
    if (out) {
        if (b) memcpy(out, b->tex_ids, sizeof b->tex_ids);
        else memset(out, 0, sizeof b->tex_ids);
    }
    ret_x(c, 0);
}
NVN_API(nvnDlssNetworkBuilderSetMaxEvaluationEntries) {
    dlss_builder_t *b = dlss_builder_of(arg_p(c, 0), 0);
    if (b) b->max_evals = (uint32_t)arg_x(c, 1);
}
NVN_API(nvnDlssNetworkBuilderGetMaxEvaluationEntries) {
    dlss_builder_t *b = dlss_builder_of(arg_p(c, 0), 0);
    ret_x(c, b ? b->max_evals : 1u);
}

NVN_API(nvnDlssNetworkInitialize) {
    dlss_net_t *n = dlss_net_of(arg_p(c, 0), 1);
    dlss_builder_t *b = dlss_builder_of(arg_p(c, 1), 0);
    if (n && b) { n->out_w = b->out_w; n->out_h = b->out_h; }
    ret_x(c, 1);
}
NVN_API(nvnDlssNetworkFinalize) { dlss_net_of(arg_p(c, 0), -1); }
NVN_API(nvnDlssNetworkResize) {
    dlss_net_t *n = dlss_net_of(arg_p(c, 0), 0);
    if (n) { n->out_w = (uint32_t)arg_x(c, 1); n->out_h = (uint32_t)arg_x(c, 2); }
    ret_x(c, 1);
}

NVN_API(nvnDlssParametersSetDefaults) {
    dlss_params_t *p = dlss_params_of(arg_p(c, 0), 1);
    if (p) { p->mv_scale_x = 1.0f; p->mv_scale_y = 1.0f; p->pre_exposure = 1.0f; }
}
#define DLSS_PARAM_TEX(fn, fld) \
    NVN_API(fn) { dlss_params_t *p = dlss_params_of(arg_p(c, 0), 0); if (p) { p->fld.tex = arg_p(c, 1); p->fld.view = arg_p(c, 2); } }
#define DLSS_PARAM_U32_PAIR(SetFn, GetFn, xf, yf) \
    NVN_API(SetFn) { dlss_params_t *p = dlss_params_of(arg_p(c, 0), 0); if (p) { p->xf = (uint32_t)arg_x(c, 1); p->yf = (uint32_t)arg_x(c, 2); } } \
    NVN_API(GetFn) { dlss_params_t *p = dlss_params_of(arg_p(c, 0), 0); dlss_write_u32(c, 1, p ? p->xf : 0); dlss_write_u32(c, 2, p ? p->yf : 0); }
#define DLSS_PARAM_F32_PAIR(SetFn, GetFn, xf, yf) \
    NVN_API(SetFn) { dlss_params_t *p = dlss_params_of(arg_p(c, 0), 0); if (p) { p->xf = arg_s(c, 0); p->yf = arg_s(c, 1); } } \
    NVN_API(GetFn) { dlss_params_t *p = dlss_params_of(arg_p(c, 0), 0); dlss_write_f32(c, 1, p ? p->xf : 0.0f); dlss_write_f32(c, 2, p ? p->yf : 0.0f); }
#define DLSS_PARAM_OVERLAY(fn, fld) \
    NVN_API(fn) { dlss_params_t *p = dlss_params_of(arg_p(c, 0), 0); if (p) p->fld = (uint32_t)arg_x(c, 1); }

DLSS_PARAM_TEX(nvnDlssParametersSetInputColor, in_color)
DLSS_PARAM_TEX(nvnDlssParametersSetOutputColor, out_color)
DLSS_PARAM_TEX(nvnDlssParametersSetMotionVectors, motion_vecs)
DLSS_PARAM_TEX(nvnDlssParametersSetDepth, depth)
DLSS_PARAM_TEX(nvnDlssParametersSetExposureTexture, exposure)
DLSS_PARAM_TEX(nvnDlssParametersSetBiasCurrentColorMask, bias_mask)

DLSS_PARAM_OVERLAY(nvnDlssParametersSetOverlayDebugLayer, dbg_layer)
DLSS_PARAM_OVERLAY(nvnDlssParametersSetOverlayFullScreen, dbg_full)
DLSS_PARAM_OVERLAY(nvnDlssParametersSetOverlayShowNans, dbg_nans)
DLSS_PARAM_OVERLAY(nvnDlssParametersSetOverlayJitterDebug, dbg_jitter)

DLSS_PARAM_F32_PAIR(nvnDlssParametersSetJitterOffset, nvnDlssParametersGetJitterOffset, jitter_x, jitter_y)
DLSS_PARAM_F32_PAIR(nvnDlssParametersSetMotionVectorScale, nvnDlssParametersGetMotionVectorScale, mv_scale_x, mv_scale_y)

NVN_API(nvnDlssParametersSetPreExposure) { dlss_params_t *p = dlss_params_of(arg_p(c, 0), 0); if (p) p->pre_exposure = arg_s(c, 0); }
NVN_API(nvnDlssParametersGetPreExposure) { dlss_params_t *p = dlss_params_of(arg_p(c, 0), 0); ret_s(c, p ? p->pre_exposure : 1.0f); }
NVN_API(nvnDlssParametersSetHistoryReset) { dlss_params_t *p = dlss_params_of(arg_p(c, 0), 0); if (p) p->history_reset = (uint8_t)nvn_arg_bool(c, 1); }
NVN_API(nvnDlssParametersGetHistoryReset) { dlss_params_t *p = dlss_params_of(arg_p(c, 0), 0); ret_x(c, p ? p->history_reset : 0); }
NVN_API(nvnDlssParametersSetEvaluationIndex) { dlss_params_t *p = dlss_params_of(arg_p(c, 0), 0); if (p) p->eval_index = (uint32_t)arg_x(c, 1); }
NVN_API(nvnDlssParametersGetEvaluationIndex) { dlss_params_t *p = dlss_params_of(arg_p(c, 0), 0); ret_x(c, p ? p->eval_index : 0); }

DLSS_PARAM_U32_PAIR(nvnDlssParametersSetInputSubrectangleSize, nvnDlssParametersGetInputSubrectangleSize, in_w, in_h)
DLSS_PARAM_U32_PAIR(nvnDlssParametersSetInputColorSubrectangleBase, nvnDlssParametersGetInputColorSubrectangleBase, in_color_x, in_color_y)
DLSS_PARAM_U32_PAIR(nvnDlssParametersSetDepthSubrectangleBase, nvnDlssParametersGetDepthSubrectangleBase, depth_x, depth_y)
DLSS_PARAM_U32_PAIR(nvnDlssParametersSetMotionVectorSubrectangleBase, nvnDlssParametersGetMotionVectorSubrectangleBase, mv_x, mv_y)
DLSS_PARAM_U32_PAIR(nvnDlssParametersSetBiasCurrentColorSubrectangleBase, nvnDlssParametersGetBiasCurrentColorSubrectangleBase, bias_x, bias_y)
DLSS_PARAM_U32_PAIR(nvnDlssParametersSetOutputSubrectangleBase, nvnDlssParametersGetOutputSubrectangleBase, out_x, out_y)
NVN2_NOT_RECORDED(nvnCommandBufferDrawMeshTasks)
NVN2_NOT_RECORDED(nvnCommandBufferDrawMeshTasks3D)
NVN2_NOT_RECORDED(nvnCommandBufferDrawMeshTasks3DIndirect)
NVN2_NOT_RECORDED(nvnCommandBufferDrawMeshTasksIndirect)
NVN2_NOT_RECORDED(nvnCommandBufferMultiDrawMeshTasks3DIndirect)
NVN2_NOT_RECORDED(nvnCommandBufferMultiDrawMeshTasks3DIndirectCount)
NVN2_NOT_RECORDED(nvnCommandBufferMultiDrawMeshTasksIndirect)
NVN2_NOT_RECORDED(nvnCommandBufferMultiDrawMeshTasksIndirectCount)
// nvnCommandBufferMultiDrawElementsIndirectCount is recorded in nvn_api_cmd.c (OP_DRAW_IDX_IND_COUNT).
NVN2_NOT_RECORDED(nvnCommandBufferMultiDrawArraysIndirectCount)
NVN2_NOT_RECORDED(nvnCommandBufferEnableExclusiveScissor)
NVN2_NOT_RECORDED(nvnCommandBufferSetExclusiveScissor)
NVN2_NOT_RECORDED(nvnCommandBufferSetExclusiveScissors)
NVN_API(nvnCommandBufferEvaluateDlss) {
    NVNcommandBuffer *cmd = arg_p(c, 0);
    dlss_net_t *n = dlss_net_of(arg_p(c, 1), 0);
    dlss_params_t *p = dlss_params_of(arg_p(c, 2), 0);
    if (!cmd || !p || !p->in_color.tex || !p->out_color.tex) return;
    static int logged = 0;
    if (!logged) {
        logged = 1;
        rt_log("dlss: EvaluateDlss in=(%d,%d %dx%d) out=(%d,%d %dx%d)",
               (int)p->in_color_x, (int)p->in_color_y, (int)p->in_w, (int)p->in_h,
               (int)p->out_x, (int)p->out_y, n ? (int)n->out_w : 0, n ? (int)n->out_h : 0);
    }
    nvn_cmd_copy_tex_blit(cmd, p->in_color.tex, p->in_color.view,
                          (int)p->in_color_x, (int)p->in_color_y, (int)p->in_w, (int)p->in_h,
                          p->out_color.tex, p->out_color.view,
                          (int)p->out_x, (int)p->out_y, n ? (int)n->out_w : 0, n ? (int)n->out_h : 0);
}
NVN2_NOT_RECORDED(nvnCommandBufferInsertDebugMarkerCompute)
NVN2_NOT_RECORDED(nvnCommandBufferInsertDebugMarkerGraphics)
NVN2_NOT_RECORDED(nvnCommandBufferPushDebugGroupCompute)
NVN2_NOT_RECORDED(nvnCommandBufferPushDebugGroupGraphics)
NVN2_NOT_RECORDED(nvnCommandBufferPopDebugGroupCompute)
NVN2_NOT_RECORDED(nvnCommandBufferPopDebugGroupGraphics)
// nvnCommandBufferPush{Graphics,Compute}Constants and their Deferred forms are recorded in nvn_api_cmd.c (OP_PUSH_CONST).
NVN2_NOT_RECORDED(nvnCommandBufferSetComputeEnable)
NVN2_NOT_RECORDED(nvnCommandBufferSetComputeEnableConditional)
NVN2_NOT_RECORDED(nvnCommandBufferSetCopyEnable)
NVN2_NOT_RECORDED(nvnCommandBufferSetCopyEnableConditional)
NVN2_NOT_RECORDED(nvnCommandBufferSetConservativeRasterMode)
// Geometry processing mode 0 is the traditional vertex pipeline, the only one the replay builds (every capture so far
// called it with 0). A nonzero value selects the mesh pipeline, which has no Vulkan counterpart here yet.
NVN2_MODE_HANDLED(nvnCommandBufferSetGeometryProcessingMode, NVN_MODE_GEOMETRY, 0)
NVN2_NOT_RECORDED(nvnCommandBufferSetRepresentativeFragmentTest)
NVN2_NOT_RECORDED(nvnCommandBufferSetCopyImageStride)

