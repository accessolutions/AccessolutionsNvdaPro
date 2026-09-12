"""Registre du menu Accessolutions partagé entre les extensions.

Les extensions peuvent embarquer chacune une copie de ce module. Le registre
de secours est donc conservé dans ``sys.modules`` afin de rester commun même
si l'objet wx ne permet pas d'y attacher directement un attribut.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass, field
from typing import Any

_REGISTRY_ATTRIBUTE = "_cb_accessolutions_shared_menu_state"
_REGISTRY_MODULE = "_accessolutions_shared_menu_registry"
WEBSITE_ITEM_KEY = "website"


@dataclass
class OwnerItem:
    item: Any
    handler: Any = None
    label: str = ""
    help_text: str = ""
    event_source: Any = None
    key: str = ""
    owns_item: bool = True
    binding_active: bool = False


@dataclass
class SharedMenuState:
    system_menu: Any
    menu: Any
    parent_item: Any
    event_source: Any = None
    owners: dict[str, list[OwnerItem]] = field(default_factory=dict)


def _fallback_registry() -> dict[int, SharedMenuState]:
    registry_module = sys.modules.get(_REGISTRY_MODULE)
    if registry_module is None:
        registry_module = type(sys)(_REGISTRY_MODULE)
        registry_module.states = {}
        sys.modules[_REGISTRY_MODULE] = registry_module
    return registry_module.states


def _get_state(system_menu: Any) -> SharedMenuState | None:
    if system_menu is None:
        return None
    state = getattr(system_menu, _REGISTRY_ATTRIBUTE, None)
    if state is not None:
        return state
    registry = _fallback_registry()
    state = registry.get(id(system_menu))
    if state is not None and state.system_menu is not system_menu:
        registry.pop(id(system_menu), None)
        return None
    return state


def _set_state(system_menu: Any, state: SharedMenuState) -> None:
    _fallback_registry()[id(system_menu)] = state
    try:
        setattr(system_menu, _REGISTRY_ATTRIBUTE, state)
    except (AttributeError, TypeError):
        pass


def _clear_state(system_menu: Any) -> None:
    try:
        delattr(system_menu, _REGISTRY_ATTRIBUTE)
    except (AttributeError, TypeError):
        pass
    _fallback_registry().pop(id(system_menu), None)


def _wx_module():
    import wx

    return wx


def _insert_submenu(system_menu: Any, position: int, title: str, submenu: Any, wx: Any) -> Any:
    if hasattr(system_menu, "InsertMenu"):
        return system_menu.InsertMenu(position, wx.ID_ANY, title, submenu)
    return system_menu.Insert(position, wx.ID_ANY, title, submenu)


def _remove_menu_item(system_menu: Any, item: Any) -> None:
    if hasattr(system_menu, "RemoveItem"):
        system_menu.RemoveItem(item)
        return
    system_menu.Remove(item)


def _find_other_owner_item(
    state: SharedMenuState,
    owner: str,
    item: Any,
) -> OwnerItem | None:
    for candidate_owner, owner_items in state.owners.items():
        if candidate_owner == owner:
            continue
        for owner_item in owner_items:
            if owner_item.item is item:
                return owner_item
    return None


def acquire(
    system_menu: Any,
    owner: str,
    *,
    event_source: Any = None,
    title: str = "Accessolutions",
    position: int = 0,
    wx_module: Any = None,
) -> SharedMenuState | None:
    if system_menu is None or not owner:
        return None
    state = _get_state(system_menu)
    if state is not None:
        state.owners.setdefault(owner, [])
        if state.event_source is None:
            state.event_source = event_source
        return state

    wx = wx_module or _wx_module()
    submenu = wx.Menu()
    parent_item = _insert_submenu(system_menu, position, title, submenu, wx)
    state = SharedMenuState(
        system_menu=system_menu,
        menu=submenu,
        parent_item=parent_item,
        event_source=event_source,
        owners={owner: []},
    )
    _set_state(system_menu, state)
    return state


def addItem(
    state: SharedMenuState | None,
    owner: str,
    label: str,
    help_text: str = "",
    handler: Any = None,
    *,
    wx_module: Any = None,
    key: str = "",
) -> Any:
    if state is None or not owner:
        return None
    wx = wx_module or _wx_module()
    owner_items = state.owners.setdefault(owner, [])
    for owner_item in owner_items:
        if (
            (key and owner_item.key == key)
            or (
                not key
                and owner_item.label == label
                and owner_item.help_text == help_text
                and owner_item.handler == handler
            )
        ):
            return owner_item.item
    if key:
        for candidate_owner, candidate_items in state.owners.items():
            if candidate_owner == owner:
                continue
            for candidate in candidate_items:
                if candidate.key == key:
                    owner_items.append(
                        OwnerItem(
                            candidate.item,
                            handler,
                            label,
                            help_text,
                            state.event_source,
                            key,
                            False,
                            False,
                        )
                    )
                    return candidate.item
    item = state.menu.Append(wx.ID_ANY, label, help_text)
    event_source = state.event_source
    binding_active = handler is not None and event_source is not None
    owner_items.append(
        OwnerItem(
            item,
            handler,
            label,
            help_text,
            event_source,
            key,
            True,
            binding_active,
        )
    )
    if binding_active:
        event_source.Bind(wx.EVT_MENU, handler, source=item)
    return item


def removeOwnerItems(state: SharedMenuState | None, owner: str, *, wx_module: Any = None) -> None:
    if state is None or not owner:
        return
    wx = wx_module or _wx_module()
    owner_items = state.owners.setdefault(owner, [])
    for owner_item in list(owner_items):
        if owner_item.binding_active and owner_item.event_source is not None:
            try:
                owner_item.event_source.Unbind(
                    wx.EVT_MENU,
                    handler=owner_item.handler,
                    source=owner_item.item,
                )
            except (AttributeError, RuntimeError, TypeError):
                pass
        other_owner_item = _find_other_owner_item(state, owner, owner_item.item)
        if other_owner_item is not None and owner_item.owns_item:
            other_owner_item.owns_item = True
            other_owner_item.event_source = (
                other_owner_item.event_source or state.event_source
            )
            if (
                other_owner_item.handler is not None
                and other_owner_item.event_source is not None
            ):
                try:
                    other_owner_item.event_source.Bind(
                        wx.EVT_MENU,
                        other_owner_item.handler,
                        source=other_owner_item.item,
                    )
                    other_owner_item.binding_active = True
                except (AttributeError, RuntimeError, TypeError):
                    pass
            continue
        if not owner_item.owns_item:
            continue
        try:
            state.menu.Remove(owner_item.item)
        except (AttributeError, RuntimeError, TypeError):
            pass
        try:
            owner_item.item.Destroy()
        except (AttributeError, RuntimeError):
            pass
    owner_items.clear()


def release(state: SharedMenuState | None, owner: str, *, wx_module: Any = None) -> None:
    if state is None or not owner:
        return
    removeOwnerItems(state, owner, wx_module=wx_module)
    state.owners.pop(owner, None)
    if state.owners:
        return

    try:
        _remove_menu_item(state.system_menu, state.parent_item)
    except (AttributeError, RuntimeError, TypeError):
        pass
    try:
        state.parent_item.Destroy()
    except (AttributeError, RuntimeError):
        pass
    try:
        state.menu.Destroy()
    except (AttributeError, RuntimeError):
        pass
    _clear_state(state.system_menu)