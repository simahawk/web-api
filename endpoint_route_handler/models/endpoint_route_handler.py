# Copyright 2021 Camptocamp SA
# @author: Simone Orsi <simone.orsi@camptocamp.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).
import importlib
from functools import partial

from distutils.log import error
import logging
import pdb
from psycopg2.extensions import AsIs

from odoo import http
from odoo import _, api, exceptions, fields, models
from odoo.addons.base_sparse_field.models.fields import Serialized

from ..exceptions import EndpointHandlerNotFound


class EndpointRoute(models.Model):

    _name = "endpoint.route"
    _description = "Endpoint Route"

    active = fields.Boolean(default=True)
    key = fields.Char(required=True, copy=False, index=True)
    name = fields.Char(required=True)
    route = fields.Char(
        required=True,
        index=True,
        compute="_compute_route",
        inverse="_inverse_route",
        readonly=False,
        store=True,
        copy=False,
    )
    routing = Serialized(copy=False)
    options = Serialized(copy=False)
    route_group = fields.Char(help="Use this to classify routes together")
    route_type = fields.Selection(selection="_selection_route_type", default="http")
    auth_type = fields.Selection(
        selection="_selection_auth_type", default="user_endpoint"
    )
    request_content_type = fields.Selection(selection="_selection_request_content_type")
    # TODO: this is limiting the possibility of supporting more than one method.
    request_method = fields.Selection(
        selection="_selection_request_method", required=True
    )
    # # TODO: validate params? Just for doc? Maybe use Cerberus?
    # # -> For now let the implementer validate the params in the snippet.
    # request_params = Serialized(help="TODO")

    endpoint_hash = fields.Char(
        compute="_compute_endpoint_hash", help="Identify the route with its main params"
    )
    csrf = fields.Boolean(default=False)
    consumer_model = fields.Char()
    # Used to register routes unrelated from another real record.
    parent_id = fields.Many2one(comodel_name="endpoint.route")

    # TODO: add flag to prevent route updates on save ->
    # should be handled by specific actions + filter in a tree view + btn on form

    _sql_constraints = [
        (
            "endpoint_key_unique",
            "unique(key)",
            "You can register an endpoint key only once.",
        ),
        (
            "endpoint_route_unique",
            "unique(route)",
            "You can register an endpoint route only once.",
        )
    ]

    @property
    def _logger(self):
        return logging.getLogger(self._name)

    def _selection_route_type(self):
        return [("http", "HTTP"), ("json", "JSON")]

    def _selection_auth_type(self):
        return [("public", "Public"), ("user_endpoint", "User")]

    def _selection_request_method(self):
        return [
            ("GET", "GET"),
            ("POST", "POST"),
            ("PUT", "PUT"),
            ("DELETE", "DELETE"),
        ]

    def _selection_request_content_type(self):
        return [
            ("", "None"),
            ("text/plain", "Text"),
            ("text/csv", "CSV"),
            ("application/json", "JSON"),
            ("application/xml", "XML"),
            ("application/x-www-form-urlencoded", "Form"),
        ]

    @api.depends(lambda self: self._routing_impacting_fields())
    def _compute_endpoint_hash(self):
        # Do not use read to be able to play this on NewId records too
        # (NewId records are classified as missing in ACL check).
        # values = self.read(self._routing_impacting_fields())
        values = [
            {fname: str(rec[fname]) for fname in self._routing_impacting_fields()}
            for rec in self
        ]
        for rec, vals in zip(self, values):
            vals.pop("id", None)
            rec.endpoint_hash = hash(tuple(vals.values()))

    def _routing_impacting_fields(self):
        return ("route", "auth_type", "request_method", "routing", "options", "csrf")

    @api.depends("route")
    def _compute_route(self):
        for rec in self:
            rec.route = rec._clean_route()

    def _inverse_route(self):
        for rec in self:
            rec.route = rec._clean_route()

    # TODO: move to something better? Eg: computed field?
    # Shall we use the route_group? TBD!
    _endpoint_route_prefix = ""

    def _clean_route(self):
        route = (self.route or "").strip()
        if not route.startswith("/"):
            route = "/" + route
        prefix = self._endpoint_route_prefix
        if prefix and not route.startswith(prefix):
            route = prefix + route
        return route

    _blacklist_routes = ("/", "/web")  # TODO: what else?

    @api.constrains("route")
    def _check_route(self):
        for rec in self:
            if rec.route in self._blacklist_routes:
                raise exceptions.UserError(
                    _("`%s` uses a blacklisted routed = `%s`") % (rec.name, rec.route)
                )

    @api.constrains("request_method", "request_content_type")
    def _check_request_method(self):
        for rec in self:
            if rec.request_method in ("POST", "PUT") and not rec.request_content_type:
                raise exceptions.UserError(
                    _("Request content type is required for POST and PUT.")
                )
    
    def _routing_mandatory_keys(self, fname):
        mandatory_keys = {
            "routing": {
                "type": {},
                "auth": {},
                "methods": {},
                "routes": {},
                "csrf": {},
            },
            "options": {
                "handler": {
                    "klass_dotted_path": {},
                    "method_name": {},
                }
            }
        }
        return mandatory_keys[fname]

    def _routing_check_missing_keys(self, value, to_check, errors=None):
        errors = errors or []
        for k, children in to_check.items():
            if not k in value:
                errors.append(k)
                continue
            self._routing_check_missing_keys(value[k], children, errors=errors)
        return errors

    @api.constrains("routing", "options")
    def _check_routing_metadata(self):
        for rec in self:
            for fname in ("options", "routing"):
                errors = self._routing_check_missing_keys(rec[fname], self._routing_mandatory_keys(fname))
                if errors:
                    raise exceptions.UserError(
                        _("%s `%s` missing mandatory keys: %s") % (rec.route, fname, ", ".join(errors))
                    )
        
    def get_consumer(self, consumer_model=None):
        consumer_model = consumer_model or self.consumer_model
        assert consumer_model
        return self.env[consumer_model].search(
            [("endpoint_route_id", "=", self.id)], limit=1
        )

    def get_endpoint(self):
        """Lookup http.Endpoint to be used for the routing map."""
        options = self.routing["options"]
        handler = self._get_handler(options)
        pargs = options.get("default_pargs", ())
        kwargs = options.get("default_kwargs", {})
        method = partial(handler, *pargs, **kwargs)
        return http.EndPoint(method, self.routing)

    def _get_handler(self, options):
        """Resolve endpoint handler lookup.

        `options` must contain `handler` key to provide:

            * the controller's klass via `klass_dotted_path`
            * the controller's method to use via `method_name`

        Lookup happens by:

            1. importing the controller klass module
            2. loading the klass
            3. accessing the method via its name

        If any of them is not found, a specific exception is raised.
        """
        # TODO: shall we cache imports?
        mod_path, klass_name = options["klass_dotted_path"].rsplit(".", 1)
        try:
            mod = importlib.import_module(mod_path)
        except ImportError as exc:
            raise EndpointHandlerNotFound(f"Module `{mod_path}` not found") from exc
        try:
            klass = getattr(mod, klass_name)
        except AttributeError as exc:
            raise EndpointHandlerNotFound(f"Class `{klass_name}` not found") from exc
        method_name = options["method_name"]
        try:
            method = getattr(klass(), method_name)
        except AttributeError as exc:
            raise EndpointHandlerNotFound(
                f"Method name `{method_name}` not found"
            ) from exc
        return method

    def get_all(self):
        return self.sudo().search([])

    def get_last_version(self):
        return self.sudo().search([], limit=1, order="write_date desc").write_date
