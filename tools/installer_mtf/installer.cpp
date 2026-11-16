// MTF-ShadowRacket Setup: the Windows installer of Mario Tennis Fever PC, and its uninstaller.
//
// Patterned on MKW-THWOMP's standalone static installer: SDL3 (static) + Dear ImGui + zstd self-extractor
// with a Championship Turf Green & Optic Yellow-Green Mario Tennis Fever theme, runtime/mtf.png icon,
// and Roboto-Medium font.
//
// Test hooks:
//   MTF_SETUP_SHOT=<frame>:<page>  saves screenshot to MTF_SETUP_SHOT_OUT and exits
//                                  (pages: welcome, folder, copy, done, uninstall)
//   MTF_SETUP_DIR=<folder>         pre-fills install folder
//   MTF_SETUP_AUTO=1               auto-runs install or uninstall without clicking
//   MTF_SETUP_NO_SHORTCUTS=1       skips Desktop/Start Menu shortcuts and registers under MTF-ShadowRacket-test

#define WIN32_LEAN_AND_MEAN
#define NOMINMAX
#include <windows.h>
#include <objbase.h>
#include <shellapi.h>
#include <shlobj.h>
#include <shobjidl.h>

#include <SDL3/SDL.h>
#include <zstd.h>

#include <algorithm>
#include <atomic>
#include <float.h>
#include <math.h>
#include <mutex>
#include <stdint.h>
#include <stdio.h>
#include <string>
#include <thread>
#include <vector>

#include "imgui.h"
#include "backends/imgui_impl_sdl3.h"
#include "backends/imgui_impl_sdlrenderer3.h"

#pragma clang diagnostic push
#pragma clang diagnostic ignored "-Wc23-extensions"
static const unsigned char kIconPng[] = {
#embed "../../runtime/mtf.png"
};
static const unsigned char kBallPng[] = {
#embed "../../runtime/mtf_ball.png"
};
static const unsigned char kRoboto[] = {
#embed "../../runtime/ui/fonts/Roboto-Medium.ttf"
};
#pragma clang diagnostic pop

static const char kName[] = "Mario Tennis Fever PC";
static const wchar_t kNameW[] = L"Mario Tennis Fever PC";
static const wchar_t kBrandW[] = L"MTF ShadowRacket";
static const wchar_t *uninst_key(void) {
    return getenv("MTF_SETUP_NO_SHORTCUTS")
               ? L"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\MTF-ShadowRacket-test"
               : L"Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\MTF-ShadowRacket";
}
static const char kMagic[8] = {'M', 'T', 'F', 'S', 'R', 'C', 'V', '1'};

// ---- Championship Turf Green + Optic Tennis Ball palette (matches runtime/ui/theme.h THEME_TENNIS)
#define C_BG          IM_COL32(8, 18, 12, 255)
#define C_PANEL       IM_COL32(18, 36, 24, 255)
#define C_RAISED      IM_COL32(28, 54, 37, 255)
#define C_HOVER       IM_COL32(38, 72, 50, 255)
#define C_PRESSED     IM_COL32(48, 88, 62, 255)
#define C_ACCENT      IM_COL32(204, 242, 42, 255)
#define C_ACCENT_HOT  IM_COL32(218, 250, 72, 255)
#define C_ACCENT_DOWN IM_COL32(168, 206, 30, 255)
#define C_ACCENT_INK  IM_COL32(12, 26, 17, 255)
#define C_TEXT        IM_COL32(246, 250, 244, 255)
#define C_HEADING     IM_COL32(190, 218, 196, 255)
#define C_DIM         IM_COL32(134, 168, 144, 255)
#define C_OFF         IM_COL32(82, 108, 90, 255)
#define C_LINE        IM_COL32(58, 102, 72, 160)
#define C_OK          IM_COL32(91, 201, 138, 255)
#define C_WARN        IM_COL32(236, 160, 70, 255)
#define C_BAD         IM_COL32(244, 112, 100, 255)

static ImVec4 v4(ImU32 c) { return ImGui::ColorConvertU32ToFloat4(c); }

static std::wstring wide(const std::string &s) {
    int n = MultiByteToWideChar(CP_UTF8, 0, s.c_str(), -1, nullptr, 0);
    std::wstring w(n ? n - 1 : 0, L'\0');
    if (n > 1) MultiByteToWideChar(CP_UTF8, 0, s.c_str(), -1, w.data(), n);
    return w;
}
static std::string utf8(const std::wstring &w) {
    int n = WideCharToMultiByte(CP_UTF8, 0, w.c_str(), -1, nullptr, 0, nullptr, nullptr);
    std::string s(n ? n - 1 : 0, '\0');
    if (n > 1) WideCharToMultiByte(CP_UTF8, 0, w.c_str(), -1, s.data(), n, nullptr, nullptr);
    return s;
}
static std::wstring self_path(void) {
    wchar_t p[MAX_PATH * 4];
    DWORD n = GetModuleFileNameW(nullptr, p, (DWORD)(sizeof p / sizeof *p));
    return std::wstring(p, n);
}
static std::wstring dir_of(const std::wstring &p) {
    size_t k = p.find_last_of(L"\\/");
    return k == std::wstring::npos ? L"." : p.substr(0, k);
}
static void human(uint64_t b, char *out, size_t n) {
    if (b >= (1ull << 30)) snprintf(out, n, "%.1f GB", b / 1073741824.0);
    else snprintf(out, n, "%.0f MB", b / 1048576.0);
}

// ---- Embedded payload (MTFSRCV1)
struct Entry { std::string path; uint64_t size, csize, at; };
struct Payload {
    uint64_t offset = 0, total = 0;
    std::string version;
    std::vector<Entry> files;
    bool ok = false;
};

static Payload read_payload(const std::wstring &exe) {
    Payload pl;
    FILE *f = _wfopen(exe.c_str(), L"rb");
    if (!f) return pl;
    char foot[16];
    if (_fseeki64(f, -16, SEEK_END) || fread(foot, 1, 16, f) != 16 || memcmp(foot + 8, kMagic, 8)) return fclose(f), pl;
    memcpy(&pl.offset, foot, 8);
    char head[8];
    uint32_t count = 0, vlen = 0;
    if (_fseeki64(f, (long long)pl.offset, SEEK_SET) || fread(head, 1, 8, f) != 8 || memcmp(head, kMagic, 8) ||
        fread(&count, 4, 1, f) != 1 || fread(&pl.total, 8, 1, f) != 1 || fread(&vlen, 4, 1, f) != 1 || vlen > 256)
        return fclose(f), pl;
    pl.version.resize(vlen);
    if (vlen && fread(pl.version.data(), 1, vlen, f) != vlen) return fclose(f), pl;
    for (uint32_t i = 0; i < count; i++) {
        uint16_t n = 0;
        Entry e;
        if (fread(&n, 2, 1, f) != 1) return fclose(f), pl;
        e.path.resize(n);
        if (fread(e.path.data(), 1, n, f) != n || fread(&e.size, 8, 1, f) != 1 || fread(&e.csize, 8, 1, f) != 1)
            return fclose(f), pl;
        e.at = (uint64_t)_ftelli64(f);
        if (_fseeki64(f, (long long)e.csize, SEEK_CUR)) return fclose(f), pl;
        pl.files.push_back(std::move(e));
    }
    fclose(f);
    pl.ok = true;
    return pl;
}

struct Job {
    std::atomic<uint64_t> done{0}, total{0};
    std::atomic<int> state{0};   // 0 idle, 1 running, 2 finished, 3 failed
    std::mutex m;
    std::string current, error;
    void set_current(const std::string &s) { std::lock_guard<std::mutex> g(m); current = s; }
    std::string get_current(void) { std::lock_guard<std::mutex> g(m); return current; }
    void fail(const std::string &s) { { std::lock_guard<std::mutex> g(m); error = s; } state = 3; }
};
static Job g_job;

static bool make_dirs(const std::wstring &path) {
    int r = SHCreateDirectoryExW(nullptr, path.c_str(), nullptr);
    return r == ERROR_SUCCESS || r == ERROR_ALREADY_EXISTS || r == ERROR_FILE_EXISTS;
}

static bool shortcut(const std::wstring &lnk, const std::wstring &target, const std::wstring &icon,
                     const std::wstring &dir) {
    IShellLinkW *sl = nullptr;
    if (FAILED(CoCreateInstance(CLSID_ShellLink, nullptr, CLSCTX_INPROC_SERVER, IID_IShellLinkW, (void **)&sl)))
        return false;
    sl->SetPath(target.c_str());
    sl->SetWorkingDirectory(dir.c_str());
    sl->SetIconLocation(icon.c_str(), 0);
    sl->SetDescription(L"Play Mario Tennis Fever PC (MTF ShadowRacket)");
    IPersistFile *pf = nullptr;
    bool ok = SUCCEEDED(sl->QueryInterface(IID_IPersistFile, (void **)&pf)) && SUCCEEDED(pf->Save(lnk.c_str(), TRUE));
    if (pf) pf->Release();
    sl->Release();
    return ok;
}

static std::wstring known(REFKNOWNFOLDERID id) {
    PWSTR p = nullptr;
    std::wstring s;
    if (SUCCEEDED(SHGetKnownFolderPath(id, 0, nullptr, &p))) s = p;
    CoTaskMemFree(p);
    return s;
}
static std::wstring desktop_lnk(void) { return known(FOLDERID_Desktop) + L"\\MTF ShadowRacket.lnk"; }
static std::wstring menu_lnk(void) { return known(FOLDERID_Programs) + L"\\MTF ShadowRacket.lnk"; }

static void reg_str(HKEY k, const wchar_t *name, const std::wstring &v) {
    RegSetValueExW(k, name, 0, REG_SZ, (const BYTE *)v.c_str(), (DWORD)((v.size() + 1) * sizeof(wchar_t)));
}
static void reg_dword(HKEY k, const wchar_t *name, DWORD v) { RegSetValueExW(k, name, 0, REG_DWORD, (const BYTE *)&v, 4); }

static void install_run(Payload pl, std::wstring exe, std::wstring dir, bool desk, bool menu) {
    CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    for (auto &ch : dir) if (ch == L'/') ch = L'\\';
    while (dir.size() > 3 && dir.back() == L'\\') dir.pop_back();
    g_job.total = pl.total;
    if (!make_dirs(dir)) return g_job.fail("The folder could not be created: " + utf8(dir));
    FILE *in = _wfopen(exe.c_str(), L"rb");
    if (!in) return g_job.fail("This setup could not read itself.");
    ZSTD_DCtx *dc = ZSTD_createDCtx();
    std::vector<char> ibuf(ZSTD_DStreamInSize()), obuf(ZSTD_DStreamOutSize());
    std::wstring manifest;
    for (const Entry &e : pl.files) {
        std::wstring rel = wide(e.path), out = dir + L"\\" + rel;
        for (auto &ch : out) if (ch == L'/') ch = L'\\';
        g_job.set_current(e.path);
        make_dirs(dir_of(out));
        FILE *o = _wfopen(out.c_str(), L"wb");
        if (!o) {
            fclose(in), ZSTD_freeDCtx(dc);
            return g_job.fail("Could not write " + e.path + ". Is the game or launcher still open?");
        }
        _fseeki64(in, (long long)e.at, SEEK_SET);
        ZSTD_DCtx_reset(dc, ZSTD_reset_session_only);
        uint64_t left = e.csize;
        while (left) {
            size_t want = (size_t)std::min<uint64_t>(left, ibuf.size()), got = fread(ibuf.data(), 1, want, in);
            if (!got) break;
            left -= got;
            ZSTD_inBuffer ib = {ibuf.data(), got, 0};
            while (ib.pos < ib.size) {
                ZSTD_outBuffer ob = {obuf.data(), obuf.size(), 0};
                size_t r = ZSTD_decompressStream(dc, &ob, &ib);
                if (ZSTD_isError(r)) {
                    fclose(o), fclose(in), ZSTD_freeDCtx(dc);
                    return g_job.fail("This setup archive is damaged (" + e.path + "): download it again.");
                }
                fwrite(obuf.data(), 1, ob.pos, o);
                g_job.done += ob.pos;
            }
        }
        if (fclose(o)) return g_job.fail("Could not finish writing " + e.path + " (disk full?).");
        manifest += rel + L"\n";
    }
    ZSTD_freeDCtx(dc);
    {
        std::vector<char> stub((size_t)pl.offset);
        _fseeki64(in, 0, SEEK_SET);
        size_t got = fread(stub.data(), 1, stub.size(), in);
        FILE *u = _wfopen((dir + L"\\uninstall.exe").c_str(), L"wb");
        if (u) fwrite(stub.data(), 1, got, u), fclose(u);
        manifest += L"uninstall.exe\n";
    }
    fclose(in);
    {
        FILE *m = _wfopen((dir + L"\\mtf-shadowracket-install.txt").c_str(), L"wb");
        if (m) {
            std::string s = utf8(manifest);
            fwrite(s.data(), 1, s.size(), m), fclose(m);
        }
    }
    std::wstring launcher = dir + L"\\MTFLauncher.exe";
    std::wstring icon = dir + L"\\mtf.ico";
    if (GetFileAttributesW(icon.c_str()) == INVALID_FILE_ATTRIBUTES) icon = launcher;
    if (desk) shortcut(desktop_lnk(), launcher, icon, dir);
    if (menu) shortcut(menu_lnk(), launcher, icon, dir);
    HKEY k;
    if (RegCreateKeyExW(HKEY_CURRENT_USER, uninst_key(), 0, nullptr, 0, KEY_WRITE, nullptr, &k, nullptr) == ERROR_SUCCESS) {
        reg_str(k, L"DisplayName", kNameW);
        reg_str(k, L"DisplayVersion", wide(pl.version));
        reg_str(k, L"Publisher", kBrandW);
        reg_str(k, L"DisplayIcon", icon);
        reg_str(k, L"InstallLocation", dir);
        reg_str(k, L"UninstallString", L"\"" + dir + L"\\uninstall.exe\"");
        reg_dword(k, L"NoModify", 1);
        reg_dword(k, L"NoRepair", 1);
        reg_dword(k, L"EstimatedSize", (DWORD)(pl.total / 1024));
        RegCloseKey(k);
    }
    CoUninitialize();
    g_job.state = 2;
}

static std::mutex g_left_m;
static std::vector<std::wstring> g_left_files;
static void delete_retry(const std::wstring &p) {
    for (int i = 0; i < 30; i++) {
        if (DeleteFileW(p.c_str())) return;
        DWORD e = GetLastError();
        if (e == ERROR_FILE_NOT_FOUND || e == ERROR_PATH_NOT_FOUND) return;
        Sleep(100);
    }
    std::lock_guard<std::mutex> g(g_left_m);
    g_left_files.push_back(p);
}

static void remove_pycache(const std::wstring &dir) {
    WIN32_FIND_DATAW fd;
    HANDLE h = FindFirstFileW((dir + L"\\*").c_str(), &fd);
    if (h == INVALID_HANDLE_VALUE) return;
    do {
        std::wstring n = fd.cFileName;
        if (!(fd.dwFileAttributes & FILE_ATTRIBUTE_DIRECTORY) || n == L"." || n == L"..") continue;
        std::wstring sub = dir + L"\\" + n;
        if (n == L"__pycache__") {
            std::wstring from = sub + L'\0';
            SHFILEOPSTRUCTW op = {};
            op.wFunc = FO_DELETE;
            op.pFrom = from.c_str();
            op.fFlags = FOF_NO_UI;
            SHFileOperationW(&op);
        } else {
            remove_pycache(sub);
        }
    } while (FindNextFileW(h, &fd));
    FindClose(h);
}

static void uninstall_run(std::wstring dir, bool everything) {
    g_job.total = 1;
    std::wstring self = L"uninstall.exe";
    if (everything) {
        WIN32_FIND_DATAW fd;
        HANDLE h = FindFirstFileW((dir + L"\\*").c_str(), &fd);
        if (h != INVALID_HANDLE_VALUE) {
            do {
                std::wstring n = fd.cFileName;
                if (n == L"." || n == L".." || !_wcsicmp(n.c_str(), self.c_str())) continue;
                g_job.set_current(utf8(n));
                std::wstring p = dir + L"\\" + n + L'\0';
                SHFILEOPSTRUCTW op = {};
                op.wFunc = FO_DELETE;
                op.pFrom = p.c_str();
                op.fFlags = FOF_NO_UI;
                SHFileOperationW(&op);
            } while (FindNextFileW(h, &fd));
            FindClose(h);
        }
    } else {
        FILE *m = _wfopen((dir + L"\\mtf-shadowracket-install.txt").c_str(), L"rb");
        std::string text;
        if (m) {
            char buf[65536];
            size_t n;
            while ((n = fread(buf, 1, sizeof buf, m))) text.append(buf, n);
            fclose(m);
        }
        std::vector<std::wstring> dirs;
        size_t a = 0;
        while (a < text.size()) {
            size_t b = text.find('\n', a);
            if (b == std::string::npos) b = text.size();
            std::wstring rel = wide(text.substr(a, b - a));
            a = b + 1;
            if (rel.empty() || !_wcsicmp(rel.c_str(), self.c_str())) continue;
            g_job.set_current(utf8(rel));
            std::wstring p = dir + L"\\" + rel;
            for (auto &ch : p) if (ch == L'/') ch = L'\\';
            delete_retry(p);
            for (std::wstring d = dir_of(p); d.size() > dir.size(); d = dir_of(d)) dirs.push_back(d);
        }
        DeleteFileW((dir + L"\\mtf-shadowracket-install.txt").c_str());
        remove_pycache(dir);
        std::sort(dirs.begin(), dirs.end(), [](const std::wstring &x, const std::wstring &y) { return x.size() > y.size(); });
        for (const auto &d : dirs) RemoveDirectoryW(d.c_str());
    }
    CoInitializeEx(nullptr, COINIT_APARTMENTTHREADED);
    if (!getenv("MTF_SETUP_NO_SHORTCUTS")) {
        DeleteFileW(desktop_lnk().c_str());
        DeleteFileW(menu_lnk().c_str());
    }
    CoUninitialize();
    RegDeleteKeyW(HKEY_CURRENT_USER, uninst_key());
    g_job.done = 1;
    g_job.state = 2;
}

static void delete_self_later(const std::wstring &dir) {
    std::wstring cmd = L"cmd.exe /c ping -n 4 127.0.0.1 >nul";
    {
        std::lock_guard<std::mutex> g(g_left_m);
        for (const auto &f : g_left_files) cmd += L" & del /f /q \"" + f + L"\"";
        for (const auto &f : g_left_files)
            for (std::wstring d = dir_of(f); d.size() > dir.size(); d = dir_of(d)) cmd += L" & rmdir \"" + d + L"\" 2>nul";
    }
    cmd += L" & del /f /q \"" + dir + L"\\uninstall.exe\" & rmdir \"" + dir + L"\\profile\" 2>nul & rmdir \"" + dir + L"\" 2>nul";
    STARTUPINFOW si = {sizeof si};
    PROCESS_INFORMATION pi = {};
    if (CreateProcessW(nullptr, cmd.data(), nullptr, nullptr, FALSE, CREATE_NO_WINDOW, nullptr, nullptr, &si, &pi))
        CloseHandle(pi.hThread), CloseHandle(pi.hProcess);
}

// ---- Drawing: Championship Turf stripes, court chalk lines & spinning optic tennis ball
struct Ui {
    SDL_Window *win = nullptr;
    SDL_Renderer *ren = nullptr;
    SDL_Texture *icon = nullptr;
    SDL_Texture *ball = nullptr;
    ImFont *body = nullptr, *head = nullptr, *big = nullptr, *small = nullptr;
    float scale = 1;
};
static Ui U;

static void draw_tennis_ball(ImDrawList *dl, ImVec2 center, float r, float angle) {
    if (U.ball) {
        // Subtle rotation of the 256x256 studio-shaded tennis ball sprite
        float s = r * 1.09f;   // sprite diameter / R = 1 / 0.46
        float ca = cosf(angle * 0.25f), sa = sinf(angle * 0.25f);
        auto corner = [&](float dx, float dy) {
            return ImVec2(center.x + dx * ca - dy * sa, center.y + dx * sa + dy * ca);
        };
        dl->AddImageQuad((ImTextureID)(intptr_t)U.ball,
                         corner(-s, -s), corner(s, -s), corner(s, s), corner(-s, s));
        return;
    }
    dl->AddCircleFilled(center, r, IM_COL32(235, 212, 22, 240), 48);
}

static void backdrop(ImDrawList *dl, float w, float h, float t) {
    dl->AddRectFilled(ImVec2(0, 0), ImVec2(w, h), C_BG);
    // Perspective turf lanes on right side of the wizard window
    const int lanes = 7;
    float x_start = w * 0.42f;
    float lane_w = (w - x_start) / lanes;
    for (int i = 0; i < lanes; i++) {
        ImU32 col = (i % 2 == 0) ? IM_COL32(14, 32, 20, 255) : IM_COL32(20, 44, 28, 255);
        dl->AddRectFilled(ImVec2(x_start + i * lane_w, 0), ImVec2(x_start + (i + 1) * lane_w, h), col);
    }
    // Crisp court chalk lines & service box
    ImU32 chalk = IM_COL32(236, 246, 232, 46);
    ImU32 accent_line = IM_COL32(204, 242, 42, 95);
    dl->AddLine(ImVec2(w * 0.56f, 0), ImVec2(w * 0.72f, h), chalk, 3.0f);
    dl->AddLine(ImVec2(w * 0.82f, 0), ImVec2(w * 0.96f, h), accent_line, 2.5f);
    dl->AddLine(ImVec2(w * 0.48f, h * 0.52f), ImVec2(w, h * 0.34f), chalk, 3.0f);
    dl->AddLine(ImVec2(w * 0.52f, h * 0.76f), ImVec2(w, h * 0.64f), chalk, 2.0f);

    // Floating tennis ball on right court showcase
    float bob = sinf(t * 1.4f) * (h * 0.025f);
    ImVec2 ball_pos(w * 0.79f, h * 0.45f + bob);
    float ball_r = h * 0.16f;
    dl->AddEllipseFilled(ImVec2(w * 0.79f, h * 0.69f), ImVec2(ball_r * 0.95f, ball_r * 0.24f), IM_COL32(0, 0, 0, 95), 0.0f, 32);
    draw_tennis_ball(dl, ball_pos, ball_r, sinf(t * 0.7f) * 0.35f + 0.2f);

    // Smooth dark turf fade behind left text column
    ImU32 none = C_BG & ~IM_COL32_A_MASK;
    dl->AddRectFilled(ImVec2(0, 0), ImVec2(w * 0.46f, h), C_BG);
    dl->AddRectFilledMultiColor(ImVec2(w * 0.46f - 1, 0), ImVec2(w * 0.76f, h), C_BG, none, none, C_BG);
    dl->AddRectFilledMultiColor(ImVec2(0, h * 0.78f), ImVec2(w, h * 0.90f), none, none, C_BG, C_BG);
    dl->AddRectFilled(ImVec2(0, h * 0.90f - 1), ImVec2(w, h), C_BG);
}

static bool accent_button(const char *label, ImVec2 size, bool enabled = true) {
    ImGui::PushStyleColor(ImGuiCol_Button, v4(enabled ? C_ACCENT : C_RAISED));
    ImGui::PushStyleColor(ImGuiCol_ButtonHovered, v4(enabled ? C_ACCENT_HOT : C_RAISED));
    ImGui::PushStyleColor(ImGuiCol_ButtonActive, v4(enabled ? C_ACCENT_DOWN : C_RAISED));
    ImGui::PushStyleColor(ImGuiCol_Text, v4(enabled ? C_ACCENT_INK : C_OFF));
    bool r = ImGui::Button(label, size) && enabled;
    ImGui::PopStyleColor(4);
    return r;
}
static bool plain_button(const char *label, ImVec2 size) { return ImGui::Button(label, size); }

static void wrapped(ImU32 c, const char *s) {
    ImGui::PushStyleColor(ImGuiCol_Text, v4(c));
    ImGui::TextWrapped("%s", s);
    ImGui::PopStyleColor();
}

static void title_block(float S, const char *subtitle) {
    ImDrawList *dl = ImGui::GetWindowDrawList();
    ImVec2 p = ImGui::GetCursorScreenPos();
    float mark = 84 * S;
    if (U.icon) dl->AddImage((ImTextureID)(intptr_t)U.icon, p, ImVec2(p.x + mark, p.y + mark));
    ImGui::SetCursorScreenPos(ImVec2(p.x + mark + 22 * S, p.y + 2 * S));
    ImGui::PushFont(U.big);
    ImGui::TextUnformatted(kName);
    ImGui::PopFont();
    ImGui::SetCursorScreenPos(ImVec2(p.x + mark + 24 * S, ImGui::GetCursorScreenPos().y - 2 * S));
    ImGui::PushStyleColor(ImGuiCol_Text, v4(C_ACCENT_HOT));
    ImGui::TextUnformatted(subtitle);
    ImGui::PopStyleColor();
    ImGui::SetCursorScreenPos(ImVec2(p.x, p.y + mark + 26 * S));
}

static void card(float S, float width, const char *title, const char *text) {
    ImDrawList *dl = ImGui::GetWindowDrawList();
    ImVec2 p = ImGui::GetCursorScreenPos();
    float th = U.body->FontSize, dh = U.small->CalcTextSizeA(U.small->FontSize, FLT_MAX, width - 34 * S, text).y;
    float h = 12 * S + th + 6 * S + dh + 14 * S;
    dl->AddRectFilled(p, ImVec2(p.x + width, p.y + h), C_PANEL, 6 * S);
    dl->AddRect(p, ImVec2(p.x + width, p.y + h), C_LINE, 6 * S);
    dl->AddRectFilled(ImVec2(p.x, p.y + 12 * S), ImVec2(p.x + 4 * S, p.y + h - 12 * S), C_ACCENT, 2 * S);
    dl->AddText(U.body, th, ImVec2(p.x + 18 * S, p.y + 12 * S), C_TEXT, title);
    ImGui::SetCursorScreenPos(ImVec2(p.x + 18 * S, p.y + 12 * S + th + 6 * S));
    ImGui::PushFont(U.small);
    ImGui::PushStyleColor(ImGuiCol_Text, v4(C_HEADING));
    ImGui::PushTextWrapPos(p.x + width - 16 * S - ImGui::GetWindowPos().x);
    ImGui::PushStyleVar(ImGuiStyleVar_ItemSpacing, ImVec2(0, 0));
    ImGui::TextUnformatted(text);
    ImGui::PopStyleVar();
    ImGui::PopTextWrapPos();
    ImGui::PopStyleColor();
    ImGui::PopFont();
    ImGui::SetCursorScreenPos(ImVec2(p.x, p.y + h + 12 * S));
}

static void progress(float S, float width, float f) {
    ImDrawList *dl = ImGui::GetWindowDrawList();
    ImVec2 p = ImGui::GetCursorScreenPos();
    float h = 10 * S;
    dl->AddRectFilled(p, ImVec2(p.x + width, p.y + h), C_RAISED, h * 0.5f);
    if (f > 0) dl->AddRectFilled(p, ImVec2(p.x + width * fminf(f, 1.0f), p.y + h), C_ACCENT, h * 0.5f);
    ImGui::Dummy(ImVec2(width, h + 8 * S));
}

static std::mutex g_pick_m;
static std::string g_picked;
static void SDLCALL on_folder(void *, const char *const *list, int) {
    if (list && list[0]) {
        std::lock_guard<std::mutex> g(g_pick_m);
        g_picked = list[0];
    }
}

static uint64_t free_space(const std::wstring &dir) {
    std::wstring d = dir;
    ULARGE_INTEGER freeb;
    while (!d.empty()) {
        if (GetDiskFreeSpaceExW(d.c_str(), &freeb, nullptr, nullptr)) return freeb.QuadPart;
        std::wstring up = dir_of(d);
        if (up == d) break;
        d = up;
    }
    return 0;
}

enum Page { P_WELCOME, P_FOLDER, P_COPY, P_DONE, P_UNINSTALL, P_UNINSTALLING, P_UNINSTALLED };

int main(int argc, char **argv) {
    std::wstring exe = self_path(), exe_dir = dir_of(exe);
    std::wstring base = exe.substr(exe_dir.size() + 1);
    bool uninstall = !_wcsicmp(base.c_str(), L"uninstall.exe");
    for (int i = 1; i < argc; i++) uninstall |= !strcmp(argv[i], "--uninstall");
    Payload pl = uninstall ? Payload{} : read_payload(exe);

    int shot_frame = 0;
    std::string shot_page;
    if (const char *e = getenv("MTF_SETUP_SHOT")) {
        shot_frame = atoi(e);
        if (const char *c = strchr(e, ':')) shot_page = c + 1;
    }

    SDL_SetHint(SDL_HINT_VIDEO_ALLOW_SCREENSAVER, "1");
    if (!SDL_Init(SDL_INIT_VIDEO)) {
        MessageBoxW(nullptr, L"This setup could not open its window.", kNameW, MB_ICONERROR);
        return 1;
    }
    float ds = SDL_GetDisplayContentScale(SDL_GetPrimaryDisplay());
    if (ds <= 0) ds = 1;
    U.win = SDL_CreateWindow(uninstall ? "Mario Tennis Fever PC: Uninstall" : "MTF ShadowRacket Setup",
                             (int)(1180 * ds), (int)(720 * ds), SDL_WINDOW_HIGH_PIXEL_DENSITY | SDL_WINDOW_HIDDEN);
    U.ren = U.win ? SDL_CreateRenderer(U.win, nullptr) : nullptr;
    if (!U.ren) {
        MessageBoxW(nullptr, L"This setup could not open its window.", kNameW, MB_ICONERROR);
        return 1;
    }
    SDL_SetRenderVSync(U.ren, 1);
    if (SDL_Surface *s = SDL_LoadPNG_IO(SDL_IOFromConstMem(kIconPng, sizeof kIconPng), true)) {
        SDL_SetWindowIcon(U.win, s);
        U.icon = SDL_CreateTextureFromSurface(U.ren, s);
        if (U.icon) SDL_SetTextureScaleMode(U.icon, SDL_SCALEMODE_LINEAR);
        SDL_DestroySurface(s);
    }
    if (SDL_Surface *bs = SDL_LoadPNG_IO(SDL_IOFromConstMem(kBallPng, sizeof kBallPng), true)) {
        U.ball = SDL_CreateTextureFromSurface(U.ren, bs);
        if (U.ball) SDL_SetTextureScaleMode(U.ball, SDL_SCALEMODE_LINEAR);
        SDL_DestroySurface(bs);
    }
    SDL_ShowWindow(U.win);

    IMGUI_CHECKVERSION();
    ImGui::CreateContext();
    ImGuiIO &io = ImGui::GetIO();
    io.IniFilename = nullptr;
    io.ConfigFlags |= ImGuiConfigFlags_NavEnableKeyboard | ImGuiConfigFlags_NavEnableGamepad;
    float S = ds;
    U.scale = S;
    ImFontConfig fc;
    fc.FontDataOwnedByAtlas = false;
    static const ImWchar ranges[] = {0x0020, 0x017F, 0x2010, 0x2027, 0x2190, 0x2193, 0};
    U.body = io.Fonts->AddFontFromMemoryTTF((void *)kRoboto, (int)sizeof kRoboto, 22 * S, &fc, ranges);
    U.small = io.Fonts->AddFontFromMemoryTTF((void *)kRoboto, (int)sizeof kRoboto, 18 * S, &fc, ranges);
    U.head = io.Fonts->AddFontFromMemoryTTF((void *)kRoboto, (int)sizeof kRoboto, 30 * S, &fc, ranges);
    U.big = io.Fonts->AddFontFromMemoryTTF((void *)kRoboto, (int)sizeof kRoboto, 46 * S, &fc, ranges);
    ImGuiStyle &st = ImGui::GetStyle();
    ImGui::StyleColorsDark(&st);
    st.WindowRounding = 0; st.FrameRounding = 5; st.GrabRounding = 4; st.WindowBorderSize = 0;
    st.FramePadding = ImVec2(16, 9); st.ItemSpacing = ImVec2(12, 12); st.WindowPadding = ImVec2(0, 0);
    st.ScaleAllSizes(S);
    ImVec4 *c = st.Colors;
    c[ImGuiCol_WindowBg] = ImVec4(0, 0, 0, 0);
    c[ImGuiCol_Text] = v4(C_TEXT);
    c[ImGuiCol_TextDisabled] = v4(C_DIM);
    c[ImGuiCol_Button] = v4(C_RAISED);
    c[ImGuiCol_ButtonHovered] = v4(C_HOVER);
    c[ImGuiCol_ButtonActive] = v4(C_PRESSED);
    c[ImGuiCol_FrameBg] = v4(C_RAISED);
    c[ImGuiCol_FrameBgHovered] = v4(C_HOVER);
    c[ImGuiCol_FrameBgActive] = v4(C_PRESSED);
    c[ImGuiCol_CheckMark] = v4(C_ACCENT_HOT);
    c[ImGuiCol_NavCursor] = v4(C_ACCENT_HOT);
    c[ImGuiCol_TextSelectedBg] = ImVec4(0.80f, 0.95f, 0.16f, 0.35f);
    c[ImGuiCol_Border] = v4(C_LINE);
    ImGui_ImplSDL3_InitForSDLRenderer(U.win, U.ren);
    ImGui_ImplSDLRenderer3_Init(U.ren);

    Page page = uninstall ? P_UNINSTALL : P_WELCOME;
    if (shot_page == "folder") page = P_FOLDER;
    else if (shot_page == "copy") page = P_COPY, g_job.total = 100, g_job.done = 54, g_job.set_current("MTFLauncher.exe");
    else if (shot_page == "done") page = P_DONE;
    else if (shot_page == "uninstall") page = P_UNINSTALL, uninstall = true;
    std::string sys_drive = "C:";
    if (const char *sd = getenv("SystemDrive")) sys_drive = sd;
    char path[1024];
    snprintf(path, sizeof path, "%s\\Games\\Mario Tennis Fever PC", sys_drive.c_str());
    if (const char *d = getenv("MTF_SETUP_DIR")) snprintf(path, sizeof path, "%s", d);
    bool desk = true, menu = true, launch = true, everything = false;
    bool auto_mode = getenv("MTF_SETUP_AUTO") != nullptr;
    bool auto_run = auto_mode;
    if (getenv("MTF_SETUP_NO_SHORTCUTS")) desk = menu = false;
    if (auto_run && !uninstall && !shot_frame) page = P_FOLDER;
    const char *ver_str = !pl.version.empty() ? pl.version.c_str() : "Alpha 0.1.1";
    std::thread worker;
    float phase = 1.2f;
    bool quit = false;
    int frame = 0;
    while (!quit) {
        SDL_Event ev;
        while (SDL_PollEvent(&ev)) {
            ImGui_ImplSDL3_ProcessEvent(&ev);
            if (ev.type == SDL_EVENT_QUIT || ev.type == SDL_EVENT_WINDOW_CLOSE_REQUESTED) {
                if (g_job.state != 1) quit = true;
            }
        }
        {
            std::lock_guard<std::mutex> g(g_pick_m);
            if (!g_picked.empty()) {
                std::string p = g_picked;
                if (p.find("Mario Tennis Fever") == std::string::npos) p += "\\Mario Tennis Fever PC";
                snprintf(path, sizeof path, "%s", p.c_str());
                g_picked.clear();
            }
        }
        if (!shot_frame && !(SDL_GetWindowFlags(U.win) & SDL_WINDOW_INPUT_FOCUS)) SDL_Delay(30);
        else if (!shot_frame) phase += io.DeltaTime * 0.65f;
        ImGui_ImplSDLRenderer3_NewFrame();
        ImGui_ImplSDL3_NewFrame();
        ImGui::NewFrame();
        int pw, ph;
        SDL_GetRenderOutputSize(U.ren, &pw, &ph);
        float W = (float)pw, H = (float)ph;
        backdrop(ImGui::GetBackgroundDrawList(), W, H, phase);
        ImGui::SetNextWindowPos(ImVec2(0, 0));
        ImGui::SetNextWindowSize(ImVec2(W, H));
        ImGui::Begin("##setup", nullptr, ImGuiWindowFlags_NoDecoration | ImGuiWindowFlags_NoMove |
                                             ImGuiWindowFlags_NoSavedSettings | ImGuiWindowFlags_NoBackground);
        ImGui::PushFont(U.body);
        float x0 = 70 * S, colw = fminf(W * 0.54f, 660 * S), top = 56 * S, foot = H - 86 * S;
        ImGui::Indent(x0);
        ImGui::SetCursorScreenPos(ImVec2(x0, top));
        ImVec2 bsz(170 * S, 0);
        auto footer = [&](void) { ImGui::SetCursorScreenPos(ImVec2(x0, foot)); };

        switch (page) {
        case P_WELCOME: {
            char sub[160];
            snprintf(sub, sizeof sub, "MTF-ShadowRacket %s  ·  natively on Windows, not an emulator", ver_str);
            title_block(S, sub);
            card(S, colw, "Native PC recompilation",
                 "Mario Tennis Fever's ARM64 code compiles natively on your PC via bundled LLVM & Ninja tooling. Zero emulation overhead.");
            card(S, colw, "Clean Default Profile & Working Resolution Scaling",
                 "Starts cleanly at 1080p Windowed, Original internal (~960p), FSR & Frame Gen Off — with 720p/900p/1080p/1440p ready in-game (F1) or in the Launcher.");
            card(S, colw, "Ready-to-Launch MTFLauncher",
                 "Includes MTFLauncher to verify your Mario Tennis Fever 1.1.1 dump, build mtf.exe in one step, manage mods, and back up saves.");
            ImGui::SetCursorScreenPos(ImVec2(x0, ImGui::GetCursorScreenPos().y + 4 * S));
            ImGui::PushTextWrapPos(x0 + colw);
            ImGui::PushFont(U.small);
            wrapped(C_WARN, "No copyrighted game files, saves, or developer .ini settings are included. After installing, "
                            "MTFLauncher builds mtf.exe directly from your own Mario Tennis Fever 1.1.1 dump.");
            ImGui::PopFont();
            ImGui::PopTextWrapPos();
            if (!pl.ok && !shot_frame) {
                ImGui::PushFont(U.small);
                wrapped(C_BAD, "No embedded payload was found in this setup executable (rebuild via tools/build_mtf_release.py).");
                ImGui::PopFont();
            }
            footer();
            if (accent_button("Next", bsz, pl.ok || shot_frame)) page = P_FOLDER;
            ImGui::SameLine();
            if (plain_button("Cancel", bsz)) quit = true;
            break;
        }
        case P_FOLDER: {
            title_block(S, "Where should MTF ShadowRacket install?");
            ImGui::PushFont(U.small);
            wrapped(C_HEADING, "Install folder");
            ImGui::PopFont();
            ImGui::SetNextItemWidth(colw - 150 * S);
            ImGui::InputText("##dir", path, sizeof path);
            ImGui::SameLine();
            if (plain_button("Browse...", ImVec2(138 * S, 0)))
                SDL_ShowOpenFolderDialog(on_folder, nullptr, U.win, path, false);
            uint64_t freeb = free_space(wide(path));
            char need[32], have[32], line[180];
            human(pl.total, need, sizeof need);
            human(freeb, have, sizeof have);
            snprintf(line, sizeof line, "Toolchain & Launcher: %s.  Setting up your MTF dump adds about 5 GB.  Free there: %s",
                     need, have);
            ImGui::PushFont(U.small);
            wrapped(freeb && freeb < pl.total + (5ull << 30) ? C_WARN : C_DIM, line);
            ImGui::PopFont();
            ImGui::Dummy(ImVec2(1, 10 * S));
            ImGui::Checkbox("Desktop shortcut (MTF ShadowRacket)", &desk);
            ImGui::Checkbox("Start menu shortcut", &menu);
            ImGui::Dummy(ImVec2(1, 10 * S));
            ImGui::PushTextWrapPos(x0 + colw);
            ImGui::PushFont(U.small);
            wrapped(C_DIM, "Installing over an existing folder updates the launcher and compiler while preserving your mtf.exe, "
                           "saves, mtf.ini settings, and mods. No administrator rights required.");
            ImGui::PopFont();
            ImGui::PopTextWrapPos();
            footer();
            bool go = accent_button("Install", bsz, path[0] != 0) || (auto_run && pl.ok);
            if (go && !shot_frame) {
                auto_run = false;
                page = P_COPY;
                g_job.state = 1;
                worker = std::thread(install_run, pl, exe, wide(path), desk, menu);
            }
            ImGui::SameLine();
            if (plain_button("Back", bsz)) page = P_WELCOME;
            ImGui::SameLine();
            if (plain_button("Cancel", bsz)) quit = true;
            break;
        }
        case P_COPY: {
            title_block(S, g_job.state == 3 ? "Something went wrong" : "Installing MTF ShadowRacket...");
            uint64_t d = g_job.done, t = g_job.total;
            float f = t ? (float)d / (float)t : 0;
            progress(S, colw, f);
            char line[256], a[32], b[32];
            human(d, a, sizeof a), human(t, b, sizeof b);
            snprintf(line, sizeof line, "%.0f %%   %s of %s", f * 100, a, b);
            ImGui::TextUnformatted(line);
            ImGui::PushFont(U.small);
            ImGui::PushTextWrapPos(x0 + colw);
            if (g_job.state == 3) {
                std::lock_guard<std::mutex> g(g_job.m);
                wrapped(C_BAD, g_job.error.c_str());
            } else {
                wrapped(C_DIM, g_job.get_current().c_str());
            }
            ImGui::PopTextWrapPos();
            ImGui::PopFont();
            if (g_job.state == 2) {
                if (worker.joinable()) worker.join();
                page = P_DONE;
            }
            footer();
            if (g_job.state == 3) {
                if (worker.joinable()) worker.join();
                if (plain_button("Back", bsz)) page = P_FOLDER, g_job.state = 0, g_job.done = 0;
                ImGui::SameLine();
                if (plain_button("Close", bsz)) quit = true;
            }
            break;
        }
        case P_DONE: {
            title_block(S, "Installed");
            ImGui::PushTextWrapPos(x0 + colw);
            wrapped(C_TEXT, "MTF ShadowRacket (Mario Tennis Fever PC) is installed.");
            ImGui::PushFont(U.small);
            wrapped(C_DIM, "Next, open MTFLauncher -> SETUP FROM DUMP, select your Mario Tennis Fever 1.1.1 ExeFS and RomFS "
                           "folders, and click Verify & Build mtf.exe. Then press Play!");
            ImGui::PopFont();
            ImGui::PopTextWrapPos();
            ImGui::Dummy(ImVec2(1, 8 * S));
            ImGui::Checkbox("Launch MTFLauncher now", &launch);
            footer();
            if (accent_button("Finish", bsz)) {
                if (launch && !shot_frame) {
                    std::wstring dir = wide(path);
                    ShellExecuteW(nullptr, L"open", (dir + L"\\MTFLauncher.exe").c_str(), nullptr, dir.c_str(), SW_SHOWNORMAL);
                }
                quit = true;
            }
            break;
        }
        case P_UNINSTALL: {
            title_block(S, "Uninstall");
            ImGui::PushTextWrapPos(x0 + colw);
            wrapped(C_TEXT, "This removes MTF ShadowRacket's program files, shortcuts, and Windows installed apps entry.");
            ImGui::PopTextWrapPos();
            ImGui::Dummy(ImVec2(1, 8 * S));
            ImGui::Checkbox("Also remove mtf.exe, dump files, saves, settings, and mods", &everything);
            ImGui::PushFont(U.small);
            ImGui::PushTextWrapPos(x0 + colw);
            wrapped(everything ? C_WARN : C_DIM, everything ? "Everything in this folder goes, your saves too. This cannot be undone."
                                                            : "Your saves, mtf.ini settings, and built mtf.exe stay in this folder.");
            ImGui::PopTextWrapPos();
            ImGui::PopFont();
            footer();
            if ((accent_button("Uninstall", bsz) || auto_run) && !shot_frame) {
                auto_run = false;
                page = P_UNINSTALLING;
                g_job.state = 1;
                worker = std::thread(uninstall_run, exe_dir, everything);
            }
            ImGui::SameLine();
            if (plain_button("Cancel", bsz)) quit = true;
            break;
        }
        case P_UNINSTALLING:
        case P_UNINSTALLED: {
            bool done = g_job.state == 2;
            if (done && worker.joinable()) worker.join();
            title_block(S, done ? "Uninstalled" : "Removing...");
            ImGui::PushFont(U.small);
            wrapped(C_DIM, done ? "MTF ShadowRacket was removed. See you on the court!" : g_job.get_current().c_str());
            ImGui::PopFont();
            footer();
            if (done && (accent_button("Close", bsz) || auto_mode)) {
                delete_self_later(exe_dir);
                quit = true;
            }
            break;
        }
        }
        ImGui::Unindent(x0);
        {
            ImGui::PushFont(U.small);
            char v[96];
            snprintf(v, sizeof v, "MTF-ShadowRacket %s", ver_str);
            ImVec2 vs = ImGui::CalcTextSize(v);
            ImGui::GetWindowDrawList()->AddText(ImVec2(W - vs.x - 40 * S, H - vs.y - 34 * S), C_DIM, v);
            ImGui::PopFont();
        }
        ImGui::PopFont();
        ImGui::End();
        ImGui::Render();
        SDL_SetRenderDrawColor(U.ren, 8, 18, 12, 255);
        SDL_RenderClear(U.ren);
        ImGui_ImplSDLRenderer3_RenderDrawData(ImGui::GetDrawData(), U.ren);
        if (shot_frame && ++frame >= shot_frame) {
            SDL_Surface *s = SDL_RenderReadPixels(U.ren, nullptr);
            const char *out = getenv("MTF_SETUP_SHOT_OUT");
            if (s) SDL_SavePNG(s, out && *out ? out : "mtf_setup.png"), SDL_DestroySurface(s);
            quit = true;
        }
        SDL_RenderPresent(U.ren);
        if (auto_mode && page == P_DONE) quit = true;
    }
    if (worker.joinable()) worker.join();
    ImGui_ImplSDLRenderer3_Shutdown();
    ImGui_ImplSDL3_Shutdown();
    ImGui::DestroyContext();
    if (U.ball) SDL_DestroyTexture(U.ball);
    if (U.icon) SDL_DestroyTexture(U.icon);
    SDL_DestroyRenderer(U.ren);
    SDL_DestroyWindow(U.win);
    SDL_Quit();
    return g_job.state == 3 ? 1 : 0;
}

int WINAPI WinMain(HINSTANCE, HINSTANCE, LPSTR, int) {
    int argc = 0;
    LPWSTR *wargv = CommandLineToArgvW(GetCommandLineW(), &argc);
    std::vector<std::string> args;
    std::vector<char *> argv;
    for (int i = 0; i < argc; i++) args.push_back(utf8(wargv[i]));
    for (auto &a : args) argv.push_back(a.data());
    LocalFree(wargv);
    return main(argc, argv.data());
}
