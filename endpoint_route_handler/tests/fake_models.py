# Copyright 2022 Camptocamp SA
# @author Simone Orsi <simahawk@gmail.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import pdb
from odoo import api, fields, models


class EndpointConsumerTest(models.Model):
    _name = "endpoint.consumer.test"
    _inherit = ["endpoint.route.consumer.mixin"]
    _description = _name