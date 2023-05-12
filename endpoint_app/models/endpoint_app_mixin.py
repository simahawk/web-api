# Copyright 2021 Camptocamp SA (http://www.camptocamp.com)
# @author Simone Orsi <simahawk@gmail.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).

from odoo import api, fields, models
from odoo.tools import DotDict

from ..utils import RUNNING_ENV, get_version


class EndpointAppMixin(models.Model):
    """Mixin to configure endpoint apps."""

    _name = "endpoint.app.mixin"
    # TODO: collection base needed?
    # If we don't register components against it I think it's not.
    _inherit = ["collection.base", "endpoint.route.sync.mixin"]
    _description = "An endpoint app"

    active = fields.Boolean(default=True)
    name = fields.Char(required=True, translate=True)
    app_type = fields.Selection(selection=[("", "None")])
    short_name = fields.Char(
        required=True, translate=True, help="Needed for app manifest"
    )
    # Unique name
    tech_name = fields.Char(required=True, index=True)
    root_path = fields.Char(
        compute="_compute_root_path",
        inverse="_inverse_root_path",
        required=True,
        readonly=False,
        index=True,
        store=True,
        copy=False,
    )
    api_route = fields.Char(
        compute="_compute_routes",
        compute_sudo=True,
        help="Base route for endpoints attached to this app, public version.",
    )
    url = fields.Char(compute="_compute_routes", help="Public URL to use the app.")
    api_docs_url = fields.Char(
        compute="_compute_routes", help="Public URL for api docs."
    )
    # TODO: needed if w/ fastpi auth is delegated to the api route?
    # Maybe it shhould be always "public" by defualt for fastapi only?
    auth_type = fields.Selection(
        selection="_selection_auth_type", default="user_endpoint"
    )
    registered_routes = fields.Text(
        compute="_compute_registered_routes",
        compute_sudo=True,
        help="Technical field to allow developers to check registered routes on the form",
        groups="base.group_no_one",
    )
    app_version = fields.Char(compute="_compute_app_version")
    lang_id = fields.Many2one(
        "res.lang",
        string="Default language",
        help="If set, the app will be first loaded with this lang.",
    )
    lang_ids = fields.Many2many("res.lang", string="Available languages")
    route_group = fields.Char(compute="_compute_route_group")

    _sql_constraints = [
        ("tech_name", "unique(tech_name)", "tech_name must be unique"),
        ("root_path", "unique(root_path)", "root_path must be unique"),
    ]

    _route_patterns = dict(
        api="/{root_path}/api/",
        url="/{root_path}/app/{tech_name}/",
        # TODO: /openapi.json for fastapi (could be changed in base_rest too)
        docs="/{root_path}/api-docs/{tech_name}/",
        # TODO needed by default?
        manifest="/{root_path}/manifest.json",
    )

    def _route_for(self, key):
        return self._route_patterns[key].format(
            root_path=self.root_path, tech_name=self.tech_name
        )

    @api.depends("tech_name")
    def _compute_routes(self):
        for rec in self:
            rec.api_route = rec._route_for("api")
            rec.url = rec._route_for("url")
            rec.api_docs_url = rec._route_for("docs")

    @api.depends("root_path")
    def _compute_root_path(self):
        clean_route = self.env["endpoint.route.handler"].clean_route
        for rec in self:
            rec.root_path = clean_route(rec.root_path)

    def _inverse_root_path(self):
        clean_route = self.env["endpoint.route.handler"].clean_route
        for rec in self:
            rec.root_path = clean_route(rec.root_path)

    @api.constrains("root_path")
    def _check_route_path(self):
        validate_route = self.env["endpoint.route.handler"].validate_route
        for rec in self:
            validate_route(rec.root_path, rec.name)

    @api.depends()
    def _compute_registered_routes(self):
        for rec in self:
            routes = sorted(rec._registered_routes(), key=lambda x: x.route)
            vals = []
            for endpoint_rule in routes:
                vals.append(
                    f"{endpoint_rule.route} ({', '.join(endpoint_rule.routing['methods'])})"
                )
            rec.registered_routes = "\n".join(vals)

    def _compute_app_version(self):
        # Override this to choose your own versioning policy
        for rec in self:
            # TODO: is self.__module__ reliable on intheritance?
            rec.app_version = get_version(self.__module__)

    def _compute_route_group(self):
        for rec in self:
            rec.route_group = rec._get_route_group()

    def _get_route_group(self):
        return f"{self._name}:{self.tech_name}"

    def _selection_auth_type(self):
        return self.env["endpoint.route.handler"]._selection_auth_type()

    def api_url_for_endpoint(self, *parts):
        """Handy method to generate API URLs for current app."""
        path = "/".join([x.strip() for x in parts if x and x.strip()])
        return f"{self.api_route}/{path}".rstrip("/")

    def action_open_app(self):
        return {
            "type": "ir.actions.act_url",
            "name": self.name,
            "url": self.url,
            "target": "new",
        }

    def action_open_app_docs(self):
        return {
            "type": "ir.actions.act_url",
            "name": self.name,
            "url": self.api_docs_url,
            "target": "new",
        }

    def _routing_impacting_fields(self):
        return ("tech_name", "auth_type", "root_path")

    def _registered_endpoint_rule_keys(self):
        # `endpoint.route.sync.mixin` api
        return [x[0] for x in self._registered_routes()]

    def _registered_routes(self):
        registry = self.env["endpoint.route.handler"]._endpoint_registry
        return registry.get_rules_by_group(self.route_group)

    def _name_with_env(self):
        name = self.name
        if RUNNING_ENV and RUNNING_ENV != "prod":
            name += f" ({RUNNING_ENV})"
        return name

    def _make_app_info(self, demo=False):
        base_url = self.api_route.rstrip("/") + "/"
        return DotDict(
            name=self._name_with_env(),
            short_name=self.short_name,
            base_url=base_url,
            url=self.url,
            manifest_url=self.url + "manifest.json",
            auth_type=self.auth_type,
            profile_required=self.profile_required,
            demo_mode=demo,
            version=self.app_version,
            running_env=RUNNING_ENV,
            lang=self._app_info_lang(),
        )

    def _app_info_lang(self):
        enabled = []
        conv = self._app_convert_lang_code
        if self.lang_ids:
            enabled = [conv(x.code) for x in self.lang_ids]
        return dict(
            default=conv(self.lang_id.code) if self.lang_id else False,
            enabled=enabled,
        )

    def _app_convert_lang_code(self, code):
        # TODO: we should probably let the front decide the format
        return code.replace("_", "-")

    def _make_app_manifest(self, icons=None, **kw):
        param = (
            self.env["ir.config_parameter"]
            .sudo()
            .get_param("web.base.url", "")
            .rstrip("/")
        )
        manifest = {
            "name": self._name_with_env(),
            "short_name": self.short_name,
            "start_url": param + self.url,
            "scope": param + self.url,
            "id": self.url,
            "display": "fullscreen",
            "icons": icons or [],
        }
        manifest.update(kw)
        return manifest

    @api.onchange("lang_id")
    def _onchange_lang_id(self):
        if self.env.context.get("from_onchange__lang_ids"):
            return
        if self.lang_id and self.lang_id not in self.lang_ids:
            self.with_context(from_onchange__lang_id=1).lang_ids += self.lang_id

    @api.onchange("lang_ids")
    def _onchange_lang_ids(self):
        if self.env.context.get("from_onchange__lang_id"):
            return
        if self.lang_ids and self.lang_id and self.lang_id not in self.lang_ids:
            self.with_context(from_onchange__lang_ids=1).lang_id = False
