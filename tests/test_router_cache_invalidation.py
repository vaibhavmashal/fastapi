from fastapi import APIRouter, FastAPI
from fastapi.routing import APIRoute
from fastapi.testclient import TestClient
from starlette.responses import PlainTextResponse
from starlette.routing import Route


def test_child_routes_append_invalidates_parent_cache():
    child = APIRouter()

    @child.get("/first")
    def first():
        return {"msg": "first"}

    app = FastAPI()
    app.include_router(child, prefix="/api")
    client = TestClient(app)

    # Initial dispatch caches effective routes
    res = client.get("/api/first")
    assert res.status_code == 200
    assert res.json() == {"msg": "first"}

    res = client.get("/api/second")
    assert res.status_code == 404

    # Directly mutate child.routes via append
    def second():
        return {"msg": "second"}

    child.routes.append(APIRoute("/second", second))

    # Dispatch should now recognize the newly appended route without stale cache
    res = client.get("/api/second")
    assert res.status_code == 200
    assert res.json() == {"msg": "second"}


def test_child_routes_remove_invalidates_parent_cache():
    child = APIRouter()

    @child.get("/first")
    def first():
        return {"msg": "first"}

    @child.get("/second")
    def second():
        return {"msg": "second"}

    app = FastAPI()
    app.include_router(child, prefix="/api")
    client = TestClient(app)

    # Initial dispatch
    res = client.get("/api/first")
    assert res.status_code == 200
    res = client.get("/api/second")
    assert res.status_code == 200

    # Remove the first route directly
    first_route = child.routes[0]
    child.routes.remove(first_route)

    # Dispatch should not have ghost route for /first
    res = client.get("/api/first")
    assert res.status_code == 404
    res = client.get("/api/second")
    assert res.status_code == 200


def test_child_routes_pop_and_clear_invalidates_parent_cache():
    child = APIRouter()

    @child.get("/first")
    def first():
        return {"msg": "first"}

    @child.get("/second")
    def second():
        return {"msg": "second"}

    app = FastAPI()
    app.include_router(child, prefix="/api")
    client = TestClient(app)

    assert client.get("/api/second").status_code == 200
    child.routes.pop()
    assert client.get("/api/second").status_code == 404
    assert client.get("/api/first").status_code == 200

    child.routes.clear()
    assert client.get("/api/first").status_code == 404


def test_child_routes_extend_and_insert_invalidates_parent_cache():
    child = APIRouter()

    @child.get("/first")
    def first():
        return {"msg": "first"}

    app = FastAPI()
    app.include_router(child, prefix="/api")
    client = TestClient(app)

    assert client.get("/api/first").status_code == 200

    def r2():
        return {"msg": "r2"}

    def r3():
        return {"msg": "r3"}

    child.routes.extend([APIRoute("/r2", r2), APIRoute("/r3", r3)])

    assert client.get("/api/r2").status_code == 200
    assert client.get("/api/r3").status_code == 200

    def r0():
        return {"msg": "r0"}

    child.routes.insert(0, APIRoute("/r0", r0))
    assert client.get("/api/r0").status_code == 200


def test_child_routes_item_assignment_and_deletion_invalidates_parent_cache():
    child = APIRouter()

    @child.get("/first")
    def first():
        return {"msg": "first"}

    app = FastAPI()
    app.include_router(child, prefix="/api")
    client = TestClient(app)

    assert client.get("/api/first").status_code == 200

    def replaced():
        return {"msg": "replaced"}

    # Replace via __setitem__
    child.routes[0] = APIRoute("/replaced", replaced)
    assert client.get("/api/first").status_code == 404
    assert client.get("/api/replaced").status_code == 200

    # Delete via __delitem__
    del child.routes[0]
    assert client.get("/api/replaced").status_code == 404


def test_child_routes_slice_assignment_and_deletion_invalidates_parent_cache():
    child = APIRouter()

    @child.get("/a")
    def a():
        return {"msg": "a"}

    @child.get("/b")
    def b():
        return {"msg": "b"}

    app = FastAPI()
    app.include_router(child, prefix="/api")
    client = TestClient(app)

    assert client.get("/api/a").status_code == 200
    assert client.get("/api/b").status_code == 200

    def c():
        return {"msg": "c"}

    def d():
        return {"msg": "d"}

    child.routes[0:2] = [APIRoute("/c", c), APIRoute("/d", d)]
    assert client.get("/api/a").status_code == 404
    assert client.get("/api/b").status_code == 404
    assert client.get("/api/c").status_code == 200
    assert client.get("/api/d").status_code == 200

    del child.routes[0:1]
    assert client.get("/api/c").status_code == 404
    assert client.get("/api/d").status_code == 200


def test_child_routes_iadd_and_assignment_invalidates_parent_cache():
    child = APIRouter()

    @child.get("/first")
    def first():
        return {"msg": "first"}

    app = FastAPI()
    app.include_router(child, prefix="/api")
    client = TestClient(app)

    assert client.get("/api/first").status_code == 200

    def second():
        return {"msg": "second"}

    child.routes += [APIRoute("/second", second)]
    assert client.get("/api/second").status_code == 200

    def third():
        return {"msg": "third"}

    child.routes = [APIRoute("/third", third)]
    assert client.get("/api/first").status_code == 404
    assert client.get("/api/second").status_code == 404
    assert client.get("/api/third").status_code == 200


def test_deeply_nested_router_routes_mutation_invalidates_cache():
    grandchild = APIRouter()

    @grandchild.get("/leaf")
    def leaf():
        return {"msg": "leaf"}

    child = APIRouter()
    child.include_router(grandchild, prefix="/nested")

    parent = APIRouter()
    parent.include_router(child, prefix="/sub")

    app = FastAPI()
    app.include_router(parent, prefix="/root")
    client = TestClient(app)

    assert client.get("/root/sub/nested/leaf").status_code == 200

    # Add a route to grandchild directly
    def leaf2():
        return {"msg": "leaf2"}

    grandchild.routes.append(APIRoute("/leaf2", leaf2))
    assert client.get("/root/sub/nested/leaf2").status_code == 200

    # Remove the original route from grandchild
    grandchild.routes.pop(0)
    assert client.get("/root/sub/nested/leaf").status_code == 404
    assert client.get("/root/sub/nested/leaf2").status_code == 200


def test_child_starlette_route_mutation_invalidates_parent_cache():
    child = APIRouter()

    def starlette_handler(request):
        return PlainTextResponse("starlette")

    child.routes.append(Route("/starlette", starlette_handler))

    app = FastAPI()
    app.include_router(child, prefix="/api")
    client = TestClient(app)

    res = client.get("/api/starlette")
    assert res.status_code == 200
    assert res.text == "starlette"

    child.routes.clear()
    res = client.get("/api/starlette")
    assert res.status_code == 404


def test_routes_mutation_invalidates_openapi_schema_cache():
    child = APIRouter()

    @child.get("/first")
    def first():
        return {"msg": "first"}

    app = FastAPI()
    app.include_router(child, prefix="/api")

    # Initial openapi schema generation
    schema1 = app.openapi()
    assert "/api/first" in schema1["paths"]
    assert "/api/second" not in schema1["paths"]

    # Mutate child routes directly
    def second():
        return {"msg": "second"}

    child.routes.append(APIRoute("/second", second))

    # OpenAPI schema should be refreshed
    schema2 = app.openapi()
    assert "/api/first" in schema2["paths"]
    assert "/api/second" in schema2["paths"]
