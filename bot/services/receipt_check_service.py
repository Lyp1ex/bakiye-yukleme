from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
import base64
import json
import logging
from typing import Any

import requests

from bot.config.settings import Settings

logger = logging.getLogger(__name__)


@dataclass
class ReceiptCheckResult:
    analyzed: bool
    passed: bool
    is_receipt: bool | None
    amount_text: str
    amount_match: bool | None
    date_text: str
    date_match: bool | None
    iban_text: str
    iban_match: bool | None
    risk_score: int
    risk_flags: list[str]
    summary: str


def _to_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        txt = str(value).strip().replace("TL", "").replace("₺", "").replace(" ", "")
        txt = txt.replace(".", "").replace(",", ".")
        return Decimal(txt)
    except Exception:
        return None


def _to_datetime(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        raw = str(value).strip().replace("Z", "+00:00")
        dt = datetime.fromisoformat(raw)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _normalize_iban(value: Any) -> str:
    if value is None:
        return ""
    return str(value).replace(" ", "").upper().strip()


def _to_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    txt = str(value).strip().lower()
    return txt in {"1", "true", "yes", "evet"}


def _extract_json(raw_text: str) -> dict[str, Any]:
    text = (raw_text or "").strip()
    if text.startswith("```"):
        text = text.strip("`")
        if text.lower().startswith("json"):
            text = text[4:].strip()

    try:
        parsed = json.loads(text)
        if isinstance(parsed, dict):
            return parsed
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        candidate = text[start : end + 1]
        parsed = json.loads(candidate)
        if isinstance(parsed, dict):
            return parsed

    raise ValueError("model_json_parse_failed")


def _call_gemini(
    settings: Settings,
    image_bytes: bytes,
    mime_type: str,
    expected_amount_try: Decimal,
    expected_iban: str | None,
) -> dict[str, Any]:
    if not settings.gemini_api_key:
        raise RuntimeError("gemini_key_missing")

    instruction = (
        "Sen bir banka dekont doğrulama asistanısın. "
        "Sadece JSON döndür. "
        "Alanlar: is_receipt(bool), amount_text(str), date_iso(str), iban_text(str), reasoning(str).\n"
        "Görsel bir banka dekontu mu kontrol et. "
        f"Beklenen ödeme tutarı (TL): {expected_amount_try}. "
        f"Beklenen alıcı IBAN: {expected_iban or '-'} "
        "Mümkünse dekont üzerindeki ödeme tutarını amount_text alanına, "
        "işlem tarihini ISO formatında date_iso alanına, "
        "alıcı IBAN bilgisini iban_text alanına yaz."
    )
    b64 = base64.b64encode(image_bytes).decode("utf-8")
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": instruction},
                    {"inline_data": {"mime_type": mime_type, "data": b64}},
                ]
            }
        ],
        "generationConfig": {
            "temperature": 0,
            "responseMimeType": "application/json",
        },
    }
    response = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{settings.gemini_model}:generateContent",
        params={"key": settings.gemini_api_key},
        json=payload,
        timeout=45,
    )
    response.raise_for_status()
    data = response.json()

    candidates = data.get("candidates") or []
    if not candidates:
        raise ValueError("gemini_no_candidate")
    parts = (candidates[0].get("content") or {}).get("parts") or []
    if not parts:
        raise ValueError("gemini_no_part")
    text = parts[0].get("text") or ""
    return _extract_json(text)


def _http_error_reason(exc: requests.HTTPError) -> str:
    status = exc.response.status_code if exc.response is not None else "unknown"
    message = ""
    if exc.response is not None:
        try:
            payload = exc.response.json()
            err = payload.get("error") if isinstance(payload, dict) else None
            if isinstance(err, dict):
                message = str(err.get("status") or err.get("code") or err.get("message") or "")
            elif isinstance(payload, dict):
                message = str(payload.get("message") or "")
        except Exception:
            message = exc.response.text[:120]
    if not message:
        message = str(exc)[:120]
    return f"http_{status}:{message}"


def verify_receipt_image(
    settings: Settings,
    image_bytes: bytes,
    expected_amount_try: Decimal,
    expected_iban: str | None = None,
    mime_type: str = "image/jpeg",
) -> ReceiptCheckResult:
    if not settings.receipt_ai_enabled:
        return ReceiptCheckResult(
            analyzed=False,
            passed=True,
            is_receipt=None,
            amount_text="-",
            amount_match=None,
            date_text="-",
            date_match=None,
            iban_text="-",
            iban_match=None,
            risk_score=0,
            risk_flags=[],
            summary="AI dekont kontrolü kapalı.",
        )

    if not settings.gemini_api_key:
        return ReceiptCheckResult(
            analyzed=False,
            passed=not settings.receipt_ai_strict,
            is_receipt=None,
            amount_text="-",
            amount_match=None,
            date_text="-",
            date_match=None,
            iban_text="-",
            iban_match=None,
            risk_score=20,
            risk_flags=["gemini_key_missing"],
            summary="GEMINI_API_KEY yok, AI dekont kontrolü yapılamadı.",
        )

    try:
        parsed = _call_gemini(
            settings=settings,
            image_bytes=image_bytes,
            mime_type=mime_type,
            expected_amount_try=expected_amount_try,
            expected_iban=expected_iban,
        )
    except requests.HTTPError as exc:
        reason = _http_error_reason(exc)
        logger.warning("Gemini dekont kontrolü başarısız", extra={"reason": reason})
        return ReceiptCheckResult(
            analyzed=False,
            passed=not settings.receipt_ai_strict,
            is_receipt=None,
            amount_text="-",
            amount_match=None,
            date_text="-",
            date_match=None,
            iban_text="-",
            iban_match=None,
            risk_score=30,
            risk_flags=["ai_failure"],
            summary=f"AI dekont kontrolü başarısız oldu, manuel incelemeye düştü. Hata: {reason}",
        )
    except Exception as exc:
        logger.exception("Gemini dekont kontrolü başarısız", exc_info=exc)
        return ReceiptCheckResult(
            analyzed=False,
            passed=not settings.receipt_ai_strict,
            is_receipt=None,
            amount_text="-",
            amount_match=None,
            date_text="-",
            date_match=None,
            iban_text="-",
            iban_match=None,
            risk_score=30,
            risk_flags=["ai_failure"],
            summary="AI dekont kontrolü başarısız oldu, manuel incelemeye düştü.",
        )

    is_receipt = _to_bool(parsed.get("is_receipt"))
    amount_text = str(parsed.get("amount_text") or "-").strip()
    date_text = str(parsed.get("date_iso") or "-").strip()
    iban_text = str(parsed.get("iban_text") or "-").strip()
    reasoning = str(parsed.get("reasoning") or "").strip()

    found_amount = _to_decimal(amount_text)
    amount_match: bool | None = None
    if found_amount is not None:
        diff = abs(found_amount - Decimal(expected_amount_try))
        amount_match = diff <= settings.receipt_amount_tolerance_try

    found_date = _to_datetime(date_text)
    date_match: bool | None = None
    if found_date is not None:
        now = datetime.now(timezone.utc)
        day_diff = abs((now.date() - found_date.date()).days)
        date_match = day_diff <= settings.receipt_date_max_diff_days

    expected_iban_norm = _normalize_iban(expected_iban or "")
    found_iban_norm = _normalize_iban(iban_text if iban_text != "-" else "")
    iban_match: bool | None = None
    if expected_iban_norm and found_iban_norm:
        iban_match = expected_iban_norm == found_iban_norm

    pass_checks = bool(
        is_receipt
        and (amount_match is not False)
        and (date_match is not False)
        and (iban_match is not False)
    )

    risk_score = 0
    risk_flags: list[str] = []
    if not is_receipt:
        risk_score += 45
        risk_flags.append("not_receipt")
    if amount_match is False:
        risk_score += 30
        risk_flags.append("amount_mismatch")
    if date_match is False:
        risk_score += 20
        risk_flags.append("date_mismatch")
    if iban_match is False:
        risk_score += 25
        risk_flags.append("iban_mismatch")
    risk_score = max(0, min(risk_score, 100))

    if settings.receipt_ai_strict:
        passed = pass_checks and risk_score < settings.receipt_risk_reject_threshold
    else:
        passed = True

    summary_parts = [
        "Sağlayıcı: GEMINI",
        f"Dekont: {'Evet' if is_receipt else 'Hayır'}",
        f"Tutar: {amount_text} ({'uyumlu' if amount_match else 'uyumsuz' if amount_match is False else 'belirsiz'})",
        f"Tarih: {date_text} ({'uyumlu' if date_match else 'uyumsuz' if date_match is False else 'belirsiz'})",
        f"IBAN: {iban_text} ({'uyumlu' if iban_match else 'uyumsuz' if iban_match is False else 'belirsiz'})",
        f"Risk Skoru: {risk_score}/100",
    ]
    if risk_flags:
        summary_parts.append(f"Risk Bayrakları: {', '.join(risk_flags)}")
    if reasoning:
        summary_parts.append(f"Not: {reasoning}")

    return ReceiptCheckResult(
        analyzed=True,
        passed=passed,
        is_receipt=is_receipt,
        amount_text=amount_text,
        amount_match=amount_match,
        date_text=date_text,
        date_match=date_match,
        iban_text=iban_text,
        iban_match=iban_match,
        risk_score=risk_score,
        risk_flags=risk_flags,
        summary=" | ".join(summary_parts),
    )

