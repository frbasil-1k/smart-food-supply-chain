from __future__ import annotations

from datetime import datetime, timedelta

from flask import Flask
from flask.testing import FlaskClient

from conftest import auth_headers, csrf, login

FUTURE = (datetime.now() + timedelta(days=3)).replace(microsecond=0).isoformat()
BEST_BEFORE = (datetime.now() + timedelta(days=4)).replace(microsecond=0).isoformat()


def test_session_cookie_is_httponly_and_csrf_cookie_is_readable(api_client: FlaskClient) -> None:
    token = csrf(api_client)
    response = api_client.post(
        "/api/auth/login",
        json={"email": "donor.a@example.test", "password": "TestPass!12345"},
        headers=auth_headers(token),
    )
    cookies = response.headers.getlist("Set-Cookie")
    session_cookie = next(cookie for cookie in cookies if cookie.startswith("sfc_session="))
    csrf_cookie = next(cookie for cookie in cookies if cookie.startswith("sfc_csrf="))
    assert "HttpOnly" in session_cookie
    assert "SameSite=Lax" in session_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "SameSite=Lax" in csrf_cookie


def test_activation_token_activates_inactive_user(db_app: Flask) -> None:
    manager_client = db_app.test_client()
    manager = login(manager_client, "manager.a@example.test")
    response = manager_client.post("/api/users/10/activation-token", headers=auth_headers(manager))
    assert response.status_code == 201, response.get_json()
    body = response.get_json()["data"]
    assert body["delivery"] == "shown_once"
    assert body["activation_token"]
    assert body["expires_at"]

    activation_client = db_app.test_client()
    preauth = csrf(activation_client)
    response = activation_client.post(
        "/api/auth/activate",
        json={"token": body["activation_token"], "new_password": "BrandNew!23456"},
        headers=auth_headers(preauth),
    )
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["data"]["user"]["account_status"] == "ACTIVE"
    assert activation_client.get("/api/auth/me").status_code == 200

    fresh = db_app.test_client()
    old_token = csrf(fresh)
    assert (
        fresh.post(
            "/api/auth/login",
            json={"email": "pending.donor@example.test", "password": "TestPass!12345"},
            headers=auth_headers(old_token),
        ).status_code
        == 401
    )
    assert login(fresh, "pending.donor@example.test", "BrandNew!23456")


def test_activation_rejects_weak_password_and_reuse(db_app: Flask) -> None:
    manager_client = db_app.test_client()
    manager = login(manager_client, "manager.a@example.test")
    token = manager_client.post(
        "/api/users/10/activation-token", headers=auth_headers(manager)
    ).get_json()["data"]["activation_token"]
    client = db_app.test_client()
    preauth = csrf(client)
    weak = client.post(
        "/api/auth/activate",
        json={"token": token, "new_password": "password"},
        headers=auth_headers(preauth),
    )
    assert weak.status_code == 422
    assert weak.get_json()["error"]["code"] == "password_policy"
    good = client.post(
        "/api/auth/activate",
        json={"token": token, "new_password": "BrandNew!23456"},
        headers=auth_headers(preauth),
    )
    assert good.status_code == 200
    reuse_client = db_app.test_client()
    reuse_preauth = csrf(reuse_client)
    reuse = reuse_client.post(
        "/api/auth/activate",
        json={"token": token, "new_password": "BrandNew!23457"},
        headers=auth_headers(reuse_preauth),
    )
    assert reuse.status_code == 401
    assert reuse.get_json()["error"]["code"] == "token_invalid_or_expired"


def test_reset_token_and_password_change(db_app: Flask) -> None:
    manager_client = db_app.test_client()
    manager = login(manager_client, "manager.a@example.test")
    reset = manager_client.post("/api/users/3/password-reset-token", headers=auth_headers(manager))
    assert reset.status_code == 201, reset.get_json()
    token = reset.get_json()["data"]["reset_token"]
    client = db_app.test_client()
    preauth = csrf(client)
    response = client.post(
        "/api/auth/password-reset/confirm",
        json={"token": token, "new_password": "ResetPass!23456"},
        headers=auth_headers(preauth),
    )
    assert response.status_code == 204
    assert login(client, "donor.a@example.test", "ResetPass!23456")

    change_token = client.get("/api/auth/csrf").get_json()["data"]["csrf_token"]
    response = client.post(
        "/api/auth/password",
        json={"current_password": "ResetPass!23456", "new_password": "ChangedPass!23456"},
        headers=auth_headers(change_token),
    )
    assert response.status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    assert login(client, "donor.a@example.test", "ChangedPass!23456")


def test_login_lockout_is_generic_and_temporary(api_client: FlaskClient) -> None:
    for _ in range(5):
        token = csrf(api_client)
        response = api_client.post(
            "/api/auth/login",
            json={"email": "donor.a@example.test", "password": "WrongPass!23456"},
            headers=auth_headers(token),
        )
        assert response.status_code == 401
    token = csrf(api_client)
    locked = api_client.post(
        "/api/auth/login",
        json={"email": "donor.a@example.test", "password": "TestPass!12345"},
        headers=auth_headers(token),
    )
    assert locked.status_code == 401
    assert locked.get_json()["error"]["code"] == "account_locked"


def test_role_guard_and_user_directory(api_client: FlaskClient) -> None:
    donor = login(api_client, "donor.a@example.test")
    forbidden = api_client.post("/api/branches", json={}, headers=auth_headers(donor))
    assert forbidden.status_code == 403
    assert forbidden.get_json()["error"]["code"] == "forbidden_role"

    manager = login(api_client, "manager.a@example.test")
    listing = api_client.get("/api/users").get_json()
    ids = {row["user_id"] for row in listing["data"]}
    assert 1 not in ids
    assert 3 in ids
    assert 10 in ids
    assert "password_hash" not in str(listing)
    assert (
        api_client.patch(
            "/api/users/10",
            json={"account_status": "SUSPENDED"},
            headers=auth_headers(manager),
        ).status_code
        == 422
    )


def test_branch_and_route_creation_force_manager_scope(api_client: FlaskClient) -> None:
    manager = login(api_client, "manager.a@example.test")
    response = api_client.post(
        "/api/branches",
        json={
            "organization_id": 1,
            "branch_name": "New Branch",
            "address": "New Address",
            "pincode": "403003",
            "contact_no": "9876543210",
            "established_date": "2026-01-01",
        },
        headers=auth_headers(manager),
    )
    assert response.status_code == 201, response.get_json()
    assert response.get_json()["data"]["regional_manager"]["user_id"] == 1

    payload = {
        "managing_branch_id": 1,
        "designated_driver_user_id": 6,
        "coverage_area_id": 1,
        "route_type": "PICKUP",
        "route_status": "ACTIVE",
    }
    route = api_client.post("/api/routes", json=payload, headers=auth_headers(manager))
    assert route.status_code == 201, route.get_json()
    assert route.get_json()["data"]["managing_branch"]["branch_id"] == 1
    wrong = api_client.post(
        "/api/routes",
        json={**payload, "managing_branch_id": 2},
        headers=auth_headers(manager),
    )
    assert wrong.status_code == 404


def test_unrouted_branch_donation_is_visible_only_to_its_manager(api_client: FlaskClient) -> None:
    donor = login(api_client, "donor.a@example.test")
    response = api_client.post(
        "/api/donations",
        json={
            "pickup_route_id": None,
            "pickup_datetime": FUTURE,
            "pickup_address": "12 Test Street",
            "pickup_pincode": "403001",
            "pickup_contact": "+919876543210",
            "urgency_level": "NORMAL",
            "items": [
                {
                    "category_id": 1,
                    "item_name": "Rice",
                    "quantity_kg": "10.00",
                    "best_before": BEST_BEFORE,
                }
            ],
        },
        headers=auth_headers(donor),
    )
    assert response.status_code == 201, response.get_json()
    donation_id = response.get_json()["data"]["donation_id"]

    manager_a = login(api_client, "manager.a@example.test")
    assert api_client.get(f"/api/donations/{donation_id}").status_code == 200
    donors = api_client.get("/api/reports/donors").get_json()["data"]
    assert any(row["donor_id"] == 3 and row["total_donations"] == 1 for row in donors)
    assert (
        api_client.patch(
            f"/api/donations/{donation_id}/route",
            json={"pickup_route_id": 1},
            headers=auth_headers(manager_a),
        ).status_code
        == 200
    )

    login(api_client, "manager.b@example.test")
    assert api_client.get(f"/api/donations/{donation_id}").status_code == 404


def test_driver_dependents_composite_path(api_client: FlaskClient) -> None:
    driver = login(api_client, "driver.a@example.test")
    created = api_client.post(
        "/api/dependents",
        json={
            "full_name": "Child A",
            "relationship": "Child",
            "date_of_birth": "2015-01-01",
            "phone": "9876543210",
        },
        headers=auth_headers(driver),
    )
    assert created.status_code == 201, created.get_json()
    assert created.get_json()["data"]["dependent_no"] == 1
    patched = api_client.patch(
        "/api/dependents/6/1",
        json={"full_name": "Child B"},
        headers=auth_headers(driver),
    )
    assert patched.status_code == 200
    assert patched.get_json()["data"]["full_name"] == "Child B"
    other = api_client.patch(
        "/api/dependents/9/1", json={"full_name": "No"}, headers=auth_headers(driver)
    )
    assert other.status_code == 404
