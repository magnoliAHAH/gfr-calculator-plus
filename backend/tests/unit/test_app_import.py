"""Приложение собирается, OpenAPI генерируется, ключевые маршруты на месте."""
def test_app_builds_and_exposes_routes():
    from app.main import app

    schema = app.openapi()
    paths = set(schema["paths"])
    for p in ("/api/v1/auth/login", "/api/v1/auth/me", "/api/v1/calculate",
              "/api/v1/audit", "/api/v1/audit/{audit_id}/verify",
              "/api/v1/audit/{audit_id}/decision", "/api/v1/meta/drugs", "/health"):
        assert p in paths, p
    assert schema["openapi"].startswith("3.")
