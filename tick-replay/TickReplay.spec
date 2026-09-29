# PyInstaller recipe for the Windows program:  pyinstaller --noconfirm TickReplay.spec
# Produces dist/TickReplay/TickReplay.exe (+ an _internal folder that must stay next to it).
from PyInstaller.utils.hooks import collect_submodules

a = Analysis(
    ["desktop.py"],
    pathex=["."],
    datas=[("web", "web")],
    hiddenimports=collect_submodules("uvicorn") + [
        "server.app", "server.store", "tools.import_ticks", "tools.make_sample", "multipart",
    ],
    excludes=["tkinter", "matplotlib", "IPython", "pytest", "cryptography"],
)
pyz = PYZ(a.pure)
exe = EXE(
    pyz, a.scripts, [],
    exclude_binaries=True,
    name="TickReplay",
    console=False,          # no black command window
    icon="assets/icon.ico",
)
coll = COLLECT(exe, a.binaries, a.datas, name="TickReplay")
