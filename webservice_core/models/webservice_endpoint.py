# Copyright 2026 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import _, api, exceptions, fields, models


class WebserviceEndpoint(models.Model):
    """A specific, UI-configurable call on a webservice backend.

    Unlike a plain ``backend.call(method, url=..., ...)``, an endpoint bundles
    the HTTP method, relative path, static headers and (optionally) its own
    authentication into one named, reusable record: ``endpoint.call(...)``.

    Authentication is inherited from the backend unless ``override_auth`` is
    set, in which case the endpoint uses its own auth fields (from
    ``webservice.request.mixin``) instead - fully independent from the
    backend's credentials.
    """

    _name = "webservice.endpoint"
    _inherit = ["webservice.request.mixin"]
    _description = "WebService Endpoint"

    name = fields.Char(required=True)
    tech_name = fields.Char(required=True)
    description = fields.Text(required=True)
    backend_id = fields.Many2one(
        "webservice.backend", required=True, ondelete="cascade", index=True
    )
    company_id = fields.Many2one(
        related="backend_id.company_id", store=True, readonly=True
    )
    active = fields.Boolean(default=True)
    http_method = fields.Selection(
        [
            ("get", "GET"),
            ("post", "POST"),
            ("put", "PUT"),
            ("delete", "DELETE"),
        ],
        required=True,
        default="get",
    )
    path = fields.Char(
        help="Relative path appended to the backend URL. "
        "Supports the same '{placeholder}' syntax as the backend URL."
    )
    override_auth = fields.Boolean(
        string="Override Authentication",
        help="Use this endpoint's own authentication instead of the backend's.",
    )
    auth_type = fields.Selection(required=False)
    header_ids = fields.One2many(
        "webservice.endpoint.header", "endpoint_id", string="Headers"
    )

    _sql_constraints = [
        (
            "tech_name_backend_uniq",
            "unique(backend_id, tech_name)",
            "An endpoint with this technical name already exists for this backend.",
        ),
    ]

    @api.constrains("override_auth", "auth_type")
    def _check_override_auth(self):
        for rec in self:
            if rec.override_auth and not rec.auth_type:
                raise exceptions.UserError(
                    _(
                        "Endpoint '%(name)s' overrides authentication: "
                        "an authentication type is required."
                    )
                    % {"name": rec.name}
                )

    def _get_base_url(self):
        return self.backend_id.url

    def call(self, url_params=None, **kwargs):
        self.ensure_one()
        kwargs.setdefault("url", self.path)
        headers = {h.name: h.value for h in self.header_ids}
        headers.update(kwargs.pop("headers", None) or {})
        if headers:
            kwargs["headers"] = headers
        if self.content_type and "content_type" not in kwargs:
            kwargs["content_type"] = self.content_type
        if self.override_auth:
            return super().call(self.http_method, url_params=url_params, **kwargs)
        return self.backend_id.call(self.http_method, url_params=url_params, **kwargs)
