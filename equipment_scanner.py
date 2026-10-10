"""
장비 성장 모달 기반 장비 티어 스캐너 (초안).

메인 화면 장비 아이콘 OCR 인식률이 낮아, UI를 직접 조작해
'장비 성장' 모달과 '애용품 정보' 팝업에서 티어를 판독한다.

계층 구조 (위에서 아래로 읽으면 흐름이 보이도록 배치):
    EquipmentScanWorkflow   절차 오케스트레이션 + 슬롯 단위 예외 격리
    EquipmentMenuNavigator  UI 조작 전담 (클릭, 조건 대기, 팝업 닫기) - 판독 안 함
    EquipmentScreenReader   데이터 추출 전담 (크롭, OCR, 화면 상태 판정) - 클릭 안 함
    GameScreen / OcrEngine  저수준 I/O (캡처·클릭 / RapidOCR 래핑)
    parse_* / crop_* 함수   순수 함수 (단위 테스트 대상)

단독 실행:
    py equipment_scanner.py
    학생 기본 정보 화면에서 F8 = 스캔 시작, 스캔 중 F9 = 비상 정지
"""
from __future__ import annotations

import datetime
import json
import logging
import os
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from typing import Callable, Iterator, Optional

import cv2
import numpy as np
import pyautogui

from ocr_audit import NullAuditRecorder, OcrAuditRecorder

logger = logging.getLogger("equipment_scanner")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
TUNING_PATH = os.path.join(BASE_DIR, "config", "equipment_tuning.json")
LOG_FILE_PATH = os.path.join(BASE_DIR, "logs", "equipment_scanner.log")
FAILED_CROP_DIR = os.path.join(BASE_DIR, "logs", "equipment_fail")
REVIEW_CROP_DIR = os.path.join(BASE_DIR, "logs", "equipment_review")

REGULAR_SLOT_INDICES = (1, 2, 3)
FAVORITE_SLOT_INDEX = 4
MAX_REGULAR_TIER = 10
MAX_FAVORITE_TIER = 2
MAX_EQUIPMENT_LEVEL = 99
MAX_T1_LEVEL = 10
CONTENT_SIZE = (1920, 1080)

# 블루아카이브 장비 티어별 최대 레벨 매핑
TIER_MAX_LEVEL = {
    1: 10,
    2: 20,
    3: 30,
    4: 40,
    5: 45,
    6: 50,
    7: 55,
    8: 60,
    9: 65,
    10: 70,
}

Point = tuple[float, float]
Region = tuple[float, float, float, float]


# ============================================================================
# 예외
# ============================================================================
class EquipmentScanError(Exception):
    """슬롯/팝업 단위로 복구 가능한 스캔 실패."""


class ExpectedUiNotFound(EquipmentScanError):
    """클릭 후 기대한 화면(모달, 팝업, 패널 갱신)이 나타나지 않음."""


class TierNotRecognized(EquipmentScanError):
    """티어 뱃지 OCR 판독 실패."""


class ScanAborted(BaseException):
    """사용자 비상 정지(F9 / pyautogui fail-safe).

    BaseException 상속: 슬롯 단위 `except Exception` 에 삼켜지지 않고 즉시 전파된다.
    """


# ============================================================================
# 결과 DTO
# ============================================================================
@dataclass
class TierReading:
    tier: int
    level: Optional[int]
    raw_text: str
    crop_path: Optional[str] = None


@dataclass
class SlotScanResult:
    slot_index: int
    tier: Optional[int] = None
    level: Optional[int] = None
    raw_text: str = ""
    error: Optional[str] = None
    crop_path: Optional[str] = None

    @property
    def succeeded(self) -> bool:
        return self.error is None and self.tier is not None


class FavoriteStatus:
    EQUIPPED = "EQUIPPED"
    EMPTY = "EMPTY"
    FAILED = "FAILED"
    NOT_SCANNED = "NOT_SCANNED"


@dataclass
class FavoriteScanResult:
    status: str = FavoriteStatus.NOT_SCANNED
    tier: Optional[int] = None
    raw_text: str = ""
    error: Optional[str] = None
    crop_path: Optional[str] = None


@dataclass
class EquipmentScanResult:
    slots: list[SlotScanResult] = field(default_factory=list)
    favorite: FavoriteScanResult = field(default_factory=FavoriteScanResult)
    menu_error: Optional[str] = None
    return_error: Optional[str] = None

    @property
    def needs_review(self) -> bool:
        favorite_unresolved = self.favorite.status in (FavoriteStatus.FAILED, FavoriteStatus.NOT_SCANNED)
        any_slot_failed = len(self.slots) < len(REGULAR_SLOT_INDICES) or not all(s.succeeded for s in self.slots)
        return bool(self.menu_error) or any_slot_failed or favorite_unresolved

    def to_extractor_format(self) -> dict:
        equipment = {
            f"slot{slot.slot_index}": {"tier": slot.tier, "level": slot.level or 0, "crop": slot.crop_path}
            for slot in self.slots if slot.succeeded
        }
        if self.favorite.status == FavoriteStatus.EQUIPPED:
            equipment[f"slot{FAVORITE_SLOT_INDEX}"] = {"tier": self.favorite.tier, "level": 0, "crop": self.favorite.crop_path}
        elif self.favorite.status == FavoriteStatus.EMPTY:
            equipment[f"slot{FAVORITE_SLOT_INDEX}"] = {"tier": 0, "level": 0}
        return equipment

    def to_dict(self) -> dict:
        return {**asdict(self), "needs_review": self.needs_review}


# ============================================================================
# 1) 워크플로우 - 절차 오케스트레이션
# ============================================================================
class EquipmentScanWorkflow:
    """장비 스캔 절차. 각 단계 실패를 격리해 다음 슬롯/다음 학생으로 넘어간다."""

    def __init__(self, navigator: "EquipmentMenuNavigator", reader: "EquipmentScreenReader"):
        self._navigator = navigator
        self._reader = reader

    def run(self) -> EquipmentScanResult:
        logger.info("========== 장비 스캔 시작 ==========")
        result = EquipmentScanResult()
        if self._enter_equipment_menu(result):
            result.slots = [self.scan_equipment_slot(index) for index in REGULAR_SLOT_INDICES]
            self._return_to_main_screen(result)
            
        if not result.return_error:
            result.favorite = self.handle_favorite_item()
        else:
            result.favorite = FavoriteScanResult(FavoriteStatus.FAILED, error="장비 모달 닫기 실패로 팝업 스캔 스킵")
            
        _log_summary(result)
        return result

    def scan_equipment_slot(self, slot_index: int) -> SlotScanResult:
        context = f"[슬롯 {slot_index}/{len(REGULAR_SLOT_INDICES)}]"
        logger.info("%s 클릭 -> 상세 패널 갱신 대기", context)
        try:
            frame = self._navigator.select_slot(slot_index)
            reading = self._reader.read_slot_tier(frame, slot_index)
        except Exception as error:
            _log_recoverable_failure(context, error)
            return SlotScanResult(slot_index, error=str(error))
        logger.info("%s [OK] T%d / Lv.%s (OCR=%r)", context, reading.tier, reading.level or "?", reading.raw_text)
        return SlotScanResult(slot_index, reading.tier, reading.level, reading.raw_text, crop_path=reading.crop_path)

    def handle_favorite_item(self) -> FavoriteScanResult:
        context = "[애용품]"
        logger.info("%s 4번 슬롯 클릭 -> 팝업 감지 대기", context)
        try:
            popup_opened = self._navigator.open_favorite_popup()
        except Exception as error:
            _log_recoverable_failure(context, error)
            return FavoriteScanResult(FavoriteStatus.FAILED, error=str(error))
        if not popup_opened:
            logger.info("%s 팝업 없음 -> 미착용/미보유(EMPTY)로 간주, 스킵", context)
            return FavoriteScanResult(FavoriteStatus.EMPTY)
        logger.info("%s [OK] '애용품 정보' 팝업 감지", context)
        return self._read_favorite_then_close(context)

    def _enter_equipment_menu(self, result: EquipmentScanResult) -> bool:
        try:
            self._navigator.open_equipment_menu()
            return True
        except Exception as error:
            _log_recoverable_failure("[메뉴] 진입 실패 -> 이 학생 장비 스캔 스킵:", error)
            result.menu_error = str(error)
            return False

    def _read_favorite_then_close(self, context: str) -> FavoriteScanResult:
        favorite = self._read_favorite_tier(context)
        try:
            self._navigator.close_favorite_popup()
        except Exception as error:
            _log_recoverable_failure(f"{context} 팝업 닫기", error)
        return favorite

    def _read_favorite_tier(self, context: str) -> FavoriteScanResult:
        try:
            reading = self._reader.read_favorite_tier(self._navigator.current_frame())
        except Exception as error:
            _log_recoverable_failure(context, error)
            return FavoriteScanResult(FavoriteStatus.FAILED, error=str(error))
        logger.info("%s [OK] T%d 판별 (OCR=%r)", context, reading.tier, reading.raw_text)
        return FavoriteScanResult(FavoriteStatus.EQUIPPED, reading.tier, reading.raw_text, crop_path=reading.crop_path)

    def _return_to_main_screen(self, result: EquipmentScanResult) -> None:
        try:
            self._navigator.close_equipment_menu()
        except Exception as error:
            _log_recoverable_failure("[복귀]", error)
            result.return_error = str(error)


def _log_recoverable_failure(context: str, error: Exception) -> None:
    """예상된 실패는 한 줄 경고, 예상 못 한 실패는 스택 트레이스까지 남긴다. except 블록 안에서 호출할 것."""
    if isinstance(error, EquipmentScanError):
        logger.warning("%s [FAIL] %s", context, error)
    else:
        logger.exception("%s [FAIL] 예기치 못한 오류: %r", context, error)


def _log_summary(result: EquipmentScanResult) -> None:
    slot_text = " ".join(
        f"슬롯{s.slot_index}={'T%d' % s.tier if s.succeeded else 'FAIL'}" for s in result.slots
    ) or "슬롯=미스캔"
    favorite = result.favorite
    favorite_text = f"T{favorite.tier}" if favorite.status == FavoriteStatus.EQUIPPED else favorite.status
    logger.info("========== 장비 스캔 종료: %s 애용품=%s needs_review=%s ==========",
                slot_text, favorite_text, result.needs_review)


# ============================================================================
# 2) UI 조작 - 클릭 / 대기 / 닫기
# ============================================================================
class EquipmentMenuNavigator:
    """UI 조작 전담. 화면 상태 판정은 reader 에 위임하고, 티어 값은 다루지 않는다."""

    DEFAULT_SELECTED_SLOT = 1

    def __init__(self, screen: "GameScreen", reader: "EquipmentScreenReader", layout: "UiLayout",
                 should_abort: Callable[[], bool]):
        self._screen = screen
        self._reader = reader
        self._layout = layout
        self._should_abort = should_abort

    def open_equipment_menu(self) -> None:
        frame = self._screen.capture()
        if self._reader.is_equipment_menu_open(frame):
            logger.info("[메뉴] 장비 성장 모달이 이미 열려 있음")
            return
        self._screen.click(self._find_equipment_button(frame))
        self._wait_for(self._reader.is_equipment_menu_open, "menu_open_timeout_sec", "장비 성장 모달")
        self._sleep(1.5)
        logger.info("[메뉴] [OK] 장비 성장 모달 진입 확인")

    def select_slot(self, slot_index: int) -> np.ndarray:
        """슬롯 클릭 후 1.5초 대기하여 프레임을 반환한다."""
        self._screen.click(self._layout.point(f"slot_{slot_index}"))
        self._sleep(1.5)
        frame = self._screen.capture()
        if not self._reader.is_equipment_menu_open(frame):
            logger.warning("[슬롯 %d] 클릭 후 장비 성장 모달 미검출 -> 재오픈 시도", slot_index)
            self.open_equipment_menu()
            frame = self._screen.capture()
        return frame

    def open_favorite_popup(self) -> bool:
        """메인 화면에서 4번 슬롯 클릭. 1.5초 대기 후 화면 변화로 팝업 감지."""
        before = self._screen.capture()
        self._screen.click(self._layout.point("main_slot_4"))
        self._sleep(1.5)
        after = self._screen.capture()
        
        if self._reader.has_region_changed(before, after, "popup_detect_area"):
            logger.info("[애용품] 팝업 화면 변화 감지")
            return True
            
        logger.info("[애용품] 화면 변화 없음 -> 팝업 없음(미착용)")
        return False

    def close_favorite_popup(self) -> None:
        self._screen.press_key("esc")
        self._sleep(1.5)

    def close_equipment_menu(self) -> None:
        if not self._reader.is_equipment_menu_open(self._screen.capture()):
            logger.info("[복귀] 장비 성장 모달 없음 -> 이미 메인 화면")
            return
        self._close_with_fallback("equipment_menu_close", "esc", self._reader.is_equipment_menu_open, "장비 성장 모달")
        self._sleep(1.5)

    def current_frame(self) -> np.ndarray:
        return self._screen.capture()

    # --- 내부 헬퍼 -----------------------------------------------------------
    def _find_equipment_button(self, frame: np.ndarray) -> Point:
        located = self._reader.locate_equipment_button(frame)
        if located is not None:
            logger.info("[메뉴] '장비 성장' 버튼 OCR 탐지 -> (%.3f, %.3f) 클릭", *located)
            return located
        fallback = self._layout.point("equipment_button")
        logger.warning("[메뉴] '장비 성장' 버튼 OCR 탐지 실패 -> 기본 좌표 (%.3f, %.3f) 클릭", *fallback)
        return fallback

    def _click_and_settle(self, point_name: str, region_name: str) -> np.ndarray:
        self._screen.click(self._layout.point(point_name))
        return self._sleep(1.5)

    def _close_with_fallback(self, close_point: str, fallback_key: str,
                             is_open: Callable[[np.ndarray], bool], ui_name: str) -> None:
        self._screen.click(self._layout.point(close_point))
        if self._wait_for_absence(is_open):
            logger.info("[닫기] %s 닫힘 (X 버튼)", ui_name)
            return
        logger.warning("[닫기] X 클릭으로 %s 안 닫힘 -> '%s' 키 재시도", ui_name, fallback_key)
        self._screen.press_key(fallback_key)
        if not self._wait_for_absence(is_open):
            raise ExpectedUiNotFound(f"{ui_name} 닫기 실패 (화면={save_failed_crop(self._screen.capture(), 'close_failed')})")
        logger.info("[닫기] %s 닫힘 ('%s' 키)", ui_name, fallback_key)

    def _wait_for(self, predicate: Callable[[np.ndarray], bool], timeout_key: str, ui_name: str) -> np.ndarray:
        found, frame = self._poll(predicate, timeout_key)
        if not found:
            timeout = self._layout.timing[timeout_key]
            raise ExpectedUiNotFound(f"{ui_name} 미검출 ({timeout}s 초과, 화면={save_failed_crop(frame, 'missing_ui')})")
        return frame

    def _wait_for_absence(self, predicate: Callable[[np.ndarray], bool]) -> bool:
        closed, _ = self._poll(lambda frame: not predicate(frame), "close_timeout_sec")
        return closed

    def _poll(self, predicate: Callable[[np.ndarray], bool], timeout_key: str) -> tuple[bool, np.ndarray]:
        """조건 기반 대기: 고정 sleep 대신 조건이 참이 될 때까지 캡처-판정을 반복한다."""
        deadline = time.monotonic() + self._layout.timing[timeout_key]
        frame = self._screen.capture()
        while not predicate(frame):
            if time.monotonic() >= deadline:
                return False, frame
            self._sleep(self._layout.timing["poll_interval_sec"])
            frame = self._screen.capture()
        return True, frame

    def _wait_until_stable(self, region_name: str) -> np.ndarray:
        """전환 애니메이션 대기: 최소 대기 후, 연속 두 프레임이 같아질 때까지 폴링한다."""
        timing = self._layout.timing
        self._sleep(timing["min_settle_sec"])
        deadline = time.monotonic() + timing["stable_timeout_sec"]
        previous = self._screen.capture()
        while time.monotonic() < deadline:
            self._sleep(timing["poll_interval_sec"])
            current = self._screen.capture()
            if self._reader.is_region_stable(previous, current, region_name):
                return current
            previous = current
        logger.warning("[대기] '%s' 영역이 %.1fs 내 안정화 안 됨 -> 마지막 프레임 사용", region_name, timing["stable_timeout_sec"])
        return previous

    def _sleep(self, seconds: float) -> None:
        if self._should_abort():
            raise ScanAborted("F9 비상 정지 감지")
        time.sleep(seconds)


# ============================================================================
# 3) 데이터 추출 - 크롭 / OCR / 상태 판정
# ============================================================================
class EquipmentScreenReader:
    """프레임을 읽기만 한다. 클릭·대기는 하지 않는다."""

    MENU_TITLE_KEYWORDS = ("장비", "성장")
    EQUIPMENT_BUTTON_KEYWORD = "성장"

    def __init__(self, layout: "UiLayout", ocr: "OcrEngine", audit: Optional[Any] = None):
        self._layout = layout
        self._ocr = ocr
        self._audit = audit if audit is not None else NullAuditRecorder()

    def is_equipment_menu_open(self, frame: np.ndarray) -> bool:
        return self._title_contains(frame, "equipment_menu_title", self.MENU_TITLE_KEYWORDS)

    def has_region_changed(self, before: np.ndarray, after: np.ndarray, region_name: str) -> bool:
        return self._region_diff(before, after, region_name) >= self._layout.thresholds["changed_mean_diff"]

    def is_region_stable(self, previous: np.ndarray, current: np.ndarray, region_name: str) -> bool:
        return self._region_diff(previous, current, region_name) < self._layout.thresholds["stable_mean_diff"]

    def locate_equipment_button(self, frame: np.ndarray) -> Optional[Point]:
        region = self._layout.region("equipment_button_search")
        crop = crop_region(frame, region)
        for box, text in self._ocr.find_korean_text(crop):
            if self.EQUIPMENT_BUTTON_KEYWORD in text.replace(" ", ""):
                return box_center_to_frame_point(box, crop.shape, region)
        return None

    def read_slot_tier(self, frame: np.ndarray, slot_idx: int) -> TierReading:
        tag = f"slot{slot_idx}"
        # 1. 통합 배지 영역 (티어 배지 + 레벨 텍스트 동시 판독 / T1 자동 추론)
        unified = self._read_slot_unified(frame, slot_idx, tag)
        if unified is not None:
            return unified

        # 2. 개별 영역 (detail_tier_badge + detail_level)
        try:
            tier, raw_text, crop_path = self._read_tier(frame, "detail_tier_badge", MAX_REGULAR_TIER, tag)
            level = self._read_level(frame, slot_idx)
            return TierReading(tier, level, raw_text, crop_path)
        except TierNotRecognized as error:
            # 3. 최후 수단: 모달 좌측 레일 슬롯 아이콘(slot_1..3)에서 판독
            rail_reading = self._read_slot_from_rail(frame, slot_idx, tag)
            if rail_reading is not None:
                logger.info("[슬롯 %d] 좌측 레일 아이콘에서 T%d / Lv.%s 판독 성공",
                            slot_idx, rail_reading.tier, rail_reading.level or "?")
                return rail_reading
            raise error

    def _read_slot_unified(self, frame: np.ndarray, slot_idx: int, tag: str) -> Optional[TierReading]:
        """티어 배지와 레벨 영역을 포괄하는 통합 영역 판독. T1(배지 없이 Lv.만 표기)도 정상 처리."""
        region = self._get_unified_slot_region()
        crop = crop_region(frame, region)
        candidates = list(self._ocr.iter_line_candidates(crop))
        if not candidates:
            return None

        found_tier: Optional[int] = None
        found_tier_text: str = ""
        found_level: Optional[int] = None

        for text in candidates:
            if found_tier is None:
                t = parse_tier_text(text, MAX_REGULAR_TIER)
                if t is not None:
                    found_tier = t
                    found_tier_text = text
            if found_level is None:
                lvl = parse_level_text(text)
                if lvl is not None:
                    found_level = lvl

        # 티어와 레벨 둘 다 없으면 개별 폴백으로 넘김
        if found_tier is None and found_level is None:
            return None

        note = ""
        # 블루아카이브 규칙: T-배지 없이 Lv.1~10만 존재하는 장비는 T1
        if found_tier is None and found_level is not None and found_level <= MAX_T1_LEVEL:
            found_tier = 1
            found_tier_text = f"Lv.{found_level}"
            note = "T1_INFERRED_FROM_LEVEL"

        # 티어는 잡혔으나 레벨이 미검출된 경우 개별 영역 시도
        if found_tier is not None and found_level is None:
            found_level = self._read_level(frame, slot_idx)

        if found_tier is not None:
            crop_path = save_crop_for_review(crop, tag)
            self._audit.record(f"{tag}.tier", "detail_item_badge", crop, candidates, found_tier, "OK", note=note)
            if found_level is not None:
                self._audit.record(f"{tag}.level", "detail_item_badge", crop, candidates, found_level, "OK", note=note)
            return TierReading(found_tier, found_level, found_tier_text, crop_path)

        return None

    def _read_slot_from_rail(self, frame: np.ndarray, slot_idx: int, tag: str) -> Optional[TierReading]:
        """모달 좌측 레일 슬롯 아이콘을 크롭하여 티어/레벨 판독."""
        try:
            sx, sy = self._layout.point(f"slot_{slot_idx}")
        except Exception:
            return None

        rail_region = (max(0.0, sx - 0.047), max(0.0, sy - 0.055), 0.095, 0.110)
        crop = crop_region(frame, rail_region)
        candidates = list(self._ocr.iter_line_candidates(crop))
        if not candidates:
            return None

        found_tier: Optional[int] = None
        found_tier_text: str = ""
        found_level: Optional[int] = None

        for text in candidates:
            if found_tier is None:
                t = parse_tier_text(text, MAX_REGULAR_TIER)
                if t is not None:
                    found_tier = t
                    found_tier_text = text
            if found_level is None:
                lvl = parse_level_text(text)
                if lvl is not None:
                    found_level = lvl

        if found_tier is None and found_level is not None and found_level <= MAX_T1_LEVEL:
            found_tier = 1
            found_tier_text = f"Lv.{found_level}"

        if found_tier is not None:
            crop_path = save_crop_for_review(crop, tag)
            self._audit.record(f"{tag}.tier", f"rail_slot_{slot_idx}", crop, candidates, found_tier, "OK", note="READ_FROM_LEFT_RAIL")
            if found_level is not None:
                self._audit.record(f"{tag}.level", f"rail_slot_{slot_idx}", crop, candidates, found_level, "OK", note="READ_FROM_LEFT_RAIL")
            return TierReading(found_tier, found_level, found_tier_text, crop_path)

        return None

    def _get_unified_slot_region(self) -> Region:
        try:
            return self._layout.region("detail_item_badge")
        except KeyError:
            pass
        try:
            t_reg = self._layout.region("detail_tier_badge")
            l_reg = self._layout.region("detail_level")
            min_x = min(t_reg[0], l_reg[0])
            max_x = max(t_reg[0] + t_reg[2], l_reg[0] + l_reg[2])
            min_y = min(t_reg[1], l_reg[1], 0.320)
            max_y = max(t_reg[1] + t_reg[3], l_reg[1] + l_reg[3], 0.425)
            return (min_x, min_y, max_x - min_x, max_y - min_y)
        except Exception:
            return (0.255, 0.320, 0.180, 0.110)

    def read_favorite_tier(self, frame: np.ndarray) -> TierReading:
        tier, raw_text, crop_path = self._read_tier(frame, "favorite_tier_badge", MAX_FAVORITE_TIER, "slot4")
        return TierReading(tier, None, raw_text, crop_path)

    def _read_tier(self, frame: np.ndarray, region_name: str, max_tier: int, tag: str) -> tuple[int, str, Optional[str]]:
        crop = crop_region(frame, self._layout.region(region_name))
        crop_path = save_crop_for_review(crop, tag)
        candidates = []
        found_tier: Optional[int] = None
        found_text: str = ""
        for text in self._ocr.iter_line_candidates(crop):
            candidates.append(text)
            tier = parse_tier_text(text, max_tier)
            if tier is not None and found_tier is None:
                found_tier = tier
                found_text = text

        if found_tier is not None:
            self._audit.record(f"{tag}.tier", region_name, crop, candidates, found_tier, "OK")
            return found_tier, found_text, crop_path

        self._audit.record(f"{tag}.tier", region_name, crop, candidates, None, "PARSE_FAIL")
        raise TierNotRecognized(
            f"{region_name} 판독 실패 (OCR 후보={candidates}, 크롭={save_failed_crop(crop, region_name)})"
        )

    def _read_level(self, frame: np.ndarray, slot_idx: int = 1) -> Optional[int]:
        crop = crop_region(frame, self._layout.region("detail_level"))
        candidates = []
        found_level: Optional[int] = None
        for text in self._ocr.iter_line_candidates(crop):
            candidates.append(text)
            level = parse_level_text(text)
            if level is not None and found_level is None:
                found_level = level

        if found_level is not None:
            self._audit.record(f"slot{slot_idx}.level", "detail_level", crop, candidates, found_level, "OK")
            return found_level

        self._audit.record(f"slot{slot_idx}.level", "detail_level", crop, candidates, None, "PARSE_FAIL")
        logger.warning(
            "[레벨] 판독 실패 -> 티어만 사용 (OCR 후보=%s, 크롭=%s)",
            candidates,
            save_failed_crop(crop, "detail_level"),
        )
        return None

    def _title_contains(self, frame: np.ndarray, region_name: str, keywords: tuple[str, ...]) -> bool:
        text = self._ocr.read_korean_line(crop_region(frame, self._layout.region(region_name)))
        return contains_any(text, keywords)

    def _region_diff(self, a: np.ndarray, b: np.ndarray, region_name: str) -> float:
        region = self._layout.region(region_name)
        return mean_abs_diff(crop_region(a, region), crop_region(b, region))


# ============================================================================
# 4) 저수준 I/O - 화면 / OCR / 레이아웃
# ============================================================================
class GameScreen:
    """게임 화면 캡처·클릭. 좌표는 16:9 콘텐츠 영역 기준 상대값으로 주고받는다."""

    def __init__(self, grabber, monitor: dict, click_hold_sec: float):
        self._grabber = grabber
        self._content_box = centered_16_9_box(monitor)
        self._click_hold_sec = click_hold_sec
        logger.debug("콘텐츠 영역: %s", self._content_box)

    def capture(self) -> np.ndarray:
        frame = cv2.cvtColor(np.array(self._grabber.grab(self._content_box)), cv2.COLOR_BGRA2BGR)
        if (frame.shape[1], frame.shape[0]) == CONTENT_SIZE:
            return frame
        return cv2.resize(frame, CONTENT_SIZE, interpolation=cv2.INTER_AREA)

    def click(self, point: Point) -> None:
        x, y = self._to_screen(point)
        logger.debug("click rel=(%.3f, %.3f) -> abs=(%d, %d)", point[0], point[1], x, y)
        try:
            pyautogui.mouseDown(x=x, y=y)
            time.sleep(self._click_hold_sec)
            pyautogui.mouseUp(x=x, y=y)
        except pyautogui.FailSafeException as error:
            raise ScanAborted("pyautogui fail-safe (마우스 화면 모서리)") from error

    def press_key(self, key: str) -> None:
        logger.debug("key press: %s", key)
        pyautogui.press(key)

    def _to_screen(self, point: Point) -> tuple[int, int]:
        box = self._content_box
        return box["left"] + round(point[0] * box["width"]), box["top"] + round(point[1] * box["height"])


class OcrEngine:
    """RapidOCR 래퍼. 전처리 변형을 순서대로 시도하며 후보 문자열을 내놓는다."""

    def __init__(self, korean_reader, english_reader):
        self._korean = korean_reader
        self._english = english_reader

    def read_korean_line(self, crop: np.ndarray) -> str:
        return self._recognize(self._korean, upscale(crop))

    def iter_line_candidates(self, crop: np.ndarray) -> Iterator[str]:
        for _, text in self.find_english_text(crop):
            t = text.strip()
            if t:
                yield t
        for variant in preprocess_variants(crop):
            text = self._recognize(self._english, variant)
            if text:
                yield text

    def find_english_text(self, crop: np.ndarray) -> list[tuple[list, str]]:
        result, _ = self._english(crop)
        return [(box, text) for box, text, _confidence in (result or [])]

    def find_korean_text(self, crop: np.ndarray) -> list[tuple[list, str]]:
        result, _ = self._korean(crop)
        return [(box, text) for box, text, _confidence in (result or [])]

    @staticmethod
    def _recognize(reader, image: np.ndarray) -> str:
        result, _ = reader.text_recognizer([image])
        return result[0][0].strip() if result else ""


@dataclass(frozen=True)
class UiLayout:
    svc: "core.coordinates.CoordinateService"
    timing: dict[str, float]
    thresholds: dict[str, float]

    @classmethod
    def load(cls, svc: "core.coordinates.CoordinateService", tuning_path: str = TUNING_PATH) -> "UiLayout":
        with open(tuning_path, encoding="utf-8") as file:
            raw = json.load(file)
        return cls(
            svc=svc,
            timing=raw["timing"],
            thresholds=raw["thresholds"],
        )

    def point(self, name: str) -> Point:
        return self.svc.point(name)

    def region(self, name: str) -> Region:
        return self.svc.region(name)


# ============================================================================
# 5) 순수 함수 - 파싱 / 이미지 유틸
# ============================================================================
_DIGIT_ALIASES = str.maketrans({
    "I": "1", "l": "1", "i": "1", "|": "1",
    "O": "0", "o": "0", "D": "0",
    "Z": "7", "z": "7",
})
_NOISE_PUNCT = str.maketrans("", "", "()[]{}<>'\":;,`~-_")
_TIER_PATTERN = re.compile(r"[Tt]([0-9Ili|OoDZz]{1,2})")
_LEVEL_PATTERN = re.compile(r"[LlI1][Vv][.:,]?([0-9IlOo]{1,2})")


def parse_tier_text(text: str, max_tier: int) -> Optional[int]:
    """'T10', 'TI0', 'T1O', 'T 7', '(I)', '(T5)', 'Tl', 'Lv.1', 'Z' 등 OCR 문자열에서 1..max_tier 범위의 티어를 뽑는다."""
    if not text:
        return None
    cleaned = text.translate(_NOISE_PUNCT).strip()
    if not cleaned:
        return None
    compact = re.sub(r"\s+", "", cleaned)
    match = _TIER_PATTERN.search(compact)
    if match:
        return _longest_valid_tier_prefix(match.group(1), max_tier)
    tier = _to_tier(compact, max_tier)
    if tier is not None:
        return tier
    # 블루아카이브 규칙: T-배지가 없고 Lv.1~10만 표기된 일반 장비는 T1 기본 장비
    if max_tier > MAX_FAVORITE_TIER:
        level = parse_level_text(text)
        if level is not None and level <= MAX_T1_LEVEL:
            return 1
    return None


def parse_level_text(text: str) -> Optional[int]:
    if not text:
        return None
    match = _LEVEL_PATTERN.search(re.sub(r"\s+", "", text))
    if not match:
        return None
    digits = match.group(1).translate(_DIGIT_ALIASES)
    level = int(digits) if digits.isdigit() else 0
    return level if 1 <= level <= MAX_EQUIPMENT_LEVEL else None


def _longest_valid_tier_prefix(token: str, max_tier: int) -> Optional[int]:
    for end in range(len(token), 0, -1):
        tier = _to_tier(token[:end], max_tier)
        if tier is not None:
            return tier
    return None


def _to_tier(token: str, max_tier: int) -> Optional[int]:
    digits = token.translate(_DIGIT_ALIASES)
    if not digits.isdigit():
        return None
    value = int(digits)
    return value if 1 <= value <= max_tier else None


def contains_any(text: str, keywords: tuple[str, ...]) -> bool:
    compact = text.replace(" ", "")
    return any(keyword in compact for keyword in keywords)


def crop_region(frame: np.ndarray, region: Region) -> np.ndarray:
    height, width = frame.shape[:2]
    x, y, w, h = region
    return frame[int(y * height):int((y + h) * height), int(x * width):int((x + w) * width)]


def mean_abs_diff(a: np.ndarray, b: np.ndarray) -> float:
    gray_a = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    gray_b = cv2.cvtColor(b, cv2.COLOR_BGR2GRAY)
    return float(np.mean(cv2.absdiff(gray_a, gray_b)))


def box_center_to_frame_point(box: list, crop_shape: tuple, region: Region) -> Point:
    crop_height, crop_width = crop_shape[:2]
    center_x = sum(p[0] for p in box) / len(box) / crop_width
    center_y = sum(p[1] for p in box) / len(box) / crop_height
    x, y, w, h = region
    return x + center_x * w, y + center_y * h


def centered_16_9_box(monitor: dict) -> dict:
    """와이드/세로 모니터에서 중앙 16:9 영역만 잘라낸다 (모달은 화면 중앙 기준으로 배치됨)."""
    left, top, width, height = monitor["left"], monitor["top"], monitor["width"], monitor["height"]
    target_ratio = 16 / 9
    if width / height > target_ratio:
        content_width = round(height * target_ratio)
        left, width = left + (width - content_width) // 2, content_width
    elif width / height < target_ratio:
        content_height = round(width / target_ratio)
        top, height = top + (height - content_height) // 2, content_height
    return {"left": left, "top": top, "width": width, "height": height}


def upscale(image: np.ndarray, factor: int = 3) -> np.ndarray:
    return cv2.resize(image, None, fx=factor, fy=factor, interpolation=cv2.INTER_CUBIC)


def preprocess_variants(crop: np.ndarray) -> Iterator[np.ndarray]:
    """원본 확대 -> 대비 강화 그레이 -> Otsu 이진화 순. 앞 단계에서 판독되면 뒤는 생략된다."""
    scaled = upscale(crop)
    yield scaled
    gray = cv2.cvtColor(scaled, cv2.COLOR_BGR2GRAY)
    yield cv2.cvtColor(cv2.convertScaleAbs(gray, alpha=1.5, beta=0), cv2.COLOR_GRAY2BGR)
    _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    yield cv2.cvtColor(binary, cv2.COLOR_GRAY2BGR)


def save_failed_crop(image: np.ndarray, tag: str) -> str:
    """판독 실패 증거 보존 (사후 원인 분석용). 저장 실패해도 스캔은 계속된다."""
    try:
        return _write_timestamped_png(image, FAILED_CROP_DIR, tag)
    except Exception as error:
        return f"<저장 실패: {error!r}>"


def save_crop_for_review(image: np.ndarray, tag: str) -> Optional[str]:
    """GUI 검수 화면용 크롭 저장. 실패 시 None (크롭 미표시) - 스캔은 계속된다."""
    try:
        return _write_timestamped_png(image, REVIEW_CROP_DIR, tag)
    except Exception:
        logger.warning("[크롭] 리뷰 크롭 저장 실패 (tag=%s)", tag, exc_info=True)
        return None


def _write_timestamped_png(image: np.ndarray, directory: str, tag: str) -> str:
    os.makedirs(directory, exist_ok=True)
    stamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    path = os.path.join(directory, f"{tag}_{stamp}.png")
    cv2.imencode(".png", image)[1].tofile(path)
    return path


# ============================================================================
# 조립 / 로깅 / 진입점
# ============================================================================
class _CallbackLogHandler(logging.Handler):
    """GUI 로그창(callback_log) 연동용."""

    def __init__(self, callback: Callable[[str], None]):
        super().__init__()
        self._callback = callback

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._callback(self.format(record))
        except Exception:
            self.handleError(record)


def configure_logging(gui_callback: Optional[Callable[[str], None]] = None,
                      console_level: int = logging.INFO) -> None:
    """터미널(INFO) + 파일(DEBUG) + 선택적 GUI 콜백. 중복 호출해도 핸들러는 한 번만 붙는다."""
    if logger.handlers:
        return
    os.makedirs(os.path.dirname(LOG_FILE_PATH), exist_ok=True)
    formatter = logging.Formatter("%(asctime)s [%(levelname)s] %(message)s", "%H:%M:%S")
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(console_level)
    file_handler = logging.FileHandler(LOG_FILE_PATH, encoding="utf-8")
    file_handler.setLevel(logging.DEBUG)
    handlers: list[logging.Handler] = [console, file_handler]
    if gui_callback:
        handlers.append(_CallbackLogHandler(gui_callback))
    for handler in handlers:
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False


def build_default_workflow(tuning_path: str = TUNING_PATH, audit: Optional[Any] = None) -> EquipmentScanWorkflow:
    """실제 게임 환경용 조립. 무거운 의존성(OCR 모델, 학생 목록 요청)은 여기서만 import 한다.

    주의: mss 인스턴스는 스레드 종속 -> 워크플로우를 실행할 스레드에서 호출할 것.
    """
    import keyboard
    import mss
    import extractor
    from scanner import get_bluearchive_monitor
    from core.coordinates import CoordinateService

    svc = CoordinateService.instance()
    layout = UiLayout.load(svc, tuning_path)
    grabber = mss.mss()
    screen = GameScreen(grabber, get_bluearchive_monitor(grabber), layout.timing["click_hold_sec"])
    audit_recorder = audit if audit is not None else OcrAuditRecorder()
    reader = EquipmentScreenReader(layout, OcrEngine(extractor.reader_ko, extractor.reader_en), audit=audit_recorder)
    navigator = EquipmentMenuNavigator(screen, reader, layout, should_abort=lambda: keyboard.is_pressed("F9"))
    return EquipmentScanWorkflow(navigator, reader)


def main() -> int:
    import keyboard

    configure_logging()
    workflow = build_default_workflow()
    logger.info("학생 기본 정보 화면을 띄운 뒤 [F8] = 장비 스캔 시작 / 스캔 중 [F9] = 비상 정지")
    keyboard.wait("F8")
    try:
        result = workflow.run()
    except ScanAborted as abort:
        logger.warning("[중단] %s", abort)
        return 1
    print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    return 2 if result.needs_review else 0


if __name__ == "__main__":
    sys.exit(main())
