from pathlib import Path
import subprocess, hashlib, re, shlex

src = Path(r"C:\Games\MTF PC\build\mtf111")
dst = Path(r"C:\Games\MTF PC\build\mtf111-lakitu")
repo = Path(r"C:\Games\DKB PC\Universal-NS2-to-PC")
ninja = (dst / "build.ninja").read_text(encoding="utf-8")
rt = re.search(r"^rtflags = (.+)$", ninja, re.M).group(1)
cc = r"C:\msys64\ucrt64\bin\clang.exe"
for s in ("vk_exec_xfer.c", "vk_backend.c", "nvn_ext.c", "vk_texture.c", "vk_device.c", "vk_rec.c", "vk_exec_draw.c",
          "nvn_api_core.c", "nvn_api_cmd.c"):
    stem = Path(s).stem
    obj = dst / "obj" / "runtime" / (stem + ".o")
    flags = shlex.split(rt, posix=True)
    if s.endswith(".cpp"):
        flags += ["-std=c++20", "-I", "runtime/third_party/eglantine"]
    args = [cc] + flags + ["-c", f"runtime/{s}", "-o", str(obj)]
    print("COMPILING", s)
    r = subprocess.run(args, cwd=repo)
    if r.returncode: raise SystemExit(r.returncode)
m = re.search(r"mtf111-lakitu/mtf\.exe: link (.+)$", ninja, re.M)
raw = m.group(1)
unesc=[]; i=0
while i < len(raw):
    if raw[i]=="$" and i+1 < len(raw):
        unesc.append(raw[i+1]); i += 2
    else:
        unesc.append(raw[i]); i += 1
text="".join(unesc)
prefix="C:/Games/MTF PC/"
objs=[prefix+p.strip() for p in text.split(prefix) if p.strip()]
missing=[o for o in objs if not Path(o).exists()]
print("RSP", len(objs), "MISSING", len(missing))
if missing: print(missing[:3]); raise SystemExit(2)
rsp=dst/"mtf.exe.rsp"
rsp.write_text("\n".join(f'"{o}"' for o in objs)+"\n", encoding="utf-8")
cmd=[cc,"-fuse-ld=lld","-Wl,--stack,16777216","-Wl,--wrap,f_700205e8fc","-Xlinker",f"--Map={dst.as_posix()}/mtf.map",f"@{rsp}","-lpsapi","-lbcrypt","-lvulkan-1","-luser32","-lgdi32","-ldwmapi","-limm32","-lwinmm","-lSDL3","-lopus","-l:libvpx.a","-l:libdav1d.a","-l:libzstd.a","-l:libstdc++.a","-l:libwinpthread.a","-o",str(dst/"mtf.exe")]
print("LINKING")
r=subprocess.run(cmd, cwd=repo)
print("LINK_EXIT", r.returncode)
if r.returncode: raise SystemExit(r.returncode)
def sha(p):
    h=hashlib.sha256()
    with open(p,"rb") as f:
        for c in iter(lambda:f.read(1<<20),b""): h.update(c)
    return h.hexdigest().upper()
side,ship=sha(dst/"mtf.exe"),sha(src/"mtf.exe")
print("SIDE", side); print("SHIP", ship)
print("SHIP_OK", ship=="5F37D3517D1419313B0FC389F9D05C271784C24363FF9A71C2DA6312F7633619")
print("SIDE_CHANGED", side!=ship)
