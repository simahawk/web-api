# Copyright 2023 Camptocamp SA (http://www.camptocamp.com)
# @author Simone Orsi <simahawk@gmail.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import fields, models


class FakeApp(models.Model):

    _name = "fake.endpoint.app"
    _inherit = ["endpoint.app.mixin"]

    app_type = fields.Selection(selection_add=[("fake", "Fake")])
