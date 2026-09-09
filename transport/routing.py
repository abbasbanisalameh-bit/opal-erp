"""Routing boundary for OPAL Transport.

Road routing is opt-in through an explicitly configured OSRM-compatible
endpoint. Without that configuration the system uses deterministic geographic
proximity; it never sends family coordinates to a third party by default.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from urllib.parse import quote
from urllib.request import Request, urlopen
import json
import os


class RoutingProvider(ABC):
    name = "abstract"

    @abstractmethod
    def optimize_waypoints(self, stops):
        raise NotImplementedError

    def distance_km(self, a, b):
        from .services import _distance_km
        return _distance_km(a["latitude"], a["longitude"], b["latitude"], b["longitude"])


class ProximityRoutingProvider(RoutingProvider):
    name = "proximity"

    def optimize_waypoints(self, stops):
        from .services import _distance_km
        remaining = list(stops)
        if len(remaining) <= 2:
            return remaining
        current = min(remaining, key=lambda x: (float(x["latitude"]), float(x["longitude"])))
        remaining.remove(current)
        ordered = [current]
        while remaining:
            nxt = min(remaining, key=lambda x: _distance_km(current["latitude"], current["longitude"], x["latitude"], x["longitude"]))
            remaining.remove(nxt)
            ordered.append(nxt)
            current = nxt
        return ordered


class OSRMRoutingProvider(ProximityRoutingProvider):
    name = "osrm"

    def __init__(self, base_url):
        self.base_url = base_url.rstrip("/")

    def _route_distance(self, a, b):
        coords = f'{float(a["longitude"])},{float(a["latitude"])};{float(b["longitude"])},{float(b["latitude"])}'
        url = f"{self.base_url}/route/v1/driving/{quote(coords, safe=';,') }?overview=false"
        req = Request(url, headers={"User-Agent": "OPAL-Transport/1.0"})
        with urlopen(req, timeout=8) as response:
            data = json.loads(response.read().decode("utf-8"))
        routes = data.get("routes") or []
        if not routes:
            raise RuntimeError("road routing returned no route")
        return float(routes[0]["distance"]) / 1000.0

    def distance_km(self, a, b):
        try:
            return self._route_distance(a, b)
        except Exception:
            return super().distance_km(a, b)


def get_routing_provider():
    provider = (os.environ.get("OPAL_TRANSPORT_ROUTING_PROVIDER") or "proximity").strip().lower()
    base_url = (os.environ.get("OPAL_TRANSPORT_ROUTING_URL") or "").strip()
    if provider == "osrm" and base_url:
        return OSRMRoutingProvider(base_url)
    return ProximityRoutingProvider()
