# Copyright 2022 Camptocamp SA
# @author: Simone Orsi <simone.orsi@camptocamp.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import logging
import pdb

from odoo import api, fields, models
from odoo.addons.base_sparse_field.models.fields import Serialized


_logger = logging.getLogger(__name__)

    
class EndpointRouteConsumerMixin(models.AbstractModel):
    """Mixin to host defaults and helpers for models consuming routes.
    """

    _name = "endpoint.route.consumer.mixin"
    _description = "Endpoint Route consumer mixin"

    endpoint_route_id = fields.Many2one(
        comodel_name="endpoint.route",
        delegate=True,
        required=True,
        ondelete="cascade"
    )

    # custom_routing = Serialized(copy=False)

    def unlink(self):
        routes = self.mapped("endpoint_route_id")
        res = super().unlink()
        routes.unlink()
        return res

    def _force_routing_map_refresh(self):
        """Signal changes to make all routing maps refresh."""
        self.env["ir.http"]._clear_routing_map()

    # TODO: needed?
    def _endpoint_routes(self):
        return self.mapped("endpoint_route_id")

    def _endpoint_route_unique_key(self):
        return "{0._name}:{0.id}".format(self)

    @api.model_create_multi
    def create(self, vals_list):
        for vals in vals_list:
            vals.update(self._generate_route_defaults(vals.copy()))
        return super().create(vals_list)

    def write(self, vals):
        impacting = self.env["endpoint.route"]._routing_impacting_fields()
        if set(vals.keys()).intersection(set(impacting)):
            vals.update(self._generate_route_defaults(vals.copy()))
        return super().write(vals)

    _mandatory_routing_keys = ("type", "auth", "methods", "routes", "csrf")
    
    def _generate_route_defaults(self, vals):
        vals["consumer_model"] = self._name
        if "key" not in vals:
            vals["key"] = self._endpoint_route_unique_key()
        if "options" not in vals:
            try:
                handler = self._default_endpoint_options_handler(vals)
            except NotImplementedError:
                handler = self._fallback_endpoint_options_handler(vals)
            vals["options"] = {"handler": handler}
        default_routing = self._get_default_routing(vals)
        routing = vals.get("routing", {})
        for k in self._mandatory_routing_keys:
            if not routing.get(k) and k in default_routing:
                routing[k] = default_routing[k]
        vals["routing"] = routing
        return vals

    def _default_endpoint_options_handler(self, vals):
        raise NotImplementedError()

    def _fallback_endpoint_options_handler(self, vals):
        _logger.warning(
            "No specific endpoint handler options defined for: %s, falling back to default",
            self._name,
        )
        base_path = "odoo.addons.endpoint_route_handler.controllers.main"
        return {
            "klass_dotted_path": f"{base_path}.EndpointNotFoundController",
            "method_name": "auto_not_found",
        }

    # TOOD: the aim here is to decouple the generation of the routing params
    # from the routing model.
    # We should probably make custom_route computed/writeable.
    def _get_default_routing(self, vals):
        routing = {}
        field_defaults =  self.default_get(["auth_type", "route_type", "request_method", "csrf"])
        for k, v in field_defaults.items():
            if k not in vals:
                vals[k] = v
        if "route_type" in vals:
            routing["type"] = vals["route_type"]
        if "auth_type" in vals:
            routing["auth"] = vals["auth_type"]
        if "request_method" in vals:
            routing["methods"] = [vals["request_method"],]
        if "route" in vals:
            routing["routes"] = [vals["route"],]
        if "csrf" in vals:
            routing["csrf"] = vals["csrf"]
        return routing
        