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
    _table = "endpoint_route"

    @classmethod
    def registry_for(cls, cr):
        return cls(cr)

    def __init__(self, cr):
        self.cr = cr

    def get_rules(self, keys=None, where=None):
        for row in self._get_rules(keys=keys, where=where):
            yield EndpointRule.from_row(self.cr.dbname, row)

    def _get_rules(self, keys=None, where=None, one=False):
        query = "SELECT {} FROM endpoint_route".format(",".join(EndpointRule.ordered_columns()))
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
        "endpoint_hash",
        "routing_metadata",
        "route_group",
    )

    def __init__(self, dbname, **kw):
        self._dbname = dbname
        for k in self.ordered_columns():
            setattr(self, k, kw.get(k))

    @staticmethod
    def ordered_columns():
        return (
            "key",
            "route",
            "options",
            "routing",
            "endpoint_hash",
            "route_group",
        )

    def __repr__(self):
        # FIXME: use class name, remove key
        return (
            f"<{self.__class__.__name__}: {self.key}"
            + (f" #{self.route_group}" if self.route_group else "nogroup")
            + ">"
        )

    def _ordered_columns(cls):
        return 

    @classmethod
    def from_record(cls, record):
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
