"""Resolve a device model's MIoT spec (named services/properties/actions) from the
public ``miot-spec.org`` repository, cached to disk (specs are static).

``describe(state, model)`` returns a flattened :class:`DeviceSpec` with human-named
properties (siid/piid, format, access, valid values) and actions (siid/aiid), or
``None`` when the model has no public spec (e.g. ``blt.*`` / ``miir.*`` / unknown).
Network only happens on a cache miss.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field

import requests

from ..config import StateDir

CATALOG_URL = "https://miot-spec.org/miot-spec-v2/instances?status=all"
INSTANCE_URL = "https://miot-spec.org/miot-spec-v2/instance"
_HEADERS = {"User-Agent": "mihome-ctl"}


@dataclass
class SpecProp:
    siid: int
    piid: int
    service: str
    name: str
    format: str
    access: list[str]
    value_range: list | None = None
    value_list: list | None = None


@dataclass
class SpecAction:
    siid: int
    aiid: int
    service: str
    name: str
    in_: list


@dataclass
class DeviceSpec:
    model: str
    urn: str
    props: list[SpecProp] = field(default_factory=list)
    actions: list[SpecAction] = field(default_factory=list)


def access_flags(p: SpecProp) -> str:
    return (
        ("R" if "read" in p.access else "")
        + ("W" if "write" in p.access else "")
        + ("N" if "notify" in p.access else "")
    )


def prop_constraint(p: SpecProp) -> str:
    if p.value_list:
        return " ".join(f"{x.get('value')}={x.get('description')}" for x in p.value_list)
    if p.value_range:
        return f"{p.value_range[0]}..{p.value_range[1]}"
    return ""


def _build_models_map(state: StateDir) -> dict:
    data = requests.get(CATALOG_URL, headers=_HEADERS, timeout=30).json()
    insts = data.get("instances", data) if isinstance(data, dict) else data
    best: dict[str, tuple[tuple[int, int], str]] = {}
    for it in insts or []:
        model, urn = it.get("model"), it.get("type")
        if not model or not urn:
            continue
        rank = (1 if it.get("status") == "released" else 0, it.get("version") or 0)
        cur = best.get(model)
        if cur is None or rank > cur[0]:
            best[model] = (rank, urn)
    mapping = {m: v[1] for m, v in best.items()}
    state.models_json.parent.mkdir(parents=True, exist_ok=True)
    state.models_json.write_text(json.dumps(mapping), encoding="utf-8")
    return mapping


def _models_map(state: StateDir) -> dict:
    if state.models_json.exists():
        try:
            return json.loads(state.models_json.read_text(encoding="utf-8"))
        except Exception:
            pass
    return _build_models_map(state)


def urn_for_model(state: StateDir, model: str) -> str | None:
    return _models_map(state).get(model)


def fetch_instance(state: StateDir, urn: str) -> dict:
    cache = state.spec_json(urn)
    if cache.exists():
        try:
            return json.loads(cache.read_text(encoding="utf-8"))
        except Exception:
            pass
    data = requests.get(INSTANCE_URL, params={"type": urn}, headers=_HEADERS, timeout=30).json()
    cache.parent.mkdir(parents=True, exist_ok=True)
    cache.write_text(json.dumps(data), encoding="utf-8")
    return data


def describe(state: StateDir, model: str) -> DeviceSpec | None:
    urn = urn_for_model(state, model)
    if not urn:
        return None
    inst = fetch_instance(state, urn)
    spec = DeviceSpec(model=model, urn=urn)
    for svc in inst.get("services", []) or []:
        siid = svc.get("iid")
        if siid is None:
            continue
        stype = svc.get("type", "").split(":")
        sname = svc.get("description") or (stype[3] if len(stype) > 3 else "")
        for p in svc.get("properties", []) or []:
            piid = p.get("iid")
            if piid is None:
                continue
            spec.props.append(
                SpecProp(
                    siid=int(siid),
                    piid=int(piid),
                    service=sname,
                    name=p.get("description") or "",
                    format=p.get("format") or "",
                    access=p.get("access") or [],
                    value_range=p.get("value-range"),
                    value_list=p.get("value-list"),
                )
            )
        for a in svc.get("actions", []) or []:
            aiid = a.get("iid")
            if aiid is None:
                continue
            spec.actions.append(
                SpecAction(
                    siid=int(siid),
                    aiid=int(aiid),
                    service=sname,
                    name=a.get("description") or "",
                    in_=a.get("in") or [],
                )
            )
    return spec
