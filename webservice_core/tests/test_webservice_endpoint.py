# Copyright 2026 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
import responses
from psycopg2 import errors as pg_errors

from odoo import exceptions
from odoo.tests.common import tagged
from odoo.tools import mute_logger

from .common import CommonWebService


@tagged("-at_install", "post_install")
class TestWebserviceEndpoint(CommonWebService):
    @classmethod
    def _setup_records(cls):
        res = super()._setup_records()
        cls.url = "https://localhost.demo.odoo/"
        cls.backend = cls.env["webservice.backend"].create(
            {
                "name": "WebService",
                "protocol": "http",
                "url": cls.url,
                "content_type": "application/xml",
                "tech_name": "demo_ws",
                "auth_type": "api_key",
                "api_key": "backend-key",
                "api_key_header": "Api-Key",
            }
        )
        cls.endpoint = cls.env["webservice.endpoint"].create(
            {
                "name": "Get Order Status",
                "tech_name": "get_order_status",
                "description": "Retrieve the status of an order",
                "backend_id": cls.backend.id,
                "http_method": "get",
                "path": "orders/{order_id}/status",
            }
        )
        return res

    def test_tech_name_unique_per_backend(self):
        with (
            mute_logger("odoo.sql_db"),
            self.assertRaises(pg_errors.UniqueViolation),
            self.cr.savepoint(),
        ):
            self.env["webservice.endpoint"].create(
                {
                    "name": "Duplicate",
                    "tech_name": "get_order_status",
                    "description": "Duplicate tech_name on the same backend",
                    "backend_id": self.backend.id,
                    "http_method": "post",
                }
            )

    def test_tech_name_unique_across_backends_ok(self):
        other_backend = self.backend.copy({"tech_name": "demo_ws_2"})
        # Same ``tech_name`` on a different backend is allowed.
        endpoint = self.env["webservice.endpoint"].create(
            {
                "name": "Get Order Status",
                "tech_name": "get_order_status",
                "description": "Same tech_name, different backend",
                "backend_id": other_backend.id,
                "http_method": "get",
            }
        )
        self.assertTrue(endpoint)

    def test_override_auth_requires_auth_type(self):
        with self.assertRaises(exceptions.UserError):
            self.endpoint.write({"override_auth": True})

    @responses.activate
    def test_call_delegates_to_backend_auth(self):
        url = f"{self.url}orders/42/status"
        responses.add(responses.GET, url, body="{}")
        result = self.endpoint.call(url_params={"order_id": 42})
        self.assertEqual(result, b"{}")
        self.assertEqual(len(responses.calls), 1)
        # No override: the backend's own API key is used.
        self.assertEqual(responses.calls[0].request.headers["Api-Key"], "backend-key")
        self.assertEqual(
            responses.calls[0].request.headers["Content-Type"], "application/xml"
        )

    @responses.activate
    def test_call_with_override_auth_uses_own_credentials(self):
        self.endpoint.write(
            {
                "override_auth": True,
                "auth_type": "api_key",
                "api_key": "endpoint-key",
                "api_key_header": "Api-Key",
                "content_type": "application/json",
            }
        )
        url = f"{self.url}orders/42/status"
        responses.add(responses.GET, url, body="{}")
        result = self.endpoint.call(url_params={"order_id": 42})
        self.assertEqual(result, b"{}")
        self.assertEqual(len(responses.calls), 1)
        self.assertEqual(responses.calls[0].request.headers["Api-Key"], "endpoint-key")
        self.assertEqual(
            responses.calls[0].request.headers["Content-Type"], "application/json"
        )

    @responses.activate
    def test_call_merges_static_headers(self):
        self.endpoint.write(
            {"header_ids": [(0, 0, {"name": "X-Demo", "value": "demo-value"})]}
        )
        url = f"{self.url}orders/42/status"
        responses.add(responses.GET, url, body="{}")
        self.endpoint.call(url_params={"order_id": 42})
        self.assertEqual(responses.calls[0].request.headers["X-Demo"], "demo-value")

    @responses.activate
    def test_call_headers_override_static_headers(self):
        self.endpoint.write(
            {"header_ids": [(0, 0, {"name": "X-Demo", "value": "demo-value"})]}
        )
        url = f"{self.url}orders/42/status"
        responses.add(responses.GET, url, body="{}")
        self.endpoint.call(
            url_params={"order_id": 42}, headers={"X-Demo": "call-time-value"}
        )
        self.assertEqual(
            responses.calls[0].request.headers["X-Demo"], "call-time-value"
        )
