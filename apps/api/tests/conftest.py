from __future__ import annotations

import os
from collections.abc import Iterator
from datetime import date, datetime
from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session

from sfc_api import create_app
from sfc_api.config import Settings
from sfc_api.extensions import build_engine
from sfc_api.models import (
    AppUser,
    Branch,
    CoverageArea,
    FoodCategory,
    Organization,
    Route,
    RouteAssignment,
    UserCredential,
)
from sfc_api.security.passwords import hash_password

TEST_SECRET_KEY = "test-only-secret-key-" + "x" * 40


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment="testing",
        secret_key=TEST_SECRET_KEY,
        timezone="Asia/Kolkata",
        log_level="DEBUG",
        database_url=None,
        testing=True,
    )


@pytest.fixture
def app(settings: Settings) -> Flask:
    return create_app(settings)


@pytest.fixture
def client(app: Flask) -> Iterator[FlaskClient]:
    with app.test_client() as test_client:
        yield test_client


TEST_DB = "smart_food_supply_chain_api_test"
TEST_PASSWORD = "TestPass!12345"
_TEST_HASH = hash_password(TEST_PASSWORD)
_ROOT_CNF = Path(os.environ.get("SFC_ROOT_CNF", "C:/Users/basil/.sfc_phase2.cnf"))
_TEST_PASSWORD_FILE = Path(
    os.environ.get("SFC_API_TEST_PASSWORD_FILE", "C:/Users/basil/.sfc_api_test_password")
)
_TABLES = [
    "delivery_review",
    "spoilage_record",
    "delivery_item",
    "delivery",
    "inspection_log",
    "donation_status_history",
    "donation_item",
    "donation",
    "route_assignment",
    "route",
    "dependent",
    "user_credential",
    "branch",
    "app_user",
    "coverage_area",
    "food_category",
    "organization",
]


def _root_connection():
    import configparser

    parser = configparser.ConfigParser()
    parser.read(_ROOT_CNF)
    password = parser.get("client", "password", fallback=None)
    if not password or not _TEST_PASSWORD_FILE.is_file():
        pytest.skip("Automated database credentials are not available on this machine.")
    return create_engine(
        f"mysql+pymysql://root:{password}@127.0.0.1:3306/{TEST_DB}?charset=utf8mb4"
    )


def _test_engine():
    password = _TEST_PASSWORD_FILE.read_text(encoding="utf-8").strip()
    return build_engine(
        f"mysql+pymysql://sfc_api_test@127.0.0.1:3306/{TEST_DB}?charset=utf8mb4",
        password,
    )


def reset_and_seed() -> None:
    assert TEST_DB == "smart_food_supply_chain_api_test", "Refusing a non-test database."
    root = _root_connection()
    try:
        with root.begin() as connection:
            connection.execute(text("SET FOREIGN_KEY_CHECKS=0"))
            for table in _TABLES:
                connection.execute(text(f"TRUNCATE TABLE `{table}`"))
            connection.execute(text("SET FOREIGN_KEY_CHECKS=1"))
    finally:
        root.dispose()
    engine = _test_engine()
    try:
        with Session(engine) as db:
            db.add(
                Organization(
                    organization_id=1,
                    organization_name="Test Org",
                    hq_address="HQ",
                    hq_pincode="403001",
                    hq_contact_no="9876543210",
                )
            )
            db.flush()
            for uid, name, email, role in [
                (1, "Manager A", "manager.a@example.test", "NGO_MANAGER"),
                (2, "Manager B", "manager.b@example.test", "NGO_MANAGER"),
                (3, "Donor A", "donor.a@example.test", "DONOR"),
                (4, "Donor B", "donor.b@example.test", "DONOR"),
                (5, "Donor Orphan", "donor.o@example.test", "DONOR"),
                (6, "Driver A", "driver.a@example.test", "DRIVER"),
                (7, "Driver B", "driver.b@example.test", "DRIVER"),
                (8, "Inspector A", "inspector.a@example.test", "SAFETY_INSPECTOR"),
                (9, "Inspector B", "inspector.b@example.test", "SAFETY_INSPECTOR"),
                (10, "Pending Donor", "pending.donor@example.test", "DONOR"),
            ]:
                db.add(
                    AppUser(
                        user_id=uid,
                        full_name=name,
                        email=email,
                        phone="9876543210",
                        user_role=role,
                        account_status="INACTIVE" if uid == 10 else "ACTIVE",
                        primary_branch_id=None,
                    )
                )
            db.flush()
            db.add_all(
                [
                    Branch(
                        branch_id=1,
                        organization_id=1,
                        branch_name="Branch A",
                        address="A",
                        pincode="403001",
                        contact_no="9876543210",
                        established_date=date(2020, 1, 1),
                        regional_manager_user_id=1,
                    ),
                    Branch(
                        branch_id=2,
                        organization_id=1,
                        branch_name="Branch B",
                        address="B",
                        pincode="403002",
                        contact_no="9876543210",
                        established_date=date(2020, 1, 1),
                        regional_manager_user_id=2,
                    ),
                ]
            )
            db.flush()
            for uid, branch_id in [
                (1, 1),
                (2, 2),
                (3, 1),
                (4, 2),
                (6, 1),
                (7, 2),
                (8, 1),
                (9, 2),
                (10, 1),
            ]:
                db.get(AppUser, uid).primary_branch_id = branch_id
            db.add_all(
                [
                    CoverageArea(
                        coverage_area_id=1, area_name="Area A", city="Panaji", pincode="403001"
                    ),
                    CoverageArea(
                        coverage_area_id=2, area_name="Area B", city="Margao", pincode="403002"
                    ),
                    FoodCategory(category_id=1, category_name="Cooked meals"),
                    FoodCategory(category_id=2, category_name="Bakery"),
                    FoodCategory(category_id=3, category_name="Produce"),
                ]
            )
            db.flush()
            db.add_all(
                [
                    Route(
                        route_id=1,
                        managing_branch_id=1,
                        designated_driver_user_id=6,
                        coverage_area_id=1,
                        route_type="PICKUP",
                        route_status="ACTIVE",
                    ),
                    Route(
                        route_id=2,
                        managing_branch_id=2,
                        designated_driver_user_id=7,
                        coverage_area_id=2,
                        route_type="PICKUP",
                        route_status="ACTIVE",
                    ),
                ]
            )
            db.flush()
            db.add(
                RouteAssignment(
                    user_id=6,
                    route_id=1,
                    hours_per_week=10,
                    assigned_date=date(2026, 1, 1),
                )
            )
            for uid in range(1, 11):
                db.add(
                    UserCredential(
                        user_id=uid,
                        password_hash=_TEST_HASH,
                        must_change_password=uid == 10,
                        failed_attempts=0,
                        password_changed_at=datetime(2026, 1, 1),
                        created_at=datetime(2026, 1, 1),
                        updated_at=datetime(2026, 1, 1),
                    )
                )
            db.commit()
    finally:
        engine.dispose()


@pytest.fixture
def db_settings() -> Settings:
    password = _TEST_PASSWORD_FILE.read_text(encoding="utf-8").strip()
    return Settings(
        environment="testing",
        secret_key="integration-secret-" + "p" * 40,
        timezone="Asia/Kolkata",
        log_level="WARNING",
        database_url=f"mysql+pymysql://sfc_api_test@127.0.0.1:3306/{TEST_DB}?charset=utf8mb4",
        testing=True,
        database_password=password,
        app_origins=("http://127.0.0.1:5173",),
    )


@pytest.fixture
def db_app(db_settings: Settings) -> Flask:
    reset_and_seed()
    return create_app(db_settings)


@pytest.fixture
def api_client(db_app: Flask) -> Iterator[FlaskClient]:
    with db_app.test_client() as test_client:
        yield test_client


def csrf(client: FlaskClient) -> str:
    response = client.get("/api/auth/csrf")
    assert response.status_code == 200
    return response.get_json()["data"]["csrf_token"]


def auth_headers(token: str) -> dict[str, str]:
    return {"X-CSRF-Token": token, "Origin": "http://127.0.0.1:5173"}


def login(client: FlaskClient, email: str, password: str = TEST_PASSWORD) -> str:
    token = csrf(client)
    response = client.post(
        "/api/auth/login",
        json={"email": email, "password": password},
        headers=auth_headers(token),
    )
    assert response.status_code == 200, response.get_json()
    return response.get_json()["data"]["csrf_token"]
