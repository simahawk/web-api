# Copyright 2021 Camptocamp SA (http://www.camptocamp.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
# @author Simone Orsi <simahawk@gmail.com>
import os

from odoo.modules.module import load_information_from_description_file
from odoo.tools.config import config as odoo_config

APP_VERSIONS = {}


def get_version(module_name, module_path=None):
    """Return module version straight from manifest."""
    global APP_VERSIONS
    if APP_VERSIONS.get(module_name):
        return APP_VERSIONS[module_name]
    try:
        info = load_information_from_description_file(module_name, mod_path=module_path)
        APP_VERSIONS[module_name] = info["version"]
        return APP_VERSIONS[module_name]
    except Exception:
        return "dev"


def _get_running_env():
    """Retrieve current system environment.

    Expected key `RUNNING_ENV` is compliant w/ `server_environment` naming
    but is not depending on it.

    Additionally, as specific key for endpoint apps is supported.

    You don't need `server_environment` module to have this feature.
    """
    for key in ("ENDPOINT_APP_RUNNING_ENV", "RUNNING_ENV"):
        if os.getenv(key):
            return os.getenv(key)
        if odoo_config.options.get(key.lower()):
            return odoo_config.get(key.lower())
    return "prod"


RUNNING_ENV = _get_running_env()
