"""
Aureon SaaS — HTTP gateway routes.
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

`register_saas_routes(app)` mounts the platform surface onto the operator's Flask
app — so one service (8790) serves operator + cognition + the SaaS catalog behind
the same security envelope (bearer/rate-limit already applied to /api/* by the
operator's before_request gate).

Routes:
  GET  /api/catalog            categorized catalog (12 categories × domains × systems)
  GET  /api/domains            per-domain reachability report
  GET  /api/domains/<domain>   one domain: entry point + its systems
  GET  /api/status             live platform health (honest, often degraded)
  GET  /api/organism           connectome coverage + recent pulses + mesh membership
  GET  /api/cognition          the whole cognitive substrate + provenance + truth roll-up
  GET  /api/cognition/<part>   one cognitive surface: field·bus·mycelium·connectome·brain
  GET  /api/metacognition      the organism's self-assessment (reads its own signals)
  GET  /api/affect             how Aureon feels: victory·defeat·fear·resolve (real signals)
  GET  /api/soul               how Aureon reacts: thought+feeling+lineage → a determination
  GET  /api/inner-work         the soul's inner work: belief·love·determination·ego-death, the ascent
  GET  /api/pursuit            the pursuit of happiness: pillars, unified energy & the next safe step
  GET  /api/approvals          the director's desk: big plays prepared, awaiting Gary's decision
  POST /api/approvals/<id>     record Gary's approve/reject (the human gate; never executes the move)
  GET  /api/company            the full workforce: every role across 8 departments, crew-staffable
  GET  /api/defense            the bio family: sensor lanes · statistical-validity dossier · immune layer
  GET  /api/manifests/<name>   a frontend manifest, rendered live (JSON)
  POST /api/manifests/refresh  rebuild catalog + rewrite frontend manifests

Optional tenancy bridge: when ``AUREON_SUPABASE_JWT_SECRET`` is set, these routes
additionally require a valid Supabase JWT (HS256) — stdlib verify, no new dep.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode, urlparse
from urllib.request import Request, urlopen, build_opener, HTTPRedirectHandler

from aureon.core.no_external_calls import no_external_api_calls
from aureon.operator.identity import verify_supabase_jwt

logger = logging.getLogger("aureon.saas.gateway")


# ── Supabase JWT (optional, stdlib HS256) ─────────────────────────────────────
# The verifier now lives in ``aureon.operator.identity`` so the operator gate and this gateway share
# one implementation; re-exported here for backward compatibility (imports + tests unchanged).


def build_organism_payload() -> Dict[str, Any]:
    """Observe existing runtime sources; a GET must never construct an organ."""
    from aureon.saas.observed_runtime import observed_organism

    return observed_organism()


def _bounded_count(value: Any) -> int | None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value if value <= 9007199254740991 else None


def _short_text(value: Any, *, limit: int = 120) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text[:limit] if text else None


RESEARCH_PROXY_TIMEOUT_SEC = float(os.getenv("AUREON_RESEARCH_PROXY_TIMEOUT_SEC", "8") or 8.0)
RESEARCH_PROXY_MAX_BYTES = 8 * 1024 * 1024
NOAA_SOURCE_MAX_AGE_SEC = 20 * 60
USGS_SOURCE_MAX_AGE_SEC = 5 * 60
RESONANCE_ONE_UPDATE_MAX_AGE_SEC = 90 * 60
RESONANCE_ONE_WINDOW_MAX_AGE_SEC = 135 * 60
NOAA_FEEDS: Dict[str, Dict[str, Any]] = {
    "wind": {
        "label": "Solar wind plasma",
        "url": "https://services.swpc.noaa.gov/json/rtsw/rtsw_wind_1m.json",
        "metrics": (("proton_speed", 0.0, None), ("proton_density", 0.0, None), ("proton_temperature", 0.0, None)),
    },
    "imf": {
        "label": "Interplanetary magnetic field",
        "url": "https://services.swpc.noaa.gov/json/rtsw/rtsw_mag_1m.json",
        "metrics": (("bz_gsm", None, None),),
    },
    "goes": {
        "label": "GOES magnetic field",
        "url": "https://services.swpc.noaa.gov/json/goes/primary/magnetometers-6-hour.json",
        "metrics": (("Hp", None, None), ("total", 0.0, None)),
    },
    "kp": {
        "label": "Estimated planetary Kp",
        "url": "https://services.swpc.noaa.gov/json/planetary_k_index_1m.json",
        "metrics": (("estimated_kp", 0.0, 9.0),),
    },
}
USGS_EARTHQUAKE_SOURCE = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/4.5_week.geojson"
RESONANCE_ONE_SOURCE = "https://resonanceone.app/api/now"
SCHUMANN_DERIVED_SOURCE_ID = "NOAA_SWPC_KP_DERIVED_SCHUMANN"
SCHUMANN_DERIVED_SOURCE_URL = NOAA_FEEDS["kp"]["url"]
SCHUMANN_SUNGEO_SOURCE_ID = "SUNGEO_STATION_ACTIVITY"
SCHUMANN_SUNGEO_CURRENT_SOURCE = "https://sungeo.net/api/current?lang=en"
SCHUMANN_SUNGEO_STATIONS_SOURCE = "https://sungeo.net/api/station-analyses"
SCHUMANN_SUNGEO_MAX_AGE_SEC = 90 * 60
SCHUMANN_PHASE_BY_STATUS = {
    "calm": "stable",
    "quiet": "stable",
    "normal": "stable",
    "stable": "stable",
    "elevated": "elevated",
    "active": "elevated",
    "storm": "disturbed",
    "high": "disturbed",
    "disturbed": "disturbed",
}


def _utc_iso_from_epoch(epoch_ms_or_sec: float) -> str:
    epoch = float(epoch_ms_or_sec)
    if epoch > 10_000_000_000:
        epoch /= 1000.0
    return datetime.fromtimestamp(epoch, timezone.utc).isoformat().replace("+00:00", "Z")


def _source_time_epoch(value: Any) -> float | None:
    if isinstance(value, (int, float)) and not isinstance(value, bool) and value > 0:
        epoch = float(value) / 1000.0 if float(value) > 10_000_000_000 else float(value)
        return epoch if epoch <= time.time() + 5.0 else None
    if not isinstance(value, str) or not value.strip():
        return None
    raw = value.strip()
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    elif len(raw) >= 19 and "+" not in raw[10:] and "-" not in raw[10:]:
        raw = raw + "+00:00"
    try:
        epoch = datetime.fromisoformat(raw).timestamp()
    except ValueError:
        return None
    return epoch if epoch > 0 and epoch <= time.time() + 5.0 else None


def _finite_number(value: Any, minimum: float | None = None, maximum: float | None = None) -> float | None:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return None
    number = float(value)
    if number != number or number in (float("inf"), float("-inf")):
        return None
    if minimum is not None and number < minimum:
        return None
    if maximum is not None and number > maximum:
        return None
    return number


SUPABASE_REST_MAX_BYTES = 2 * 1024 * 1024
SUPABASE_ANALYTICS_LIMIT = 500
SUPABASE_ANALYTICS_TIMEOUT_SEC = float(os.getenv("AUREON_SUPABASE_ANALYTICS_TIMEOUT_SEC", "8") or 8.0)
TRADING_ANALYTICS_TENANT_ENV_NAMES = (
    "AUREON_TRADING_TENANT_ID",
    "AUREON_SUPABASE_USER_ID",
    "SUPABASE_USER_ID",
)
TRADING_ANALYTICS_COLUMNS = (
    "id",
    "user_id",
    "symbol",
    "exchange",
    "side",
    "opened_at",
    "closed_at",
    "source_id",
    "source_timestamp",
    "realized_pnl",
    "status",
    "generated_values",
    "truth_status",
    "entry_price",
    "exit_price",
    "close_reason",
)


def _analytics_tenant_from_env() -> str:
    for name in TRADING_ANALYTICS_TENANT_ENV_NAMES:
        value = _short_text(os.environ.get(name), limit=160)
        if value:
            return value
    return ""


def _bearer_token(auth_header: Any) -> str:
    raw = _short_text(auth_header, limit=4000) or ""
    if not raw.startswith("Bearer "):
        return ""
    return raw[len("Bearer "):].strip()


def _b64url_json(segment: str) -> Dict[str, Any]:
    try:
        padded = segment + ("=" * (-len(segment) % 4))
        value = json.loads(base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8"))
        return value if isinstance(value, dict) else {}
    except Exception:
        return {}


def _jwt_claims_unverified(token: str) -> Dict[str, Any]:
    parts = token.split(".")
    if len(parts) != 3:
        return {}
    return _b64url_json(parts[1])


def _project_ref_from_claims(claims: Dict[str, Any]) -> str:
    ref = _short_text(claims.get("ref"), limit=80)
    if ref:
        return ref
    issuer = _short_text(claims.get("iss"), limit=500) or ""
    try:
        host = urlparse(issuer).hostname or ""
    except Exception:
        host = ""
    if host.endswith(".supabase.co"):
        return host.split(".", 1)[0]
    return ""


def _project_ref_from_url(url: str) -> str:
    try:
        host = urlparse(url).hostname or ""
    except Exception:
        return ""
    if host.endswith(".supabase.co"):
        return host.split(".", 1)[0]
    return ""


def _supabase_public_key_from_request(headers: Any) -> str:
    return (
        _short_text(os.environ.get("AUREON_SUPABASE_PUBLISHABLE_KEY"), limit=4000)
        or _short_text(os.environ.get("AUREON_SUPABASE_ANON_KEY"), limit=4000)
        or _short_text(os.environ.get("SUPABASE_ANON_KEY"), limit=4000)
        or _short_text(os.environ.get("VITE_SUPABASE_ANON_KEY"), limit=4000)
        or _short_text(os.environ.get("VITE_SUPABASE_PUBLISHABLE_KEY"), limit=4000)
        or _short_text(headers.get("X-Aureon-Supabase-Publishable-Key"), limit=4000)
        or ""
    )


def _supabase_url_from_env_or_claims(user_claims: Dict[str, Any], public_key_claims: Dict[str, Any]) -> str:
    configured = _short_text(
        os.environ.get("AUREON_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
        or os.environ.get("VITE_SUPABASE_URL"), limit=500
    ) or ""
    # A caller's unsigned claims must not choose where credentials are sent.
    try:
        parsed = urlparse(configured)
        configured_port = parsed.port
    except ValueError:
        return ""
    if (parsed.scheme == "https" and parsed.hostname and parsed.hostname.endswith(".supabase.co")
            and not parsed.username and not parsed.password and configured_port in (None, 443)
            and parsed.path in ("", "/") and not parsed.query and not parsed.fragment):
        return configured.rstrip("/")
    return ""


def _tenant_bearer_supabase_auth(headers: Any) -> Dict[str, str]:
    bearer = _bearer_token(headers.get("Authorization"))
    public_key = _supabase_public_key_from_request(headers)
    if not bearer or not public_key:
        return {}
    user_claims = _jwt_claims_unverified(bearer)
    public_claims = _jwt_claims_unverified(public_key)
    tenant_id = _short_text(user_claims.get("sub"), limit=160) or ""
    if not tenant_id:
        return {}
    public_role = _short_text(public_claims.get("role"), limit=80)
    if public_claims and public_role != "anon":
        return {}
    user_ref = _project_ref_from_claims(user_claims)
    key_ref = _project_ref_from_claims(public_claims)
    configured_url = _short_text(
        os.environ.get("AUREON_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
        or os.environ.get("VITE_SUPABASE_URL"), limit=500
    ) or ""
    configured_ref = _project_ref_from_url(configured_url) if configured_url else ""
    refs = {item for item in (user_ref, key_ref, configured_ref) if item}
    if len(refs) > 1:
        return {}
    url = _supabase_url_from_env_or_claims(user_claims, public_claims)
    if not url or not _project_ref_from_url(url):
        return {}
    return {
        "mode": "tenant_bearer_rls",
        "tenant_id": tenant_id,
        "url": url,
        "apikey": public_key,
        "authorization": bearer,
    }


def _server_side_supabase_auth(tenant_id: str) -> Dict[str, str]:
    url = _supabase_url_from_env_or_claims({}, {})
    key = _short_text(
        os.environ.get("SUPABASE_SERVICE_ROLE_KEY")
        or os.environ.get("SUPABASE_SECRET_KEY")
        or os.environ.get("SUPABASE_SERVICE_KEY"),
        limit=4000,
    ) or ""
    if not url or not key or not tenant_id:
        return {}
    return {
        "mode": "server_service_role_user_id_filter",
        "tenant_id": tenant_id,
        "url": url.rstrip("/"),
        "apikey": key,
        "authorization": key,
    }


def _analytics_range_start(range_name: str, now_ms: int) -> str:
    days = {"24h": 1, "7d": 7, "30d": 30}
    if range_name == "all":
        return "1970-01-01T00:00:00+00:00"
    day_count = days.get(range_name, 7)
    return datetime.fromtimestamp((now_ms / 1000.0) - (day_count * 86400), tz=timezone.utc).isoformat()


def _unavailable_trading_analytics(reason: str, *, range_name: str, received_at: int | None = None) -> Dict[str, Any]:
    return {
        "available": False,
        "range": range_name,
        "receivedAt": received_at if isinstance(received_at, int) else int(time.time() * 1000),
        "records": [],
        "count": 0,
        "truth_status": "unavailable",
        "generated_values": False,
        "source": "supabase.trading_positions.server_side_user_id_filter",
        "reason": _short_text(reason, limit=220) or "closed_position_analytics_unavailable",
    }


class _NoCredentialRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        # The initially pinned Supabase destination owns these credentials.
        # Never forward them, including on a same-host redirect.
        return None


def _open_supabase_request(request: Request, *, timeout: float):
    return build_opener(_NoCredentialRedirect()).open(request, timeout=timeout)


def _read_supabase_closed_position_analytics(
    range_name: str,
    tenant_id: str,
    *,
    auth: Dict[str, str] | None = None,
) -> Dict[str, Any]:
    received_at = int(time.time() * 1000)
    auth = auth or _server_side_supabase_auth(tenant_id)
    if not auth:
        url_present = bool(_short_text(
            os.environ.get("AUREON_SUPABASE_URL") or os.environ.get("SUPABASE_URL")
            or os.environ.get("VITE_SUPABASE_URL"), limit=500
        ))
        service_key_present = bool(_short_text(os.environ.get("SUPABASE_SERVICE_ROLE_KEY") or os.environ.get("SUPABASE_SECRET_KEY") or os.environ.get("SUPABASE_SERVICE_KEY"), limit=4000))
        reason = "Tenant/user id is required for server-side trading_positions filtering" if url_present and service_key_present and not tenant_id else "Supabase URL plus server-side service key or tenant bearer/public key is not configured"
        return _unavailable_trading_analytics(
            reason,
            range_name=range_name,
            received_at=received_at,
        )
    tenant_id = _short_text(auth.get("tenant_id"), limit=160) or tenant_id
    if not tenant_id:
        return _unavailable_trading_analytics(
            "Tenant/user id is required for server-side trading_positions filtering",
            range_name=range_name,
            received_at=received_at,
        )
    base_url = auth["url"].rstrip("/") + "/rest/v1/trading_positions"
    query: Dict[str, str] = {
        "select": ",".join(TRADING_ANALYTICS_COLUMNS),
        "user_id": f"eq.{tenant_id}",
        "status": "eq.closed",
        "generated_values": "is.false",
        "closed_at": "not.is.null",
        "order": "closed_at.asc",
        "limit": str(SUPABASE_ANALYTICS_LIMIT),
    }
    if range_name != "all":
        query["closed_at"] = f"gte.{_analytics_range_start(range_name, received_at)}"
    request = Request(
        base_url + "?" + urlencode(query),
        headers={
            "Accept": "application/json",
            "apikey": auth["apikey"],
            "Authorization": f"Bearer {auth['authorization']}",
            "Prefer": "count=exact",
            "User-Agent": "Aureon-local-tenant-scoped-analytics/1.0",
        },
    )
    try:
        with _open_supabase_request(request, timeout=SUPABASE_ANALYTICS_TIMEOUT_SEC) as response:
            body = response.read(SUPABASE_REST_MAX_BYTES + 1)
            if len(body) > SUPABASE_REST_MAX_BYTES:
                return _unavailable_trading_analytics(
                    "Supabase analytics response exceeded size limit",
                    range_name=range_name,
                    received_at=received_at,
                )
            records = json.loads(body.decode("utf-8"))
            content_range = response.headers.get("content-range") or response.headers.get("Content-Range") or ""
    except HTTPError as exc:
        return _unavailable_trading_analytics(
            f"Supabase analytics request failed with HTTP {exc.code}",
            range_name=range_name,
            received_at=received_at,
        )
    except (OSError, URLError, UnicodeError, ValueError) as exc:
        return _unavailable_trading_analytics(
            f"Supabase analytics source unavailable:{type(exc).__name__}",
            range_name=range_name,
            received_at=received_at,
        )
    if not isinstance(records, list):
        return _unavailable_trading_analytics(
            "Supabase analytics response was not an array",
            range_name=range_name,
            received_at=received_at,
        )
    if any(not isinstance(row, dict) or row.get("user_id") != tenant_id for row in records):
        return _unavailable_trading_analytics(
            "Supabase analytics row ownership did not match the authenticated account scope",
            range_name=range_name, received_at=received_at,
        )
    exact_count = len(records)
    if "/" in content_range:
        maybe_count = content_range.rsplit("/", 1)[-1]
        if maybe_count.isdigit():
            exact_count = int(maybe_count)
    if exact_count != len(records):
        return _unavailable_trading_analytics(
            "Supabase analytics result was truncated before a complete exact count",
            range_name=range_name,
            received_at=received_at,
        )
    return {
        "available": True,
        "range": range_name,
        "receivedAt": received_at,
        "records": [{key: value for key, value in row.items() if key != "user_id"} for row in records],
        "count": len(records),
        "truth_status": "real_derived",
        "generated_values": False,
        "source": "supabase.trading_positions.server_side_user_id_filter",
        "tenant_scope": "user_id",
        "auth_mode": auth.get("mode", "unknown"),
        "reason": "Tenant-scoped closed trading_positions records read through the local backend",
    }


def _bounded_public_json(url: str, *, max_bytes: int = RESEARCH_PROXY_MAX_BYTES) -> tuple[Any, int]:
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "Aureon-local-readonly-research-proxy/1.0"})
    with urlopen(request, timeout=RESEARCH_PROXY_TIMEOUT_SEC) as response:
        length_header = response.headers.get("Content-Length") or response.headers.get("content-length")
        if length_header and length_header.isdigit() and int(length_header) > max_bytes:
            raise ValueError("public source response exceeded size limit")
        chunks: list[bytes] = []
        total = 0
        while True:
            chunk = response.read(65536)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                raise ValueError("public source response exceeded size limit")
            chunks.append(chunk)
    body = b"".join(chunks)
    return json.loads(body.decode("utf-8")), int(time.time() * 1000)


def _unavailable_research_receipt(source: str, reason: str, *, source_url: str | None = None) -> Dict[str, Any]:
    return {
        "available": False,
        "truth_status": "unavailable",
        "generated_values": False,
        "source": source,
        "source_url": source_url,
        "receivedAt": None,
        "reason": _short_text(reason, limit=220) or "source_unavailable",
    }


def _read_noaa_feed(feed: str, payload: Any, received_at: int, *, now: float | None = None) -> Dict[str, Any]:
    now = time.time() if now is None else now
    definition = NOAA_FEEDS.get(feed)
    if definition is None or not isinstance(payload, list):
        return {"feed": feed, "status": "unavailable", "receivedAt": None, "samples": [], "reason": "Malformed NOAA response or receipt"}
    samples: list[Dict[str, Any]] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        stamp = _source_time_epoch(row.get("time_tag"))
        if stamp is None or now - stamp > NOAA_SOURCE_MAX_AGE_SEC:
            continue
        if feed in {"wind", "imf"} and row.get("active") is not True:
            continue
        if feed == "goes" and row.get("arcjet_flag") is not False:
            continue
        if feed == "kp":
            source = "NOAA SWPC planetary Kp estimate"
        elif feed == "goes" and isinstance(row.get("satellite"), int) and row["satellite"] > 0:
            source = f"NOAA GOES-{row['satellite']}"
        else:
            source = str(row.get("source") or "").strip()
        if not source or (feed == "goes" and not source.startswith("NOAA GOES-")):
            continue
        values: Dict[str, float | None] = {}
        for key, minimum, maximum in definition["metrics"]:
            value = _finite_number(row.get(key), minimum, maximum)
            if value in (-9999.0, -99999.0):
                value = None
            values[key] = value
        if not any(value is not None for value in values.values()):
            continue
        samples.append({"source": source, "observedAt": _utc_iso_from_epoch(stamp), "values": values})
    samples.sort(key=lambda item: item["observedAt"])
    if not samples:
        return {"feed": feed, "status": "unavailable", "receivedAt": None, "samples": [], "reason": "No qualified timestamped NOAA readings"}
    return {"feed": feed, "status": "observed", "receivedAt": received_at, "samples": samples[-60:], "reason": "NOAA public source response via local gateway"}


def _read_schumann_proxy(payload: Any, received_at: int) -> Dict[str, Any] | None:
    """Derive the existing NOAA-Kp Schumann proxy without browser-side Supabase calls.

    This is explicitly a real-derived proxy. It is not a direct station
    Schumann measurement, and UI surfaces that require station observations
    must continue to reject it.
    """
    now = time.time()
    if not isinstance(payload, list):
        return None
    rows: list[tuple[float, float]] = []
    for row in payload:
        if not isinstance(row, dict):
            continue
        stamp = _source_time_epoch(row.get("time_tag"))
        raw_kp = row.get("kp_index") if row.get("kp_index") is not None else row.get("estimated_kp")
        kp = _finite_number(raw_kp, 0.0, 9.0)
        if stamp is not None and kp is not None:
            rows.append((stamp, kp))
    if not rows:
        return None
    rows.sort(key=lambda item: item[0])
    latest_stamp, latest_kp = rows[-1]
    if now - latest_stamp > NOAA_SOURCE_MAX_AGE_SEC:
        return None

    def derived_frequency(kp: float) -> float:
        return 7.83 + (kp - 3.0) * 0.015

    disturbance = max(0.0, min(1.0, latest_kp / 9.0))
    quality = max(0.35, 1.0 - disturbance * 0.65)
    fundamental_hz = derived_frequency(latest_kp)
    amplitude = min(1.0, 0.60 + 0.05 * latest_kp)
    coherence_boost = max(0.0, (quality - 0.5) * 0.1)
    recent = [derived_frequency(kp) for stamp, kp in rows if latest_stamp - stamp <= 60 * 60]
    if not recent:
        return None
    mean = sum(recent) / len(recent)
    variance = sum((value - mean) ** 2 for value in recent) / len(recent)
    if amplitude > 0.85 and quality > 0.85 and disturbance < 0.2:
        phase = "peak"
    elif amplitude > 0.70 and quality > 0.75 and disturbance < 0.4:
        phase = "elevated"
    elif disturbance > 0.7 or quality < 0.5:
        phase = "disturbed"
    else:
        phase = "stable"
    harmonics = [
        {"frequency": fundamental_hz, "amplitude": amplitude, "name": "Fundamental (n=1)"},
        {"frequency": 14.3 * (0.92 + disturbance * 0.08), "amplitude": amplitude * 0.7, "name": "2nd Mode (n=2)"},
        {"frequency": 20.8 * (0.88 + disturbance * 0.12), "amplitude": amplitude * 0.5, "name": "3rd Mode (n=3)"},
        {"frequency": 27.3 * (0.84 + disturbance * 0.16), "amplitude": amplitude * 0.35, "name": "4th Mode (n=4)"},
    ]
    return {
        "fundamentalHz": fundamental_hz,
        "amplitude": amplitude,
        "quality": quality,
        "variance": variance,
        "coherenceBoost": coherence_boost,
        "resonancePhase": phase,
        "earthDisturbance": disturbance,
        "harmonics": harmonics,
        "truthStatus": "real_derived",
        "sourceId": SCHUMANN_DERIVED_SOURCE_ID,
        "sourceUrl": SCHUMANN_DERIVED_SOURCE_URL,
        "sourceTimestamp": _utc_iso_from_epoch(latest_stamp),
        "collectedAt": _utc_iso_from_epoch(received_at),
        "freshnessTtlSeconds": NOAA_SOURCE_MAX_AGE_SEC,
        "generatedValues": False,
        "derivation": "Aureon HNC Schumann proxy from live NOAA planetary Kp; not a direct station measurement",
    }



def _schumann_phase_from_status(status: Any) -> str | None:
    return SCHUMANN_PHASE_BY_STATUS.get(str(status or "").strip().lower())


def _read_sungeo_schumann_activity(
    payload: Any,
    received_at: int,
    *,
    station_payload: Any | None = None,
) -> Dict[str, Any] | None:
    """Read SunGeo public Schumann station activity without inventing Hz values.

    SunGeo's current endpoint publishes a station-backed activity score/status
    and station counts, but it does not publish a measured fundamental
    frequency or calibrated amplitude. The returned shape keeps the existing UI
    contract alive with a nominal frequency reference while marking
    frequencyReported=false so downstream code cannot treat it as a measured Hz
    feed or trading/coherence gate.
    """
    now = time.time()
    if not isinstance(payload, dict):
        return None
    updated = _source_time_epoch(payload.get("updated_at"))
    score = _finite_number(payload.get("score"), 0.0, 100.0)
    phase = _schumann_phase_from_status(payload.get("status"))
    station_count_value = _finite_number(payload.get("stations"), 0.0, 100.0)
    monitored_value = _finite_number(payload.get("stations_monitored"), 0.0, 100.0)
    if monitored_value is None and station_count_value is not None:
        monitored_value = station_count_value
    if (
        updated is None
        or score is None
        or phase is None
        or station_count_value is None
        or station_count_value <= 0
        or monitored_value is None
        or monitored_value <= 0
        or station_count_value > monitored_value
        or received_at <= 0
        or received_at / 1000.0 > now + 5.0
        or now - updated > SCHUMANN_SUNGEO_MAX_AGE_SEC
        or now - (received_at / 1000.0) > SCHUMANN_SUNGEO_MAX_AGE_SEC
    ):
        return None

    station_signals: list[Dict[str, Any]] = []
    station_scores: list[float] = []
    if isinstance(station_payload, dict):
        for source, station in sorted(station_payload.items()):
            if not isinstance(station, dict):
                continue
            station_score = _finite_number(station.get("score"), 0.0, 100.0)
            station_updated = _source_time_epoch(station.get("updated_at"))
            station_phase = _schumann_phase_from_status(station.get("status"))
            source_name = _short_text(source, limit=80)
            if (
                station_score is None
                or station_updated is None
                or station_phase is None
                or not source_name
                or now - station_updated > SCHUMANN_SUNGEO_MAX_AGE_SEC
            ):
                continue
            station_scores.append(station_score)
            station_signals.append({
                "source": source_name,
                "status": str(station.get("status") or "").strip().lower(),
                "activityScore": station_score,
                "timestamp": _utc_iso_from_epoch(station_updated),
            })

    observed_scores = [score] + station_scores
    score_mean = sum(observed_scores) / len(observed_scores)
    score_variance = sum((value - score_mean) ** 2 for value in observed_scores) / len(observed_scores)
    quality = max(0.0, min(1.0, station_count_value / monitored_value))
    normalized_score = score / 100.0
    attribution = _short_text(payload.get("attribution"), limit=260)
    return {
        "measurementKind": "station_activity",
        "frequencyReported": False,
        "frequencyBasis": "nominal_reference_not_source_measurement",
        "fundamentalHz": 7.83,
        "amplitude": normalized_score,
        "activityScore": score,
        "quality": quality,
        "variance": score_variance / 10_000.0,
        "coherenceBoost": 0.0,
        "resonancePhase": phase,
        "earthDisturbance": normalized_score,
        "harmonics": [],
        "stationCount": int(station_count_value),
        "stationsMonitored": int(monitored_value),
        "stationSignals": station_signals,
        "truthStatus": "real_observed",
        "sourceId": SCHUMANN_SUNGEO_SOURCE_ID,
        "sourceUrl": SCHUMANN_SUNGEO_CURRENT_SOURCE,
        "stationSourceUrl": SCHUMANN_SUNGEO_STATIONS_SOURCE,
        "sourceTimestamp": _utc_iso_from_epoch(updated),
        "collectedAt": _utc_iso_from_epoch(received_at),
        "freshnessTtlSeconds": SCHUMANN_SUNGEO_MAX_AGE_SEC,
        "generatedValues": False,
        "derivation": (
            "SunGeo public Schumann station activity score across monitoring stations; "
            "frequency and calibrated amplitude are not reported by this source"
        ),
        "attribution": attribution,
    }


def _unavailable_schumann_proxy_receipt(reason: str) -> Dict[str, Any]:
    return {
        "truthStatus": "no_data",
        "sourceId": SCHUMANN_DERIVED_SOURCE_ID,
        "sourceUrl": SCHUMANN_DERIVED_SOURCE_URL,
        "generatedValues": False,
        "reason": _short_text(reason, limit=220) or "schumann_proxy_unavailable",
        "derivation": "Aureon HNC Schumann proxy from live NOAA planetary Kp; not a direct station measurement",
    }


def _read_usgs_observation(payload: Any, received_at: int) -> Dict[str, Any] | None:
    if not isinstance(payload, dict):
        return None
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    generated = _source_time_epoch(metadata.get("generated"))
    features = payload.get("features")
    if (
        payload.get("type") != "FeatureCollection"
        or metadata.get("status") != 200
        or generated is None
        or time.time() - generated > USGS_SOURCE_MAX_AGE_SEC
        or not isinstance(features, list)
        or not isinstance(metadata.get("count"), int)
        or metadata.get("count") != len(features)
    ):
        return None
    events: list[Dict[str, Any]] = []
    for item in features:
        if not isinstance(item, dict):
            continue
        props = item.get("properties") if isinstance(item.get("properties"), dict) else {}
        geom = item.get("geometry") if isinstance(item.get("geometry"), dict) else {}
        coords = geom.get("coordinates")
        occurred = _source_time_epoch(props.get("time"))
        event_id = str(item.get("id") or "").strip()
        if (
            item.get("type") != "Feature"
            or not event_id
            or occurred is None
            or geom.get("type") != "Point"
            or not isinstance(coords, list)
            or len(coords) < 2
            or _finite_number(coords[0], -180.0, 180.0) is None
            or _finite_number(coords[1], -90.0, 90.0) is None
        ):
            continue
        updated = _source_time_epoch(props.get("updated"))
        depth = _finite_number(coords[2]) if len(coords) > 2 else None
        mag = _finite_number(props.get("mag"))
        place = str(props.get("place") or "").strip() or None
        events.append({
            "id": event_id,
            "magnitude": mag,
            "location": place,
            "depthKm": depth,
            "occurredAt": _utc_iso_from_epoch(occurred),
            "updatedAt": _utc_iso_from_epoch(updated) if updated is not None else None,
            "latitude": float(coords[1]),
            "longitude": float(coords[0]),
        })
    if features and not events:
        return None
    events.sort(key=lambda item: item["occurredAt"], reverse=True)
    return {
        "source": USGS_EARTHQUAKE_SOURCE,
        "generatedAt": _utc_iso_from_epoch(generated),
        "receivedAt": _utc_iso_from_epoch(received_at),
        "events": events,
        "returnedCount": len(features),
        "rejectedCount": len(features) - len(events),
    }


def _read_resonance_one(payload: Any, received_at: int) -> Dict[str, Any] | None:
    now = time.time()
    if not isinstance(payload, dict):
        return None
    window = payload.get("observation_window") if isinstance(payload.get("observation_window"), dict) else {}
    updated = _source_time_epoch(payload.get("updated_at"))
    start = _source_time_epoch(window.get("start"))
    end = _source_time_epoch(window.get("end"))
    activity = _finite_number(payload.get("activity_index"), 0.0, 100.0)
    source = str(payload.get("data_source") or "").strip()
    if (
        updated is None or start is None or end is None or activity is None or not source
        or start >= end or end - start > 90 * 60
        or end > updated or now - updated > RESONANCE_ONE_UPDATE_MAX_AGE_SEC
        or now - end > RESONANCE_ONE_WINDOW_MAX_AGE_SEC
        or received_at <= 0 or received_at / 1000.0 > now + 5.0
        or now - (received_at / 1000.0) > RESONANCE_ONE_UPDATE_MAX_AGE_SEC
    ):
        return None
    weights = payload.get("weighting") if isinstance(payload.get("weighting"), dict) else {}
    schumann_w = _finite_number(weights.get("schumann_pct"), 0.0, 100.0)
    kp_w = _finite_number(weights.get("kp_pct"), 0.0, 100.0)
    solar_w = _finite_number(weights.get("solar_pct"), 0.0, 100.0)
    weighting = None
    if schumann_w is not None and kp_w is not None and solar_w is not None and abs(schumann_w + kp_w + solar_w - 100.0) < 0.001:
        weighting = {"schumann": schumann_w, "kp": kp_w, "solar": solar_w}
    attribution = payload.get("attribution") if isinstance(payload.get("attribution"), dict) else {}
    return {
        "source": RESONANCE_ONE_SOURCE,
        "dataSource": source,
        "updatedAt": _utc_iso_from_epoch(updated),
        "windowStart": _utc_iso_from_epoch(start),
        "windowEnd": _utc_iso_from_epoch(end),
        "receivedAt": _utc_iso_from_epoch(received_at),
        "activityIndex": activity,
        "schumannIndex": _finite_number(payload.get("schumann_index"), 0.0, 100.0),
        "kpIndex": _finite_number(payload.get("kp_index"), 0.0, 9.0),
        "solarFlareIndex": _finite_number(payload.get("solar_flare_index"), 0.0, 100.0),
        "localInterference": payload.get("local_interference") if isinstance(payload.get("local_interference"), bool) else None,
        "dataQuality": str(payload.get("data_quality") or "").strip() or None,
        "confidenceScore": _finite_number(payload.get("confidence_score"), 0.0, 100.0),
        "weighting": weighting,
        "attribution": {
            "schumann": str(attribution.get("schumann") or "").strip() or None,
            "kp": str(attribution.get("kp") or "").strip() or None,
            "solar": str(attribution.get("solar") or "").strip() or None,
        },
    }


def _research_source_error(source: str, exc: Exception) -> Dict[str, Any]:
    reason = f"{source}_source_unavailable:{type(exc).__name__}:{exc}"
    return _unavailable_research_receipt(source, reason)


def _company_brain_fabric_verification() -> Dict[str, Any]:
    """Project generated Agent Company brain-fabric evidence for the live UI."""

    root = Path(__file__).resolve().parents[2]
    candidates = (
        root / "frontend" / "public" / "aureon_agent_company_bill_list.json",
        root / "docs" / "audits" / "aureon_agent_company_bill_list.json",
    )
    path = next((item for item in candidates if item.exists()), candidates[0])
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001 - runtime projection must degrade, not 500
        return {
            "available": False,
            "truth_status": "no_data",
            "generated_values": False,
            "read_state": "failed",
            "reason": f"agent_company_brain_fabric_read_failed:{type(exc).__name__}",
            "source": "aureon_agent_company_bill_list",
            "source_path": str(path),
            "routing_live": False,
            "execution_ready": False,
            "blockers": ["agent_company_brain_fabric_report_unavailable"],
        }
    if not isinstance(report, dict):
        return {
            "available": False,
            "truth_status": "no_data",
            "generated_values": False,
            "read_state": "invalid",
            "reason": "agent_company_brain_fabric_report_malformed",
            "source": "aureon_agent_company_bill_list",
            "source_path": str(path),
            "routing_live": False,
            "execution_ready": False,
            "blockers": ["agent_company_brain_fabric_report_malformed"],
        }
    brain = report.get("brain_fabric") if isinstance(report.get("brain_fabric"), dict) else {}
    summary = report.get("summary") if isinstance(report.get("summary"), dict) else {}
    passport_count = _bounded_count(brain.get("brain_passport_count"))
    routed_count = _bounded_count(brain.get("hnc_routed_brain_count"))
    canonical_count = _bounded_count(brain.get("canonical_role_count"))
    routing_live = bool(
        brain.get("routing_live") is True
        or (
            brain.get("all_brains_hnc_routed") is True
            and passport_count is not None
            and routed_count == passport_count
            and passport_count > 0
        )
    )
    execution_ready = bool(brain.get("ready") is True or brain.get("execution_ready") is True)
    blockers = [str(item)[:120] for item in brain.get("blockers", []) if isinstance(item, str) and item.strip()]
    if routing_live and not execution_ready and "authenticated_truth_authority_bundle_required_for_executable_work" not in blockers:
        blockers.append("authenticated_truth_authority_bundle_required_for_executable_work")
    return {
        "available": True,
        "truth_status": "real_derived",
        "generated_values": False,
        "read_state": "observed",
        "source": "aureon_agent_company_bill_list",
        "source_path": str(path),
        "source_generated_at": _short_text(report.get("generated_at"), limit=80),
        "report_status": _short_text(report.get("status"), limit=120),
        "brain_fabric_status": _short_text(brain.get("status"), limit=120),
        "routing_live": routing_live,
        "execution_ready": execution_ready,
        "brain_fabric_ready": brain.get("ready") is True,
        "truth_gate_enforced": brain.get("truth_gate_enforced") is True,
        "provider_mode": _short_text(brain.get("provider_mode"), limit=120),
        "hnc_routed_brain_count": routed_count,
        "brain_passport_count": passport_count,
        "canonical_role_count": canonical_count,
        "agent_brain_count": _bounded_count(brain.get("agent_brain_count")),
        "process_brain_count": _bounded_count(brain.get("process_brain_count")),
        "all_brains_hnc_routed": brain.get("all_brains_hnc_routed") is True,
        "tools_enabled": brain.get("tools_enabled") is True,
        "action_eligible": brain.get("action_eligible") is True,
        "economic_eligible": brain.get("economic_eligible") is True,
        "summary_routing_live": summary.get("brain_fabric_routing_live") is True,
        "blockers": blockers,
    }


def _project_runtime_organ(row: Any) -> Dict[str, Any] | None:
    if not isinstance(row, dict):
        return None
    name = _short_text(row.get("name"), limit=100)
    if name is None:
        return None
    return {
        "name": name,
        "pid": _bounded_count(row.get("pid")),
        "pid_running": row.get("pid_running") if isinstance(row.get("pid_running"), bool) else None,
        "identity_verified": row.get("identity_verified") is True,
        "launch_time_consistent": row.get("launch_time_consistent") is True,
        "functional_health": _short_text(row.get("functional_health"), limit=80) or "unknown",
        "read_state": _short_text(row.get("read_state"), limit=80) or "unavailable",
        "reason": _short_text(row.get("reason"), limit=160),
    }


def _company_runtime_binding_manifest() -> Dict[str, Any]:
    """Read optional role-to-running-service bindings without treating them as workers."""

    root = Path(__file__).resolve().parents[2]
    candidates: list[Path] = []
    configured = _short_text(os.environ.get("AUREON_AGENT_COMPANY_RUNTIME_BINDING_PATH"), limit=260)
    if configured:
        candidates.append(Path(configured))
    candidates.extend((
        root / "frontend" / "public" / "aureon_agent_company_runtime_bindings.json",
        root / "docs" / "audits" / "aureon_agent_company_runtime_bindings.json",
    ))
    path = next((item for item in candidates if item.exists()), candidates[0] if candidates else root / "frontend" / "public" / "aureon_agent_company_runtime_bindings.json")
    if not path.exists():
        return {
            "available": False,
            "read_state": "missing",
            "truth_status": "no_data",
            "generated_values": False,
            "source_path": str(path),
            "bindings": [],
            "reason": "role_runtime_binding_manifest_missing",
        }
    try:
        report = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError, UnicodeError):
        return {
            "available": False,
            "read_state": "failed",
            "truth_status": "no_data",
            "generated_values": False,
            "source_path": str(path),
            "bindings": [],
            "reason": "role_runtime_binding_manifest_unreadable_or_invalid",
        }
    bindings = report.get("bindings")
    if (
        report.get("schema_version") != "aureon-agent-company-runtime-bindings-v1"
        or report.get("truth_status") != "real_derived"
        or report.get("generated_values") is not False
        or not isinstance(bindings, list)
        or len(bindings) > 256
    ):
        return {
            "available": False,
            "read_state": "failed",
            "truth_status": "no_data",
            "generated_values": False,
            "source_path": str(path),
            "bindings": [],
            "reason": "role_runtime_binding_manifest_schema_invalid",
        }
    projected: list[Dict[str, Any]] = []
    for row in bindings:
        if not isinstance(row, dict):
            continue
        role_id = _short_text(row.get("role_id"), limit=100)
        organ_name = _short_text(row.get("organ_name"), limit=100)
        claim = _short_text(row.get("claim"), limit=120) or "live_service_surface_binding_only"
        binding_kind = _short_text(row.get("binding_kind"), limit=80) or "service_surface"
        if not role_id or not organ_name or claim != "live_service_surface_binding_only":
            continue
        evidence = row.get("evidence") if isinstance(row.get("evidence"), list) else []
        projected.append({
            "role_id": role_id,
            "organ_name": organ_name,
            "binding_kind": binding_kind,
            "claim": claim,
            "source": _short_text(row.get("source"), limit=160) or "aureon_agent_company_runtime_bindings",
            "evidence": [_short_text(item, limit=180) for item in evidence if _short_text(item, limit=180)][:8],
        })
    held_raw = report.get("held_planned_bindings") if isinstance(report.get("held_planned_bindings"), list) else []
    held_projected: list[Dict[str, Any]] = []
    for row in held_raw:
        if not isinstance(row, dict):
            continue
        role_id = _short_text(row.get("role_id"), limit=100)
        missing = row.get("missing_surfaces") if isinstance(row.get("missing_surfaces"), list) else []
        missing_surfaces = [_short_text(item, limit=160) for item in missing if _short_text(item, limit=160)][:8]
        if role_id and missing_surfaces:
            held_projected.append({"role_id": role_id, "missing_surfaces": missing_surfaces})
    held_count = _bounded_count(report.get("held_count"))
    if held_count is None:
        held_count = len(held_projected)
    return {
        "available": True,
        "read_state": "observed",
        "truth_status": "real_derived",
        "generated_values": False,
        "source_path": str(path),
        "source_generated_at": _short_text(report.get("generated_at"), limit=80),
        "binding_count": len(projected),
        "held_count": held_count,
        "held_planned_bindings": held_projected,
        "bindings": projected,
        "scope_note": "Role bindings prove a configured role has a live service surface to work through. They do not prove an autonomous employee process or grant tool/exchange authority.",
    }


def _manifest_role_runtime_matches(
    roles: list[Dict[str, Any]],
    running_organs: list[Dict[str, Any]],
    manifest: Dict[str, Any],
) -> list[Dict[str, Any]]:
    role_ids = {str(role.get("role_id")) for role in roles if isinstance(role, dict) and role.get("role_id")}
    running_by_name = {
        row["name"]: row
        for row in running_organs
        if row.get("identity_verified") is True and row.get("pid_running") is True
    }
    matches: list[Dict[str, Any]] = []
    seen: set[str] = set()
    if manifest.get("available") is not True:
        return matches
    for binding in manifest.get("bindings", []):
        if not isinstance(binding, dict):
            continue
        role_id = _short_text(binding.get("role_id"), limit=100)
        organ_name = _short_text(binding.get("organ_name"), limit=100)
        if not role_id or not organ_name or role_id not in role_ids or role_id in seen:
            continue
        organ = running_by_name.get(organ_name)
        if organ is None:
            continue
        matches.append({
            "role_id": role_id,
            "organ_name": organ_name,
            "pid": organ.get("pid"),
            "binding_kind": _short_text(binding.get("binding_kind"), limit=80) or "service_surface",
            "claim": "live_service_surface_binding_only",
            "source": _short_text(binding.get("source"), limit=160) or "aureon_agent_company_runtime_bindings",
            "evidence": binding.get("evidence") if isinstance(binding.get("evidence"), list) else [],
        })
        seen.add(role_id)
    return matches


def _company_runtime_verification(roles: list[Dict[str, Any]], process: Dict[str, Any]) -> Dict[str, Any]:
    """Summarize live organ liveness for the company roster without inventing role bindings.

    The workforce catalogue contains configured roles. The organ registry contains
    runtime processes. Until an authoritative role_id-to-organ binding manifest exists,
    this function reports both facts separately and refuses to mark the workforce itself
    as live.
    """
    process = process if isinstance(process, dict) else {}
    raw_counts = process.get("counts") if isinstance(process.get("counts"), dict) else {}

    def count(name: str) -> int | None:
        return _bounded_count(raw_counts.get(name))

    registered = count("registered")
    measured = count("measured")
    running_verified = count("running_verified")
    running_unverified = count("running_unverified")
    absent = count("absent")
    unknown = count("unknown")
    running_total = None
    if running_verified is not None or running_unverified is not None:
        running_total = (running_verified or 0) + (running_unverified or 0)

    organs = process.get("organs") if isinstance(process.get("organs"), list) else []
    projected_organs = [item for item in (_project_runtime_organ(row) for row in organs) if item is not None]
    running_organs = [row for row in projected_organs if row.get("pid_running") is True]
    stopped_organs = [row for row in projected_organs if row.get("pid_running") is not True]

    role_by_id: dict[str, Dict[str, Any]] = {}
    ordered_role_ids: list[str] = []
    for role in roles:
        if not isinstance(role, dict) or not role.get("role_id"):
            continue
        role_id = str(role.get("role_id"))
        if role_id in role_by_id:
            continue
        role_by_id[role_id] = role
        ordered_role_ids.append(role_id)
    role_ids = set(ordered_role_ids)
    exact_role_matches = [
        {
            "role_id": row["name"],
            "organ_name": row["name"],
            "pid": row.get("pid"),
            "binding_kind": "exact_runtime_organ",
            "claim": "verified_running_role_process",
            "source": "registered_pid_os_probe",
            "evidence": ["role_id equals identity-verified running organ name"],
        }
        for row in running_organs
        if row["name"] in role_ids and row.get("identity_verified") is True
    ]
    runtime_binding_manifest = _company_runtime_binding_manifest()
    role_surface_gaps = runtime_binding_manifest.get("held_planned_bindings") if isinstance(runtime_binding_manifest.get("held_planned_bindings"), list) else []
    role_surface_gap_count = len(role_surface_gaps)
    manifest_role_matches = _manifest_role_runtime_matches(roles, running_organs, runtime_binding_manifest)
    role_match_by_id = {row["role_id"]: row for row in exact_role_matches}
    for row in manifest_role_matches:
        role_match_by_id.setdefault(row["role_id"], row)
    role_matches = list(role_match_by_id.values())
    matched_role_ids = {str(row.get("role_id")) for row in role_matches if row.get("role_id")}
    unbound_roles: list[Dict[str, Any]] = []
    unbound_roles_by_department: dict[str, list[Dict[str, str]]] = {}
    bound_roles_by_department: dict[str, int] = {}
    service_surface_bindings_by_organ: dict[str, int] = {}
    for match in role_matches:
        role_id = str(match.get("role_id"))
        role = role_by_id.get(role_id, {})
        department = _short_text(role.get("department"), limit=100) or "unknown"
        bound_roles_by_department[department] = bound_roles_by_department.get(department, 0) + 1
        organ_name = _short_text(match.get("organ_name"), limit=100) or "unknown"
        service_surface_bindings_by_organ[organ_name] = service_surface_bindings_by_organ.get(organ_name, 0) + 1
    for role_id in ordered_role_ids:
        if role_id in matched_role_ids:
            continue
        role = role_by_id[role_id]
        department = _short_text(role.get("department"), limit=100) or "unknown"
        unbound = {
            "role_id": role_id,
            "title": _short_text(role.get("title"), limit=140) or role_id,
            "authority_level": _short_text(role.get("authority_level"), limit=120) or "unknown",
        }
        unbound_roles.append(unbound)
        unbound_roles_by_department.setdefault(department, []).append(unbound)
    role_binding_available = bool(role_matches)
    if len(role_matches) == len(role_ids) and role_ids:
        role_binding_state = "verified"
    elif role_matches:
        role_binding_state = "partial"
    else:
        role_binding_state = "unavailable"

    blockers: list[str] = []
    available = process.get("available") is True and process.get("fresh") is True and process.get("read_state") == "observed"
    if not available:
        live_company_operation_state = "runtime_probe_unavailable"
    elif len(role_matches) == len(role_ids) and role_ids:
        live_company_operation_state = (
            "all_configured_roles_have_live_service_surfaces_with_declared_surface_gaps_action_held"
            if role_surface_gap_count
            else "all_configured_roles_have_live_service_surfaces_action_held"
        )
    elif role_matches:
        live_company_operation_state = "partial_live_service_surfaces_action_held"
    else:
        live_company_operation_state = "configured_catalogue_only_runtime_unbound"
    if not available:
        blockers.append(_short_text(process.get("reason"), limit=120) or "registered_pid_os_probe_unavailable")
    if not role_binding_available:
        blockers.append("agent_role_to_runtime_organ_binding_manifest_unavailable")
    elif len(role_matches) < len(role_ids):
        blockers.append("agent_role_to_runtime_organ_binding_manifest_partial")
    if role_surface_gap_count:
        blockers.append("agent_role_declared_surface_gaps_remain")

    brain_fabric_verification = _company_brain_fabric_verification()

    return {
        "available": available,
        "fresh": process.get("fresh") is True,
        "read_state": _short_text(process.get("read_state"), limit=80) or "unavailable",
        "truth_status": "real_observed" if available else "no_data",
        "generated_values": False,
        "source": _short_text(process.get("source"), limit=120) or "registered_pid_os_probe",
        "source_path": _short_text(process.get("source_path"), limit=260),
        "source_timestamp": process.get("source_timestamp") if isinstance(process.get("source_timestamp"), (int, float)) and not isinstance(process.get("source_timestamp"), bool) else None,
        "receipt_timestamp": process.get("receipt_timestamp") if isinstance(process.get("receipt_timestamp"), (int, float)) and not isinstance(process.get("receipt_timestamp"), bool) else None,
        "age_seconds": process.get("age_seconds") if isinstance(process.get("age_seconds"), (int, float)) and not isinstance(process.get("age_seconds"), bool) else None,
        "max_age_seconds": process.get("max_age_seconds") if isinstance(process.get("max_age_seconds"), (int, float)) and not isinstance(process.get("max_age_seconds"), bool) else None,
        "source_clock_kind": _short_text(process.get("source_clock_kind"), limit=80) or "os_process_measurement",
        "identity_receipt_read_state": _short_text(process.get("identity_receipt_read_state"), limit=80),
        "configured_role_count": len(roles),
        "verified_running_role_count": len(role_matches),
        "runtime_role_binding_available": role_binding_available,
        "role_binding_state": role_binding_state,
        "live_company_operation_state": live_company_operation_state,
        "matching_rule": "exact_role_id_or_manifest_live_service_surface_binding",
        "running_role_matches": role_matches[:80],
        "exact_running_role_match_count": len(exact_role_matches),
        "manifest_running_role_match_count": len(manifest_role_matches),
        "unbound_role_count": len(unbound_roles),
        "role_surface_gap_count": role_surface_gap_count,
        "role_surface_gaps": role_surface_gaps,
        "bound_roles_by_department": bound_roles_by_department,
        "unbound_roles_by_department": unbound_roles_by_department,
        "service_surface_bindings_by_organ": service_surface_bindings_by_organ,
        "runtime_binding_manifest": {key: value for key, value in runtime_binding_manifest.items() if key != "bindings"},
        "organ_counts": {
            "registered": registered,
            "measured": measured,
            "running_verified": running_verified,
            "running_unverified": running_unverified,
            "running_total": running_total,
            "absent": absent,
            "unknown": unknown,
        },
        "sample_running_organs": running_organs[:12],
        "sample_stopped_organs": stopped_organs[:12],
        "blockers": blockers,
        "brain_fabric_verification": brain_fabric_verification,
        "scope_note": "Registered PID liveness and launch identity only. Manifest role bindings prove live service surfaces for configured roles, not autonomous employee processes. Brain-fabric routing is reported separately from executable tool/action authority.",
    }


def register_saas_routes(app: Any) -> Any:
    """Mount the SaaS catalog/status routes onto an existing Flask app."""
    from flask import g, jsonify, request

    from aureon.core.jsonsafe import json_safe
    from aureon.saas.catalog import build_catalog, render_manifests, write_frontend_manifests
    from aureon.saas.cognitive import provenance_block
    from aureon.saas.domains import (
        PRODUCT_DOMAINS,
        domain_health,
        domain_report,
        probe_domain,
    )
    from aureon.saas.status import get_platform_status

    def _stamp(payload: Dict[str, Any], truth_status: str) -> Dict[str, Any]:
        """Attach the shared provenance header + an honest top-level truth_status
        so every SaaS surface carries data provenance (compliance)."""
        return {**payload, "provenance": provenance_block(), "truth_status": truth_status}

    jwt_secret = str(os.environ.get("AUREON_SUPABASE_JWT_SECRET", "") or "")
    tenant_auth_configured = bool(
        jwt_secret
        or (
            str(os.environ.get("AUREON_SUPABASE_URL", "") or "").strip()
            and str(os.environ.get("AUREON_SUPABASE_PUBLISHABLE_KEY", "") or "").strip()
        )
    )

    def _tenant_ok() -> bool:
        """When a Supabase JWT secret is configured, require a valid tenant token."""
        if not tenant_auth_configured:
            return True  # tenancy bridge disabled
        # The admin/operator bearer is NOT a Supabase JWT, so it can never satisfy the check below.
        # Without this branch, stacking @_guarded over @_admin_only 401s the operator before the
        # admin check is even reached — locking every identity out of those control-plane routes.
        # ``g.is_admin`` is set only by the operator gate, which has already authenticated the
        # bearer in constant time; absent (bare-app mount) ⇒ False ⇒ the JWT path below, unchanged.
        if getattr(g, "identity_kind", None) in {"admin", "tenant"}:
            return True
        if not jwt_secret:
            return False
        auth = request.headers.get("Authorization", "")
        if not auth.startswith("Bearer "):
            return False
        claims = verify_supabase_jwt(auth[len("Bearer "):].strip(), jwt_secret)
        if claims is None:
            return False
        g.tenant = claims.get("sub")  # user id for downstream scoping
        return True

    def _guarded(fn):
        def wrapper(*a, **k):
            if not _tenant_ok():
                return jsonify({"error": {"code": 401, "message": "valid Supabase token required"}}), 401
            return fn(*a, **k)
        wrapper.__name__ = fn.__name__
        return wrapper

    def _admin_only(fn):
        """Operator-only control-plane route: refuse a signed-in end user (tenant).

        ``g.is_admin`` is set by the operator's request gate (admin bearer or the open
        single-operator default ⇒ True). It is absent when these routes are mounted on a bare app
        (e.g. the compliance audit), so the default is permissive and nothing changes there.
        """
        def wrapper(*a, **k):
            if not getattr(g, "is_admin", True):
                return jsonify({"error": {"code": 403, "message": "this control-plane route is "
                                                                  "operator-only", "plane": "admin"}}), 403
            return fn(*a, **k)
        wrapper.__name__ = fn.__name__
        return wrapper

    def _authenticated_admin_only(fn):
        """Require the configured operator bearer, never the open dev plane.

        This stronger boundary is reserved for decisions that may later be
        consumed as authority. ``open`` remains useful for local read-only
        development, but it is not an authenticated owner identity.
        """
        def wrapper(*a, **k):
            if getattr(g, "identity_kind", None) != "admin":
                return jsonify({
                    "error": {
                        "code": 403,
                        "message": "authenticated operator bearer required",
                        "plane": "admin",
                    }
                }), 403
            return fn(*a, **k)
        wrapper.__name__ = fn.__name__
        return wrapper

    @app.get("/api/catalog")
    @_guarded
    def saas_catalog():
        # Counts are derived from a real filesystem scan of aureon/.
        return jsonify(_stamp(build_catalog(use_cache=True), "real_derived"))

    @app.get("/api/domains")
    @_guarded
    def saas_domains():
        # Every domain carries a real operational health rollup (module/dashboard/wiring counts,
        # LOC, capabilities) derived from the filesystem scan — not just import-reachability.
        catalog = build_catalog(use_cache=True)
        return jsonify(_stamp(
            {"product_domains": PRODUCT_DOMAINS, "domains": domain_report(catalog=catalog)},
            "real_derived"))

    @app.get("/api/domains/<domain>")
    @_guarded
    def saas_domain(domain: str):
        catalog = build_catalog(use_cache=True)
        systems = [
            s for cat in catalog.get("categories", {}).values() for s in cat["systems"]
            if s.get("fs_domain") == domain or s.get("product_domain") == domain
        ]
        return jsonify(_stamp(
            {"domain": domain, "entry": probe_domain(domain),
             "health": domain_health(domain, catalog),
             "system_count": len(systems), "systems": systems[:200]}, "real_derived"))

    @app.get("/api/research/noaa/<feed>")
    @_guarded
    def api_research_noaa(feed: str):
        feed = str(feed or "").strip().lower()
        definition = NOAA_FEEDS.get(feed)
        if definition is None:
            return jsonify({"feed": feed, "status": "unavailable", "receivedAt": None, "samples": [], "reason": "NOAA feed is not allowlisted"}), 404
        if no_external_api_calls():
            return jsonify(_unavailable_research_receipt(f"noaa_{feed}", "AUREON_NO_EXTERNAL_API_CALLS", source_url=str(definition["url"])))
        try:
            payload, received_at = _bounded_public_json(str(definition["url"]))
            return jsonify(_read_noaa_feed(feed, payload, received_at))
        except Exception as exc:  # noqa: BLE001 - read-only source projection must degrade without 500
            logger.warning("NOAA research source unavailable for %s: %s", feed, exc)
            receipt = _research_source_error(f"noaa_{feed}", exc)
            receipt.update({"feed": feed, "status": "unavailable", "receivedAt": None, "samples": [], "source_url": definition["url"]})
            return jsonify(receipt)

    @app.get("/api/research/schumann")
    @_guarded
    def api_research_schumann():
        if no_external_api_calls():
            return jsonify(_unavailable_schumann_proxy_receipt("AUREON_NO_EXTERNAL_API_CALLS"))
        direct_reason = ""
        try:
            payload, received_at = _bounded_public_json(SCHUMANN_SUNGEO_CURRENT_SOURCE)
            station_payload = None
            try:
                station_payload, _station_received_at = _bounded_public_json(SCHUMANN_SUNGEO_STATIONS_SOURCE)
            except Exception as station_exc:  # noqa: BLE001 - optional station detail must not break aggregate
                logger.info("SunGeo station detail source unavailable: %s", station_exc)
            observation = _read_sungeo_schumann_activity(payload, received_at, station_payload=station_payload)
            if observation is not None:
                return jsonify(observation)
            direct_reason = "SunGeo station activity source is stale, incomplete or malformed"
        except Exception as exc:  # noqa: BLE001 - read-only source projection must degrade without 500
            logger.warning("SunGeo Schumann station source unavailable: %s", exc)
            direct_reason = f"sungeo_source_unavailable:{type(exc).__name__}:{exc}"

        try:
            payload, received_at = _bounded_public_json(SCHUMANN_DERIVED_SOURCE_URL)
            observation = _read_schumann_proxy(payload, received_at)
            if observation is None:
                return jsonify(_unavailable_schumann_proxy_receipt(direct_reason or "NOAA Kp source is stale, incomplete or malformed"))
            if direct_reason:
                observation["directObservationAvailable"] = False
                observation["directObservationReason"] = _short_text(direct_reason, limit=220)
            return jsonify(observation)
        except Exception as exc:  # noqa: BLE001 - read-only source projection must degrade without 500
            logger.warning("Schumann proxy source unavailable: %s", exc)
            return jsonify(_unavailable_schumann_proxy_receipt(direct_reason or f"schumann_proxy_source_unavailable:{type(exc).__name__}:{exc}"))

    @app.get("/api/research/usgs-earthquakes")
    @_guarded
    def api_research_usgs_earthquakes():
        if no_external_api_calls():
            return jsonify(_unavailable_research_receipt("usgs_earthquakes", "AUREON_NO_EXTERNAL_API_CALLS", source_url=USGS_EARTHQUAKE_SOURCE))
        try:
            payload, received_at = _bounded_public_json(USGS_EARTHQUAKE_SOURCE)
            observation = _read_usgs_observation(payload, received_at)
            if observation is None:
                return jsonify(_unavailable_research_receipt("usgs_earthquakes", "USGS source is stale, incomplete or malformed", source_url=USGS_EARTHQUAKE_SOURCE))
            return jsonify({"payload": payload, "receivedAt": received_at, "observation": observation, "source_url": USGS_EARTHQUAKE_SOURCE})
        except Exception as exc:  # noqa: BLE001 - read-only source projection must degrade without 500
            logger.warning("USGS research source unavailable: %s", exc)
            receipt = _research_source_error("usgs_earthquakes", exc)
            receipt["source_url"] = USGS_EARTHQUAKE_SOURCE
            return jsonify(receipt)

    @app.get("/api/research/resonance-one")
    @_guarded
    def api_research_resonance_one():
        if no_external_api_calls():
            return jsonify(_unavailable_research_receipt("resonance_one", "AUREON_NO_EXTERNAL_API_CALLS", source_url=RESONANCE_ONE_SOURCE))
        try:
            payload, received_at = _bounded_public_json(RESONANCE_ONE_SOURCE, max_bytes=1024 * 1024)
            observation = _read_resonance_one(payload, received_at)
            if observation is None:
                return jsonify(_unavailable_research_receipt("resonance_one", "ResonanceOne report is stale, incomplete or malformed", source_url=RESONANCE_ONE_SOURCE))
            return jsonify({"payload": payload, "receivedAt": received_at, "observation": observation, "source_url": RESONANCE_ONE_SOURCE})
        except Exception as exc:  # noqa: BLE001 - read-only source projection must degrade without 500
            logger.warning("ResonanceOne research source unavailable: %s", exc)
            receipt = _research_source_error("resonance_one", exc)
            receipt["source_url"] = RESONANCE_ONE_SOURCE
            return jsonify(receipt)

    @app.get("/api/coverage")
    @_guarded
    def saas_coverage():
        # Repo-wide coverage audit: reconciles the real aureon/ package tree against the SaaS
        # taxonomy + catalog, proving every domain is surfaced (no uncovered, no phantom).
        # Also carries the benchmark-coverage march (b63): which domains hold a
        # Tier-A pin, the named gap roadmap, and the one-way ratchet verdict.
        from aureon.analytics.benchmark_coverage import (
            build_coverage,
            load_baseline,
            ratchet_check,
        )
        from aureon.saas.coverage import build_coverage_audit

        payload = build_coverage_audit()
        bc = build_coverage()
        payload["benchmark_coverage"] = dict(bc.to_dict(),
                                             ratchet=ratchet_check(bc, load_baseline()))
        return jsonify(_stamp(payload, "real_derived"))

    @app.get("/api/trading/closed-position-analytics")
    @_guarded
    def api_trading_closed_position_analytics():
        range_name = str(request.args.get("range") or "7d").strip().lower()
        if range_name not in {"24h", "7d", "30d", "all"}:
            range_name = "7d"
        tenant_auth = _tenant_bearer_supabase_auth(request.headers)
        # Caller JWTs use upstream RLS. Service credentials are reserved for a
        # verified operator and an explicitly configured account, never open mode
        # or an unverified JWT sub. A failed caller token has no admin fallback.
        tenant_id = str(tenant_auth.get("tenant_id") or "").strip()
        if not tenant_auth:
            if getattr(g, "identity_kind", None) == "admin":
                tenant_id = _analytics_tenant_from_env()
            else:
                response = jsonify(_unavailable_trading_analytics(
                    "Authenticated account and configured Supabase project required",
                    range_name=range_name,
                ))
                response.headers["Cache-Control"] = "no-store"
                return response, 401
        return jsonify(json_safe(_read_supabase_closed_position_analytics(range_name, tenant_id, auth=tenant_auth or None)))

    @app.get("/api/status")
    @_guarded
    def saas_status():
        # Live health reads (import reachability + runtime probes).
        # Missing source ages may be infinite; browsers require strict JSON.
        data = get_platform_status()
        return jsonify(json_safe(_stamp(data, data.get("truth_status", "no_data"))))

    @app.get("/api/organism")
    @_guarded
    def saas_organism():
        # The connectome's honest coverage of the body + recent breaths + mesh.
        # Stamped at the route (not in build_organism_payload, which /api/pulse composes).
        data = build_organism_payload()
        return jsonify(json_safe(_stamp(data, data.get("truth_status", "no_data"))))

    @app.get("/api/metacognition")
    @_guarded
    def saas_metacognition():
        from aureon.saas.observed_runtime import assessment_observation
        data = assessment_observation("metacognition")
        return jsonify(json_safe(_stamp(data, data.get("truth_status", "no_data"))))

    @app.get("/api/affect")
    @_guarded
    def saas_affect():
        from aureon.saas.observed_runtime import assessment_observation
        data = assessment_observation("affect")
        return jsonify(json_safe(_stamp(data, data.get("truth_status", "no_data"))))

    @app.get("/api/soul")
    @_guarded
    def saas_soul():
        from aureon.saas.observed_runtime import assessment_observation
        data = assessment_observation("soul")
        return jsonify(json_safe(_stamp(data, data.get("truth_status", "no_data"))))

    @app.get("/api/inner-work")
    @_guarded
    def saas_inner_work():
        from aureon.saas.observed_runtime import assessment_observation
        data = assessment_observation("inner_work")
        return jsonify(json_safe(_stamp(data, data.get("truth_status", "no_data"))))

    @app.get("/api/pursuit")
    @_guarded
    def saas_pursuit():
        from aureon.saas.observed_runtime import assessment_observation
        data = assessment_observation("pursuit")
        return jsonify(json_safe(_stamp(data, data.get("truth_status", "no_data"))))

    @app.get("/api/approvals")
    @_guarded
    def saas_approvals():
        # The director's desk: the big plays Aureon prepared and is holding for Gary's
        # decision. Read-only. Approving elsewhere records the decision; it never
        # executes the live move.
        try:
            from aureon.core.approval_queue import get_approval_queue

            data = get_approval_queue().summary()
        except Exception as exc:  # noqa: BLE001 — degrade honestly, never 500
            data = {"pending": [], "recent": [], "error": str(exc)[:200]}
        return jsonify(_stamp(data, "real_derived"))

    @app.post("/api/approvals/<item_id>")
    @_guarded
    @_authenticated_admin_only
    def saas_approvals_decide(item_id: str):
        # Record Gary's approve/reject for a prepared big play. This is the human
        # gate — it records the decision and does NOT execute the irreversible move
        # (no consumer fires a live trade/payment/filing/email off it). Bearer-gated.
        from flask import request

        body = request.get_json(silent=True) or {}
        decision = str(body.get("decision") or "").strip().lower()
        note = str(body.get("note") or "")
        if "approver" in body:
            return jsonify(_stamp({
                "ok": False,
                "error": "approver identity is derived by the server",
            }, "no_data")), 400
        if decision not in ("approve", "reject"):
            return jsonify(_stamp({"ok": False, "error": "decision must be 'approve' or 'reject'"},
                                  "no_data")), 400
        try:
            from aureon.core.approval_queue import get_approval_queue

            item = get_approval_queue().decide(
                item_id,
                decision,
                approver="gary-operator-admin",
                note=note,
                auth_context={
                    "identity_kind": "admin",
                    "authn_method": "operator_static_bearer",
                },
            )
        except Exception as exc:  # noqa: BLE001
            return jsonify(_stamp({"ok": False, "error": str(exc)[:200]}, "no_data")), 500
        if item is None:
            return jsonify(_stamp({"ok": False, "error": "unknown or already-decided item"}, "no_data")), 404
        return jsonify(_stamp({"ok": True, "item": item,
                               "note": "decision recorded; execution stays a deliberate human/armed step"},
                              "real_derived"))

    @app.get("/api/company")
    @_guarded
    def saas_company():
        # Aureon's full workforce — every role from the CEO Goal Steward to the Log
        # Janitor, across all eight departments — the company it can staff a fitted
        # crew from. Read-only, offline (the roster is pure data, no cold boot).
        try:
            from aureon.autonomous.aureon_agent_company_builder import DEPARTMENTS, _role_specs

            roles = [{"role_id": r.role_id, "title": r.title, "department": r.department,
                      "seniority": r.seniority, "mission": r.mission,
                      "authority_level": r.authority_level, "tools_allowed": list(r.tools_allowed)}
                     for r in _role_specs()]
            by_dept: dict[str, int] = {}
            for r in roles:
                by_dept[r["department"]] = by_dept.get(r["department"], 0) + 1
            try:
                from aureon.saas.observed_runtime import process_observation

                process_row = process_observation()
            except Exception as exc:  # noqa: BLE001 — runtime observation must degrade, never sink the roster
                process_row = {
                    "available": False,
                    "fresh": False,
                    "read_state": "failed",
                    "reason": f"company_runtime_process_observation_failed:{type(exc).__name__}",
                    "counts": None,
                    "organs": [],
                }
            data = {"departments": DEPARTMENTS, "roles": roles,
                    "summary": {"role_count": len(roles), "department_count": len(DEPARTMENTS),
                                "roles_by_department": by_dept},
                    "runtime_verification": _company_runtime_verification(roles, process_row),
                    "note": "the workforce Aureon staffs a fitted crew from; roles prepare, the "
                            "hard boundary + approval desk gate every irreversible move. Runtime organs are "
                            "observed separately from role configuration."}
            ts = "real_derived"
        except Exception as exc:  # noqa: BLE001 — degrade honestly, never 500
            data = {"departments": [], "roles": [], "error": str(exc)[:200]}
            ts = "no_data"
        return jsonify(_stamp(data, ts))

    @app.get("/api/org")
    @_guarded
    def saas_org():
        # The organization behind Aureon OS — R&A Consulting and Brokerage Services Ltd
        # (trading as Aureon Zorza Technologies), its company number, the Innovate NI Silver
        # recognition, community support and contact — verifiable public facts transcribed
        # from COMPANY.md. Distinct from /api/company, which is the agent workforce roster.
        try:
            from aureon.saas.company_profile import build_company_profile

            profile = build_company_profile()
            return jsonify(_stamp(profile, profile.get("truth_status", "real_derived")))
        except Exception as exc:  # noqa: BLE001 — degrade honestly, never 500
            return jsonify(_stamp({"available": False, "error": str(exc)[:200]}, "no_data"))

    @app.get("/api/consciousness")
    @_guarded
    def saas_consciousness():
        # The organism's inner capabilities, categorized — self-perception, selfhood,
        # purpose, governance, the workforce and the body — each with its purpose,
        # route, safety posture and honest live truth_status. Read-only to inspect;
        # every irreversible move still routes to the director's desk.
        try:
            from aureon.saas.consciousness_catalog import build_consciousness_catalog

            cat = build_consciousness_catalog()
            return jsonify(json_safe(_stamp(cat, cat.get("truth_status", "no_data"))))
        except Exception as exc:  # noqa: BLE001 — degrade honestly, never 500
            return jsonify(_stamp(
                {"available": False, "categories": {}, "surfaces": [], "error": str(exc)[:200]},
                "no_data"))

    @app.get("/api/defense")
    @_guarded
    def saas_defense():
        # The bio family — sensor lanes, the statistical-validity dossier, and the cognitive
        # immune layer (integrity guard · swarm defense · MCP membrane) — grouped, with real
        # passed/metrics/evidence from the committed Tier-A benchmark report and a live
        # bus-trace overlay where a module has run. Read-only; no bio module is run on request.
        try:
            from aureon.saas.defense_catalog import build_defense_catalog

            cat = build_defense_catalog()
            return jsonify(json_safe(_stamp(cat, cat.get("truth_status", "no_data"))))
        except Exception as exc:  # noqa: BLE001 — degrade honestly, never 500
            return jsonify(_stamp(
                {"groups": {}, "group_order": [], "counts": {}, "error": str(exc)[:200]},
                "no_data"))

    @app.get("/api/automation")
    @_guarded
    def saas_automation():
        # Progress toward the whole repo being connected into the organism and driveable
        # by the soul/consciousness logic — one honest percentage decomposed by dimension
        # (connectivity · integration · consciousness · surfacing) and by category.
        # Composed from real coverage signals only; observational, authorizes nothing.
        try:
            from aureon.saas.automation_index import automation_index

            idx = automation_index()
            return jsonify(json_safe(_stamp(idx, idx.get("truth_status", "no_data"))))
        except Exception as exc:  # noqa: BLE001 — degrade honestly, never 500
            return jsonify(_stamp(
                {"index_pct": None, "dimensions": {}, "error": str(exc)[:200]}, "no_data"))


    # ── the cognitive substrate as verified SaaS ──────────────────────────────
    # The organism's cognitive + meta-cognitive systems (HNC field, thought-bus
    # links, mycelium mesh, connectome body-map, miner brain) surfaced as
    # read-only APIs, each response stamped with data provenance. Auto-metered
    # by the billing after_request hook + behind the same bearer/tenancy gates.
    from aureon.saas.cognitive import (
        brain_surface,
        build_cognitive_payload,
        bus_surface,
        connectome_surface,
        field_surface,
        mycelium_surface,
    )

    @app.get("/api/cognition")
    @_guarded
    def saas_cognition():
        # The whole substrate + provenance + truth-status roll-up.
        return jsonify(json_safe(build_cognitive_payload()))

    @app.get("/api/cognition/field")
    @_guarded
    def saas_cognition_field():
        return jsonify(json_safe({"surface": "field", "data": field_surface()}))

    @app.get("/api/cognition/bus")
    @_guarded
    def saas_cognition_bus():
        return jsonify(json_safe({"surface": "bus", "data": bus_surface()}))

    @app.get("/api/cognition/mycelium")
    @_guarded
    def saas_cognition_mycelium():
        return jsonify(json_safe({"surface": "mycelium", "data": mycelium_surface()}))

    @app.get("/api/cognition/connectome")
    @_guarded
    def saas_cognition_connectome():
        return jsonify(json_safe({"surface": "connectome", "data": connectome_surface()}))

    @app.get("/api/cognition/brain")
    @_guarded
    def saas_cognition_brain():
        return jsonify(json_safe({"surface": "brain", "data": brain_surface()}))

    @app.get("/api/manifests/<name>")
    @_guarded
    def saas_manifest(name: str):
        # Live manifests over HTTP so the production frontend can fetch them
        # through the /api proxy instead of relying on baked static files.
        manifests = render_manifests(catalog=build_catalog(use_cache=True), status=get_platform_status())
        if name not in manifests:
            return jsonify({"error": {"code": 404, "message": f"unknown manifest: {name}",
                                      "available": sorted(manifests)}}), 404
        return jsonify(json_safe(manifests[name]))

    @app.post("/api/manifests/refresh")
    @_guarded
    @_admin_only
    def saas_refresh():
        catalog = build_catalog()  # force rebuild; /api/manifests/<name> now serves fresh data
        manifests = render_manifests(catalog=catalog, status=get_platform_status())
        # The static frontend/public copies are owned by the repo's manifest
        # pipeline; overwrite them only when explicitly opted in.
        written: list[str] = []
        if str(os.environ.get("AUREON_WRITE_STATIC_MANIFESTS", "") or "") == "1":
            written = write_frontend_manifests(catalog=catalog, status=get_platform_status())
        return jsonify({"refreshed": True, "manifests": sorted(manifests),
                        "static_files_written": [p.split("/")[-1] for p in written],
                        "total_systems": catalog.get("total_systems", 0)})

    logger.info("SaaS gateway routes registered (tenancy bridge: %s)",
                "on" if tenant_auth_configured else "off")
    return app


__all__ = ["register_saas_routes", "verify_supabase_jwt"]
