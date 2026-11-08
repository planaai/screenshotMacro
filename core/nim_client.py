"""
core/nim_client.py - NVIDIA NIM Vision API Client, Prompt Loader, and Parser.

Provides:
- Dynamic prompt loading with code fence and backtick stripping.
- Robust multimodal Base64 image encoding (NumPy, PIL, file paths, raw bytes).
- 6-stage resilient JSON response parser (handling <think> tags, markdown fences,
  outer braces, and trailing commas).
- Bidirectional schema adapter mapping vision output to Plana_SE UI fields.
- OpenAI-compatible multimodal NIM client with 2048-token reasoning budget
  and secret masking.
"""

from __future__ import annotations

import base64
import io
import json
import logging
import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union

import requests
import numpy as np
from PIL import Image

try:
    from core.masking import mask_api_key, mask_text, set_global_secret_key
except ImportError:
    def mask_api_key(key: str) -> str:
        return "nvapi-****" if str(key).startswith("nvapi-") else "****"

    def mask_text(text: str, secret_key: str = "") -> str:
        return str(text).replace(secret_key, mask_api_key(secret_key)) if secret_key else str(text)

    def set_global_secret_key(key: str) -> None:
        pass

try:
    from core.paths import get_bundle_dir
except ImportError:
    def get_bundle_dir() -> str:
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


logger = logging.getLogger("nim_client")

# Model Constants
DEFAULT_MODEL = "nvidia/nemotron-3.5-super-vl-120b-a12b"
ALT_MODEL = "mistralai/mistral-large-4-1t-a52b"
SUPPORTED_MODELS = (DEFAULT_MODEL, ALT_MODEL)
NIM_ENDPOINT = "https://integrate.api.nvidia.com/v1/chat/completions"
DEFAULT_MAX_TOKENS = 2048
DEFAULT_TEMPERATURE = 0.1
DEFAULT_TIMEOUT = 60.0


# ==============================================================================
# Exceptions
# ==============================================================================

class NimClientError(RuntimeError):
    """Base exception for NVIDIA NIM client errors."""

    def __init__(self, message: str, status_code: Optional[int] = None, response_body: str = "") -> None:
        super().__init__(message)
        self.status_code = status_code
        self.response_body = response_body


class NimAuthenticationError(NimClientError):
    """HTTP 401: Invalid or unauthorized API key."""
    pass


class NimRateLimitError(NimClientError):
    """HTTP 429: NIM API rate limit exceeded."""
    pass


class NimServerError(NimClientError):
    """HTTP 5xx: NIM API internal server error."""
    pass


class NimTimeoutError(NimClientError, TimeoutError):
    """Request to NIM API timed out."""
    pass


class NimParseError(ValueError):
    """Failed to parse LLM response into required schema."""
    pass


# ==============================================================================
# Helper Functions: Prompt Loading & Image Encoding
# ==============================================================================

def _resolve_prompt_path(prompt_path: str) -> str:
    """Resolves prompt path searching cwd, bundle dir, and package root."""
    if os.path.isabs(prompt_path):
        return prompt_path

    # Candidate 1: Current working directory
    cwd_candidate = os.path.abspath(prompt_path)
    if os.path.isfile(cwd_candidate):
        return cwd_candidate

    # Candidate 2: PyInstaller bundle directory
    bundle_candidate = os.path.join(get_bundle_dir(), prompt_path)
    if os.path.isfile(bundle_candidate):
        return bundle_candidate

    # Candidate 3: Root directory relative to this module
    module_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    root_candidate = os.path.join(module_root, prompt_path)
    if os.path.isfile(root_candidate):
        return root_candidate

    return cwd_candidate


def load_prompt_template(prompt_path: str = "prompt.md") -> str:
    """Loads prompt from disk and strips leading/trailing backticks and whitespace."""
    target_path = _resolve_prompt_path(prompt_path or "prompt.md")

    if not os.path.isfile(target_path):
        raise FileNotFoundError(f"Prompt template file not found: {target_path}")

    with open(target_path, "r", encoding="utf-8") as f:
        content = f.read()

    cleaned = content.strip()
    # Strip markdown fence wrapper if entire file was wrapped
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        cleaned = "\n".join(lines).strip()

    # Strip leading/trailing backticks and whitespace
    cleaned = cleaned.strip("`").strip()
    if not cleaned:
        raise ValueError(f"Prompt template file '{target_path}' is empty.")

    return cleaned


def encode_image_base64(image_input: Any) -> str:
    """Encodes numpy array (BGR/BGRA), PIL Image, or file path to Base64 JPEG data URL."""
    if image_input is None:
        raise TypeError("image_input cannot be None")

    # Already a data URL
    if isinstance(image_input, str) and image_input.startswith("data:image/"):
        return image_input

    # NumPy ndarray (OpenCV BGR / BGRA Mat)
    if isinstance(image_input, np.ndarray):
        import cv2

        if image_input.size == 0:
            raise ValueError("Provided numpy image array is empty.")
        img = image_input
        if len(img.shape) == 3 and img.shape[2] == 4:
            img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        success, buf = cv2.imencode(".jpg", img, [int(cv2.IMWRITE_JPEG_QUALITY), 95])
        if not success:
            raise ValueError("Failed to encode numpy array to JPEG format.")
        raw_bytes = buf.tobytes()

    # PIL Image
    elif isinstance(image_input, Image.Image):
        img = image_input
        if img.mode not in ("RGB", "L"):
            img = img.convert("RGB")
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=95)
        raw_bytes = buf.getvalue()

    # File path (str or os.PathLike)
    elif isinstance(image_input, (str, os.PathLike)):
        filepath = str(image_input)
        if not os.path.isfile(filepath):
            raise FileNotFoundError(f"Image file not found: {filepath}")

        with open(filepath, "rb") as f:
            header = f.read(3)
        if header == b"\xff\xd8\xff":
            with open(filepath, "rb") as f:
                raw_bytes = f.read()
        else:
            with Image.open(filepath) as img:
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=95)
                raw_bytes = buf.getvalue()

    # Raw bytes / bytearray
    elif isinstance(image_input, (bytes, bytearray)):
        raw_bytes = bytes(image_input)
        if not raw_bytes.startswith(b"\xff\xd8\xff"):
            with Image.open(io.BytesIO(raw_bytes)) as img:
                if img.mode not in ("RGB", "L"):
                    img = img.convert("RGB")
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=95)
                raw_bytes = buf.getvalue()

    else:
        raise TypeError(f"Unsupported image input type: {type(image_input).__name__}")

    b64_str = base64.b64encode(raw_bytes).decode("ascii")
    return f"data:image/jpeg;base64,{b64_str}"


# ==============================================================================
# Response Parser
# ==============================================================================

def _repair_trailing_commas(json_str: str) -> str:
    """Removes trailing commas before closing braces and brackets."""
    trailing_comma_regex = re.compile(r",\s*([}\]])")
    cleaned = trailing_comma_regex.sub(r"\1", json_str)
    while trailing_comma_regex.search(cleaned):
        cleaned = trailing_comma_regex.sub(r"\1", cleaned)
    return cleaned


def parse_nim_response(response_text: Union[str, Dict[str, Any]]) -> Dict[str, Any]:
    """
    Parses NVIDIA NIM vision model response into a dictionary.

    Stages:
    1. Unpack OpenAI Chat Completion wrappers (dict or JSON string with 'choices')
    2. Strip reasoning/thinking blocks (<think>...</think>)
    3. Extract JSON content from markdown code fences (```json or ```)
    4. Locate outer curly braces ({ ... })
    5. Clean trailing commas
    6. Parse with json.loads and validate dict return type
    """
    if response_text is None:
        raise NimParseError("Received None response_text")

    # Stage 1: Unwrap dictionary or detect OpenAI completion envelope
    if isinstance(response_text, dict):
        if "choices" in response_text:
            choices = response_text.get("choices")
            if not choices or not isinstance(choices, list):
                raise NimParseError("Invalid OpenAI completion payload: 'choices' is empty or not a list")
            first_choice = choices[0]
            if not isinstance(first_choice, dict) or "message" not in first_choice:
                raise NimParseError("Invalid OpenAI completion choice: missing 'message' object")
            message = first_choice.get("message", {})
            content = message.get("content")
            if content is None:
                raise NimParseError("OpenAI completion message content is None")
            if isinstance(content, dict):
                return content
            response_text = str(content)
        else:
            return response_text
    elif not isinstance(response_text, str):
        raise TypeError(f"Expected str or dict for response_text, got {type(response_text).__name__}")

    text = response_text.strip()
    if not text:
        raise NimParseError("Empty response text received")

    # Stage 1b: If string is an OpenAI Chat Completion JSON envelope, extract message content
    if text.startswith("{") and '"choices"' in text:
        try:
            parsed_outer = json.loads(text)
            if isinstance(parsed_outer, dict) and "choices" in parsed_outer:
                return parse_nim_response(parsed_outer)
        except Exception:
            pass

    # Stage 2: Strip <think>...</think> tags (including unclosed trailing tags)
    text = re.sub(r"<think>[\s\S]*?</think>", "", text, flags=re.IGNORECASE)
    text = re.sub(r"<think>[\s\S]*$", "", text, flags=re.IGNORECASE)
    text = text.strip()

    if not text:
        raise NimParseError("No content remaining after stripping <think> tags")

    # Stage 3: Extract from markdown code fences (```json ... ``` or ``` ... ```)
    fence_pattern = re.compile(r"```(?:json)?\s*([\s\S]*?)\s*```", re.IGNORECASE)
    fence_match = fence_pattern.search(text)
    if fence_match:
        text = fence_match.group(1).strip()

    # Stage 4: Locate outer { and }
    start_idx = text.find("{")
    end_idx = text.rfind("}")
    if start_idx == -1 or end_idx == -1 or end_idx <= start_idx:
        raise NimParseError(f"No valid JSON object delimiters ('{{' and '}}') found in response: {text[:150]!r}")

    json_str = text[start_idx : end_idx + 1]

    # Stage 5 & 6: Clean trailing commas and parse with json.loads
    try:
        data = json.loads(json_str, strict=False)
    except json.JSONDecodeError:
        cleaned_json_str = _repair_trailing_commas(json_str)
        try:
            data = json.loads(cleaned_json_str, strict=False)
        except json.JSONDecodeError as clean_err:
            line = clean_err.lineno
            col = clean_err.colno
            lines = cleaned_json_str.splitlines()
            context_line = lines[line - 1] if 0 < line <= len(lines) else ""
            raise NimParseError(
                f"Failed to parse JSON response: {clean_err.msg} at line {line}, col {col}. "
                f"Near line content: {context_line!r}. Text snippet: {text[:200]!r}"
            ) from clean_err

    if not isinstance(data, dict):
        raise NimParseError(f"Parsed JSON must be an object (dict), but got {type(data).__name__}")

    return data


# ==============================================================================
# UI Schema Adapter
# ==============================================================================

def _to_int(val: Any, default: Optional[int] = None) -> Optional[int]:
    """Converts value to int safely, returning default on failure or None."""
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


def _parse_skill_level(val: Any, is_ex: bool = False) -> Optional[int]:
    """Parses skill level string or integer (MAX -> 5/10, Lv.X -> X)."""
    if val is None:
        return None
    if isinstance(val, str):
        s = val.strip().upper()
        if s == "MAX":
            return 5 if is_ex else 10
        if s.startswith("LV."):
            return _to_int(s[3:])
        if s.startswith("LV"):
            return _to_int(s[2:])
    return _to_int(val)


def adapt_vision_schema_to_ui(vision_data: dict) -> dict:
    """
    Converts prompt.md output schema to Plana_SE DetailWindow entry keys.

    Handles prompt.md format, legacy UI format, and mixed formats cleanly.
    Preserves None when releaseLevel is absent.
    """
    if not isinstance(vision_data, dict):
        vision_data = {}

    adapted: Dict[str, Any] = {}

    # 1. Student Profile
    adapted["studentName"] = vision_data.get("studentName")

    # level -> currentLevel
    if "level" in vision_data and vision_data["level"] is not None:
        adapted["currentLevel"] = _to_int(vision_data["level"])
    elif "currentLevel" in vision_data:
        adapted["currentLevel"] = _to_int(vision_data["currentLevel"])
    else:
        adapted["currentLevel"] = None

    # starGrade -> currentStar
    if "starGrade" in vision_data and vision_data["starGrade"] is not None:
        adapted["currentStar"] = _to_int(vision_data["starGrade"])
    elif "currentStar" in vision_data:
        adapted["currentStar"] = _to_int(vision_data["currentStar"])
    else:
        adapted["currentStar"] = None

    adapted["bondRank"] = _to_int(vision_data.get("bondRank"))

    # 2. Skills
    raw_skills = vision_data.get("skills")
    if not isinstance(raw_skills, dict):
        raw_skills = {}

    ex_val = raw_skills.get("ex")
    basic_val = raw_skills.get("normal") if "normal" in raw_skills else raw_skills.get("basic")
    enh_val = raw_skills.get("passive") if "passive" in raw_skills else raw_skills.get("enh")
    sub_val = raw_skills.get("sub")

    adapted["skills"] = {
        "ex": _parse_skill_level(ex_val, is_ex=True),
        "basic": _parse_skill_level(basic_val),
        "enh": _parse_skill_level(enh_val),
        "sub": _parse_skill_level(sub_val),
    }

    # 3. Dedicated Weapon
    raw_weapon = vision_data.get("weapon")
    if not isinstance(raw_weapon, dict):
        raw_weapon = {}

    if raw_weapon.get("unequipped") is True:
        adapted["weapon"] = {"star": None, "level": None}
    else:
        star_val = raw_weapon.get("starGrade") if "starGrade" in raw_weapon else raw_weapon.get("star")
        lvl_val = raw_weapon.get("level")
        adapted["weapon"] = {
            "star": _to_int(star_val),
            "level": _to_int(lvl_val),
        }

    # 4. Equipments & Favorite Item
    equipment: Dict[str, Dict[str, Optional[int]]] = {}
    raw_eq = vision_data.get("equipment")
    if isinstance(raw_eq, dict):
        for k in ["slot1", "slot2", "slot3", "slot4"]:
            if k in raw_eq and isinstance(raw_eq[k], dict):
                equipment[k] = dict(raw_eq[k])

    raw_equipments = vision_data.get("equipments")
    if isinstance(raw_equipments, list):
        for idx, item in enumerate(raw_equipments, 1):
            if not isinstance(item, dict):
                continue
            slot_num = item.get("slot", idx)
            slot_key = f"slot{slot_num}"
            if item.get("unequipped") is True:
                equipment[slot_key] = {"tier": None, "level": None}
            else:
                equipment[slot_key] = {
                    "tier": _to_int(item.get("tier")),
                    "level": _to_int(item.get("level")),
                }

    for i in (1, 2, 3):
        slot_key = f"slot{i}"
        if slot_key not in equipment:
            equipment[slot_key] = {"tier": None, "level": None}

    raw_fav = vision_data.get("favoriteItem")
    if isinstance(raw_fav, dict):
        if raw_fav.get("unequipped") is True:
            fav_tier = None
        else:
            fav_tier = _to_int(raw_fav.get("tier"))
        equipment["slot4"] = {"tier": fav_tier, "level": None}
    elif "slot4" not in equipment:
        equipment["slot4"] = {"tier": None, "level": None}

    adapted["equipment"] = equipment

    # 5. Stats
    raw_stats = vision_data.get("stats")
    if not isinstance(raw_stats, dict):
        raw_stats = {}

    def _extract_stat_and_ability(
        stat_key: str, legacy_val_key: str, legacy_ability_key: str
    ) -> Tuple[Optional[int], Optional[int]]:
        item = raw_stats.get(stat_key)
        val = None
        ability = None
        if isinstance(item, dict):
            val = item.get("value")
            ability = item.get("releaseLevel")
        elif item is not None:
            val = item

        if val is None and legacy_val_key in raw_stats:
            val = raw_stats.get(legacy_val_key)
        if ability is None and legacy_ability_key in raw_stats:
            ability = raw_stats.get(legacy_ability_key)

        return _to_int(val), _to_int(ability)

    hp_v, hp_a = _extract_stat_and_ability("hp", "maxHP", "hpAbility")
    atk_v, atk_a = _extract_stat_and_ability("atk", "attackPower", "atkAbility")
    def_v, def_a = _extract_stat_and_ability("def", "defensePower", "defAbility")
    heal_v, heal_a = _extract_stat_and_ability("heal", "healPower", "healAbility")

    adapted["stats"] = {
        "maxHP": hp_v,
        "hpAbility": hp_a,
        "attackPower": atk_v,
        "atkAbility": atk_a,
        "defensePower": def_v,
        "defAbility": def_a,
        "healPower": heal_v,
        "healAbility": heal_a,
    }

    return adapted


# ==============================================================================
# NVIDIA NIM Client
# ==============================================================================

class NvidiaNimClient:
    """NVIDIA NIM Vision API client complying with OpenAI Multimodal Chat Completions."""

    def __init__(
        self,
        api_key: str,
        model: str = DEFAULT_MODEL,
        endpoint: str = NIM_ENDPOINT,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        temperature: float = DEFAULT_TEMPERATURE,
        timeout: float = DEFAULT_TIMEOUT,
        prompt_path: str = "prompt.md",
        session: Optional[requests.Session] = None,
    ) -> None:
        if not api_key or not isinstance(api_key, str) or not api_key.strip():
            raise ValueError("api_key must be a non-empty string.")
        self.api_key = api_key.strip()
        set_global_secret_key(self.api_key)

        self.model = model.strip() if (model and isinstance(model, str) and model.strip()) else DEFAULT_MODEL
        self.endpoint = endpoint or NIM_ENDPOINT
        self.max_tokens = int(max_tokens) if max_tokens else DEFAULT_MAX_TOKENS
        self.temperature = float(temperature) if temperature is not None else DEFAULT_TEMPERATURE
        self.timeout = float(timeout) if timeout is not None else DEFAULT_TIMEOUT
        self.prompt_path = prompt_path or "prompt.md"
        self._session = session
        self._cached_prompt: Optional[str] = None

    def get_prompt_template(self) -> str:
        """Returns cached prompt template or loads dynamically from disk."""
        if self._cached_prompt is None:
            self._cached_prompt = load_prompt_template(self.prompt_path)
        return self._cached_prompt

    def build_payload(self, image_data_url: str, prompt: Optional[str] = None) -> Dict[str, Any]:
        """Constructs OpenAI-compliant multimodal chat completions payload."""
        prompt_text = prompt if prompt is not None else self.get_prompt_template()
        return {
            "model": self.model,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": prompt_text,
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": image_data_url,
                            },
                        },
                    ],
                }
            ],
            "max_tokens": self.max_tokens,
            "temperature": self.temperature,
        }

    def chat_completion(self, image_input: Any, prompt: Optional[str] = None) -> str:
        """Encodes image, dispatches request to NIM endpoint, handles errors, and returns content string."""
        image_data_url = encode_image_base64(image_input)
        payload = self.build_payload(image_data_url, prompt=prompt)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        try:
            if self._session is not None:
                response = self._session.post(
                    self.endpoint,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
            else:
                response = requests.post(
                    self.endpoint,
                    json=payload,
                    headers=headers,
                    timeout=self.timeout,
                )
        except requests.exceptions.Timeout as e:
            err_msg = f"NVIDIA NIM API request timed out after {self.timeout}s"
            logger.error(err_msg)
            raise NimTimeoutError(err_msg) from e
        except requests.exceptions.ConnectionError as e:
            err_msg = mask_text(f"Failed to connect to NVIDIA NIM endpoint '{self.endpoint}': {e}", self.api_key)
            logger.error(err_msg)
            raise NimClientError(err_msg) from e
        except requests.exceptions.RequestException as e:
            err_msg = mask_text(f"NVIDIA NIM API request failed: {e}", self.api_key)
            logger.error(err_msg)
            raise NimClientError(err_msg) from e

        status_code = response.status_code
        if status_code == 200:
            try:
                resp_json = response.json()
            except Exception as e:
                err_msg = mask_text(f"Failed to decode NIM JSON response: {response.text[:200]}", self.api_key)
                logger.error(err_msg)
                raise NimClientError(err_msg, status_code=200, response_body=response.text) from e

            choices = resp_json.get("choices")
            if not choices or not isinstance(choices, list) or len(choices) == 0:
                raise NimClientError("NIM API response contained no choices.", status_code=200)

            choice = choices[0]
            if not isinstance(choice, dict):
                raise NimClientError("NIM API completion choice is not a dict.", status_code=200)

            message = choice.get("message")
            if not isinstance(message, dict) or "content" not in message:
                raise NimClientError("NIM API completion choice missing 'message.content'.", status_code=200)

            content = message.get("content")
            if content is None:
                raise NimClientError("NIM API message content is None.", status_code=200)

            return str(content)

        # Handle HTTP Errors with secret masking
        body_text = mask_text(response.text, self.api_key)
        masked_key = mask_api_key(self.api_key)

        if status_code == 401:
            err_msg = f"NVIDIA NIM API key is invalid or unauthorized (HTTP 401). Key: {masked_key}. Details: {body_text}"
            logger.error(err_msg)
            raise NimAuthenticationError(err_msg, status_code=401, response_body=response.text)
        elif status_code == 429:
            err_msg = f"NVIDIA NIM API rate limit exceeded (HTTP 429). Details: {body_text}"
            logger.warning(err_msg)
            raise NimRateLimitError(err_msg, status_code=429, response_body=response.text)
        elif status_code >= 500:
            err_msg = f"NVIDIA NIM API server error (HTTP {status_code}). Details: {body_text}"
            logger.error(err_msg)
            raise NimServerError(err_msg, status_code=status_code, response_body=response.text)
        else:
            err_msg = f"NVIDIA NIM API request failed with HTTP {status_code}. Details: {body_text}"
            logger.error(err_msg)
            raise NimClientError(err_msg, status_code=status_code, response_body=response.text)

    def extract_from_image(
        self,
        image_input: Any,
        prompt: Optional[str] = None,
        adapt_to_ui: bool = False,
    ) -> Dict[str, Any]:
        """Extracts structured student data from screenshot image."""
        raw_content = self.chat_completion(image_input, prompt=prompt)
        parsed = parse_nim_response(raw_content)

        if adapt_to_ui:
            return adapt_vision_schema_to_ui(parsed)

        return parsed
