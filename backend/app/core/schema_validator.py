from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator
from lxml import etree

_SCHEMAS_DIR = Path(__file__).parent.parent / "schemas"

_json_schema = json.loads((_SCHEMAS_DIR / "workout.schema.json").read_text(encoding="utf-8"))
_json_validator = Draft202012Validator(_json_schema)

_xsd_doc = etree.parse(str(_SCHEMAS_DIR / "workout.xsd"))
_xsd = etree.XMLSchema(_xsd_doc)


def validate_json(data: dict) -> list[dict]:
    errors: list[dict] = []
    for err in _json_validator.iter_errors(data):
        # For oneOf/anyOf failures, surface the sub-errors instead of the generic
        # "is not valid under any of the given schemas" message so users see the
        # specific constraint that failed (e.g. maximum, required).
        if err.validator in ("oneOf", "anyOf") and err.context:
            for sub in err.context:
                errors.append({
                    "path": _format_json_path(sub.absolute_path),
                    "message": sub.message,
                    "schema_path": _format_schema_path(sub.absolute_schema_path),
                })
        else:
            errors.append({
                "path": _format_json_path(err.absolute_path),
                "message": err.message,
                "schema_path": _format_schema_path(err.absolute_schema_path),
            })
    return errors


def validate_xml(xml_bytes: bytes) -> tuple[dict | None, list[dict]]:
    try:
        tree = etree.fromstring(xml_bytes)
    except etree.XMLSyntaxError as exc:
        return None, [{"path": "$", "message": f"XML parse error: {exc}", "schema_path": ""}]

    if not _xsd.validate(tree):
        errors = [
            {"path": "$", "message": str(e), "schema_path": ""}
            for e in _xsd.error_log
        ]
        return None, errors

    from .xml_parser import xml_to_dict
    return xml_to_dict(tree), []


def _format_json_path(path) -> str:
    if not path:
        return "$"
    parts = []
    for part in path:
        if isinstance(part, int):
            parts.append(f"[{part}]")
        else:
            parts.append(f"[{part}]")
    return "$" + "".join(parts)


def _format_schema_path(path) -> str:
    return "/" + "/".join(str(p) for p in path)
