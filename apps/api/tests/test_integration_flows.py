from __future__ import annotations

from datetime import datetime, timedelta

from flask.testing import FlaskClient

from conftest import auth_headers, csrf, login

FUTURE = (datetime.now() + timedelta(days=3)).replace(microsecond=0).isoformat()
BEST_BEFORE = (datetime.now() + timedelta(days=4)).replace(microsecond=0).isoformat()


def donation_payload(route_id: int = 1, quantity: str = "10.00") -> dict:
    return {
        "pickup_route_id": route_id,
        "pickup_datetime": FUTURE,
        "pickup_address": "12 Test Street",
        "pickup_pincode": "403001",
        "pickup_contact": "+919876543210",
        "urgency_level": "NORMAL",
        "items": [
            {
                "category_id": 1,
                "item_name": "Rice",
                "quantity_kg": quantity,
                "best_before": BEST_BEFORE,
            }
        ],
    }


def create_donation(client: FlaskClient, token: str, **kwargs) -> dict:
    response = client.post(
        "/api/donations",
        json=donation_payload(**kwargs),
        headers=auth_headers(token),
    )
    assert response.status_code == 201, response.get_json()
    return response.get_json()["data"]


def test_csrf_and_origin_are_required(api_client: FlaskClient) -> None:
    assert api_client.post("/api/auth/login", json={}).status_code == 403
    token = csrf(api_client)
    response = api_client.post(
        "/api/auth/login",
        json={"email": "donor.a@example.test", "password": "TestPass!12345"},
        headers={"X-CSRF-Token": token},
    )
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == "origin_not_allowed"


def test_login_me_logout(api_client: FlaskClient) -> None:
    token = login(api_client, "donor.a@example.test")
    me = api_client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.get_json()["data"]["role"] == "DONOR"
    assert me.get_json()["data"]["primary_branch_id"] == 1
    response = api_client.post("/api/auth/logout", headers=auth_headers(token))
    assert response.status_code == 204
    assert api_client.get("/api/auth/me").status_code == 401


def test_donor_without_branch_cannot_select_a_route(api_client: FlaskClient) -> None:
    token = login(api_client, "donor.o@example.test")
    response = api_client.post(
        "/api/donations", json=donation_payload(), headers=auth_headers(token)
    )
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "donor_branch_required"
    assert api_client.get("/api/donations").get_json()["data"] == []


def test_donor_cannot_use_another_branch_route(api_client: FlaskClient) -> None:
    token = login(api_client, "donor.a@example.test")
    response = api_client.post(
        "/api/donations", json=donation_payload(route_id=2), headers=auth_headers(token)
    )
    assert response.status_code == 422
    assert response.get_json()["error"]["code"] == "invalid_reference"


def test_manager_and_driver_scope_are_enforced(api_client: FlaskClient) -> None:
    donor = login(api_client, "donor.a@example.test")
    donation = create_donation(api_client, donor)
    manager_b = login(api_client, "manager.b@example.test")
    assert api_client.get(f"/api/donations/{donation['donation_id']}").status_code == 404
    assert (
        api_client.patch(
            f"/api/donations/{donation['donation_id']}/status",
            json={"target_status": "SCHEDULED"},
            headers=auth_headers(manager_b),
        ).status_code
        == 404
    )
    login(api_client, "driver.b@example.test")
    assert api_client.get(f"/api/donations/{donation['donation_id']}").status_code == 404


def test_full_donation_to_delivery_journey(api_client: FlaskClient) -> None:
    donor = login(api_client, "donor.a@example.test")
    donation = create_donation(api_client, donor)
    donation_id = donation["donation_id"]
    item_id = donation["items"][0]["food_item_id"]

    manager = login(api_client, "manager.a@example.test")
    response = api_client.patch(
        f"/api/donations/{donation_id}/status",
        json={"target_status": "SCHEDULED", "note": "Route confirmed"},
        headers=auth_headers(manager),
    )
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["data"]["to_status"] == "SCHEDULED"

    driver = login(api_client, "driver.a@example.test")
    response = api_client.patch(
        f"/api/donations/{donation_id}/status",
        json={"target_status": "COLLECTED"},
        headers=auth_headers(driver),
    )
    assert response.status_code == 200, response.get_json()

    inspector = login(api_client, "inspector.a@example.test")
    response = api_client.post(
        f"/api/donations/{donation_id}/inspections",
        json={
            "packaging_integrity": "INTACT",
            "safety_status": "PASSED",
            "temperature_c": "4.00",
            "remarks": "Cold chain verified",
        },
        headers=auth_headers(inspector),
    )
    assert response.status_code == 201, response.get_json()

    manager = login(api_client, "manager.a@example.test")
    response = api_client.patch(
        f"/api/donations/{donation_id}/status",
        json={"target_status": "APPROVED"},
        headers=auth_headers(manager),
    )
    assert response.status_code == 200, response.get_json()

    response = api_client.post(
        "/api/deliveries",
        json={
            "donation_id": donation_id,
            "route_id": 1,
            "recipient_branch_id": 1,
            "driver_user_id": 6,
            "scheduled_for": FUTURE,
            "items": [{"food_item_id": item_id, "quantity_delivered_kg": "10.00"}],
        },
        headers=auth_headers(manager),
    )
    assert response.status_code == 201, response.get_json()
    delivery_id = response.get_json()["data"]["delivery_id"]
    assert response.get_json()["data"]["status"] == "PLANNED"

    driver = login(api_client, "driver.a@example.test")
    response = api_client.patch(
        f"/api/deliveries/{delivery_id}/status",
        json={"target_status": "IN_TRANSIT"},
        headers=auth_headers(driver),
    )
    assert response.status_code == 200, response.get_json()
    response = api_client.patch(
        f"/api/deliveries/{delivery_id}/status",
        json={"target_status": "DELIVERED"},
        headers=auth_headers(driver),
    )
    assert response.status_code == 200, response.get_json()
    assert response.get_json()["data"]["status"] == "DELIVERED"

    detail = api_client.get(f"/api/donations/{donation_id}").get_json()["data"]
    assert detail["status"] == "COMPLETED"
    assert detail["items"][0]["delivered_kg"] == "10.00"
    assert detail["items"][0]["available_kg"] == "0.00"

    manager = login(api_client, "manager.a@example.test")
    response = api_client.post(
        f"/api/deliveries/{delivery_id}/review",
        json={"rating": 5, "quality_notes": "Good handling"},
        headers=auth_headers(manager),
    )
    assert response.status_code == 201, response.get_json()
    duplicate = api_client.post(
        f"/api/deliveries/{delivery_id}/review",
        json={"rating": 4},
        headers=auth_headers(manager),
    )
    assert duplicate.status_code == 409
    assert duplicate.get_json()["error"]["code"] == "duplicate_review"

    assert api_client.get("/api/reports/overview").status_code == 200
    donors = api_client.get("/api/reports/donors").get_json()["data"]
    assert any(row["donor_id"] == 3 for row in donors)
    activity = api_client.get("/api/activity").get_json()["data"]
    assert any(row["event_type"] == "delivery_delivered" for row in activity)


def test_spoilage_reconciles_and_cannot_exceed_available(api_client: FlaskClient) -> None:
    donor = login(api_client, "donor.a@example.test")
    donation = create_donation(api_client, donor, quantity="10.00")
    donation_id = donation["donation_id"]
    item_id = donation["items"][0]["food_item_id"]
    manager = login(api_client, "manager.a@example.test")
    api_client.patch(
        f"/api/donations/{donation_id}/status",
        json={"target_status": "SCHEDULED"},
        headers=auth_headers(manager),
    )
    driver = login(api_client, "driver.a@example.test")
    api_client.patch(
        f"/api/donations/{donation_id}/status",
        json={"target_status": "COLLECTED"},
        headers=auth_headers(driver),
    )
    inspector = login(api_client, "inspector.a@example.test")
    api_client.post(
        f"/api/donations/{donation_id}/inspections",
        json={"packaging_integrity": "INTACT", "safety_status": "PASSED"},
        headers=auth_headers(inspector),
    )
    manager = login(api_client, "manager.a@example.test")
    api_client.patch(
        f"/api/donations/{donation_id}/status",
        json={"target_status": "APPROVED"},
        headers=auth_headers(manager),
    )
    response = api_client.post(
        "/api/spoilage",
        json={
            "food_item_id": item_id,
            "quantity_spoiled_kg": "2.00",
            "reason": "Chiller failure",
        },
        headers=auth_headers(manager),
    )
    assert response.status_code == 201, response.get_json()
    assert response.get_json()["data"]["quantity_spoiled_kg"] == "2.00"
    detail = api_client.get(f"/api/donations/{donation_id}").get_json()["data"]
    assert detail["status"] == "PARTIALLY_DISTRIBUTED"
    excessive = api_client.post(
        "/api/spoilage",
        json={
            "food_item_id": item_id,
            "quantity_spoiled_kg": "9.00",
            "reason": "Too much",
        },
        headers=auth_headers(manager),
    )
    assert excessive.status_code == 409
    assert excessive.get_json()["error"]["code"] == "allocation_exceeds_available"


def test_cancel_planned_delivery_releases_allocation(api_client: FlaskClient) -> None:
    donor = login(api_client, "donor.a@example.test")
    donation = create_donation(api_client, donor)
    donation_id = donation["donation_id"]
    item_id = donation["items"][0]["food_item_id"]
    manager = login(api_client, "manager.a@example.test")
    api_client.patch(
        f"/api/donations/{donation_id}/status",
        json={"target_status": "SCHEDULED"},
        headers=auth_headers(manager),
    )
    driver = login(api_client, "driver.a@example.test")
    api_client.patch(
        f"/api/donations/{donation_id}/status",
        json={"target_status": "COLLECTED"},
        headers=auth_headers(driver),
    )
    inspector = login(api_client, "inspector.a@example.test")
    api_client.post(
        f"/api/donations/{donation_id}/inspections",
        json={"packaging_integrity": "INTACT", "safety_status": "PASSED"},
        headers=auth_headers(inspector),
    )
    manager = login(api_client, "manager.a@example.test")
    api_client.patch(
        f"/api/donations/{donation_id}/status",
        json={"target_status": "APPROVED"},
        headers=auth_headers(manager),
    )
    created = api_client.post(
        "/api/deliveries",
        json={
            "donation_id": donation_id,
            "route_id": 1,
            "recipient_branch_id": 1,
            "scheduled_for": FUTURE,
            "items": [{"food_item_id": item_id, "quantity_delivered_kg": "6.00"}],
        },
        headers=auth_headers(manager),
    )
    assert created.status_code == 201, created.get_json()
    delivery_id = created.get_json()["data"]["delivery_id"]
    cancelled = api_client.patch(
        f"/api/deliveries/{delivery_id}/status",
        json={"target_status": "CANCELLED"},
        headers=auth_headers(manager),
    )
    assert cancelled.status_code == 200, cancelled.get_json()
    assert cancelled.get_json()["data"]["items"] == []
    assert (
        api_client.get(f"/api/deliveries/{delivery_id}").get_json()["data"]["status"] == "CANCELLED"
    )


def test_failed_delivery_is_terminal_and_does_not_distribute(api_client: FlaskClient) -> None:
    donor = login(api_client, "donor.a@example.test")
    donation = create_donation(api_client, donor)
    donation_id = donation["donation_id"]
    item_id = donation["items"][0]["food_item_id"]
    manager = login(api_client, "manager.a@example.test")
    api_client.patch(
        f"/api/donations/{donation_id}/status",
        json={"target_status": "SCHEDULED"},
        headers=auth_headers(manager),
    )
    driver = login(api_client, "driver.a@example.test")
    api_client.patch(
        f"/api/donations/{donation_id}/status",
        json={"target_status": "COLLECTED"},
        headers=auth_headers(driver),
    )
    inspector = login(api_client, "inspector.a@example.test")
    api_client.post(
        f"/api/donations/{donation_id}/inspections",
        json={"packaging_integrity": "INTACT", "safety_status": "PASSED"},
        headers=auth_headers(inspector),
    )
    manager = login(api_client, "manager.a@example.test")
    api_client.patch(
        f"/api/donations/{donation_id}/status",
        json={"target_status": "APPROVED"},
        headers=auth_headers(manager),
    )
    created = api_client.post(
        "/api/deliveries",
        json={
            "donation_id": donation_id,
            "route_id": 1,
            "recipient_branch_id": 1,
            "items": [{"food_item_id": item_id, "quantity_delivered_kg": "10.00"}],
        },
        headers=auth_headers(manager),
    )
    delivery_id = created.get_json()["data"]["delivery_id"]
    failed = api_client.patch(
        f"/api/deliveries/{delivery_id}/status",
        json={"target_status": "FAILED"},
        headers=auth_headers(manager),
    )
    assert failed.status_code == 200, failed.get_json()
    cancelled = api_client.patch(
        f"/api/deliveries/{delivery_id}/status",
        json={"target_status": "CANCELLED"},
        headers=auth_headers(manager),
    )
    assert cancelled.status_code == 409
    assert cancelled.get_json()["error"]["code"] == "invalid_transition"
    detail = api_client.get(f"/api/donations/{donation_id}").get_json()["data"]
    assert detail["status"] == "APPROVED"
    assert detail["items"][0]["delivered_kg"] == "0.00"
