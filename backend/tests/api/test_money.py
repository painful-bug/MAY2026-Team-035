"""Invoice and payment validation API cases."""

from fastapi.testclient import TestClient


def test_api_013_invoice_rejects_empty_line_items(
    admin_api_client: TestClient,
    csrf_headers: dict[str, str],
) -> None:
    endpoint = "POST /api/v1/invoices"
    input_data = {
        "title": "August maintenance",
        "flat": "B-1204",
        "lineItems": [],
    }
    expected_output = {
        "status_code": 422,
        "error_code": "request_validation_error",
    }

    response = admin_api_client.post(
        "/api/v1/invoices",
        json=input_data,
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
    }

    assert endpoint == "POST /api/v1/invoices"
    assert actual_output["status_code"] == expected_output["status_code"]
    assert actual_output["body"]["error"]["code"] == expected_output["error_code"]


def test_api_014_payment_rejects_zero_amount(
    admin_api_client: TestClient,
    csrf_headers: dict[str, str],
) -> None:
    endpoint = "POST /api/v1/invoices/invoice-id/payments"
    input_data = {"amount": 0, "method": "UPI", "reference": "UPI-001"}
    expected_output = {
        "status_code": 422,
        "error_code": "request_validation_error",
    }

    response = admin_api_client.post(
        "/api/v1/invoices/invoice-id/payments",
        json=input_data,
        headers=csrf_headers,
    )
    actual_output = {
        "status_code": response.status_code,
        "body": response.json(),
    }

    assert endpoint == "POST /api/v1/invoices/invoice-id/payments"
    assert actual_output["status_code"] == expected_output["status_code"]
    assert actual_output["body"]["error"]["code"] == expected_output["error_code"]
