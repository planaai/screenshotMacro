"""
PyInstaller runtime hook: Fix PyTorch DLL loading (WinError 1114) on Windows.
This hook runs BEFORE any application code and pre-loads all torch DLLs
using ctypes.CDLL with explicit paths, bypassing torch's own LoadLibraryExW
approach that fails in frozen environments.
"""
import os
import sys
import ctypes

if sys.platform == 'win32' and getattr(sys, 'frozen', False):
    base = sys._MEIPASS
    torch_lib = os.path.join(base, "torch", "lib")

    if os.path.isdir(torch_lib):
        # 1. Register DLL search directories
        os.environ['PATH'] = torch_lib + os.pathsep + base + os.pathsep + os.environ.get('PATH', '')
        try:
            os.add_dll_directory(torch_lib)
            os.add_dll_directory(base)
        except (OSError, AttributeError):
            pass

        # 2. Pre-load VC runtime DLLs
        for vcrt in ['vcruntime140.dll', 'msvcp140.dll', 'vcruntime140_1.dll', 'MSVCP140_ATOMIC_WAIT.dll', 'VCOMP140.DLL']:
            vcrt_path = os.path.join(base, vcrt)
            if os.path.exists(vcrt_path):
                try:
                    ctypes.CDLL(vcrt_path)
                except OSError:
                    pass

        # 3. Pre-load ALL torch DLLs in the correct dependency order
        load_order = [
            'libiomp5md.dll',
            'libiompstubs5md.dll',
            'uv.dll',
            'c10.dll',
            'torch_global_deps.dll',
            'torch.dll',
            'shm.dll',
            'torch_cpu.dll',
            'torch_python.dll',
        ]
        for dll_name in load_order:
            dll_path = os.path.join(torch_lib, dll_name)
            if os.path.exists(dll_path):
                try:
                    ctypes.CDLL(dll_path)
                except OSError:
                    pass
