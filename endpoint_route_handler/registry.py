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
