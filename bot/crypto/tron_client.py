from __future__ import annotations

from decimal import Decimal
import logging
from typing import Any

import requests

logger = logging.getLogger(__name__)


class TronClient:
    def __init__(self, rpc_url: str, timeout: int = 20):
        self.rpc_url = rpc_url.rstrip("/")
        self.timeout = timeout

    def fetch_incoming_trx(self, wallet_address: str, limit: int = 200) -> list[dict[str, Any]]:
        if not wallet_address:
            return []

        url = f"{self.rpc_url}/v1/accounts/{wallet_address}/transactions"
        params = {
            "only_to": "true",
            "only_confirmed": "true",
            "limit": str(limit),
            "order_by": "block_timestamp,desc",
        }

        response = requests.get(url, params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()

        result: list[dict[str, Any]] = []
        for tx in payload.get("data", []):
            tx_hash = tx.get("txID")
            block_timestamp = tx.get("block_timestamp")
            contracts = tx.get("raw_data", {}).get("contract", [])
            if not tx_hash or not block_timestamp or not contracts:
                continue

            contract = contracts[0]
            if contract.get("type") != "TransferContract":
                continue

            value = contract.get("parameter", {}).get("value", {})
            amount_sun = value.get("amount")
            if amount_sun is None:
                continue

            amount_trx = Decimal(str(amount_sun)) / Decimal("1000000")
            result.append(
                {
                    "tx_hash": tx_hash,
                    "timestamp_ms": int(block_timestamp),
                    "amount_trx": amount_trx,
                    "from_address": value.get("owner_address"),
                    "to_address": value.get("to_address"),
                }
            )

        logger.debug("Fetched %s TRX transfers", len(result))
        return result
