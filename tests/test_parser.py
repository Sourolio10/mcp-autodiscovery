import json
import pytest
from autodiscovery.parser import OpenAPIParser

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
    "components": {
        "schemas": {
            "Pet": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "name": {"type": "string"},
                },
            }
        }
    },
}

REF_SPEC = {
    "openapi": "3.0.0",
    "info": {"title": "Ref Test", "version": "1.0"},
    "paths": {
        "/items": {
            "get": {
                "operationId": "listItems",
                "responses": {
                    "200": {
                        "content": {
                            "application/json": {
                                "schema": {"$ref": "#/components/schemas/Item"}
                            }
                        }
                    }
                },
            }
        }
    },
    "components": {
        "schemas": {
            "Item": {
                "type": "object",
                "properties": {"id": {"type": "integer"}, "label": {"type": "string"}},
            }
        }
    },
}


@pytest.mark.asyncio
async def test_load_raw_json():
    parser = OpenAPIParser()
    spec = await parser.load(json.dumps(PETSTORE_SPEC))
    assert "paths" in spec
    assert "/pets" in spec["paths"]


@pytest.mark.asyncio
async def test_load_raw_yaml():
    import yaml

    parser = OpenAPIParser()
    spec = await parser.load(yaml.dump(PETSTORE_SPEC))
    assert "paths" in spec


@pytest.mark.asyncio
async def test_ref_resolution():
    parser = OpenAPIParser()
    spec = await parser.load(json.dumps(REF_SPEC))
    # The $ref inside the response schema should be inlined
    response_schema = (
        spec["paths"]["/items"]["get"]["responses"]["200"]
        ["content"]["application/json"]["schema"]
    )
    assert response_schema.get("type") == "object", "Ref should be resolved to its target"
    assert "properties" in response_schema


@pytest.mark.asyncio
async def test_invalid_spec_raises():
    parser = OpenAPIParser()
    with pytest.raises(ValueError):
        await parser.load('{"not": "a spec"}')


@pytest.mark.asyncio
async def test_invalid_content_raises():
    parser = OpenAPIParser()
    with pytest.raises(Exception):
        await parser.load("this is not json or yaml at all ::::")
