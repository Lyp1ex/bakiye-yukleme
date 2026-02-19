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


def verify_receipt_image(
    settings: Settings,
    image_bytes: bytes,
    expected_amount_try: Decimal,
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
            summary="AI dekont kontrolü kapalı.",
        )

    if not settings.openai_api_key:
        return ReceiptCheckResult(
            analyzed=False,
            passed=not settings.receipt_ai_strict,
            is_receipt=None,
            amount_text="-",
            amount_match=None,
            date_text="-",
            date_match=None,
            summary="OPENAI_API_KEY yok, AI dekont kontrolü yapılamadı.",
        )

    try:
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:image/jpeg;base64,{b64}"

        system_prompt = (
            "Sen bir banka dekont doğrulama asistanısın. "
            "Sadece JSON döndür. "
            "Alanlar: is_receipt(bool), amount_text(str), date_iso(str), reasoning(str)."
        )
        user_prompt = (
            "Görsel bir banka dekontu mu kontrol et. "
            f"Beklenen ödeme tutarı (TL): {expected_amount_try}. "
            "Mümkünse dekont üzerindeki ödeme tutarını amount_text alanına, "
            "işlem tarihini ISO formatında date_iso alanına yaz."
        )

        payload = {
            "model": "gpt-4o-mini",
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": user_prompt},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            "temperature": 0,
        }
        headers = {
            "Authorization": f"Bearer {settings.openai_api_key}",
            "Content-Type": "application/json",
        }
        response = requests.post(
            "https://api.openai.com/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=45,
        )
        response.raise_for_status()
        data = response.json()
        content = data["choices"][0]["message"]["content"]
        parsed = json.loads(content)
    except Exception as exc:
        logger.exception("AI dekont kontrolü başarısız", exc_info=exc)
        return ReceiptCheckResult(
            analyzed=False,
            passed=not settings.receipt_ai_strict,
            is_receipt=None,
            amount_text="-",
            amount_match=None,
            date_text="-",
            date_match=None,
            summary="AI dekont kontrolü başarısız oldu, manuel incelemeye düştü.",
        )

    is_receipt = bool(parsed.get("is_receipt"))
    amount_text = str(parsed.get("amount_text") or "-").strip()
    date_text = str(parsed.get("date_iso") or "-").strip()
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

    pass_checks = bool(
        is_receipt
        and (amount_match is not False)
        and (date_match is not False)
    )

    if settings.receipt_ai_strict:
        passed = pass_checks
    else:
        passed = True

    summary_parts = [
        f"Dekont: {'Evet' if is_receipt else 'Hayır'}",
        f"Tutar: {amount_text} ({'uyumlu' if amount_match else 'uyumsuz' if amount_match is False else 'belirsiz'})",
        f"Tarih: {date_text} ({'uyumlu' if date_match else 'uyumsuz' if date_match is False else 'belirsiz'})",
    ]
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
        summary=" | ".join(summary_parts),
    )
