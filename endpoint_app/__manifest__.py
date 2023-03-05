# Copyright 2023 Camptocamp SA (http://www.camptocamp.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

{
    "name": "Endpoint app",
    "summary": "Core module for creating mobile apps",
    "version": "16.0.1.0.0",
    "development_status": "Beta",
    "category": "Web",
    "website": "https://github.com/OCA/web-api",
    "author": "Camptocamp, Odoo Community Association (OCA)",
    "maintainers": ["simahawk"],
    "license": "LGPL-3",
    "application": True,
    "depends": [
        "base_sparse_field",
        "endpoint_route_handler",
    ],
    "data": [
        "views/endpoint_app.xml",
        "views/menus.xml",
    ],
}
