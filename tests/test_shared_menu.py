"""Tests du registre de menu partagé utilisé par les extensions Accessolutions."""

from __future__ import annotations

import importlib.util
import sys
import types
import unittest
from pathlib import Path


MODULE_PATH = (
    Path(__file__).resolve().parents[1]
    / "globalPlugins"
    / "AccessolutionsNvdaPro"
    / "sharedMenu.py"
)


class FakeItem:
    def __init__(self, label=""):
        self.label = label
        self.destroyed = False

    def Destroy(self):
        self.destroyed = True


class FakeMenu:
    def __init__(self):
        self.items = []
        self.destroyed = False

    def InsertMenu(self, position, item_id, title, submenu):
        item = FakeItem(title)
        item.submenu = submenu
        self.items.insert(position, item)
        return item

    def Append(self, item_id, label, help_text):
        item = FakeItem(label)
        self.items.append(item)
        return item

    def RemoveItem(self, item):
        if item in self.items:
            self.items.remove(item)

    def Remove(self, item):
        if item in self.items:
            self.items.remove(item)

    def Destroy(self):
        self.destroyed = True


class FakeEventSource:
    def __init__(self):
        self.bound = []
        self.unbound = []

    def Bind(self, event, handler, source=None):
        self.bound.append((event, handler, source))

    def Unbind(self, event, handler=None, source=None):
        self.unbound.append((event, handler, source))


class AttributeRestrictedMenu:
    __slots__ = ("items", "destroyed")

    def __init__(self):
        self.items = []
        self.destroyed = False

    def InsertMenu(self, position, item_id, title, submenu):
        item = FakeItem(title)
        item.submenu = submenu
        self.items.insert(position, item)
        return item

    def Append(self, item_id, label, help_text):
        item = FakeItem(label)
        self.items.append(item)
        return item

    def RemoveItem(self, item):
        if item in self.items:
            self.items.remove(item)

    def Remove(self, item):
        self.RemoveItem(item)

    def Destroy(self):
        self.destroyed = True


class SharedMenuTests(unittest.TestCase):
    def setUp(self):
        spec = importlib.util.spec_from_file_location("pro_shared_menu", MODULE_PATH)
        self.shared_menu = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = self.shared_menu
        spec.loader.exec_module(self.shared_menu)
        self.wx_module = types.SimpleNamespace(Menu=FakeMenu, ID_ANY=-1, EVT_MENU=object())
        self.system_menu = FakeMenu()
        self.events = FakeEventSource()

    def tearDown(self):
        sys.modules.pop("pro_shared_menu", None)

    def test_two_owners_share_parent_and_cleanup_only_their_items(self):
        first = self.shared_menu.acquire(
            self.system_menu,
            "clavierBraille",
            event_source=self.events,
            wx_module=self.wx_module,
        )
        second = self.shared_menu.acquire(
            self.system_menu,
            "accessolutionsNVDAPro",
            event_source=self.events,
            wx_module=self.wx_module,
        )
        self.assertIs(first, second)
        first_item = self.shared_menu.addItem(
            first,
            "clavierBraille",
            "Options",
            handler=lambda event: None,
            wx_module=self.wx_module,
        )
        second_item = self.shared_menu.addItem(
            first,
            "accessolutionsNVDAPro",
            "Assistance",
            wx_module=self.wx_module,
        )

        self.shared_menu.release(first, "clavierBraille", wx_module=self.wx_module)

        self.assertNotIn(first_item, first.menu.items)
        self.assertIn(second_item, first.menu.items)
        self.assertFalse(first.menu.destroyed)
        self.assertEqual(len(self.events.unbound), 1)

        self.shared_menu.release(second, "accessolutionsNVDAPro", wx_module=self.wx_module)

        self.assertTrue(first.menu.destroyed)
        self.assertNotIn(first.parent_item, self.system_menu.items)

    def test_reverse_owner_order_keeps_remaining_items(self):
        state = self.shared_menu.acquire(
            self.system_menu,
            "accessolutionsNVDAPro",
            event_source=self.events,
            wx_module=self.wx_module,
        )
        same_state = self.shared_menu.acquire(
            self.system_menu,
            "clavierBraille",
            event_source=self.events,
            wx_module=self.wx_module,
        )
        self.assertIs(state, same_state)
        pro_item = self.shared_menu.addItem(
            state,
            "accessolutionsNVDAPro",
            "Assistance",
            wx_module=self.wx_module,
        )
        braille_item = self.shared_menu.addItem(
            state,
            "clavierBraille",
            "Options",
            wx_module=self.wx_module,
        )

        self.shared_menu.release(state, "accessolutionsNVDAPro", wx_module=self.wx_module)

        self.assertNotIn(pro_item, state.menu.items)
        self.assertIn(braille_item, state.menu.items)
        self.assertFalse(state.menu.destroyed)

        self.shared_menu.release(state, "clavierBraille", wx_module=self.wx_module)
        self.assertTrue(state.menu.destroyed)

    def test_logical_key_shares_item_and_transfers_binding(self):
        state = self.shared_menu.acquire(
            self.system_menu,
            "clavierBraille",
            event_source=self.events,
            wx_module=self.wx_module,
        )
        self.shared_menu.acquire(
            self.system_menu,
            "accessolutionsNVDAPro",
            event_source=self.events,
            wx_module=self.wx_module,
        )
        first_handler = lambda event: None
        second_handler = lambda event: None

        first_item = self.shared_menu.addItem(
            state,
            "clavierBraille",
            "Site",
            handler=first_handler,
            key="website",
            wx_module=self.wx_module,
        )
        second_item = self.shared_menu.addItem(
            state,
            "accessolutionsNVDAPro",
            "Site traduit différemment",
            handler=second_handler,
            key="website",
            wx_module=self.wx_module,
        )

        self.assertIs(first_item, second_item)
        self.assertEqual(len(state.menu.items), 1)
        self.assertEqual(len(self.events.bound), 1)

        self.shared_menu.release(state, "clavierBraille", wx_module=self.wx_module)

        self.assertIn(second_item, state.menu.items)
        self.assertEqual(len(self.events.unbound), 1)
        self.assertEqual(len(self.events.bound), 2)

        self.shared_menu.release(state, "accessolutionsNVDAPro", wx_module=self.wx_module)
        self.assertTrue(state.menu.destroyed)

    def test_independent_module_copies_share_attribute_restricted_menu(self):
        second_name = "pro_shared_menu_second"
        second_spec = importlib.util.spec_from_file_location(second_name, MODULE_PATH)
        second_module = importlib.util.module_from_spec(second_spec)
        sys.modules[second_name] = second_module
        second_spec.loader.exec_module(second_module)
        system_menu = AttributeRestrictedMenu()
        try:
            first_state = self.shared_menu.acquire(
                system_menu,
                "accessolutionsNVDAPro",
                event_source=self.events,
                wx_module=self.wx_module,
            )
            second_state = second_module.acquire(
                system_menu,
                "clavierBraille",
                event_source=self.events,
                wx_module=self.wx_module,
            )
            self.assertIs(first_state, second_state)

            first_item = self.shared_menu.addItem(
                first_state,
                "accessolutionsNVDAPro",
                "Produits et services",
                handler=lambda event: None,
                key=self.shared_menu.WEBSITE_ITEM_KEY,
                wx_module=self.wx_module,
            )
            second_item = second_module.addItem(
                second_state,
                "clavierBraille",
                "Produits et services traduits",
                handler=lambda event: None,
                key=second_module.WEBSITE_ITEM_KEY,
                wx_module=self.wx_module,
            )

            self.assertIs(first_item, second_item)
            self.assertEqual(len(system_menu.items), 1)
            self.assertEqual(len(first_state.menu.items), 1)
        finally:
            self.shared_menu.release(
                first_state,
                "accessolutionsNVDAPro",
                wx_module=self.wx_module,
            )
            second_module.release(
                second_state,
                "clavierBraille",
                wx_module=self.wx_module,
            )
            sys.modules.pop(second_name, None)


if __name__ == "__main__":
    unittest.main()