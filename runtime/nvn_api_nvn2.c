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
// void ...Set{Hdr}Display/ContentMetadata(obj, const metadata *): kept by no one
NVN_API(nvnWindowBuilderSetHdrDisplayMetadata) { (void)c; }
NVN_API(nvnWindowBuilderSetHdrContentMetadata) { (void)c; }
NVN_API(nvnWindowSetHdrDisplayMetadata) { (void)c; }
NVN_API(nvnWindowSetHdrContentMetadata) { (void)c; }

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
NVN_API(nvnDlssNetworkBuilderGetTexturePool) { ret_x(c, 0); }
NVN_API(nvnDlssNetworkBuilderGetTextureIDs) { ret_x(c, 0); }
NVN_API(nvnDlssNetworkResize) { ret_x(c, 0); }
NVN2_NOT_RECORDED(nvnCommandBufferDrawMeshTasks)
NVN2_NOT_RECORDED(nvnCommandBufferDrawMeshTasks3D)
NVN2_NOT_RECORDED(nvnCommandBufferDrawMeshTasks3DIndirect)
NVN2_NOT_RECORDED(nvnCommandBufferDrawMeshTasksIndirect)
NVN2_NOT_RECORDED(nvnCommandBufferMultiDrawMeshTasks3DIndirect)
NVN2_NOT_RECORDED(nvnCommandBufferMultiDrawMeshTasks3DIndirectCount)
NVN2_NOT_RECORDED(nvnCommandBufferMultiDrawMeshTasksIndirect)
NVN2_NOT_RECORDED(nvnCommandBufferMultiDrawMeshTasksIndirectCount)
NVN2_NOT_RECORDED(nvnCommandBufferMultiDrawElementsIndirectCount)
NVN2_NOT_RECORDED(nvnCommandBufferMultiDrawArraysIndirectCount)
NVN2_NOT_RECORDED(nvnCommandBufferEnableExclusiveScissor)
NVN2_NOT_RECORDED(nvnCommandBufferSetExclusiveScissor)
NVN2_NOT_RECORDED(nvnCommandBufferSetExclusiveScissors)
NVN2_NOT_RECORDED(nvnCommandBufferEvaluateDlss)
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

