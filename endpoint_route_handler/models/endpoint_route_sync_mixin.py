# Copyright 2021 Camptocamp SA
# @author: Simone Orsi <simone.orsi@camptocamp.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import logging
from functools import partial

from odoo import api, fields, models

from ..registry import EndpointRegistry

_logger = logging.getLogger(__file__)


# TODO: remove
class EndpointRouteSyncMixin(models.AbstractModel):
    """Mixin to handle synchronization of custom routes to the registry.

    Consumers of this mixin gain:

        * handling of sync state
        * sync helpers
        * automatic registration of routes on boot

    Consumers of this mixin must implement:

        * `_prepare_endpoint_rules` to retrieve all the `EndpointRule` to register
        * `_registered_endpoint_rule_keys` to retrieve all keys of registered rules
    """

    _name = "endpoint.route.sync.mixin"
    _description = "Endpoint Route sync mixin"

    active = fields.Boolean(default=True)
    registry_sync = fields.Boolean(
        help="ON: the record has been modified and registry was not notified."
        "\nNo change will be active until this flag is set to false via proper action."
        "\n\nOFF: record in line with the registry, nothing to do.",
        default=False,
        copy=False,
    )

    def write(self, vals):
        if any([x in vals for x in self._routing_impacting_fields() + ("active",)]):
            # Mark as out of sync
            vals["registry_sync"] = False
        res = super().write(vals)
        if vals.get("registry_sync"):
            # NOTE: this is not done on create to allow bulk reload of the envs
            # and avoid multiple env restarts in case of multiple edits
            # on one or more records in a row.
            self._add_after_commit_hook(self.ids)
        return res

    @api.model
    def _add_after_commit_hook(self, record_ids):
        self.env.cr.postcommit.add(
            partial(self._handle_registry_sync, record_ids),
        )

    def _handle_registry_sync(self, record_ids=None):
        record_ids = record_ids or self.ids
        _logger.info("%s sync registry for %s", self._name, str(record_ids))
        records = self.browse(record_ids).exists()
        records.filtered(lambda x: x.active).write({"registry_sync": True})

    @property
    def _endpoint_registry(self):
        return EndpointRegistry.registry_for(self.env.cr)

    def unlink(self):
        self._force_routing_map_refresh()
        return super().unlink()

    def _force_routing_map_refresh(self):
        """Signal changes to make all routing maps refresh."""
        self.env["ir.http"]._clear_routing_map()  # TODO: redundant?
    
    # TODO: still useful?
    def _registered_endpoint_rule_keys(self):
        """Return list of registered `EndpointRule` unique keys for current model."""
        raise NotImplementedError()
