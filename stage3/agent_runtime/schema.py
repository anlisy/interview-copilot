from __future__ import annotations

from typing import Any


class SchemaError(ValueError):
    pass


def _type_matches(value: Any, schema_type: str) -> bool:
    if schema_type == "object":
        return isinstance(value, dict)
    if schema_type == "array":
        return isinstance(value, list)
    if schema_type == "string":
        return isinstance(value, str)
    if schema_type == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if schema_type == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if schema_type == "boolean":
        return isinstance(value, bool)
    if schema_type == "null":
        return value is None
    raise SchemaError(f"不支持 schema type={schema_type}")


def validate_json(value: Any, schema: dict[str, Any], path: str = "$", *, allow_extra: bool = True) -> None:
    if not isinstance(schema, dict):
        raise SchemaError(f"{path} schema 必须是 object")

    if "const" in schema and value != schema["const"]:
        raise SchemaError(f"{path} 不等于 const={schema['const']!r}")
    if "enum" in schema and value not in schema["enum"]:
        raise SchemaError(f"{path} 不在 enum={schema['enum']}")

    if "anyOf" in schema:
        errors = []
        for idx, candidate in enumerate(schema["anyOf"]):
            try:
                validate_json(value, candidate, path, allow_extra=allow_extra)
                break
            except SchemaError as exc:
                errors.append(str(exc))
        else:
            raise SchemaError(f"{path} 不匹配 anyOf: {errors[:3]}")
    elif "oneOf" in schema:
        matched = 0
        last_error: str | None = None
        for candidate in schema["oneOf"]:
            try:
                validate_json(value, candidate, path, allow_extra=allow_extra)
                matched += 1
            except SchemaError as exc:
                last_error = str(exc)
        if matched != 1:
            raise SchemaError(f"{path} 不满足 oneOf, matched={matched}; {last_error or ''}")

    stype = schema.get("type")
    if isinstance(stype, list):
        if not any(_type_matches(value, t) for t in stype):
            raise SchemaError(f"{path} 类型不匹配: expected={stype}")
    elif stype is not None:
        if not _type_matches(value, stype):
            raise SchemaError(f"{path} 类型不匹配: expected={stype}")

    if isinstance(value, dict):
        required = schema.get("required", [])
        for key in required:
            if key not in value:
                raise SchemaError(f"{path}.{key} 缺失")
        props = schema.get("properties", {})
        additional = schema.get("additionalProperties", True)
        if additional is False and not allow_extra:
            extra = set(value) - set(props)
            if extra:
                raise SchemaError(f"{path} 存在未允许字段: {sorted(extra)}")
        elif isinstance(additional, dict):
            for key in set(value) - set(props):
                validate_json(value[key], additional, f"{path}.{key}", allow_extra=allow_extra)
        for key, child in props.items():
            if key in value:
                validate_json(value[key], child, f"{path}.{key}", allow_extra=allow_extra)

    if isinstance(value, list) and isinstance(schema.get("items"), dict):
        for idx, item in enumerate(value):
            validate_json(item, schema["items"], f"{path}[{idx}]", allow_extra=allow_extra)

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            raise SchemaError(f"{path} 长度不足")
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            raise SchemaError(f"{path} 长度超限")

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            raise SchemaError(f"{path} 小于 minimum={schema['minimum']}")
        if "maximum" in schema and value > schema["maximum"]:
            raise SchemaError(f"{path} 大于 maximum={schema['maximum']}")

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            raise SchemaError(f"{path} item 数量不足")
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            raise SchemaError(f"{path} item 数量超限")
