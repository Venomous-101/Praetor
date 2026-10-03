"""Strict, minimal schema validation for tool arguments.

Every tool call is validated before execution. The validator is
intentionally small and auditable (stdlib only) and follows a
default-deny posture: unknown argument names are rejected outright.
"""
from __future__ import annotations

from typing import Any, Mapping

_ALLOWED_TYPES = {"string", "integer", "number", "boolean", "array", "object", "null"}


class ValidationError(ValueError):
    """Arguments did not conform to the tool schema."""


def validate_schema(schema: Mapping[str, Any]) -> None:
    """Check that a tool declares a well-formed schema."""
    if not isinstance(schema, Mapping):
        raise ValidationError("schema must be a mapping")
    if schema.get("type") != "object":
        raise ValidationError("top-level schema type must be 'object'")
    props = schema.get("properties")
    if not isinstance(props, Mapping):
        raise ValidationError("schema must declare a 'properties' mapping")
    for name, prop in props.items():
        if not isinstance(prop, Mapping) or "type" not in prop:
            raise ValidationError("property '" + str(name) + "' must declare a type")
        if prop["type"] not in _ALLOWED_TYPES:
            raise ValidationError("property '" + str(name) + "' has an unsupported type")
    required = schema.get("required", [])
    if not isinstance(required, list):
        raise ValidationError("'required' must be a list")
    unknown = [r for r in required if r not in props]
    if unknown:
        raise ValidationError("required fields missing from properties: " + repr(unknown))


def validate_arguments(schema: Mapping[str, Any], arguments: Mapping[str, Any]) -> None:
    """Validate arguments against a schema (default-deny)."""
    if not isinstance(arguments, Mapping):
        raise ValidationError("arguments must be an object")
    props = schema.get("properties", {})
    required = schema.get("required", [])
    for key in arguments:
        if key not in props:
            raise ValidationError("unknown argument '" + str(key) + "'")
    for key in required:
        if key not in arguments:
            raise ValidationError("missing required argument '" + str(key) + "'")
    for key, value in arguments.items():
        _check_type(str(key), value, props[key])
    for key, constraint in props.items():
        enum_values = constraint.get("enum")
        if enum_values is not None and key in arguments and arguments[key] not in enum_values:
            raise ValidationError("argument '" + str(key) + "' must be one of " + repr(enum_values))


def _check_type(key: str, value: Any, constraint: Mapping[str, Any]) -> None:
    expected = constraint.get("type")
    ok = {
        "string": isinstance(value, str),
        "integer": isinstance(value, int) and not isinstance(value, bool),
        "number": isinstance(value, (int, float)) and not isinstance(value, bool),
        "boolean": isinstance(value, bool),
        "array": isinstance(value, list),
        "object": isinstance(value, dict),
        "null": value is None,
    }
    if expected not in ok or not ok[expected]:
        raise ValidationError("argument '" + key + "' must be of type '" + str(expected) + "'")
