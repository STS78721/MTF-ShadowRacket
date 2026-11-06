// Intel XeSS 1.3 / XeLL Upscaler & Anti-Lag Integration for DKB Recomp
#include "vk_xess.h"
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <windows.h>

#include "cfg.h"
#include "host.h"
#include "platform/platform.h"

typedef void *xess_context_handle_t;

typedef enum {
    XESS_QUALITY_SETTING_PERFORMANCE = 1,
    XESS_QUALITY_SETTING_BALANCED = 2,
    XESS_QUALITY_SETTING_QUALITY = 3,
    XESS_QUALITY_SETTING_ULTRA_PERFORMANCE = 4,
    XESS_QUALITY_SETTING_ULTRA_QUALITY = 5,
    XESS_QUALITY_SETTING_ULTRA_QUALITY_PLUS = 6,
    XESS_QUALITY_SETTING_AA = 7
} xess_quality_settings_t;

typedef struct {
    uint32_t x;
    uint32_t y;
} xess_2d_t;

typedef struct {
    uint16_t major;
    uint16_t minor;
    uint16_t patch;
    uint16_t reserved;
} xess_version_t;

typedef struct {
    xess_2d_t outputResolution;
    xess_quality_settings_t qualitySetting;
    uint32_t initFlags;
    VkPipelineCache pipelineCache;
} xess_vk_init_params_t;

typedef struct {
    VkImage colorTexture;
    VkImage velocityTexture;
    VkImage depthTexture;
    VkImage exposureTexture;
    VkImage responsivePixelMaskTexture;
    VkImage outputTexture;
    float jitterOffsetX;
    float jitterOffsetY;
    uint32_t exposureScaleMode;
    int resetHistory;
    xess_2d_t inputColorResolution;
} xess_vk_execute_params_t;

typedef int (*pfn_xessVKCreateContext)(VkDevice device, xess_context_handle_t *phContext);
typedef int (*pfn_xessDestroyContext)(xess_context_handle_t hContext);
typedef int (*pfn_xessGetVersion)(xess_version_t *pVersion);
typedef int (*pfn_xessVKInit)(xess_context_handle_t hContext, const xess_vk_init_params_t *pInitParams);
typedef int (*pfn_xessVKExecute)(xess_context_handle_t hContext, VkCommandBuffer cb, const xess_vk_execute_params_t *pExecParams);
typedef int (*pfn_xessSelectNetworkModel)(xess_context_handle_t hContext, xess_quality_settings_t quality);
typedef int (*pfn_xessGetOptimalInputResolution)(xess_context_handle_t hContext, const xess_2d_t *pTargetResolution,
                                                 xess_quality_settings_t quality, xess_2d_t *pInputResolution);

static struct {
    HMODULE dll;
    pfn_xessVKCreateContext create_ctx;
    pfn_xessDestroyContext destroy_ctx;
    pfn_xessGetVersion get_ver;
    pfn_xessVKInit init;
    pfn_xessVKExecute execute;
    pfn_xessSelectNetworkModel select_model;
    pfn_xessGetOptimalInputResolution get_opt_res;

    xess_context_handle_t ctx;
    int tried, ok;
    uint32_t cur_w, cur_h;
    xess_quality_settings_t cur_quality;
    int logged;
} X;

static void load_xess(void) {
    if (X.tried) return;
    X.tried = 1;
    X.dll = LoadLibraryA("libxess.dll");
    if (!X.dll) {
        rt_log("vk_xess: libxess.dll not found; Intel XeSS disabled");
        return;
    }
    X.create_ctx = (pfn_xessVKCreateContext)GetProcAddress(X.dll, "xessVKCreateContext");
    X.destroy_ctx = (pfn_xessDestroyContext)GetProcAddress(X.dll, "xessDestroyContext");
    X.get_ver = (pfn_xessGetVersion)GetProcAddress(X.dll, "xessGetVersion");
    X.init = (pfn_xessVKInit)GetProcAddress(X.dll, "xessVKInit");
    X.execute = (pfn_xessVKExecute)GetProcAddress(X.dll, "xessVKExecute");
    X.select_model = (pfn_xessSelectNetworkModel)GetProcAddress(X.dll, "xessSelectNetworkModel");
    X.get_opt_res = (pfn_xessGetOptimalInputResolution)GetProcAddress(X.dll, "xessGetOptimalInputResolution");

    if (!X.create_ctx || !X.destroy_ctx || !X.init || !X.execute) {
        rt_log("vk_xess: missing exports in libxess.dll");
        FreeLibrary(X.dll);
        X.dll = NULL;
        return;
    }
    xess_version_t ver = {0};
    if (X.get_ver && X.get_ver(&ver) == 0) {
        rt_log("vk_xess: Intel XeSS runtime loaded (version %u.%u.%u)", ver.major, ver.minor, ver.patch);
    } else {
        rt_log("vk_xess: Intel XeSS runtime loaded");
    }
    X.ok = 1;
}

void vk_xess_instance_exts(const char **ext, uint32_t *n, uint32_t max) {
    (void)ext; (void)n; (void)max;
}

void vk_xess_device_exts(const VkExtensionProperties *have, uint32_t nhave, const char **ext, uint32_t *n, uint32_t max) {
    (void)have; (void)nhave; (void)ext; (void)n; (void)max;
}

void vk_xess_init(void) {
    load_xess();
}

int vk_xess_available(void) {
    if (!X.tried) load_xess();
    return X.ok;
}

static xess_quality_settings_t pick_quality(void) {
    const char *p = cfg_value("TOTK_UPSCALER_PRESET");
    if (!p || !*p) p = "quality";
    if (!strcmp(p, "performance")) return XESS_QUALITY_SETTING_PERFORMANCE;
    if (!strcmp(p, "balanced")) return XESS_QUALITY_SETTING_BALANCED;
    if (!strcmp(p, "ultra_performance")) return XESS_QUALITY_SETTING_ULTRA_PERFORMANCE;
    if (!strcmp(p, "ultra_quality")) return XESS_QUALITY_SETTING_ULTRA_QUALITY;
    if (!strcmp(p, "native")) return XESS_QUALITY_SETTING_AA;
    return XESS_QUALITY_SETTING_QUALITY;
}

int vk_xess_record(VkCommandBuffer cb, unsigned slot, VkImage src, VkFormat fmt, int sw, int sh,
                   const int crop[4], VkImage dst, const int out[4]) {
    (void)slot; (void)sw; (void)sh;
    if (strcmp(cfg_value("TOTK_UPSCALER"), "xess")) return 0;
    if (!X.tried) load_xess();
    if (!X.ok) return 0;

    int cw = crop[2], ch = crop[3];
    uint32_t dw = (uint32_t)out[2], dh = (uint32_t)out[3];
    if (dw <= (uint32_t)cw && dh <= (uint32_t)ch) return 0;
    if (!fmt) return 0;

    VkCtx *c = vk_ctx();
    if (!c || !c->device) return 0;

    xess_quality_settings_t q = pick_quality();

    if (!X.ctx || X.cur_w != dw || X.cur_h != dh || X.cur_quality != q) {
        if (X.ctx) {
            X.destroy_ctx(X.ctx);
            X.ctx = NULL;
        }
        if (X.create_ctx(c->device, &X.ctx) != 0 || !X.ctx) {
            rt_log("vk_xess: xessVKCreateContext failed");
            return 0;
        }
        xess_vk_init_params_t ip = {
            .outputResolution = {dw, dh},
            .qualitySetting = q,
            .initFlags = 0,
            .pipelineCache = VK_NULL_HANDLE
        };
        if (X.init(X.ctx, &ip) != 0) {
            rt_log("vk_xess: xessVKInit failed for %ux%u", dw, dh);
            X.destroy_ctx(X.ctx);
            X.ctx = NULL;
            return 0;
        }
        X.cur_w = dw;
        X.cur_h = dh;
        X.cur_quality = q;
        rt_log("vk_xess: Intel XeSS initialized: %dx%d -> %ux%u (quality %d)", cw, ch, dw, dh, (int)q);
    }

    xess_vk_execute_params_t ep = {
        .colorTexture = src,
        .velocityTexture = VK_NULL_HANDLE,
        .depthTexture = VK_NULL_HANDLE,
        .exposureTexture = VK_NULL_HANDLE,
        .responsivePixelMaskTexture = VK_NULL_HANDLE,
        .outputTexture = dst,
        .jitterOffsetX = 0.0f,
        .jitterOffsetY = 0.0f,
        .exposureScaleMode = 0,
        .resetHistory = 0,
        .inputColorResolution = {(uint32_t)cw, (uint32_t)ch}
    };

    if (X.execute(X.ctx, cb, &ep) != 0) {
        return 0;
    }
    return 1;
}

void vk_xess_release(void) {
    if (X.ctx && X.destroy_ctx) {
        X.destroy_ctx(X.ctx);
        X.ctx = NULL;
    }
    if (X.dll) {
        FreeLibrary(X.dll);
        X.dll = NULL;
    }
    memset(&X, 0, sizeof X);
}
