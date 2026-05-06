from pydantic import BaseModel


CURRENT_SCHEMA = "1.0"
SUPPORTED_VERSIONS = ["1.0"]


class SchemaVersion(BaseModel):
    version: str = CURRENT_SCHEMA
    description: str = "Initial schema"


def validate_schema(data: dict) -> bool:
    schema_version = data.get("schema_version")
    return schema_version in SUPPORTED_VERSIONS


def assert_schema(data: dict) -> None:
    schema_version = data.get("schema_version")
    if schema_version not in SUPPORTED_VERSIONS:
        raise ValueError(
            f"Unsupported schema version: {schema_version}. "
            f"Supported: {SUPPORTED_VERSIONS}"
        )
