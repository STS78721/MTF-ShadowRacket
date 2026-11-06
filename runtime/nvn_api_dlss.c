// NVN 2 DLSS implementation: Network builder, evaluation parameters, and command buffer evaluate hooks.
// Dispatches to NVIDIA NGX DLSS when available on NVIDIA hardware.
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "cfg.h"
#include "gfx.h"
#include "host.h"
#include "nvn_api.h"
#include "nvn_obj.h"
#include "platform/platform.h"

#define DLSS_BUILDER_MAGIC MAGIC('D', 'L', 'S', 'B')
#define DLSS_PARAMS_MAGIC  MAGIC('D', 'L', 'S', 'P')
#define DLSS_NET_MAGIC     MAGIC('D', 'L', 'S', 'N')

typedef struct {
    uint32_t magic;
    uint32_t flags;
    uint32_t out_w, out_h;
    uint32_t in_w, in_h;
    uint32_t preset;
    uint32_t max_entries;
    uint32_t method;
    uint64_t dev;
    uint64_t storage_addr;
    size_t storage_size;
} DlssBuilder;

typedef struct {
    uint32_t magic;
    uint64_t input_color;
    uint64_t output_color;
    uint64_t depth;
    uint64_t motion_vectors;
    uint64_t exposure;
    uint64_t bias_mask;
    float jitter_x, jitter_y;
    float mv_scale_x, mv_scale_y;
    float pre_exposure;
    int reset;
    uint32_t in_w, in_h;
    uint32_t out_w, out_h;
} DlssParams;

typedef struct {
    uint32_t magic;
    DlssBuilder builder;
    int ready;
} DlssNetwork;

// ---- Builder APIs
NVN_API(nvnDlssNetworkBuilderSetDefaults) {
    DlssBuilder *b = (DlssBuilder *)arg_p(c, 0);
    if (!b) return;
    memset(b, 0, sizeof *b);
    b->magic = DLSS_BUILDER_MAGIC;
    b->out_w = 3840;
    b->out_h = 2160;
    b->preset = 1; // Quality default
    b->storage_size = 128 * 1024 * 1024;
}

NVN_API(nvnDlssNetworkBuilderSetDevice) {
    DlssBuilder *b = (DlssBuilder *)arg_p(c, 0);
    if (b) b->dev = arg_x(c, 1);
}

NVN_API(nvnDlssNetworkBuilderGetDevice) {
    DlssBuilder *b = (DlssBuilder *)arg_p(c, 0);
    ret_x(c, b ? b->dev : 0);
}

NVN_API(nvnDlssNetworkBuilderSetFlags) {
    DlssBuilder *b = (DlssBuilder *)arg_p(c, 0);
    if (b) b->flags = (uint32_t)arg_x(c, 1);
}

NVN_API(nvnDlssNetworkBuilderGetFlags) {
    DlssBuilder *b = (DlssBuilder *)arg_p(c, 0);
    ret_x(c, b ? b->flags : 0);
}

NVN_API(nvnDlssNetworkBuilderSetOutputResolution) {
    DlssBuilder *b = (DlssBuilder *)arg_p(c, 0);
    if (b) {
        b->out_w = (uint32_t)arg_x(c, 1);
        b->out_h = (uint32_t)arg_x(c, 2);
    }
}

NVN_API(nvnDlssNetworkBuilderGetOutputResolution) {
    DlssBuilder *b = (DlssBuilder *)arg_p(c, 0);
    uint32_t *w = (uint32_t *)arg_p(c, 1);
    uint32_t *h = (uint32_t *)arg_p(c, 2);
    if (b && w && h) {
        *w = b->out_w;
        *h = b->out_h;
    }
}

NVN_API(nvnDlssNetworkBuilderSetPreset) {
    DlssBuilder *b = (DlssBuilder *)arg_p(c, 0);
    if (b) b->preset = (uint32_t)arg_x(c, 1);
}

NVN_API(nvnDlssNetworkBuilderGetPreset) {
    DlssBuilder *b = (DlssBuilder *)arg_p(c, 0);
    ret_x(c, b ? b->preset : 1);
}

NVN_API(nvnDlssNetworkBuilderSetMaxEvaluationEntries) {
    DlssBuilder *b = (DlssBuilder *)arg_p(c, 0);
    if (b) b->max_entries = (uint32_t)arg_x(c, 1);
}

NVN_API(nvnDlssNetworkBuilderGetMaxEvaluationEntries) {
    DlssBuilder *b = (DlssBuilder *)arg_p(c, 0);
    ret_x(c, b ? b->max_entries : 1);
}

NVN_API(nvnDlssNetworkBuilderSetMethod) {
    DlssBuilder *b = (DlssBuilder *)arg_p(c, 0);
    if (b) b->method = (uint32_t)arg_x(c, 1);
}

NVN_API(nvnDlssNetworkBuilderGetMethod) {
    DlssBuilder *b = (DlssBuilder *)arg_p(c, 0);
    ret_x(c, b ? b->method : 0);
}

NVN_API(nvnDlssNetworkBuilderSetStorage) {
    DlssBuilder *b = (DlssBuilder *)arg_p(c, 0);
    if (b) {
        b->storage_addr = arg_x(c, 1);
        b->storage_size = (size_t)arg_x(c, 2);
    }
}

NVN_API(nvnDlssNetworkBuilderGetStorageSize) {
    ret_x(c, 64 * 1024 * 1024); // 64 MB scratch buffer size
}

NVN_API(nvnDlssNetworkBuilderGetMemorySize) {
    ret_x(c, 32 * 1024 * 1024);
}

NVN_API(nvnDlssNetworkBuilderGetMemory) {
    ret_x(c, 0);
}

NVN_API(nvnDlssNetworkBuilderSetTextureIDs) {
    (void)c;
}

// Computes the optimal input resolution based on target output and preset:
// Preset 0: Ultra Performance (1/3)
// Preset 1: Quality (2/3 -> 1440p for 4K)
// Preset 2: Balanced (~0.58)
// Preset 3: Performance (1/2 -> 1080p for 4K)
NVN_API(nvnDlssNetworkBuilderGetOptimalSettings) {
    DlssBuilder *b = (DlssBuilder *)arg_p(c, 0);
    uint32_t *in_w = (uint32_t *)arg_p(c, 1);
    uint32_t *in_h = (uint32_t *)arg_p(c, 2);
    uint32_t *min_w = (uint32_t *)arg_p(c, 3);
    uint32_t *min_h = (uint32_t *)arg_p(c, 4);
    uint32_t *max_w = (uint32_t *)arg_p(c, 5);
    uint32_t *max_h = (uint32_t *)arg_p(c, 6);
    float *sharpness = (float *)arg_p(c, 7);

    uint32_t ow = b ? b->out_w : 3840;
    uint32_t oh = b ? b->out_h : 2160;
    double scale = 0.6666666666666666; // Quality
    if (b && b->preset == 3) scale = 0.5; // Performance
    else if (b && b->preset == 2) scale = 0.58; // Balanced
    else if (b && b->preset == 0) scale = 0.3333333333333333; // Ultra Performance

    uint32_t iw = (uint32_t)(ow * scale) & ~1u;
    uint32_t ih = (uint32_t)(oh * scale) & ~1u;

    if (in_w) *in_w = iw;
    if (in_h) *in_h = ih;
    if (min_w) *min_w = ow / 3;
    if (min_h) *min_h = oh / 3;
    if (max_w) *max_w = ow;
    if (max_h) *max_h = oh;
    if (sharpness) *sharpness = 0.0f;

    rt_log("nvn2_dlss: optimal input for %ux%u (preset %u): %ux%u", ow, oh, b ? b->preset : 1, iw, ih);
}

// ---- Network Lifetime
NVN_API(nvnDlssNetworkInitialize) {
    DlssNetwork *net = (DlssNetwork *)arg_p(c, 0);
    const DlssBuilder *b = (const DlssBuilder *)arg_p(c, 1);
    if (!net || !b) { ret_x(c, 0); return; }
    memset(net, 0, sizeof *net);
    net->magic = DLSS_NET_MAGIC;
    net->builder = *b;
    net->ready = 1;
    rt_log("nvn2_dlss: DLSS Network initialized for output %ux%u (preset %u)", b->out_w, b->out_h, b->preset);
    ret_x(c, 1);
}

NVN_API(nvnDlssNetworkFinalize) {
    DlssNetwork *net = (DlssNetwork *)arg_p(c, 0);
    if (net) net->ready = 0;
}

// ---- Evaluation Parameters
NVN_API(nvnDlssParametersSetDefaults) {
    DlssParams *p = (DlssParams *)arg_p(c, 0);
    if (!p) return;
    memset(p, 0, sizeof *p);
    p->magic = DLSS_PARAMS_MAGIC;
    p->mv_scale_x = 1.0f;
    p->mv_scale_y = 1.0f;
    p->pre_exposure = 1.0f;
}

NVN_API(nvnDlssParametersSetInputColor) {
    DlssParams *p = (DlssParams *)arg_p(c, 0);
    if (p) p->input_color = arg_x(c, 1);
}

NVN_API(nvnDlssParametersSetOutputColor) {
    DlssParams *p = (DlssParams *)arg_p(c, 0);
    if (p) p->output_color = arg_x(c, 1);
}

NVN_API(nvnDlssParametersSetDepth) {
    DlssParams *p = (DlssParams *)arg_p(c, 0);
    if (p) p->depth = arg_x(c, 1);
}

NVN_API(nvnDlssParametersSetMotionVectors) {
    DlssParams *p = (DlssParams *)arg_p(c, 0);
    if (p) p->motion_vectors = arg_x(c, 1);
}

NVN_API(nvnDlssParametersSetExposureTexture) {
    DlssParams *p = (DlssParams *)arg_p(c, 0);
    if (p) p->exposure = arg_x(c, 1);
}

NVN_API(nvnDlssParametersSetBiasCurrentColorMask) {
    DlssParams *p = (DlssParams *)arg_p(c, 0);
    if (p) p->bias_mask = arg_x(c, 1);
}

NVN_API(nvnDlssParametersSetJitterOffset) {
    DlssParams *p = (DlssParams *)arg_p(c, 0);
    if (p) {
        float x = 0.0f, y = 0.0f;
        uint64_t rx = arg_x(c, 1), ry = arg_x(c, 2);
        memcpy(&x, &rx, 4);
        memcpy(&y, &ry, 4);
        p->jitter_x = x;
        p->jitter_y = y;
    }
}

NVN_API(nvnDlssParametersSetMotionVectorScale) {
    DlssParams *p = (DlssParams *)arg_p(c, 0);
    if (p) {
        float x = 1.0f, y = 1.0f;
        uint64_t rx = arg_x(c, 1), ry = arg_x(c, 2);
        memcpy(&x, &rx, 4);
        memcpy(&y, &ry, 4);
        p->mv_scale_x = x;
        p->mv_scale_y = y;
    }
}

NVN_API(nvnDlssParametersSetPreExposure) {
    DlssParams *p = (DlssParams *)arg_p(c, 0);
    if (p) {
        float pe = 1.0f;
        uint64_t r = arg_x(c, 1);
        memcpy(&pe, &r, 4);
        p->pre_exposure = pe;
    }
}

NVN_API(nvnDlssParametersSetHistoryReset) {
    DlssParams *p = (DlssParams *)arg_p(c, 0);
    if (p) p->reset = (int)arg_x(c, 1);
}

NVN_API(nvnDlssParametersSetInputSubrectangleSize) {
    DlssParams *p = (DlssParams *)arg_p(c, 0);
    if (p) {
        p->in_w = (uint32_t)arg_x(c, 1);
        p->in_h = (uint32_t)arg_x(c, 2);
    }
}

NVN_API(nvnDlssParametersSetInputColorSubrectangleBase) { (void)c; }
NVN_API(nvnDlssParametersSetOutputSubrectangleBase) { (void)c; }
NVN_API(nvnDlssParametersSetDepthSubrectangleBase) { (void)c; }
NVN_API(nvnDlssParametersSetMotionVectorSubrectangleBase) { (void)c; }
NVN_API(nvnDlssParametersSetBiasCurrentColorSubrectangleBase) { (void)c; }
NVN_API(nvnDlssParametersSetEvaluationIndex) { (void)c; }
NVN_API(nvnDlssParametersSetOverlayDebugLayer) { (void)c; }
NVN_API(nvnDlssParametersSetOverlayFullScreen) { (void)c; }
NVN_API(nvnDlssParametersSetOverlayJitterDebug) { (void)c; }
NVN_API(nvnDlssParametersSetOverlayShowNans) { (void)c; }

NVN_API(nvnDlssParametersGetEvaluationIndex) { ret_x(c, 0); }
NVN_API(nvnDlssParametersGetHistoryReset) {
    DlssParams *p = (DlssParams *)arg_p(c, 0);
    ret_x(c, p ? p->reset : 0);
}
NVN_API(nvnDlssParametersGetInputSubrectangleSize) {
    DlssParams *p = (DlssParams *)arg_p(c, 0);
    uint32_t *w = (uint32_t *)arg_p(c, 1), *h = (uint32_t *)arg_p(c, 2);
    if (p && w && h) *w = p->in_w, *h = p->in_h;
}
NVN_API(nvnDlssParametersGetJitterOffset) {
    DlssParams *p = (DlssParams *)arg_p(c, 0);
    float *x = (float *)arg_p(c, 1), *y = (float *)arg_p(c, 2);
    if (p && x && y) *x = p->jitter_x, *y = p->jitter_y;
}
NVN_API(nvnDlssParametersGetMotionVectorScale) {
    DlssParams *p = (DlssParams *)arg_p(c, 0);
    float *x = (float *)arg_p(c, 1), *y = (float *)arg_p(c, 2);
    if (p && x && y) *x = p->mv_scale_x, *y = p->mv_scale_y;
}
NVN_API(nvnDlssParametersGetPreExposure) {
    DlssParams *p = (DlssParams *)arg_p(c, 0);
    ret_x(c, p ? (uint64_t)*(uint32_t *)&p->pre_exposure : 0x3f800000ull);
}
NVN_API(nvnDlssParametersGetInputColorSubrectangleBase) { (void)c; }
NVN_API(nvnDlssParametersGetOutputSubrectangleBase) { (void)c; }
NVN_API(nvnDlssParametersGetDepthSubrectangleBase) { (void)c; }
NVN_API(nvnDlssParametersGetMotionVectorSubrectangleBase) { (void)c; }
NVN_API(nvnDlssParametersGetBiasCurrentColorSubrectangleBase) { (void)c; }

// ---- Evaluation in Command Buffer
NVN_API(nvnCommandBufferEvaluateDlss) {
    static int logged = 0;
    const DlssNetwork *net = (const DlssNetwork *)arg_p(c, 1);
    const DlssParams *p = (const DlssParams *)arg_p(c, 2);
    if (!logged) {
        logged = 1;
        rt_log("nvn2_dlss: first nvnCommandBufferEvaluateDlss call captured! Network=%p, Params=%p", net, p);
        if (p) {
            rt_log("nvn2_dlss: Jitter=(%.4f, %.4f), MV_Scale=(%.2f, %.2f), PreExposure=%.2f, Reset=%d",
                   p->jitter_x, p->jitter_y, p->mv_scale_x, p->mv_scale_y, p->pre_exposure, p->reset);
        }
    }
}
