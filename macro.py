import os
import time
import threading
import datetime
import cv2
import numpy as np
import mss
import pyautogui
import keyboard
import extractor

class CaptureMacro:
    def __init__(self, callback_done=None, callback_log=None):
        self.is_running = False
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
            
    def get_fullscreen_image(self):
        # Grab primary monitor
        monitor = self.sct.monitors[1]
        sct_img = self.sct.grab(monitor)
        img = np.array(sct_img)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img
        
    def get_name_roi(self, img):
        # Resize to 1920x1080 to match extractor's ROI precisely
        img_resized = cv2.resize(img, (1920, 1080))
        # ROI for student name (matches extractor ROI)
        x, y, w, h = (120, 840, 300, 40)
        roi = img_resized[y:y+h, x:x+w]
        return cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        
    def is_same_student(self, img1, img2):
        # Use simple absolute difference. 
        # If the average pixel difference is very low (< 5), they are identical text areas.
        diff = cv2.absdiff(img1, img2)
        mean_diff = np.mean(diff)
        return mean_diff < 5.0

    def start_listener(self):
        if self.is_running or self.is_waiting:
            self.log("이미 매크로 대기 중이거나 실행 중입니다.")
            return
            
        self.is_waiting = True
        self.log("▶ 매크로 대기 모드 진입. 게임 화면을 띄우고 [F8] 키를 누르면 시작됩니다.")
        self.log("▶ 비상 정지: [F9]")
        
        def listener_thread():
            while self.is_waiting:
                if keyboard.is_pressed('F8'):
                    self.is_waiting = False
                    self.run_macro()
                    break
                if keyboard.is_pressed('F9'):
                    self.is_waiting = False
                    self.log("비상 정지: 대기 모드를 취소합니다.")
                    break
                time.sleep(0.05)
                
        threading.Thread(target=listener_thread, daemon=True).start()
        
    def run_macro(self):
        if self.is_running: return
        self.is_running = True
        
        self.log("매크로 시작! 현재 화면 유효성 검증 중...")
        
        # Clear old macro screenshots
        for f in os.listdir(self.save_dir):
            if f.lower().endswith(('.jpg', '.png')):
                try: os.remove(os.path.join(self.save_dir, f))
                except: pass
        
        first_img = self.get_fullscreen_image()
        temp_val = os.path.join(self.save_dir, "temp_validate.jpg")
        cv2.imwrite(temp_val, first_img)
        
        # Validate using extractor
        data = extractor.extract_screenshot_data(temp_val)
        if not data or not data.get("studentName"):
            self.log("❌ 오류: 학생 정보 창을 인식하지 못했습니다!")
            self.log("학생의 상세 정보 창을 연 상태에서 F8을 눌러주세요.")
            self.is_running = False
            return
            
        first_name_roi = self.get_name_roi(first_img)
        first_name_str = data.get('studentName')
        self.log(f"✅ 첫 학생 [{first_name_str}] 확인 완료! 반복 캡처를 시작합니다...")
        
        screen_w, screen_h = pyautogui.size()
        # The '>' arrow button in Blue Archive student info screen is at the right edge.
        # Based on actual screenshot analysis (2560x1440 capture):
        #   Arrow center at approximately x=97.7% of width, y=47.2% of height
        next_x = int(screen_w * 0.977)
        next_y = int(screen_h * 0.472)
        
        count = 0
        try:
            while self.is_running:
                # Emergency Stop Check
                if keyboard.is_pressed('F9'):
                    self.log("⏹️ [F9] 비상 정지 감지! 캡처를 중단합니다.")
                    break
                    
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                filename = f"capture_{timestamp}_{count}.jpg"
                filepath = os.path.join(self.save_dir, filename)
                
                # Capture current
                current_img = self.get_fullscreen_image()
                cv2.imwrite(filepath, current_img)
                count += 1
                self.log(f"📸 캡처 완료: {count}번째 장 저장됨.")
                
                # Click next
                pyautogui.mouseDown(x=next_x, y=next_y)
                time.sleep(0.15)
                pyautogui.mouseUp(x=next_x, y=next_y)
                
                # Wait for UI animation to finish by detecting actual screen change
                current_name_roi = self.get_name_roi(current_img)
                changed = False
                for _ in range(30): # wait up to 3 seconds
                    if keyboard.is_pressed('F9'): break
                    time.sleep(0.1)
                    check_img = self.get_fullscreen_image()
                    check_name_roi = self.get_name_roi(check_img)
                    if not self.is_same_student(current_name_roi, check_name_roi):
                        changed = True
                        # Wait an additional 0.5s for the sliding animation to completely settle
                        time.sleep(0.5)
                        break
                        
                if keyboard.is_pressed('F9'):
                    self.log("⏹️ [F9] 비상 정지 감지! 캡처를 중단합니다.")
                    break
                    
                if not changed:
                    self.log(f"⚠️ 화면 전환이 지연되었습니다. 재시도합니다...")
                
                # Check if we looped back to the first student
                new_img = self.get_fullscreen_image()
                new_name_roi = self.get_name_roi(new_img)
                
                if self.is_same_student(first_name_roi, new_name_roi):
                    self.log(f"🔄 처음 학생 [{first_name_str}] 화면으로 돌아왔습니다! 캡처 종료.")
                    break
                    
        except Exception as e:
            self.log(f"매크로 실행 중 오류: {e}")
            
        finally:
            self.is_running = False
            try: os.remove(temp_val)
            except: pass
            
            if count > 0 and self.callback_done:
                self.log("모든 캡처 완료. 일괄 데이터 추출로 넘어갑니다...")
                self.callback_done(self.save_dir)
