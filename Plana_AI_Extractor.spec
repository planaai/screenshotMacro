# -*- mode: python ; coding: utf-8 -*-


a = Analysis(
    ['gui_app.py'],
    pathex=[],
    binaries=[],
    datas=[('assets', 'assets')],
    hiddenimports=['scipy._external.array_api_compat.numpy.fft', 'scipy._external.array_api_compat.numpy.linalg', 'scipy._lib.array_api_compat.numpy.fft', 'scipy._lib.array_api_compat.numpy.linalg', 'scipy.special._cdflib'],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=['pyi_rth_torch_dll_fix.py'],
    excludes=['torchaudio'],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='Plana_AI_Extractor',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=['assets/app_icon.ico'],
)
coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=['c10.dll', 'torch_cpu.dll', 'torch_python.dll', 'asmjit.dll', 'fbgemm.dll'],
    name='Plana_AI_Extractor',
)
