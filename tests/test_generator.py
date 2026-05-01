import json
import pytest
from autodiscovery.parser import OpenAPIParser
from autodiscovery.generator import generate_tools

PETSTORE_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Petstore", "version": "1.0"},
    "servers": [{"url": "https://petstore.example.com"}],
    "paths": {
        "/pets": {
            "get": {
                "operationId": "listPets",
                "summary": "List all pets",
                "parameters": [
                    {"name": "limit", "in": "query", "schema": {"type": "integer"}},
                ],
                "responses": {"200": {"description": "OK"}},
            },
            "post": {
                "operationId": "createPet",
                "summary": "Create a pet",
                "requestBody": {
                    "required": True,
                    "content": {
                        "application/json": {
                            "schema": {
                                "type": "object",
                                "properties": {
                                    "name": {"type": "string"},
                                    "tag": {"type": "string"},
                                },
                                "required": ["name"],
                            }
                        }
                    },
                },
                "responses": {"201": {"description": "Created"}},
            },
        },
        "/pets/{petId}": {
            "get": {
                "operationId": "showPetById",
                "summary": "Info for a specific pet",
                "parameters": [
                    {"name": "petId", "in": "path", "required": True, "schema": {"type": "string"}},
                ],
                "responses": {"200": {"description": "OK"}},
            }
        },
    },
}


@pytest.mark.asyncio
async def _load_spec(raw: dict) -> dict:
    parser = OpenAPIParser()
    return await parser.load(json.dumps(raw))


@pytest.fixture
async def petstore_tools():
    spec = await _load_spec(PETSTORE_SPEC)
    return generate_tools(spec, "pets", None, None, None)


@pytest.mark.asyncio
async def test_tool_count():
    spec = await _load_spec(PETSTORE_SPEC)
    tools = generate_tools(spec, "pets", None, None, None)
    assert len(tools) == 3  # listPets, createPet, showPetById


@pytest.mark.asyncio
async def test_tool_names_prefixed():
    spec = await _load_spec(PETSTORE_SPEC)
    tools = generate_tools(spec, "myapi", None, None, None)
    names = [t.name for t, _ in tools]
    assert all(n.startswith("myapi__") for n in names)


@pytest.mark.asyncio
async def test_path_param_required():
    spec = await _load_spec(PETSTORE_SPEC)
    tools = generate_tools(spec, "pets", None, None, None)
    show_tool, config = next((t, c) for t, c in tools if "showpetbyid" in t.name.lower())
    assert "petId" in show_tool.inputSchema.get("required", [])
    assert config["param_locations"]["petId"] == "path"


@pytest.mark.asyncio
async def test_body_properties_flattened():
    spec = await _load_spec(PETSTORE_SPEC)
    tools = generate_tools(spec, "pets", None, None, None)
    create_tool, config = next((t, c) for t, c in tools if "createpet" in t.name.lower())
    props = create_tool.inputSchema.get("properties", {})
    assert "name" in props, "Object body properties should be flattened into the tool schema"
    assert "tag" in props
    assert config["body_flattened"] is True


@pytest.mark.asyncio
async def test_base_url_from_spec():
    spec = await _load_spec(PETSTORE_SPEC)
    tools = generate_tools(spec, "pets", None, None, None)
    _, config = tools[0]
    assert config["base_url"] == "https://petstore.example.com"


@pytest.mark.asyncio
async def test_base_url_override():
    spec = await _load_spec(PETSTORE_SPEC)
    tools = generate_tools(spec, "pets", "https://override.example.com", None, None)
    _, config = tools[0]
    assert config["base_url"] == "https://override.example.com"


@pytest.mark.asyncio
async def test_auth_stored_in_config():
    spec = await _load_spec(PETSTORE_SPEC)
    tools = generate_tools(spec, "pets", None, "Authorization", "Bearer secret")
    _, config = tools[0]
    assert config["auth_header"] == "Authorization"
    assert config["auth_value"] == "Bearer secret"


@pytest.mark.asyncio
async def test_sanitized_tool_name_no_special_chars():
    spec = await _load_spec(PETSTORE_SPEC)
    tools = generate_tools(spec, "my-api v2", None, None, None)
    for t, _ in tools:
        assert all(c.isalnum() or c == "_" for c in t.name), f"Tool name contains invalid chars: {t.name}"
