"""Shared type aliases."""

JsonValue = str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject = dict[str, JsonValue]
