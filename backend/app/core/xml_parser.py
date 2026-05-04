from __future__ import annotations

from lxml.etree import _Element


def xml_to_dict(root: _Element) -> dict:
    """Convert a validated <Workout> lxml element into a dict matching the JSON schema."""
    result: dict = {
        "name": _text(root, "Name"),
        "sport": _text(root, "Sport"),
        "steps": [_parse_step(s) for s in root.findall("Steps/Step")],
    }

    sub_sport = root.findtext("SubSport")
    if sub_sport:
        result["sub_sport"] = sub_sport

    description = root.findtext("Description")
    if description:
        result["description"] = description

    return result


def _parse_step(elem: _Element) -> dict:
    step: dict = {
        "name": _text(elem, "Name"),
        "intensity": _text(elem, "Intensity"),
        "duration": _parse_duration(elem.find("Duration")),
    }

    target_elem = elem.find("Target")
    if target_elem is not None:
        step["target"] = _parse_target(target_elem)

    secondary_elem = elem.find("SecondaryTarget")
    if secondary_elem is not None:
        step["secondary_target"] = _parse_target(secondary_elem)

    notes = elem.findtext("Notes")
    if notes:
        step["notes"] = notes

    return step


def _parse_duration(elem: _Element) -> dict:
    dtype = _text(elem, "Type")
    dur: dict = {"type": dtype}

    if dtype == "time":
        dur["value_s"] = float(_text(elem, "ValueSeconds"))
    elif dtype == "distance":
        dur["value_m"] = float(_text(elem, "ValueMetres"))
    elif dtype == "calories":
        dur["value_kcal"] = int(_text(elem, "ValueKcal"))
    elif dtype in ("hr_less_than", "hr_greater_than"):
        dur["value_bpm"] = int(_text(elem, "ValueBpm"))
    elif dtype == "reps":
        dur["value_reps"] = int(_text(elem, "ValueReps"))
    # "open" needs no extra fields

    return dur


def _parse_target(elem: _Element) -> dict:
    ttype = _text(elem, "Type")
    tgt: dict = {"type": ttype}

    if ttype == "heart_rate":
        tgt["zone"] = int(_text(elem, "Zone"))
    elif ttype == "heart_rate_custom":
        tgt["low_bpm"] = int(_text(elem, "LowBpm"))
        tgt["high_bpm"] = int(_text(elem, "HighBpm"))
    elif ttype == "power":
        tgt["zone"] = int(_text(elem, "Zone"))
    elif ttype == "power_custom":
        tgt["low_watts"] = int(_text(elem, "LowWatts"))
        tgt["high_watts"] = int(_text(elem, "HighWatts"))
    elif ttype == "cadence":
        tgt["low_rpm"] = int(_text(elem, "LowRpm"))
        tgt["high_rpm"] = int(_text(elem, "HighRpm"))
    elif ttype in ("speed", "pace"):
        tgt["low_ms"] = float(_text(elem, "LowMs"))
        tgt["high_ms"] = float(_text(elem, "HighMs"))
    # "open" needs no extra fields

    return tgt


def _text(elem: _Element, tag: str) -> str:
    node = elem.find(tag)
    if node is None or node.text is None:
        raise ValueError(f"Missing required XML element <{tag}>")
    return node.text.strip()
