import hashlib
import json
import time
from collections import OrderedDict
from datetime import datetime, timezone

from app.modules.forecast.narrator import ForecastNarrator
from app.modules.forecast.predictors import ForecastModel
from app.core.logging import get_logger

logger = get_logger(__name__)


class ForecastCache:
    """Caché en memoria con vencimiento, para no gastar la cuota gratuita de
    Gemini cada vez que se reabre la misma comparación. Una por proceso, como
    el registro de métricas: Render free corre una sola instancia."""

    def __init__(self, ttl_seconds: float = 900, max_entries: int = 200):
        self.ttl, self.max_entries = ttl_seconds, max_entries
        self._data: OrderedDict[tuple, tuple[float, dict]] = OrderedDict()

    def get(self, key: tuple) -> dict | None:
        entry = self._data.get(key)
        if entry is None:
            return None
        if time.monotonic() - entry[0] > self.ttl:
            del self._data[key]
            return None
        return entry[1]

    def set(self, key: tuple, value: dict) -> None:
        self._data[key] = (time.monotonic(), value)
        self._data.move_to_end(key)
        while len(self._data) > self.max_entries:
            self._data.popitem(last=False)


def _fingerprint(comparison: dict) -> str:
    """Cambia si cambian las ofertas (otro precio, más stock, un recálculo)."""
    offers = sorted(
        (o["match_id"], o["unit_price"], o["quantity_available"], o["subtotal"])
        for item in comparison["items"] for o in item["offers"]
    )
    return hashlib.sha256(json.dumps(offers, default=str).encode()).hexdigest()[:16]


class ForecastService:
    def __init__(self, matching_service, history_repo, model: ForecastModel, narrator: ForecastNarrator, cache: ForecastCache):
        self.matching = matching_service
        self.history_repo = history_repo
        self.model = model
        self.narrator = narrator
        self.cache = cache

    async def forecast(self, quotation_id: int, actor_org_id: int) -> dict:
        # get_comparison también valida que la cotización sea de quien pregunta
        comparison = await self.matching.get_comparison(quotation_id, actor_org_id)
        key = (actor_org_id, quotation_id, _fingerprint(comparison))
        cached = self.cache.get(key)
        if cached is not None:
            return {**cached, "cached": True}

        provider_ids = {p["provider_org_id"] for p in comparison["providers"]}
        histories = await self.history_repo.provider_history(provider_ids, actor_org_id)
        result = self.model.predict(comparison, histories)
        narrative = await self.narrator.narrate(result)

        for option in result["options"]:
            text = narrative.options.get(option["key"])
            option["narrative"] = {
                "que_pasara": text.que_pasara if text else "",
                "riesgos": text.riesgos if text else [],
                "consejo": text.consejo if text else "",
            }
        result.update(
            summary=narrative.summary,
            narrative_source=narrative.source,
            generated_at=datetime.now(timezone.utc),
        )
        logger.info(
            "Predicción cotización %s: %s opciones, mejor=%s, texto=%s",
            quotation_id, len(result["options"]), result["best_option_key"], narrative.source,
        )
        self.cache.set(key, result)
        return {**result, "cached": False}
