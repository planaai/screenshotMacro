import os
import time
import threading
import datetime
import cv2
import numpy as np
import mss
import keyboard
import ctypes
from ctypes import wintypes
import extractor

user32 = ctypes.WinDLL('user32')
kernel32 = ctypes.WinDLL('kernel32')
psapi = ctypes.WinDLL('psapi')

PROCESS_QUERY_INFORMATION = 0x0400
PROCESS_VM_READ = 0x0010

EnumWindows = user32.EnumWindows
EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)

def get_bluearchive_monitor(sct):
    target_exe = "bluearchive.exe"
    target_rect = None
    
    def callback(hwnd, lParam):
        nonlocal target_rect
        if not user32.IsWindowVisible(hwnd):
            return True
            
        pid = wintypes.DWORD()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        hProcess = kernel32.OpenProcess(PROCESS_QUERY_INFORMATION | PROCESS_VM_READ, False, pid)
        if hProcess:
            exe_path = ctypes.create_unicode_buffer(260)
            if psapi.GetModuleFileNameExW(hProcess, 0, exe_path, 260):
                exe_name = os.path.basename(exe_path.value).lower()
                if exe_name == target_exe:
                    rect = wintypes.RECT()
                    user32.GetWindowRect(hwnd, ctypes.byref(rect))
                    target_rect = (rect.left, rect.top, rect.right, rect.bottom)
                    kernel32.CloseHandle(hProcess)
                    return False # Stop enumerating
            kernel32.CloseHandle(hProcess)
        return True
        
    EnumWindows(EnumWindowsProc(callback), 0)
    
    # If not found by exe name, fallback to window title containing "BlueArchive"
    if not target_rect:
        def callback_title(hwnd, lParam):
            nonlocal target_rect
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.lower()
                    if "bluearchive" in title or "블루 아카이브" in title or "blue archive" in title:
                        rect = wintypes.RECT()
                        user32.GetWindowRect(hwnd, ctypes.byref(rect))
                        target_rect = (rect.left, rect.top, rect.right, rect.bottom)
                        return False
            return True
        EnumWindows(EnumWindowsProc(callback_title), 0)

    if target_rect:
        x_center = (target_rect[0] + target_rect[2]) // 2
        y_center = (target_rect[1] + target_rect[3]) // 2
        # Find which monitor contains the center of the window
        for i, m in enumerate(sct.monitors[1:], 1): # sct.monitors[0] is all monitors combined
            if m["left"] <= x_center <= m["left"] + m["width"] and m["top"] <= y_center <= m["top"] + m["height"]:
                return m
                
    # fallback to monitor 1
    if len(sct.monitors) > 1:
        return sct.monitors[1]
    return sct.monitors[0]

class ScannerListener:
    def __init__(self, callback_done=None, callback_log=None):
        self.is_waiting = False
        self.callback_done = callback_done
        self.callback_log = callback_log
        self.sct = mss.mss()
        self.save_dir = os.path.join(os.getcwd(), "macro_screenshots")
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)
            
    def log(self, msg):
        if self.callback_log:
            self.callback_log(msg)
        else:
            print(msg)

    def start_listener(self):
        if self.is_waiting:
            self.log("이미 스캐너 모드 대기 중입니다.")
            return
            
        self.is_waiting = True
        self.log("▶ 스캐너 모드 진입. 게임 화면을 띄우고 [F9] 키를 누르면 화면을 캡처하고 검수를 시작합니다.")
        
        def listener_thread():
            while self.is_waiting:
                if keyboard.is_pressed('F9'):
                    self.is_waiting = False
                    self.capture_and_extract()
                    break
                time.sleep(0.05)
                
        threading.Thread(target=listener_thread, daemon=True).start()
        
    def stop_listener(self):
        self.is_waiting = False
        
    def capture_and_extract(self):
        self.log("📸 [F9] 입력 감지! 화면 캡처 중...")
        try:
            monitor = get_bluearchive_monitor(self.sct)
            sct_img = self.sct.grab(monitor)
            img = np.array(sct_img)
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            filename = f"scanner_capture_{timestamp}.jpg"
            filepath = os.path.join(self.save_dir, filename)
            
            cv2.imwrite(filepath, img)
            self.log(f"✅ 캡처 완료! ({filename}) 데이터 추출을 시도합니다...")
            
            # extract_screenshot_data
            data = extractor.extract_screenshot_data(filepath)
            
            result = {
                "path": filepath,
                "data": data if data else {},
                "status": "pending",
                "needs_review": False
            }
            if not data or not data.get("studentName") or data.get("currentLevel") is None:
                result["needs_review"] = True
                
            if self.callback_done:
                self.callback_done(result)
                
        except Exception as e:
            self.log(f"❌ 캡처 및 추출 중 오류 발생: {e}")
            if self.callback_done:
                self.callback_done(None)
