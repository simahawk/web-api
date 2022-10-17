# Copyright 2022 Camptocamp SA
# @author Simone Orsi <simahawk@gmail.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import fields, models


class EndpointConsumerTest(models.Model):
    _name = "endpoint.consumer.test"
    _description = _name

    endpoint_route_id = fields.Many2one(
        comodel_name="endpoint.route",
        delegate=True,
        required=True,
        ondelete="cascade"
    )

    def create(self, vals):
        vals["consumer_model"] = self._name
        return super().create(vals)