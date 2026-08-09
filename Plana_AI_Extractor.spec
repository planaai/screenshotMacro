# -*- mode: python ; coding: utf-8 -*-
import os
import glob
from PyInstaller.utils.hooks import collect_all

datas = [('assets', 'assets'), ('students.json', '.'), ('models', 'models')]
binaries = []
hiddenimports = [
    'scipy._external.array_api_compat.numpy.fft',
    'scipy._external.array_api_compat.numpy.linalg',
    'scipy._lib.array_api_compat.numpy.fft',
    'scipy._lib.array_api_compat.numpy.linalg',
    'scipy.special._cdflib',
]

# Collect onnxruntime
tmp_ret = collect_all('onnxruntime')
datas += tmp_ret[0]
hiddenimports += tmp_ret[2]

import onnxruntime
ort_capi_dir = os.path.join(os.path.dirname(onnxruntime.__file__), 'capi')
for ext in ('*.dll', '*.pyd'):
    for f in glob.glob(os.path.join(ort_capi_dir, ext)):
        binaries.append((f, '.'))

# Collect rapidocr_onnxruntime
tmp_ret = collect_all('rapidocr_onnxruntime')
datas += tmp_ret[0]
binaries += tmp_ret[1]
hiddenimports += tmp_ret[2]

a = Analysis(
    ['gui_app.py'],
    pathex=[],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
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
    upx_exclude=[],
    name='Plana_AI_Extractor',
)
