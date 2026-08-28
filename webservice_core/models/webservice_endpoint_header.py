# Copyright 2026 Camptocamp SA
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).
from odoo import fields, models


class WebserviceEndpointHeader(models.Model):
    _name = "webservice.endpoint.header"
    _description = "WebService Endpoint Header"

    endpoint_id = fields.Many2one(
        "webservice.endpoint", required=True, ondelete="cascade"
    )
    name = fields.Char(required=True)
    value = fields.Char(required=True)
