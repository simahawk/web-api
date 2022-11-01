# Copyright 2021 Camptocamp SA
# @author: Simone Orsi <simone.orsi@camptocamp.com>
# License LGPL-3.0 or later (http://www.gnu.org/licenses/lgpl).

import pdb
from urllib import request
from psycopg2.errors import UniqueViolation
from odoo_test_helper import FakeModelLoader


from odoo import http
from odoo.tests.common import SavepointCase, tagged

from odoo.addons.endpoint_route_handler.exceptions import EndpointHandlerNotFound
from odoo.addons.endpoint_route_handler.registry import EndpointRegistry

from .fake_controllers import CTRLFake


@tagged("-at_install", "post_install")
class TestRegistry(SavepointCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.reg = EndpointRegistry.registry_for(cls.env.cr)
        # Load fake models ->/
        cls.loader = FakeModelLoader(cls.env, cls.__module__)
        cls.loader.backup_registry()
        from .fake_models import EndpointConsumerTest
        cls.loader.update_registry((EndpointConsumerTest,))
        # ->/
        cls.model = cls.env[EndpointConsumerTest._name]

    @classmethod
    def tearDownClass(cls):
        cls.loader.restore_registry()
        super().tearDownClass()

    def _count_rules(self, groups=("test_route_handler",)):
        return len()
        # # NOTE: use always groups to filter in your tests
        # # because some other module might add rules for testing.
        # self.env.cr.execute(
        #     "SELECT COUNT(id) FROM endpoint_route WHERE route_group IN %s", (groups,)
        # )
        # return self.env.cr.fetchone()[0]

    def _make_routes(self, stop=5, start=1, **kw):
        records = self.model.browse()
        for i in range(start, stop):
            key = f"route{i}"
            route = f"/test/{i}"
            route_group = "test_route_handler"
            values = dict(
                name=f"Test {i}",
                key=key,
                request_method="GET",
                route=route,
                route_group=route_group,
            )
            values.update(kw)
            records |= self.model.create(values)
        return records
    
    def test_defaults(self):
        rec = self._make_routes(stop=2)
        self.assertEqual(rec._name, self.model._name)
        route = rec.endpoint_route_id
        self.assertEqual(route._name, "endpoint.route")
        self.assertEqual(route.get_consumer(), rec)
        self.assertEqual(route.routing, {
            'type': 'http',
            'auth': 'user_endpoint',
            'methods': ['GET'],
            'routes': ['/test/1'],
            'csrf': False
        })
        ctrl_path = (
            "odoo.addons.endpoint_route_handler.controllers"
            ".main.EndpointNotFoundController"
        )
        self.assertEqual(rec.options,
            {'handler': {
                'klass_dotted_path': ctrl_path,
                'method_name': 'auto_not_found'
            }}
        )

    def test_custom(self):
        vals = {
            "name": "Custom",
            "route": "/foo",
            "request_method": "GET",
            "options": {
                "handler": {
                    "klass_dotted_path": CTRLFake._path,
                    "method_name": "handler1",
                }
            },
        }
        rec = self.model.create(vals)
        self.assertEqual(rec.options,
            {'handler': {
                'klass_dotted_path': CTRLFake._path,
                'method_name': 'handler1'
            }}
        )
        self.assertFalse(rec.routing["csrf"])
        rec.write({"csrf": True})
        self.assertTrue(rec.routing["csrf"])
        # TODO test more

    def test_add_rule(self):
        self._make_routes(stop=5)
        recs = self.model.endpoint_route_id.get_all()
        self.assertEqual(len(recs), 4)
        # TODO: test hashes?
        # self.assertEqual(self.reg._get_rule("route1").endpoint_hash, "1")
        # self.assertEqual(self.reg._get_rule("route2").endpoint_hash, "2")
        # self.assertEqual(self.reg._get_rule("route3").endpoint_hash, "3")
        # self.assertEqual(self.reg._get_rule("route4").endpoint_hash, "4")

    def test_get_rules(self):
        self._make_routes(stop=4)
        recs = self.model.endpoint_route_id.get_all()
        self.assertEqual(len(recs), 3)
        self.assertEqual(
            sorted(recs.mapped("key")), ["route1", "route2", "route3"]
        )
        self._make_routes(start=10, stop=14)
        recs = self.model.endpoint_route_id.get_all()
        self.assertEqual(len(recs), 7)
        self.assertEqual(
            sorted(recs.mapped("key")),
            sorted(
                [
                    "route1",
                    "route2",
                    "route3",
                    "route10",
                    "route11",
                    "route12",
                    "route13",
                ]
            ),
        )

    # def test_rule_constraints(self):
    #     rule1, rule2 = self._make_routes(stop=3)
    #     msg = (
    #         'duplicate key value violates unique constraint "endpoint_route__key_uniq"'
    #     )
    #     with self.assertRaisesRegex(UniqueViolation, msg), self.env.cr.savepoint():
    #         self.reg._create({rule1.key: rule1.to_row()})
    #     msg = (
    #         "duplicate key value violates unique constraint "
    #         '"endpoint_route__endpoint_hash_uniq"'
    #     )
    #     with self.assertRaisesRegex(UniqueViolation, msg), self.env.cr.savepoint():
    #         rule2.endpoint_hash = rule1.endpoint_hash
    #         rule2.key = "key3"
    #         self.reg._create({rule2.key: rule2.to_row()})

    # def test_drop_rule(self):
    #     rules = self._make_routes(stop=3)
    #     self.assertEqual(self._count_rules(), 2)
    #     self.reg.drop_rules([x.key for x in rules])
    #     self.assertEqual(self._count_rules(), 0)

    # def test_endpoint_lookup_ko(self):
    #     options = {
    #         "handler": {
    #             "klass_dotted_path": "no.where.to.be.SeenKlass",
    #             "method_name": "foo",
    #         }
    #     }
    #     rule = self._make_routes(stop=2, options=options)[0]
    #     with self.assertRaises(EndpointHandlerNotFound):
    #         rule.endpoint  # pylint: disable=pointless-statement

    # def test_endpoint_lookup_ok(self):
    #     rule = self._make_routes(stop=2)[0]
    #     self.assertTrue(isinstance(rule.endpoint, http.EndPoint))
    #     self.assertEqual(rule.endpoint("one"), ("one", 2))

    # def test_endpoint_lookup_ok_args(self):
    #     options = {
    #         "handler": {
    #             "klass_dotted_path": CTRLFake._path,
    #             "method_name": "handler1",
    #             "default_pargs": ("one",),
    #         }
    #     }
    #     rule = self._make_routes(stop=2, options=options)[0]
    #     self.assertTrue(isinstance(rule.endpoint, http.EndPoint))
    #     self.assertEqual(rule.endpoint(), ("one", 2))

    # def test_get_rule_by_group(self):
    #     self.assertEqual(self._count_rules(), 0)
    #     self._make_routes(stop=4, route_group="one")
    #     self._make_routes(start=5, stop=7, route_group="two")
    #     self.assertEqual(self._count_rules(groups=("one", "two")), 5)
    #     rules = self.reg.get_rules_by_group("one")
    #     self.assertEqual([rule.key for rule in rules], ["route1", "route2", "route3"])
    #     rules = self.reg.get_rules_by_group("two")
    #     self.assertEqual([rule.key for rule in rules], ["route5", "route6"])
