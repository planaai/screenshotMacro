"""OCR 전수 감사(Audit) 및 모니터링 시스템.

모든 OCR 판독 시도(원문 후보, 파싱 결과, 크롭 이미지, 판정 상태)를 영구 기록하고
사후 분석 리포트를 생성할 수 있는 구조화된 JSONL 데이터를 축적한다.
사용자 지침에 따라 감사 로그와 크롭 이미지는 자동 삭제되지 않고 영구 보존된다.
"""
from __future__ import annotations

import datetime
import json
import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Optional

import cv2
import numpy as np

logger = logging.getLogger("equipment_scanner.audit")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DEFAULT_AUDIT_ROOT = os.path.join(BASE_DIR, "logs", "ocr_audit")


@dataclass(frozen=True)
class OcrObservation:
    """단일 OCR 판독 시도 레코드."""
    run_id: str
    timestamp: str
    capture: str
    field: str
    region: str
    candidates: list[str]
    parsed: Optional[int]
    status: str
    crop_path: Optional[str] = None
    note: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


class NullAuditRecorder:
    """테스트 또는 감사 비활성화 시 사용하는 No-op 레코더."""

    def __init__(self) -> None:
        self.run_id: str = "null_run"

    def begin_capture(self, capture: str) -> None:
        pass

    def record(
        self,
        field: str,
        region: str,
        crop: Optional[np.ndarray],
        candidates: list[str],
        parsed: Optional[int],
        status: str,
        note: str = "",
    ) -> OcrObservation:
        stamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        return OcrObservation(
            run_id=self.run_id,
            timestamp=stamp,
            capture="",
            field=field,
            region=region,
            candidates=list(candidates),
            parsed=parsed,
            status=status,
            crop_path=None,
            note=note,
        )


class OcrAuditRecorder:
    """OCR 판독 시도를 JSONL과 크롭 이미지로 영구 보존하는 레코더."""

    def __init__(self, root_dir: str = DEFAULT_AUDIT_ROOT, run_id: Optional[str] = None):
        self.root_dir = root_dir
        self.run_id = run_id or datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        self.run_dir = os.path.join(self.root_dir, self.run_id)
        self.crops_dir = os.path.join(self.run_dir, "crops")
        self.log_file = os.path.join(self.run_dir, "audit.jsonl")
        self._current_capture: str = ""

        try:
            os.makedirs(self.crops_dir, exist_ok=True)
        except Exception as e:
            logger.warning("[감사] 감사 디렉터리 생성 실패: %s", e)

    def begin_capture(self, capture: str) -> None:
        """현재 스캔 중인 캡처 파일명 설정."""
        self._current_capture = os.path.basename(capture)

    def record(
        self,
        field: str,
        region: str,
        crop: Optional[np.ndarray],
        candidates: list[str],
        parsed: Optional[int],
        status: str,
        note: str = "",
    ) -> OcrObservation:
        """단일 OCR 판독 결과 기록 (크롭 저장 + JSONL 추가). 오류 발생 시에도 스캔 중단 방지."""
        stamp_dt = datetime.datetime.now()
        timestamp_str = stamp_dt.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
        crop_path: Optional[str] = None

        if crop is not None and crop.size > 0:
            try:
                stamp_fn = stamp_dt.strftime("%H%M%S_%f")
                safe_field = field.replace(".", "_")
                filename = f"{safe_field}_{stamp_fn}.png"
                crop_path = os.path.join(self.crops_dir, filename)
                cv2.imencode(".png", crop)[1].tofile(crop_path)
            except Exception as e:
                logger.debug("[감사] 크롭 이미지 저장 실패 (%s): %s", field, e)
                crop_path = None

        observation = OcrObservation(
            run_id=self.run_id,
            timestamp=timestamp_str,
            capture=self._current_capture,
            field=field,
            region=region,
            candidates=list(candidates),
            parsed=parsed,
            status=status,
            crop_path=crop_path,
            note=note,
        )

        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(json.dumps(observation.to_dict(), ensure_ascii=False) + "\n")
        except Exception as e:
            logger.debug("[감사] JSONL 기록 실패 (%s): %s", field, e)

        return observation
