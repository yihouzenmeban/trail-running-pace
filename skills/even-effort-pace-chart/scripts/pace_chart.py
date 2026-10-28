#!/usr/bin/env python3
"""Offline, reproducible GPX even-effort pace charts. Python 3.10+; stdlib only."""

from __future__ import annotations

import argparse
from bisect import bisect_left, bisect_right
import csv
from dataclasses import dataclass
import hashlib
from html import escape
import io
import json
import math
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


ARTICLE_URL = "https://mp.weixin.qq.com/s/spYCP-upbqAZN0kzUm-0ng"
ARTICLE_TITLE = "耐力科学|体感一致配速表全面指南"
DEFAULTS = {
    "sample_m": 5.0,
    "smoothing_m": 20.0,
    "ascent_km_per_100m": 1.0,
    "fatigue_rate": 0.08,
    "water_ml_per_10km": 700.0,
    "target_step_minutes": 30.0,
}
CONFIG_KEYS = set(DEFAULTS) | {
    "name", "target", "targets", "track_index", "checkpoints", "cp_selection",
    "checkpoint_overrides", "distance_alignment",
}
CP_KEYS = {"name", "distance_km", "rest_minutes", "cutoff"}
OVERRIDE_KEYS = CP_KEYS | {"allow_off_route"}
CP_PATTERN = re.compile(
    r"(?<![A-Za-z])(?:CP|SP)\s*[-_#]?\s*\d*(?![A-Za-z])"
    r"|\b(?:checkpoint|aid\s*station|water\s*station|start|finish)\b"
    r"|补给|補給|检查点|檢查點|水站|起点|起點|终点|終點|起终点|起終點",
    re.IGNORECASE,
)


class InputError(ValueError):
    def __init__(self, message: str, details=None):
        super().__init__(message)
        self.details = details


@dataclass(frozen=True)
class Sample:
    distance_m: float
    elevation_m: float


@dataclass
class Route:
    points: list[tuple[float, float, float]]
    samples: list[Sample]
    candidates: list[dict]
    warnings: list[str] | None = None

    @property
    def total_m(self) -> float:
        return self.samples[-1].distance_m


def number(value, name: str, minimum=0.0, strictly_positive=False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise InputError(f"{name} must be a finite number")
    value = float(value)
    if not math.isfinite(value) or value < minimum or (strictly_positive and value <= 0):
        raise InputError(f"{name} must be finite and {'positive' if strictly_positive else f'>= {minimum}'}")
    return value


def keys(obj, allowed, context):
    if not isinstance(obj, dict):
        raise InputError(f"{context} must be an object")
    unknown = set(obj) - allowed
    if unknown:
        raise InputError(f"Unknown {context} fields: {', '.join(sorted(unknown))}")


def duration(value, name="duration") -> float:
    if not isinstance(value, str) or not re.fullmatch(r"\d{1,4}:[0-5]\d(?::[0-5]\d)?", value):
        raise InputError(f"{name} must be H:MM or H:MM:SS (hours may exceed 24)")
    parts = [int(part) for part in value.split(":")]
    if len(parts) == 2:
        parts.append(0)
    return float(parts[0] * 3600 + parts[1] * 60 + parts[2])


def format_duration(seconds: float) -> str:
    total = math.floor(seconds + 0.5)
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02}:{minutes:02}:{seconds:02}"


def format_pace(seconds: float | None) -> str:
    if seconds is None:
        return "-"
    minutes, seconds = divmod(math.floor(seconds + 0.5), 60)
    return f"{minutes}:{seconds:02}"


def tag(element) -> str:
    return element.tag.rsplit("}", 1)[-1]


def children(element, name):
    return [child for child in element if tag(child) == name]


def child_text(element, name) -> str:
    return next(((child.text or "").strip() for child in element if tag(child) == name), "")


def coordinates(element, require_elevation=True) -> tuple[float, float, float]:
    try:
        lat, lon = float(element.attrib["lat"]), float(element.attrib["lon"])
        ele_text = child_text(element, "ele")
        ele = float(ele_text) if ele_text else (None if require_elevation else 0.0)
    except (KeyError, TypeError, ValueError) as error:
        raise InputError("Invalid GPX coordinates or elevation") from error
    if not math.isfinite(lat) or not -90 <= lat <= 90 or not math.isfinite(lon) or not -180 <= lon <= 180:
        raise InputError("Invalid GPX latitude/longitude")
    if ele is None or not math.isfinite(ele):
        raise InputError("Missing or non-finite GPX elevation; supply a complete elevation profile")
    return lat, lon, ele


def longitude_delta(a: float, b: float) -> float:
    return (b - a + 180) % 360 - 180


def haversine(a, b) -> float:
    lat1, lat2 = math.radians(a[0]), math.radians(b[0])
    dlat = lat2 - lat1
    dlon = math.radians(longitude_delta(a[1], b[1]))
    h = math.sin(dlat / 2) ** 2 + math.cos(lat1) * math.cos(lat2) * math.sin(dlon / 2) ** 2
    return 6371008.8 * 2 * math.asin(math.sqrt(min(1.0, max(0.0, h))))


def load_route(path: Path, track_index: int | None = None) -> Route:
    raw = Path(path).read_bytes()
    if re.search(br"<!\s*(?:DOCTYPE|ENTITY)", raw, flags=re.IGNORECASE):
        raise InputError("GPX DTD/entity declarations are not supported")
    try:
        root = ET.fromstring(raw)
    except ET.ParseError as error:
        raise InputError(f"Invalid GPX XML: {error}") from error
    if tag(root) != "gpx":
        raise InputError("Expected a GPX root element")
    tracks = children(root, "trk")
    routes = children(root, "rte")
    alternatives = tracks or routes
    if not alternatives:
        raise InputError("No GPX track or route points found")
    if track_index is None:
        if len(alternatives) != 1:
            raise InputError("Multiple GPX routes; set track_index (1-based)", [
                {"track_index": i, "name": child_text(item, "name")}
                for i, item in enumerate(alternatives, 1)
            ])
        track_index = 1
    if isinstance(track_index, bool) or not isinstance(track_index, int) or not 1 <= track_index <= len(alternatives):
        raise InputError("track_index is outside the available routes")
    selected = alternatives[track_index - 1]
    segments = [children(segment, "trkpt") for segment in children(selected, "trkseg")] if tracks else [
        children(selected, "rtept")
    ]
    points = []
    for segment in segments:
        if not segment:
            continue
        current = [coordinates(point) for point in segment]
        if points and haversine(points[-1], current[0]) > 1:
            raise InputError("Disconnected GPX segment; select or repair a continuous route")
        for point in current:
            if points and haversine(points[-1], point) < 0.001:
                continue
            points.append(point)
    if len(points) < 2:
        raise InputError("GPX needs at least two distinct positions")
    samples = [Sample(0.0, points[0][2])]
    for previous, point in zip(points, points[1:]):
        samples.append(Sample(samples[-1].distance_m + haversine(previous, point), point[2]))
    candidates = []
    # A separate route often contains checkpoints beside a densely sampled track.
    sources = [("wpt", children(root, "wpt"))]
    if tracks:
        sources.extend((f"rte{index}:rtept", children(route, "rtept")) for index, route in enumerate(routes, 1))
    else:
        sources.append(("rtept", children(selected, "rtept")))
    for prefix, elements in sources:
        for index, element in enumerate(elements, 1):
            name, kind = child_text(element, "name"), child_text(element, "type")
            if not name and not kind:
                continue
            lat, lon, _ = coordinates(element, require_elevation=False)
            candidates.append({
                "id": f"{prefix}:{index}", "name": name or kind, "type": kind,
                "lat": lat, "lon": lon, "recognized": bool(CP_PATTERN.search(f"{name} {kind}")),
            })
    warnings = []
    max_gap = max(b.distance_m - a.distance_m for a, b in zip(samples, samples[1:]))
    if max_gap > 100:
        warnings.append(f"Sparse GPX: maximum original point spacing is {max_gap:.1f} m; interpolation adds no measurement detail.")
    if tracks and len(routes) > 1:
        warnings.append("Multiple auxiliary GPX routes supplied CP candidates; confirm their relevance in inspect output.")
    return Route(points, samples, candidates, warnings)


def interpolate(samples: list[Sample], distance: float) -> float:
    index = bisect_right(samples, distance, key=lambda p: p.distance_m) - 1
    index = max(0, min(index, len(samples) - 2))
    a, b = samples[index:index + 2]
    ratio = (distance - a.distance_m) / (b.distance_m - a.distance_m)
    return a.elevation_m + ratio * (b.elevation_m - a.elevation_m)


def smooth_profile(route: Route, sample_m=5.0, smoothing_m=20.0) -> list[Sample]:
    step = number(sample_m, "sample_m", strictly_positive=True)
    window = number(smoothing_m, "smoothing_m")
    count = math.ceil(route.total_m / step)
    if count > 2_000_000:
        raise InputError("Sampling would exceed 2,000,000 points; increase sample_m")
    distances = [index * step for index in range(count)] + [route.total_m]
    resampled = [Sample(x, interpolate(route.samples, x)) for x in distances]
    if window == 0:
        return resampled
    areas = [0.0]
    for a, b in zip(resampled, resampled[1:]):
        areas.append(areas[-1] + (b.distance_m - a.distance_m) * (a.elevation_m + b.elevation_m) / 2)

    def integral(x):
        index = max(0, min(bisect_right(distances, x) - 1, len(distances) - 2))
        a = resampled[index]
        return areas[index] + (x - a.distance_m) * (a.elevation_m + interpolate(resampled, x)) / 2

    result = []
    for x in distances:
        left, right = max(0, x - window / 2), min(route.total_m, x + window / 2)
        result.append(Sample(x, (integral(right) - integral(left)) / (right - left)))
    return result


def projection_options(route: Route, candidate: dict) -> list[dict]:
    lat, lon = candidate["lat"], candidate["lon"]
    cosine = math.cos(math.radians(lat))
    projections = []
    for index, (a, b) in enumerate(zip(route.points, route.points[1:])):
        ax, ay = math.radians(longitude_delta(lon, a[1])) * cosine * 6371008.8, math.radians(a[0] - lat) * 6371008.8
        bx, by = math.radians(longitude_delta(lon, b[1])) * cosine * 6371008.8, math.radians(b[0] - lat) * 6371008.8
        dx, dy = bx - ax, by - ay
        length_sq = dx * dx + dy * dy
        ratio = max(0.0, min(1.0, -(ax * dx + ay * dy) / length_sq)) if length_sq else 0.0
        distance = route.samples[index].distance_m + ratio * (
            route.samples[index + 1].distance_m - route.samples[index].distance_m
        )
        projections.append({"distance_m": distance, "offset_m": math.hypot(ax + ratio * dx, ay + ratio * dy)})
    nearest = min(item["offset_m"] for item in projections)
    nearby = sorted((p for p in projections if p["offset_m"] <= nearest + 20), key=lambda p: p["distance_m"])
    groups = [[nearby[0]]]
    for item in nearby[1:]:
        if item["distance_m"] - groups[-1][-1]["distance_m"] > 50:
            groups.append([])
        groups[-1].append(item)
    choices = [min(group, key=lambda p: p["offset_m"]) for group in groups]
    best = min(choices, key=lambda p: p["offset_m"])
    return [choice for choice in choices if abs(choice["distance_m"] - best["distance_m"]) > 100 or choice is best]


def station_fields(item: dict) -> dict:
    name = item.get("name")
    if not isinstance(name, str) or not name.strip():
        raise InputError("Every checkpoint needs a non-empty name")
    rest = number(item.get("rest_minutes", 0), "rest_minutes") * 60
    cutoff = duration(item["cutoff"], "cutoff") if item.get("cutoff") is not None else None
    return {"name": name.strip(), "rest_seconds": rest, "cutoff_seconds": cutoff}


def resolve_checkpoints(route: Route, config: dict) -> tuple[list[dict], float, list[str]]:
    warnings = []
    if "checkpoints" in config:
        items = config["checkpoints"]
        if not isinstance(items, list) or not items:
            raise InputError("checkpoints must contain CPs and an explicit final finish distance")
        if "cp_selection" in config or "checkpoint_overrides" in config:
            raise InputError("Use fields on manual checkpoints instead of CP selection/overrides")
        cps = []
        previous = -1.0
        for index, item in enumerate(items):
            keys(item, CP_KEYS, "checkpoint")
            distance = number(item.get("distance_km"), "distance_km") * 1000
            if distance <= previous:
                raise InputError("Checkpoint distances must be strictly increasing")
            previous = distance
            cps.append({"id": f"manual:{index + 1}", "distance_m": distance,
                        "official_distance_km": distance / 1000, **station_fields(item)})
        official_total = cps[-1]["distance_m"]
        if official_total <= 0:
            raise InputError("Finish distance must be positive")
        tolerance = max(100, route.total_m * 0.005)
        alignment = config.get("distance_alignment", "confirm")
        if alignment not in ("confirm", "scale"):
            raise InputError("distance_alignment must be confirm or scale")
        if abs(official_total - route.total_m) > tolerance and alignment != "scale":
            raise InputError("Official/GPX distance mismatch; confirm then set distance_alignment=scale",
                             {"official_m": official_total, "gpx_m": route.total_m,
                              "scale": route.total_m / official_total})
        scale = route.total_m / official_total if alignment == "scale" else 1.0
        for cp in cps:
            cp["distance_m"] *= scale
        cps[-1]["distance_m"] = route.total_m
        if len(cps) > 1 and cps[-2]["distance_m"] >= route.total_m:
            raise InputError("An intermediate checkpoint falls beyond the GPX finish")
        if alignment == "scale":
            warnings.append(f"Confirmed official-distance mapping: {scale:.8f} GPX metres per official metre.")
    else:
        scale = 1.0
        candidates = route.candidates
        if "cp_selection" in config:
            ids = config["cp_selection"]
            if not isinstance(ids, list) or not ids or not all(isinstance(i, str) for i in ids) or len(ids) != len(set(ids)):
                raise InputError("cp_selection must be a non-empty list of unique candidate IDs")
            available = {p["id"]: p for p in candidates}
            if not set(ids) <= set(available):
                raise InputError("Unknown cp_selection IDs", list(available))
            selected = [available[i] for i in ids]
        else:
            selected = [p for p in candidates if p["recognized"]]
        if not selected:
            if candidates:
                raise InputError("Named GPX waypoints need confirmation via cp_selection, or supply checkpoints", candidates)
            raise InputError("No GPX CPs found; provide checkpoints with names and cumulative kilometres")
        overrides = config.get("checkpoint_overrides", {})
        if not isinstance(overrides, dict) or not set(overrides) <= {p["id"] for p in selected}:
            raise InputError("checkpoint_overrides must reference selected CP IDs")
        cps = []
        for candidate in selected:
            override = overrides.get(candidate["id"], {})
            keys(override, OVERRIDE_KEYS, "checkpoint override")
            item = {**candidate, **override}
            if "allow_off_route" in override and not isinstance(override["allow_off_route"], bool):
                raise InputError("allow_off_route must be boolean")
            endpoint = f'{candidate["name"]} {candidate["type"]}'
            combined = bool(re.search(r"起终点|起終點", endpoint)) or (
                bool(re.search(r"\bstart\b", endpoint, re.IGNORECASE))
                and bool(re.search(r"\bfinish\b", endpoint, re.IGNORECASE))
            )
            if combined and "distance_km" not in override:
                if any(haversine((item["lat"], item["lon"]), point) > 100
                       for point in (route.points[0], route.points[-1])):
                    raise InputError("Named combined start/finish must be within 100 m of both GPX endpoints; "
                                     "provide separate checkpoints or a distance_km override")
                fields = station_fields(item)
                # A shared venue is two route occurrences; its cutoff applies only at the finish.
                for suffix, position, label in (("start", 0.0, "起点"), ("finish", route.total_m, "终点")):
                    cps.append({
                        **fields, "id": f'{candidate["id"]}:{suffix}', "distance_m": position,
                        "name": f'{fields["name"]}（{label}）', "official_distance_km": None,
                        "cutoff_seconds": fields["cutoff_seconds"] if suffix == "finish" else None,
                    })
                continue
            if "distance_km" in override:
                position = number(override["distance_km"], "distance_km") * 1000
                if position > route.total_m:
                    raise InputError("CP distance override is beyond the GPX finish")
                # A distance override explicitly selects a route occurrence and position.
                warnings.append(f'{candidate["id"]}: confirmed position override at {position / 1000:.3f} GPX km.')
            elif re.search(r"\bstart\b|起点|起點", endpoint, re.IGNORECASE):
                position = 0.0
                if haversine((item["lat"], item["lon"]), route.points[0]) > 100:
                    raise InputError("Named start is over 100 m from GPX start; provide distance_km override")
            elif re.search(r"\bfinish\b|终点|終點", endpoint, re.IGNORECASE):
                position = route.total_m
                if haversine((item["lat"], item["lon"]), route.points[-1]) > 100:
                    raise InputError("Named finish is over 100 m from GPX finish; provide distance_km override")
            else:
                options = projection_options(route, candidate)
                if len(options) > 1:
                    raise InputError(f'{candidate["id"]}: ambiguous CP route occurrence; set distance_km override', options)
                nearest = options[0]
                if nearest["offset_m"] > 100:
                    if not override.get("allow_off_route", False):
                        raise InputError(f'{candidate["id"]}: CP is over 100 m off-route; confirm before allow_off_route', nearest)
                    warnings.append(f'{candidate["id"]}: confirmed off-route CP ({nearest["offset_m"]:.1f} m).')
                position = nearest["distance_m"]
            cps.append({"id": candidate["id"], "distance_m": position,
                        "official_distance_km": None, **station_fields(item)})
        cps.sort(key=lambda cp: cp["distance_m"])
    if cps[0]["distance_m"] > 0.001:
        cps.insert(0, {"id": "start", "name": "起点", "distance_m": 0.0,
                       "official_distance_km": 0.0 if "checkpoints" in config else None,
                       "rest_seconds": 0.0, "cutoff_seconds": None})
    if route.total_m - cps[-1]["distance_m"] > 0.001:
        cps.append({"id": "finish", "name": "终点", "distance_m": route.total_m,
                    "official_distance_km": None, "rest_seconds": 0.0, "cutoff_seconds": None})
    if any(b["distance_m"] - a["distance_m"] < 0.001 for a, b in zip(cps, cps[1:])):
        raise InputError("Multiple CPs occupy the same route position; deduplicate or disambiguate them")
    if cps[0]["rest_seconds"] or cps[-1]["rest_seconds"]:
        raise InputError("Start/finish rest_minutes must be zero; no departure rest is counted there")
    return cps, scale, warnings


def grade_bin(grade_percent: float) -> int:
    if grade_percent <= -15:
        return 0
    if grade_percent <= -10:
        return 1
    if grade_percent <= -5:
        return 2
    if grade_percent < 5:
        return 3
    if grade_percent < 10:
        return 4
    if grade_percent < 15:
        return 5
    return 6


def section_stats(profile: list[Sample], left: float, right: float, factor: float, water: float) -> dict:
    if right == left:
        segment = [Sample(left, interpolate(profile, left))]
    else:
        start = bisect_right(profile, left, key=lambda p: p.distance_m)
        end = bisect_left(profile, right, key=lambda p: p.distance_m)
        segment = [Sample(left, interpolate(profile, left)), *profile[start:end],
                   Sample(right, interpolate(profile, right))]
    ascent, descent = 0.0, 0.0
    bins = [0.0] * 7
    for a, b in zip(segment, segment[1:]):
        dz, dx = b.elevation_m - a.elevation_m, b.distance_m - a.distance_m
        ascent += max(0, dz)
        descent += max(0, -dz)
        bins[grade_bin(100 * dz / dx)] += dx
    distance = right - left
    eq = distance / 1000 + ascent / 100 * factor
    return {
        "segment_distance_m": distance, "ascent_m": ascent, "descent_m": descent,
        "eq_distance_km": eq, "water_ml": eq / 10 * water,
        "grade_fractions": [b / distance if distance else 0.0 for b in bins],
        "profile": [[p.distance_m, p.elevation_m] for p in segment],
    }


def fatigue_exponent(rate: float) -> float:
    return 1 + math.log2(1 + rate)


def target_times(config: dict, step: float) -> list[float]:
    if "targets" in config:
        values = config["targets"]
        if not isinstance(values, list) or not values:
            raise InputError("targets must be a non-empty list of H:MM durations")
        times = [duration(value, "target") for value in values]
    else:
        center = duration(config.get("target"), "target")
        times = [center + offset * step * 60 for offset in (-2, -1, 0, 1, 2)]
    if any(value <= 0 for value in times) or len(set(times)) != len(times):
        raise InputError("Target durations must be positive and unique; supply an explicit targets list")
    return sorted(times)


def build_plan(path: Path, config: dict) -> dict:
    keys(config, CONFIG_KEYS, "configuration")
    parameters = {
        key: number(config.get(key, value), key,
                    strictly_positive=key in ("sample_m", "target_step_minutes"))
        for key, value in DEFAULTS.items()
    }
    if parameters["fatigue_rate"] > 1:
        raise InputError("fatigue_rate must be between 0 and 1")
    if config.get("distance_alignment", "confirm") not in ("confirm", "scale"):
        raise InputError("distance_alignment must be confirm or scale")
    if "name" in config and (not isinstance(config["name"], str) or not config["name"].strip()):
        raise InputError("name must be a non-empty string")
    route = load_route(path, config.get("track_index"))
    profile = smooth_profile(route, parameters["sample_m"], parameters["smoothing_m"])
    cps, scale, cp_warnings = resolve_checkpoints(route, config)
    cumulative_eq = 0.0
    for index, cp in enumerate(cps):
        left = cps[index - 1]["distance_m"] if index else 0.0
        cp.update(section_stats(profile, left, cp["distance_m"],
                                parameters["ascent_km_per_100m"], parameters["water_ml_per_10km"]))
        cumulative_eq += cp["eq_distance_km"]
        cp["cumulative_eq_distance_km"] = cumulative_eq
    targets = target_times(config, parameters["target_step_minutes"])
    rest_total = sum(cp["rest_seconds"] for cp in cps)
    exponent = fatigue_exponent(parameters["fatigue_rate"])
    schedules = []
    for target in targets:
        if target <= rest_total:
            raise InputError("Target duration must exceed total station rest time")
        moving_target = target - rest_total
        prior_moving, prior_rest = 0.0, 0.0
        times = []
        for index, cp in enumerate(cps):
            cumulative_moving = moving_target * (cp["cumulative_eq_distance_km"] / cumulative_eq) ** exponent
            moving = cumulative_moving - prior_moving
            arrival = cumulative_moving + prior_rest
            departure = arrival + cp["rest_seconds"]
            cutoff = cp["cutoff_seconds"]
            status = "not_checked" if cutoff is None else (
                "arrival_late" if arrival > cutoff + 1e-7 else (
                    "departure_late" if departure > cutoff + 1e-7 else "on_time"
                )
            )
            times.append({
                "arrival_seconds": arrival, "departure_seconds": departure,
                "moving_seconds": moving,
                "eq_pace_seconds_per_km": moving / cp["eq_distance_km"] if index else None,
                "cutoff_status": status,
            })
            prior_moving = cumulative_moving
            prior_rest += cp["rest_seconds"]
        schedules.append({"target_seconds": target, "checkpoints": times})
    route_stats = section_stats(profile, 0, route.total_m, parameters["ascent_km_per_100m"],
                                parameters["water_ml_per_10km"])
    warnings = list(route.warnings or []) + cp_warnings
    if any(cp["cutoff_seconds"] is None for cp in cps[1:]):
        warnings.append("部分或全部站点未提供关门时间，未校核这些站点。")
    warnings.extend([
        "模型未计入技术路面、陡下坡额外负担、天气和个人肌力差异；请结合赛事规程判断。",
        "水量仅供比较赛段差异，并非个人饮水建议。",
        "插值不增加原始测量精度；爬升统计依赖海拔数据与平滑参数。",
    ])
    return {
        "schema_version": 1,
        "name": config.get("name", Path(path).stem),
        "source": {"filename": Path(path).name, "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest()},
        "article": {"title": ARTICLE_TITLE, "author": "耐力学社 / Pili（表哥）", "url": ARTICLE_URL},
        "configuration": config,
        "parameters": {**parameters, "fatigue_exponent": exponent, "rest_total_seconds": rest_total},
        "route": {"distance_m": route.total_m, "distance_scale": scale,
                  "ascent_m": route_stats["ascent_m"], "descent_m": route_stats["descent_m"],
                  "eq_distance_km": cumulative_eq,
                  "original_points": len(route.points), "sampled_points": len(profile),
                  "grade_fractions": route_stats["grade_fractions"]},
        "checkpoints": cps, "targets_seconds": targets, "schedules": schedules, "warnings": warnings,
    }


def inspect_route(path: Path, track_index=None, sample_m=5.0, smoothing_m=20.0) -> dict:
    route = load_route(path, track_index)
    profile = smooth_profile(route, sample_m, smoothing_m)
    stats = section_stats(profile, 0, route.total_m, 1, 700)
    candidates = []
    for candidate in route.candidates:
        candidates.append({**candidate, "projection_options": projection_options(route, candidate)})
    return {
        "distance_m": route.total_m, "ascent_m": stats["ascent_m"], "descent_m": stats["descent_m"],
        "sample_m": sample_m, "smoothing_m": smoothing_m,
        "cp_candidates": candidates, "warnings": route.warnings or [],
    }


STATUS_LABELS = {
    "not_checked": "未校核", "on_time": "关门内",
    "arrival_late": "到站超时", "departure_late": "出站超时",
}
BASE_COLUMNS = [
    ("累计 km", 86), ("分段 km", 80), ("等效 km", 80), ("爬升 m", 65), ("下降 m", 65),
    ("坡度分布", 100), ("赛段肖像", 140), ("参考水 mL", 90), ("CP / 停留 / 关门", 220),
]


def wrap_text(text: str, units: int) -> list[str]:
    result, line, used = [], "", 0
    for char in text:
        size = 2 if ord(char) > 255 else 1
        if char == "\n" or (line and used + size > units):
            result.append(line)
            line, used = "", 0
        if char != "\n":
            line += char
            used += size
    if line or not result:
        result.append(line)
    return result


def svg_text(x, y, lines, size=12, color="#243c41", anchor="start", family="sans-serif") -> str:
    spans = "".join(
        f'<tspan x="{x:.2f}" dy="{0 if i == 0 else size * 1.45:.2f}">{escape(str(line))}</tspan>'
        for i, line in enumerate(lines)
    )
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" fill="{color}" font-size="{size}" '
        f'text-anchor="{anchor}" font-family="{family}">{spans}</text>'
    )


def graphic_frame(content, x, y, width, height, label, as_group) -> str:
    if as_group:
        return f'<g transform="translate({x} {y})" role="img"><title>{label}</title>{content}</g>'
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
        f'viewBox="0 0 {width} {height}" role="img" aria-label="{label}">{content}</svg>'
    )


def histogram_svg(fractions, x=0, y=0, width=90, height=42, as_group=False) -> str:
    bars = []
    labels = ("≤-15%", "-15~-10%", "-10~-5%", "-5~5%", "5~10%", "10~15%", "≥15%")
    for index, fraction in enumerate(fractions):
        bar_height = fraction * (height - 5)
        fill = "#285c67" if index < 3 else ("#fffdf7" if index == 3 else "#c17836")
        bars.append(
            f'<rect x="{index * width / 7 + 1:.2f}" y="{height - bar_height:.2f}" '
            f'width="{width / 7 - 2:.2f}" height="{bar_height:.2f}" fill="{fill}" '
            f'stroke="#9aaba9" stroke-width=".5"><title>{labels[index]}: {fraction:.1%}</title></rect>'
        )
    return graphic_frame("".join(bars), x, y, width, height, "坡度按距离加权的七档分布", as_group)


def profile_svg(profile, x=0, y=0, width=125, height=42, as_group=False) -> str:
    points = ""
    if len(profile) > 1:
        left, right = profile[0][0], profile[-1][0]
        low, high = min(p[1] for p in profile), max(p[1] for p in profile)
        points = " ".join(
            f"{3 + (distance - left) / (right - left) * (width - 6):.2f},"
            f"{height - 4 - (elevation - low) / max(high - low, 1) * (height - 8):.2f}"
            for distance, elevation in profile
        )
    content = (
        f'<path d="M0 {height - 2} H{width}" stroke="#d1dad5"/>'
        f'<polyline points="{points}" fill="none" stroke="#285c67" stroke-width="1.6"/>'
    )
    return graphic_frame(content, x, y, width, height, "分段海拔肖像，各段独立缩放", as_group)


def numeric_cells(cp) -> list[str]:
    return [
        f'{cp["distance_m"] / 1000:.2f}', f'{cp["segment_distance_m"] / 1000:.2f}',
        f'{cp["eq_distance_km"]:.2f}', f'{cp["ascent_m"]:.0f}', f'{cp["descent_m"]:.0f}',
    ]


def cp_details(cp) -> list[str]:
    lines = [cp["name"]]
    if cp["official_distance_km"] is not None:
        lines.append(f'官方 {cp["official_distance_km"]:.2f} km')
    if cp["rest_seconds"]:
        lines.append(f'停留 {cp["rest_seconds"] / 60:g} min')
    if cp["cutoff_seconds"] is not None:
        lines.append(f'关门 {format_duration(cp["cutoff_seconds"])}')
    elif cp["distance_m"] > 0:
        lines.append("关门 未提供")
    return lines


def timing_lines(cp, timing) -> list[str]:
    lines = [format_duration(timing["departure_seconds"]),
             f'({format_pace(timing["eq_pace_seconds_per_km"])})']
    if cp["rest_seconds"]:
        lines.append(f'到 {format_duration(timing["arrival_seconds"])}')
    if timing["cutoff_status"] in ("arrival_late", "departure_late"):
        lines.append(STATUS_LABELS[timing["cutoff_status"]])
    return lines


def summary_lines(plan) -> list[str]:
    route, p = plan["route"], plan["parameters"]
    return [
        f'GPX {route["distance_m"] / 1000:.2f} km · 爬升 {route["ascent_m"]:.0f} m · '
        f'下降 {route["descent_m"]:.0f} m · 等效 {route["eq_distance_km"]:.2f} km',
        f'采样 {p["sample_m"]:g} m / 居中平滑 {p["smoothing_m"]:g} m · '
        f'每 100 m 爬升折算 {p["ascent_km_per_100m"]:g} km · 掉速参数 {p["fatigue_rate"]:.1%}',
        f'目标包含停留 {p["rest_total_seconds"] / 60:g} min · 累计时间为出站时间 · 括号内为分段等效配速 min/km',
    ]


def footer_lines(plan) -> list[str]:
    return [
        "海拔肖像为各赛段独立缩放；坡度直方图左侧为下降、右侧为爬升，中间平缓档留白。",
        f'里程展示 GPX 测算值；官方里程映射系数 {plan["route"]["distance_scale"]:.8f}。',
        *plan["warnings"],
        f'依据《{ARTICLE_TITLE}》，耐力学社 / Pili（表哥）。独立实现，非 RunArt.Net 官方输出。',
        ARTICLE_URL,
        f'输入：{plan["source"]["filename"]} · SHA-256 {plan["source"]["sha256"]}',
    ]


def render_svg(plan: dict) -> str:
    widths = [width for _, width in BASE_COLUMNS] + [150] * len(plan["schedules"])
    width, margin = sum(widths) + 48, 24
    parts = [f'<rect width="{width}" height="100%" fill="#fffdf7"/>']
    title = wrap_text(plan["name"] + " · 体感一致配速表", int((width - 48) / 12))
    parts.append(svg_text(margin, 39, title, size=23, family="serif"))
    y = 39 + len(title) * 34
    for line in summary_lines(plan):
        parts.append(svg_text(margin, y, [line], size=13))
        y += 22
    y += 14
    headers = [name for name, _ in BASE_COLUMNS] + [
        f'目标 {format_duration(t)}' for t in plan["targets_seconds"]
    ]
    x = margin
    for index, (header, cell_width) in enumerate(zip(headers, widths)):
        parts.append(f'<rect x="{x}" y="{y}" width="{cell_width}" height="40" fill="#234c54"/>')
        parts.append(svg_text(x + cell_width / 2, y + 25, [header], color="#fffdf7", anchor="middle"))
        x += cell_width
    y += 40
    for index, cp in enumerate(plan["checkpoints"]):
        names = [line for detail in cp_details(cp) for line in wrap_text(detail, 29)]
        timings = [timing_lines(cp, schedule["checkpoints"][index]) for schedule in plan["schedules"]]
        row_height = max(78, 18 * max([len(names)] + [len(lines) for lines in timings]) + 24)
        x = margin
        for column, cell_width in enumerate(widths):
            color = "#f0ede3" if index % 2 == 0 else "#fffdf7"
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_width}" height="{row_height}" '
                f'fill="{color}" stroke="#d1dad5" stroke-width=".5"/>'
            )
            if column < 5:
                parts.append(svg_text(x + cell_width / 2, y + 34, [numeric_cells(cp)[column]],
                                      size=13, anchor="middle", family="monospace"))
            elif column == 5:
                parts.append(histogram_svg(cp["grade_fractions"], x + 5, y + 17, as_group=True))
            elif column == 6:
                parts.append(profile_svg(cp["profile"], x + 7, y + 17, as_group=True))
            elif column == 7:
                parts.append(svg_text(x + cell_width / 2, y + 34, [f'{cp["water_ml"]:.0f}'],
                                      size=13, anchor="middle", family="monospace"))
            elif column == 8:
                parts.append(svg_text(x + 10, y + 23, names, size=12))
            else:
                timing = plan["schedules"][column - 9]["checkpoints"][index]
                color = "#a13e26" if timing["cutoff_status"].endswith("_late") else "#243c41"
                parts.append(svg_text(x + cell_width / 2, y + 24, timings[column - 9],
                                      size=13, color=color, anchor="middle", family="monospace"))
            x += cell_width
        y += row_height
    y += 28
    for note in footer_lines(plan):
        lines = wrap_text(note, int((width - 48) / 6.5))
        parts.append(svg_text(margin, y, lines, size=12, color="#5d706b"))
        y += len(lines) * 18 + 5
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{y + 20:.0f}" '
        f'viewBox="0 0 {width} {y + 20:.0f}" role="img">'
        f'<title>{escape(plan["name"])} 体感一致配速表</title>'
        '<desc>累计出站时间与分段等效配速；所有图示和文字均在此文件内。</desc>'
        + "".join(parts) + "</svg>\n"
    )


def render_html(plan: dict) -> str:
    headers = "".join(f"<th>{escape(name)}</th>" for name, _ in BASE_COLUMNS)
    headers += "".join(f"<th>目标 {format_duration(t)}</th>" for t in plan["targets_seconds"])
    rows = []
    for index, cp in enumerate(plan["checkpoints"]):
        cells = "".join(f"<td>{cell}</td>" for cell in numeric_cells(cp))
        cells += f'<td>{histogram_svg(cp["grade_fractions"])}</td>'
        cells += f'<td>{profile_svg(cp["profile"])}</td><td>{cp["water_ml"]:.0f}</td>'
        cells += '<td class="cp">' + "<br>".join(escape(line) for line in cp_details(cp)) + "</td>"
        for schedule in plan["schedules"]:
            timing = schedule["checkpoints"][index]
            late = timing["cutoff_status"].endswith("_late")
            cells += f'<td class="{"late" if late else "timing"}">' + "<br>".join(
                escape(line) for line in timing_lines(cp, timing)
            ) + "</td>"
        rows.append("<tr>" + cells + "</tr>")
    summary = "".join(f"<p>{escape(line)}</p>" for line in summary_lines(plan))
    notes = "".join(f"<li>{escape(line)}</li>" for line in footer_lines(plan))
    return f"""<!doctype html>
<html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{escape(plan["name"])} · 体感一致配速表</title>
<style>
:root {{ --ink:#243c41; --paper:#fffdf7; --rule:#d1dad5; --accent:#234c54; }}
* {{ box-sizing:border-box; }}
body {{ margin:0; color:var(--ink); background:linear-gradient(140deg,#e6eee9,var(--paper) 55%); font-family:"Noto Serif CJK SC","Songti SC",serif; }}
main {{ padding:32px; }} h1 {{ margin:0 0 20px; font-weight:600; letter-spacing:.03em; }}
header p {{ margin:6px 0; font-size:14px; }}
.scroll {{ overflow-x:auto; margin-top:24px; border:1px solid var(--rule); background:var(--paper); }}
table {{ width:100%; min-width:1200px; border-collapse:collapse; font-family:monospace; font-variant-numeric:tabular-nums; }}
th {{ padding:15px 8px; background:var(--accent); color:var(--paper); white-space:nowrap; }}
td {{ padding:12px 8px; text-align:center; border:1px solid var(--rule); line-height:1.6; }}
tr:nth-child(odd) {{ background:#f0ede3; }} .cp {{ text-align:left; min-width:150px; max-width:260px; overflow-wrap:anywhere; font-family:serif; }}
.timing,.late {{ white-space:nowrap; }} .late {{ color:#a13e26; font-weight:bold; }}
td svg {{ display:block; margin:auto; }} footer {{ font-size:12px; line-height:1.8; overflow-wrap:anywhere; }}
@media(max-width:600px) {{ main {{ padding:18px; }} h1 {{ font-size:23px; }} }}
@page {{ size:A4 landscape; margin:8mm; }}
@media print {{
body {{ background:white; }} main {{ padding:0; }} h1 {{ font-size:17px; margin-bottom:8px; }}
header p {{ font-size:9px; margin:3px 0; }} .scroll {{ overflow:visible; margin-top:10px; border:0; }}
table {{ min-width:0; font-size:7px; }} th,td {{ padding:4px 2px; }}
thead {{ display:table-header-group; }} tr {{ break-inside:avoid; page-break-inside:avoid; }}
.cp {{ min-width:0; max-width:95px; }} td svg {{ width:55px; height:auto; }}
footer {{ font-size:8px; }} th {{ white-space:normal; }}
}}
</style></head><body><main>
<header><h1>{escape(plan["name"])} · 体感一致配速表</h1>{summary}</header>
<div class="scroll"><table><thead><tr>{headers}</tr></thead><tbody>{"".join(rows)}</tbody></table></div>
<footer><ul>{notes}</ul></footer></main></body></html>
"""


def csv_text(plan: dict) -> str:
    stream = io.StringIO(newline="")
    fields = [
        "checkpoint_id", "checkpoint_name", "gpx_distance_km", "official_distance_km",
        "segment_distance_km", "ascent_m", "descent_m", "eq_distance_km", "water_ml",
        "rest_seconds", "cutoff_seconds", "target_seconds", "arrival_seconds",
        "departure_seconds", "moving_seconds", "eq_pace_seconds_per_km", "cutoff_status",
        "arrival", "departure", "eq_pace",
    ]
    writer = csv.DictWriter(stream, fieldnames=fields)
    writer.writeheader()
    for schedule in plan["schedules"]:
        for cp, timing in zip(plan["checkpoints"], schedule["checkpoints"]):
            name = cp["name"]
            if name.lstrip().startswith(("=", "+", "-", "@")):
                name = "'" + name
            writer.writerow({
                "checkpoint_id": cp["id"], "checkpoint_name": name,
                "gpx_distance_km": cp["distance_m"] / 1000,
                "official_distance_km": cp["official_distance_km"],
                "segment_distance_km": cp["segment_distance_m"] / 1000,
                **{key: cp[key] for key in ("ascent_m", "descent_m", "eq_distance_km",
                                           "water_ml", "rest_seconds", "cutoff_seconds")},
                "target_seconds": schedule["target_seconds"],
                **timing,
                "arrival": format_duration(timing["arrival_seconds"]),
                "departure": format_duration(timing["departure_seconds"]),
                "eq_pace": format_pace(timing["eq_pace_seconds_per_km"]),
            })
    return stream.getvalue()


def write_outputs(plan: dict, output_dir: Path, overwrite=False) -> list[Path]:
    output_dir = Path(output_dir)
    files = {
        "pace-chart.json": json.dumps(plan, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        "pace-chart.csv": "\ufeff" + csv_text(plan),
        "pace-chart.html": render_html(plan),
        "pace-chart.svg": render_svg(plan),
    }
    paths = [output_dir / name for name in files]
    if not overwrite and any(path.exists() for path in paths):
        raise InputError("Output files already exist; choose a new directory or use --overwrite")
    output_dir.mkdir(parents=True, exist_ok=True)
    for path, text in zip(paths, files.values()):
        with path.open("w", encoding="utf-8", newline="") as stream:
            stream.write(text)
    return paths


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    inspect = commands.add_parser("inspect", help="Inspect geometry and embedded CP candidates")
    inspect.add_argument("gpx", type=Path)
    inspect.add_argument("--track-index", type=int)
    inspect.add_argument("--sample-m", type=float, default=5)
    inspect.add_argument("--smoothing-m", type=float, default=20)
    generate = commands.add_parser("generate", help="Generate HTML, SVG, CSV and JSON")
    generate.add_argument("gpx", type=Path)
    generate.add_argument("--config", type=Path, required=True)
    generate.add_argument("--output-dir", type=Path, required=True)
    generate.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "inspect":
            result = inspect_route(args.gpx, args.track_index, args.sample_m, args.smoothing_m)
        else:
            config = json.loads(args.config.read_text(encoding="utf-8"))
            plan = build_plan(args.gpx, config)
            paths = write_outputs(plan, args.output_dir, args.overwrite)
            result = {"outputs": [str(path) for path in paths], "warnings": plan["warnings"]}
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
        return 0
    except (InputError, OSError, UnicodeError, json.JSONDecodeError) as error:
        result = {"error": str(error)}
        if isinstance(error, InputError) and error.details is not None:
            result["details"] = error.details
        print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
