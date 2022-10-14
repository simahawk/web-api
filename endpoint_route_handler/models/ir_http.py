# Copyright 2021 Camptocamp SA
# @author: Simone Orsi <simone.orsi@camptocamp.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import logging
from itertools import chain

import werkzeug

from odoo import http, models

from ..registry import EndpointRegistry

_logger = logging.getLogger(__name__)


class IrHttp(models.AbstractModel):
    _inherit = "ir.http"

    @staticmethod
    def _get_endpoint_registry(cr):
        return EndpointRegistry.registry_for(cr)

    @classmethod
    def _generate_routing_rules(cls, modules, converters):
        # Override to inject custom endpoint rules.
        return chain(
            super()._generate_routing_rules(modules, converters),
            cls._endpoint_routing_rules(),
        )

    @classmethod
    def _endpoint_routing_rules(cls):
        """Yield custom endpoint rules"""
        e_registry = cls._get_endpoint_registry(cr = http.request.env.cr)
        for endpoint_rule in e_registry.get_rules():
            _logger.debug("LOADING %s", endpoint_rule)
            endpoint = endpoint_rule.endpoint
            for url in endpoint_rule.routing["routes"]:
                yield (url, endpoint, endpoint_rule.routing)

    @classmethod
    def _auth_method_user_endpoint(cls):
        """Special method for user auth which raises Unauthorized when needed.

        If you get an HTTP request (instead of a JSON one),
        the standard `user` method raises `SessionExpiredException`
        when there's no user session.
        This leads to a redirect to `/web/login`
        which is not desiderable for technical endpoints.

        This method makes sure that no matter the type of request we get,
        a proper exception is raised.
        """
        try:
            cls._auth_method_user()
        except http.SessionExpiredException:
            raise werkzeug.exceptions.Unauthorized()

    @classmethod
    def routing_map(cls, key=None):
        last_version_key = "_endpoint_route_last_version"
        is_routing_map_new = not hasattr(cls, "_routing_map")
        e_registry = cls._get_endpoint_registry(cr = http.request.env.cr)
        last_version = e_registry.get_last_version()
        current_version  = getattr(cls, last_version_key, None)
        if is_routing_map_new:
            setattr(cls, last_version_key, last_version)
        elif current_version < last_version:
            _logger.info("Endpoint registry updated, reset routing map")
            cls._routing_map = {}
            cls._rewrite_len = {}
        return super().routing_map(key=key)

