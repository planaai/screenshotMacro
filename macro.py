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
    _thread_local = threading.local()

    def __init__(self, callback_done=None, callback_log=None):
        self.is_running = False
        self.is_waiting = False
        self.callback_done = callback_done
        self.callback_log = callback_log
        self.save_dir = os.path.join(os.getcwd(), "macro_screenshots")
        if not os.path.exists(self.save_dir):
            os.makedirs(self.save_dir)

    @property
    def sct(self):
        cur = getattr(self._thread_local, "sct", None)
        if cur is None or getattr(cur, "_closed", False):
            self._thread_local.sct = mss.mss()
        return self._thread_local.sct

    def close_sct(self):
        cur = getattr(self._thread_local, "sct", None)
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass
            self._thread_local.sct = None

    def log(self, msg):
        if self.callback_log:
            self.callback_log(msg)
        else:
            print(msg)

    def get_game_box(self, sct=None):
        import scanner
        import equipment_scanner
        s = sct or self.sct
        monitor = scanner.get_bluearchive_monitor(s)
        return equipment_scanner.centered_16_9_box(monitor)

    def get_fullscreen_image(self, sct=None):
        s = sct or self.sct
        box = self.get_game_box(s)
        sct_img = s.grab(box)
        img = np.array(sct_img)
        return cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)

    def get_name_roi(self, img):
        if img is None or getattr(img, 'size', 0) == 0 or not hasattr(img, 'ndim'):
            return np.zeros((1, 1), dtype=np.uint8)

        if img.ndim not in (2, 3):
            return np.zeros((1, 1), dtype=np.uint8)

        if img.ndim == 3:
            if img.shape[2] == 1:
                img = img[:, :, 0]
            elif img.shape[2] not in (3, 4):
                return np.zeros((1, 1), dtype=np.uint8)

        if getattr(img, 'dtype', None) != np.uint8:
            try:
                img = np.nan_to_num(img, nan=0.0, posinf=255.0, neginf=0.0)
                img = np.clip(img, 0, 255).astype(np.uint8)
            except Exception:
                return np.zeros((1, 1), dtype=np.uint8)

        try:
            if img.ndim == 3 and img.shape[2] == 4:
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            elif img.ndim == 2:
                img = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)
        except Exception:
            return np.zeros((1, 1), dtype=np.uint8)

        try:
            h, w = img.shape[:2]
            if (w, h) not in ((1920, 1080), (2560, 1440)):
                if h != 1080:
                    target_h = 1080
                    new_w = max(1, int(round(w * target_h / h)))
                    img = cv2.resize(img, (new_w, target_h), interpolation=cv2.INTER_AREA if h > target_h else cv2.INTER_LINEAR)
                img_resized = extractor.preprocess_image(img)
            else:
                img_resized = img
        except Exception:
            return np.zeros((1, 1), dtype=np.uint8)

        if img_resized is None or getattr(img_resized, 'size', 0) == 0 or getattr(img_resized, 'ndim', 0) < 2:
            return np.zeros((1, 1), dtype=np.uint8)

        h_res, w_res = img_resized.shape[:2]
        try:
            from core.coordinates import CoordinateService
            x, y, w, h = CoordinateService.instance().region_px("macro_name_compare", size=(w_res, h_res))
        except Exception:
            return np.zeros((1, 1), dtype=np.uint8)

        x1 = max(0, min(w_res, x))
        y1 = max(0, min(h_res, y))
        x2 = max(0, min(w_res, x + w))
        y2 = max(0, min(h_res, y + h))

        if x2 <= x1 or y2 <= y1:
            return np.zeros((1, 1), dtype=np.uint8)

        roi = img_resized[y1:y2, x1:x2]
        if roi is None or getattr(roi, 'size', 0) == 0:
            return np.zeros((1, 1), dtype=np.uint8)

        try:
            if roi.ndim == 3:
                roi = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
            if getattr(roi, 'dtype', None) != np.uint8:
                roi = roi.astype(np.uint8)
            if roi.ndim != 2 or roi.size == 0:
                return np.zeros((1, 1), dtype=np.uint8)
            return roi
        except Exception:
            return np.zeros((1, 1), dtype=np.uint8)

    def is_same_student(self, img1, img2):
        if img1 is None or img2 is None or getattr(img1, 'size', 0) == 0 or getattr(img2, 'size', 0) == 0:
            return False
        if img1.shape != img2.shape:
            return False
        diff = cv2.absdiff(img1, img2)
        mean_diff = float(np.mean(diff))
        return mean_diff < 5.0

    def start_listener(self):
        if self.is_running or self.is_waiting:
            self.log("이미 매크로 대기 중이거나 실행 중입니다.")
            return

        self.is_waiting = True
        self.log("매크로 대기 모드 진입. 게임 화면을 띄우고 [F8] 키를 누르면 시작됩니다.")
        self.log("비상 정지: [F9]")

        def listener_thread():
            while self.is_waiting:
                if keyboard.is_pressed('F8'):
                    self.is_waiting = False
                    try:
                        self.run_macro()
                    except Exception as e:
                        self.log(f"[오류] 매크로 실행 중 오류 발생: {e}")
                        self.is_running = False
                    break
                if keyboard.is_pressed('F9'):
                    self.is_waiting = False
                    self.log("비상 정지: 대기 모드를 취소합니다.")
                    break
                time.sleep(0.05)

        threading.Thread(target=listener_thread, daemon=True).start()

    def run_macro(self):
        if self.is_running:
            return
        self.is_running = True

        self.log("매크로 시작! 현재 화면 유효성 검증 중...")

        # Clear old macro screenshots
        for f in os.listdir(self.save_dir):
            if f.lower().endswith(('.jpg', '.png')):
                try:
                    os.remove(os.path.join(self.save_dir, f))
                except Exception:
                    pass

        first_img = self.get_fullscreen_image()
        temp_val = os.path.join(self.save_dir, "temp_validate.jpg")
        cv2.imwrite(temp_val, first_img)

        # Validate using extractor
        data = extractor.extract_screenshot_data(temp_val)
        if not data or not data.get("studentName"):
            self.log("[오류] 학생 정보 창을 인식하지 못했습니다!")
            self.log("학생의 상세 정보 창을 연 상태에서 F8을 눌러주세요.")
            self.is_running = False
            return

        first_name_roi = self.get_name_roi(first_img)
        first_name_str = data.get('studentName')
        self.log(f"첫 학생 [{first_name_str}] 확인 완료! 반복 캡처를 시작합니다...")

        box = self.get_game_box()
        from core.coordinates import CoordinateService
        nx, ny = CoordinateService.instance().point("next_student_button")
        next_x = box["left"] + int(round(nx * box["width"]))
        next_y = box["top"] + int(round(ny * box["height"]))

        count = 0
        try:
            while self.is_running:
                # Emergency Stop Check
                if keyboard.is_pressed('F9'):
                    self.log("[정지] [F9] 비상 정지 감지! 캡처를 중단합니다.")
                    break

                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                filename = f"capture_{timestamp}_{count}.jpg"
                filepath = os.path.join(self.save_dir, filename)

                # Capture current
                current_img = self.get_fullscreen_image()
                cv2.imwrite(filepath, current_img)
                count += 1
                self.log(f"캡처 완료: {count}번째 장 저장됨.")

                # ==== NEW: 장비 스캔 워크플로우 ====
                try:
                    import equipment_scanner
                    equipment_scanner.configure_logging(gui_callback=self.log)
                    self.log("장비 상세 스캔 시작...")
                    # 핫 리로드 대응 위해 매번 새로 생성하되 스레드 로컬 sct 재사용
                    self.eq_workflow = equipment_scanner.build_default_workflow(grabber=self.sct)
                    if hasattr(self.eq_workflow._reader, "_audit"):
                        self.eq_workflow._reader._audit.begin_capture(filename)
                    eq_result = self.eq_workflow.run()
                    eq_filepath = filepath.rsplit('.', 1)[0] + "_equip.json"
                    with open(eq_filepath, 'w', encoding='utf-8') as f:
                        import json
                        json.dump(eq_result.to_extractor_format(), f, ensure_ascii=False, indent=2)
                except BaseException as e:
                    if type(e).__name__ == "ScanAborted":
                        self.log("[정지] [F9] 장비 스캔 중 비상 정지 감지! 캡처를 중단합니다.")
                        break
                    self.log(f"[경고] 장비 스캔 중 오류 발생: {e}")
                # ==================================

                # Click next
                pyautogui.mouseDown(x=next_x, y=next_y)
                time.sleep(0.15)
                pyautogui.mouseUp(x=next_x, y=next_y)

                # Wait for UI animation to finish by detecting actual screen change
                current_name_roi = self.get_name_roi(current_img)
                changed = False
                for _ in range(30): # wait up to 3 seconds
                    if keyboard.is_pressed('F9'):
                        break
                    time.sleep(0.1)
                    check_img = self.get_fullscreen_image()
                    check_name_roi = self.get_name_roi(check_img)
                    if not self.is_same_student(current_name_roi, check_name_roi):
                        changed = True
                        # Wait an additional 0.5s for the sliding animation to completely settle
                        time.sleep(0.5)
                        break

                if keyboard.is_pressed('F9'):
                    self.log("[정지] [F9] 비상 정지 감지! 캡처를 중단합니다.")
                    break

                if not changed:
                    self.log("[경고] 화면 전환이 지연되었습니다. 재시도합니다...")

                # Check if we looped back to the first student
                new_img = self.get_fullscreen_image()
                new_name_roi = self.get_name_roi(new_img)

                if self.is_same_student(first_name_roi, new_name_roi):
                    self.log(f"처음 학생 [{first_name_str}] 화면으로 돌아왔습니다! 캡처 종료.")
                    break

        except Exception as e:
            self.log(f"매크로 실행 중 오류: {e}")

        finally:
            self.is_running = False
            try:
                os.remove(temp_val)
            except Exception:
                pass
            self.close_sct()

            if count > 0 and self.callback_done:
                self.log("모든 캡처 완료. 일괄 데이터 추출로 넘어갑니다...")
                self.callback_done(self.save_dir)
