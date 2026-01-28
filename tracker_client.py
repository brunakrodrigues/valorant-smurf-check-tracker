# tracker_client.py
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests


class TrackerAPIError(Exception):
    pass


@dataclass
class ActSlice:
    """Represents an 'act/season-like' slice inferred from Tracker response."""
    key: str
    name: str
    end_time: Optional[int] = None  # epoch millis if available


class TrackerClient:
    """
    Minimal client for Tracker Network's Valorant profile endpoint.

    Auth header:
      TRN-Api-Key: <your key>

    Common endpoint used by tracker.gg frontend:
      https://api.tracker.gg/api/v2/valorant/standard/profile/riot/{riotId}?forceCollect=true

    riotId should be URL-encoded, e.g. boo%231204 (Nick#TAG).
    """

    def __init__(
        self,
        api_key: str,
        timeout: int = 20,
        min_delay_s: float = 0.2,
    ):
        self.api_key = api_key.strip()
        self.timeout = timeout
        self.min_delay_s = min_delay_s
        self._last_call = 0.0

        self.session = requests.Session()
        self.session.headers.update(
            {
                "TRN-Api-Key": self.api_key,
                "User-Agent": "valorant-smurf-checker/1.0",
                "Accept": "application/json",
            }
        )

    def _throttle(self) -> None:
        elapsed = time.time() - self._last_call
        if elapsed < self.min_delay_s:
            time.sleep(self.min_delay_s - elapsed)
        self._last_call = time.time()

    def _get_json(self, url: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        self._throttle()
        r = self.session.get(url, params=params, timeout=self.timeout)

        # Rate limit
        if r.status_code == 429:
            raise TrackerAPIError("Rate limit (429). Diminua a velocidade e tente novamente.")

        # 403 (muito comum quando a key/app não está aprovada)
        if r.status_code == 403:
            txt = (r.text or "")[:500]
            if "not been approved" in txt.lower():
                raise TrackerAPIError(
                    "TRN-Api-Key não aprovada ainda. "
                    "A Tracker Network bloqueou seu acesso (403). "
                    "Fale com eles no Discord para aprovar/whitelist sua aplicação."
                )
            raise TrackerAPIError(f"HTTP 403: {txt}")

        if r.status_code >= 400:
            raise TrackerAPIError(f"HTTP {r.status_code}: {(r.text or '')[:500]}")

        try:
            return r.json()
        except Exception as e:
            raise TrackerAPIError(f"Resposta não-JSON: {e}")

    @staticmethod
    def to_riot_url_id(nick: str, tag: str) -> str:
        # tracker usa formato {gameName}%23{tagLine}
        return requests.utils.quote(f"{nick}#{tag}", safe="")

    def fetch_profile(self, nick: str, tag: str, force_collect: bool = True) -> Dict[str, Any]:
        riot_id = self.to_riot_url_id(nick, tag)
        url = f"https://api.tracker.gg/api/v2/valorant/standard/profile/riot/{riot_id}"
        params = {"forceCollect": "true" if force_collect else "false"}
        return self._get_json(url, params=params)

    # ----------------- parsing helpers -----------------
    @staticmethod
    def _segments(data: Dict[str, Any]) -> List[Dict[str, Any]]:
        return (((data or {}).get("data") or {}).get("segments")) or []

    @staticmethod
    def _stat_value(seg: Dict[str, Any], *keys: str) -> Optional[float]:
        stats = seg.get("stats") or {}
        for k in keys:
            if k in stats:
                v = (stats[k] or {}).get("value")
                if v is not None:
                    return v
        return None

    @staticmethod
    def _meta(seg: Dict[str, Any]) -> Dict[str, Any]:
        return seg.get("metadata") or {}

    @staticmethod
    def _infer_act_key(meta: Dict[str, Any]) -> Optional[Tuple[str, str, Optional[int]]]:
        """
        Try to infer a stable 'act/season' identifier from metadata.

        Returns (key, name, end_time_millis)
        """
        key = meta.get("seasonId") or meta.get("season") or meta.get("actId") or meta.get("act")
        name = meta.get("seasonName") or meta.get("seasonDisplayName") or meta.get("actName") or meta.get("name")

        end_time = meta.get("endTime") or meta.get("endTimeMillis") or meta.get("endDateMillis")
        if end_time is not None:
            try:
                end_time = int(end_time)
            except Exception:
                end_time = None

        if not key and name:
            key = name

        if not key:
            return None

        return str(key), str(name or key), end_time

    @staticmethod
    def infer_last_acts(profile: Dict[str, Any], want: int = 3) -> List[ActSlice]:
        """
        Tracker não garante uma lista “oficial” de atos.
        Inferimos a partir de segments.metadata (seasonId/seasonName/etc).
        """
        segs = TrackerClient._segments(profile)
        seen: Dict[str, ActSlice] = {}
        order: List[str] = []

        for s in segs:
            meta = TrackerClient._meta(s)
            inf = TrackerClient._infer_act_key(meta)
            if not inf:
                continue
            key, name, end_time = inf

            if key not in seen:
                seen[key] = ActSlice(key=key, name=name, end_time=end_time)
                order.append(key)
            else:
                # melhora end_time se aparecer depois
                if seen[key].end_time is None and end_time is not None:
                    seen[key].end_time = end_time

        acts = list(seen.values())

        # Ordenação: por end_time se existir; senão usa ordem de aparição.
        if any(a.end_time is not None for a in acts):
            acts.sort(key=lambda a: (a.end_time or 0))
        else:
            acts = [seen[k] for k in order]

        return acts[-want:] if len(acts) >= want else acts

    @staticmethod
    def extract_rank_tier(seg: Dict[str, Any]) -> Optional[int]:
        """
        Tenta encontrar o tier "atual" em campos comuns.
        """
        v = TrackerClient._stat_value(seg, "rank", "tier", "competitiveTier", "rankTier")
        if v is None:
            return None
        try:
            return int(v)
        except Exception:
            return None

    @staticmethod
    def extract_peak_tier(seg: Dict[str, Any]) -> Optional[int]:
        v = TrackerClient._stat_value(seg, "peakRank", "peakTier", "peakCompetitiveTier")
        if v is None:
            return None
        try:
            return int(v)
        except Exception:
            return None

    @staticmethod
    def is_competitive_segment(seg: Dict[str, Any]) -> bool:
        meta = TrackerClient._meta(seg)
        name = (meta.get("name") or meta.get("modeName") or meta.get("queueName") or "").lower()
        if "competitive" in name or name == "ranked":
            return True
        stype = (seg.get("type") or "").lower()
        if stype == "playlist" and "competitive" in name:
            return True
        return False

    @staticmethod
    def compute_max_tier_last_acts(
        profile: Dict[str, Any],
        last_acts: List[ActSlice],
    ) -> Tuple[Dict[str, Optional[int]], Optional[int], Optional[int]]:
        """
        Returns:
          per_act_max: act_name -> max tier
          peak_last3: max tier across acts
          current_tier_guess: guess of current tier from most recent competitive segment
        """
        segs = TrackerClient._segments(profile)

        per_act_max: Dict[str, Optional[int]] = {a.name: None for a in last_acts}
        current_tier_guess: Optional[int] = None

        act_name_by_key = {a.key: a.name for a in last_acts}

        for s in segs:
            # current tier guess (first competitive segment with a tier)
            if current_tier_guess is None and TrackerClient.is_competitive_segment(s):
                t = TrackerClient.extract_rank_tier(s) or TrackerClient.extract_peak_tier(s)
                if t is not None:
                    current_tier_guess = t

            # map segment -> act
            meta = TrackerClient._meta(s)
            inf = TrackerClient._infer_act_key(meta)
            if not inf:
                continue
            key, _name, _end = inf
            if key not in act_name_by_key:
                continue

            act_name = act_name_by_key[key]

            # tier preference: peak > rank
            tier = TrackerClient.extract_peak_tier(s)
            if tier is None:
                tier = TrackerClient.extract_rank_tier(s)

            if tier is None:
                continue

            if per_act_max[act_name] is None or tier > per_act_max[act_name]:
                per_act_max[act_name] = tier

        peak_last3: Optional[int] = None
        for v in per_act_max.values():
            if v is None:
                continue
            peak_last3 = v if peak_last3 is None else max(peak_last3, v)

        return per_act_max, peak_last3, current_tier_guess
