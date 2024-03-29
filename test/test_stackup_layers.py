from pcbre.model.change import ChangeType
from pcbre.model.project import Project
from pcbre.model.stackup import Layer

__author__ = 'davidc'
import unittest
from unittest.mock import Mock


class test_stackup_layers(unittest.TestCase):
    def setUp(self):
        self.p = Project.create()

    def test_basic(self):
        layer = self.p.stackup.add_layer("foo", (1, 1, 1))

        self.assertIn(layer, self.p.stackup.layers)

        self.p.stackup.remove_layer(layer)

        self.assertNotIn(layer, self.p.stackup.layers)

    def test_callback_called_on_add_del(self):
        call_me = Mock()

        self.p.stackup.changed.connect(call_me)
        layer = self.p.stackup.add_layer("foo", (1, 1, 1))

        self.assertTrue(call_me.called)

        call_me.reset_mock()
        self.p.stackup.remove_layer(layer)

        self.assertTrue(call_me.called)
