# Copyright 2023 Camptocamp SA (http://www.camptocamp.com)
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl.html).
from odoo_test_helper import FakeModelLoader

from odoo.tests.common import TransactionCase


class CommonCase(TransactionCase):
    """Base class for writing endpoint apps tests"""

    # by default disable tracking suite-wise, it's a time saver :)
    tracking_disable = True

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.env = cls.env(
            context=dict(
                cls.env.context,
                tracking_disable=cls.tracking_disable,
            )
        )
        cls.loader = FakeModelLoader(cls.env, cls.__module__)
        cls.loader.backup_registry()
        from .fake_models import FakeApp

        cls.loader.update_registry((FakeApp,))
        cls.addClassCleanup(cls.loader.restore_registry)
        cls.app_model = cls.env[FakeApp._name]
        cls.setUpUsers()
        cls.setUpApp()

    @classmethod
    def setUpUsers(cls):
        Users = cls.env["res.users"].with_context(
            {"no_reset_password": True, "mail_create_nosubscribe": True}
        )
        cls.user_simple = Users.create(cls._user_simple_values())
        cls.user_manager = Users.create(cls._user_manager_values())
        cls.env = cls.env(user=cls.user_simple)

    @classmethod
    def _user_simple_values(cls):
        return {
            "name": "Johnny Glamour",
            "login": "jglam",
            "email": "j@glamour.example.com",
            "tz": cls.env.user.tz,
        }

    @classmethod
    def _user_manager_values(cls):
        return {
            "name": "Johnny Manager",
            "login": "jmanager",
            "email": "jmanager@example.com",
            "tz": cls.env.user.tz,
        }

    @classmethod
    def setUpApp(cls):
        cls.shopfloor_app = (
            cls.app_model.with_user(cls.user_manager)
            .create(
                {
                    "tech_name": "test",
                    "name": "Test",
                    "short_name": "test",
                }
            )
            .with_user(cls.user_simple)
        )
