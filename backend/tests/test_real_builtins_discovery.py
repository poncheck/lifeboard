"""Discovery smoke test for all the real built-in integrations and
modules shipped in backend/integrations and backend/modules — proves
the registries load every Phase 1-6 built-in without error, through
the actual API a deployment would hit.
"""


def test_all_real_integrations_and_modules_are_discovered(real_app_client):
    app_client = real_app_client
    app_client.post(
        "/api/setup",
        json={
            "full_name": "Marcin Petkowicz",
            "date_of_birth": "1986-03-26",
            "email": "marcin@example.com",
            "password": "correct-horse-battery-staple",
        },
    )
    app_client.post(
        "/api/login",
        json={"email": "marcin@example.com", "password": "correct-horse-battery-staple"},
    )

    integrations = app_client.get("/api/integrations").json()
    assert set(integrations.keys()) >= {"echo", "intervals_icu", "traccar", "weather", "portfolio"}

    modules = app_client.get("/api/modules").json()
    assert set(modules.keys()) >= {
        "clock",
        "echo",
        "training_readiness",
        "location",
        "weather",
        "nutrition",
        "portfolio",
    }

    # Every module not requiring an integration (or whose integration
    # isn't configured) must still return get_data() without raising —
    # the "no data yet" / "not connected" degrade-gracefully states.
    for module_id in modules:
        response = app_client.get(f"/api/modules/{module_id}/data")
        assert response.status_code == 200, f"{module_id} failed: {response.text}"
