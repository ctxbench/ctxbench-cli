from __future__ import annotations

import json
from typing import Any, get_args, get_origin, get_type_hints

try:
    from pydantic import BaseModel, Field, ValidationError
except ImportError:  # pragma: no cover
    class ValidationError(ValueError):
        pass

    def Field(default: Any = None, default_factory: Any | None = None, **_: Any) -> Any:
        if default_factory is not None:
            return default_factory()
        return default

    class BaseModel:
        def __init__(self, **data: Any) -> None:
            hints = get_type_hints(type(self))
            for name, annotation in hints.items():
                default = getattr(type(self), name, None)
                if name in data:
                    value = data[name]
                elif hasattr(type(self), name):
                    value = default
                else:
                    raise ValidationError(f"Missing field: {name}")
                setattr(self, name, self._coerce(annotation, value, name))
            extra = set(data) - set(hints)
            if extra:
                raise ValidationError(f"Unexpected fields: {', '.join(sorted(extra))}")
            validator = getattr(self, "_validate_model", None)
            if validator:
                validator()

        @classmethod
        def model_validate(cls, data: Any) -> Any:
            if isinstance(data, cls):
                return data
            if not isinstance(data, dict):
                raise ValidationError(f"{cls.__name__} requires an object input.")
            return cls(**data)

        @classmethod
        def model_validate_json(cls, value: str) -> Any:
            return cls.model_validate(json.loads(value))

        def model_dump(self, mode: str = "python") -> dict[str, Any]:
            result: dict[str, Any] = {}
            for name in get_type_hints(type(self)):
                value = getattr(self, name)
                result[name] = self._dump(value, mode)
            return result

        def model_dump_json(self, indent: int | None = None) -> str:
            return json.dumps(self.model_dump(mode="json"), indent=indent)

        @classmethod
        def _dump(cls, value: Any, mode: str) -> Any:
            if isinstance(value, BaseModel):
                return value.model_dump(mode=mode)
            if isinstance(value, list):
                return [cls._dump(item, mode) for item in value]
            if isinstance(value, dict):
                return {key: cls._dump(item, mode) for key, item in value.items()}
            return value

        @classmethod
        def _coerce(cls, annotation: Any, value: Any, name: str) -> Any:
            origin = get_origin(annotation)
            args = get_args(annotation)
            if annotation is Any:
                return value
            if origin is None:
                if isinstance(annotation, type) and issubclass(annotation, BaseModel):
                    return annotation.model_validate(value)
                if annotation in (str, int, float, bool):
                    if not isinstance(value, annotation):
                        raise ValidationError(
                            f"Field {name} expected {annotation.__name__}, got {type(value).__name__}"
                        )
                    return value
                return value
            if origin in (list, tuple):
                if not isinstance(value, list):
                    raise ValidationError(f"Field {name} expected list.")
                item_type = args[0] if args else Any
                return [cls._coerce(item_type, item, name) for item in value]
            if origin is dict:
                if not isinstance(value, dict):
                    raise ValidationError(f"Field {name} expected object.")
                value_type = args[1] if len(args) > 1 else Any
                return {key: cls._coerce(value_type, item, name) for key, item in value.items()}
            if origin is type(None):
                if value is not None:
                    raise ValidationError(f"Field {name} expected null.")
                return value
            if str(origin) == "typing.Union":
                last_error: Exception | None = None
                for option in args:
                    if option is type(None) and value is None:
                        return None
                    try:
                        return cls._coerce(option, value, name)
                    except Exception as exc:
                        last_error = exc
                raise ValidationError(str(last_error) if last_error else f"Invalid field {name}")
            return value
