# Copyright 2021 Camptocamp SA
# @author: Simone Orsi <simone.orsi@camptocamp.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import importlib
import json
from functools import partial


from odoo import http
from odoo.tools import DotDict


from .exceptions import EndpointHandlerNotFound


class EndpointRegistry:
    """Registry for endpoints.

    Used to:

    * track registered endpoints
    * retrieve routing rules to load in ir.http routing map
    """

    __slots__ = "cr"
    _table = "endpoint_route_handler"

    @classmethod
    def registry_for(cls, cr):
        return cls(cr)

    def __init__(self, cr):
        self.cr = cr

    def get_rules(self, keys=None, where=None):
        for row in self._get_rules(keys=keys, where=where):
            yield EndpointRule.from_row(self.cr.dbname, row)

    def _get_rules(self, keys=None, where=None, one=False):
        query = "SELECT * FROM endpoint_route"
        pargs = ()
        if keys and not where:
            query += " WHERE key IN %s"
            pargs = (tuple(keys),)
        elif where:
            query += " " + where
        self.cr.execute(query, pargs)
        return self.cr.fetchdictone() if one else self.cr.fetchdictall()

    def get_rules_by_group(self, group):
        rules = self.get_rules(where=f"WHERE route_group='{group}'")
        return rules

    def make_rule(self, *a, **kw):
        return EndpointRule(self.cr.dbname, *a, **kw)

    def get_last_version(self):
        # TODO: do we really need this check?
        # self.cr.execute("SELECT 1 FROM pg_class WHERE RELNAME = 'endpoint_route_version'")
        # if self.cr.fetchone():
        self.cr.execute("SELECT last_value FROM endpoint_route_version")
        return self.cr.fetchone()[0]


class EndpointRule:
    """Hold information for a custom endpoint rule."""

    __slots__ = (
        "_dbname",
        "_opts",
        "key",
        "route",
        "options",
        "endpoint_hash",
        "routing",
        "route_group",
    )

    def __init__(self, dbname, **kw):
        self._dbname = dbname
        for k in self._ordered_columns:
            setattr(self, k, kw.get(k))

    def __repr__(self):
        # FIXME: use class name, remove key
        return (
            f"<{self.__class__.__name__}: {self.key}"
            + (f" #{self.route_group}" if self.route_group else "nogroup")
            + ">"
        )

    @classmethod
    def _ordered_columns(cls):
        return [k for k in cls.__slots__ if not k.startswith("_")]

    @property
    def options(self):
        return DotDict(self._opts)

    @options.setter
    def options(self, value):
        """Validate options.

        See `_get_handler` for more info.
        """
        assert "klass_dotted_path" in value["handler"]
        assert "method_name" in value["handler"]
        self._opts = value

    @property
    def handler_options(self):
        return self.options.handler

    @classmethod
    def from_row(cls, dbname, row):
        key, route, options, routing, endpoint_hash, route_group = row[1:]
        options = json.loads(options)
        routing = json.loads(routing)
        init_args = (
            dbname,
            key,
            route,
            options,
            routing,
            endpoint_hash,
            route_group,
        )
        return cls(*init_args)

    @property
    def endpoint(self):
        """Lookup http.Endpoint to be used for the routing map."""
        handler = self._get_handler()
        pargs = self.handler_options.get("default_pargs", ())
        kwargs = self.handler_options.get("default_kwargs", {})
        method = partial(handler, *pargs, **kwargs)
        return http.EndPoint(method, self.routing)

    def _get_handler(self):
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
        mod_path, klass_name = self.handler_options.klass_dotted_path.rsplit(".", 1)
        try:
            mod = importlib.import_module(mod_path)
        except ImportError as exc:
            raise EndpointHandlerNotFound(f"Module `{mod_path}` not found") from exc
        try:
            klass = getattr(mod, klass_name)
        except AttributeError as exc:
            raise EndpointHandlerNotFound(f"Class `{klass_name}` not found") from exc
        method_name = self.handler_options.method_name
        try:
            method = getattr(klass(), method_name)
        except AttributeError as exc:
            raise EndpointHandlerNotFound(
                f"Method name `{method_name}` not found"
            ) from exc
        return method
