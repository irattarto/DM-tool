"""Small widgets for choosing adventure modules: a menu that stays open while boxes are ticked, and a picker button."""

from typing import Dict, Iterable, List, Set

from PyQt6.QtCore import pyqtSignal
from PyQt6.QtWidgets import QMenu, QPushButton


class StayOpenMenu(QMenu):
    """A menu whose checkable entries can be ticked one after another without it closing."""

    def mouseReleaseEvent(self, event):
        action = self.actionAt(event.pos())
        if action is not None and action.isCheckable() and action.isEnabled():
            action.trigger()
            return
        super().mouseReleaseEvent(event)


class ModulePickerButton(QPushButton):
    """A button listing the modules an entry belongs to; its menu ticks any number of them."""

    selection_changed = pyqtSignal()

    def __init__(self, modules: Dict[int, str], selected: Iterable[int] = (), parent=None):
        super().__init__(parent)
        self._modules = dict(modules)
        self._selected: Set[int] = {m for m in selected if m in self._modules}
        self._menu = StayOpenMenu(self)
        self.setMenu(self._menu)
        self._menu.aboutToShow.connect(self._fill_menu)
        self.setToolTip("The adventure modules this entry belongs to (none, one or several)")
        self._update_text()

    def selected_ids(self) -> List[int]:
        return sorted(self._selected)

    def set_selected(self, selected: Iterable[int]):
        self._selected = {m for m in selected if m in self._modules}
        self._update_text()

    def _fill_menu(self):
        self._menu.clear()
        if not self._modules:
            self._menu.addAction("No modules yet - create one on the Modules page").setEnabled(False)
            return
        for module_id, title in sorted(self._modules.items(), key=lambda pair: pair[1].casefold()):
            action = self._menu.addAction(title)
            action.setCheckable(True)
            action.setChecked(module_id in self._selected)
            action.toggled.connect(lambda checked, m=module_id: self._toggle(m, checked))

    def _toggle(self, module_id: int, checked: bool):
        (self._selected.add if checked else self._selected.discard)(module_id)
        self._update_text()
        self.selection_changed.emit()

    def _update_text(self):
        titles = [self._modules[m] for m in sorted(self._selected, key=lambda m: self._modules[m].casefold())]
        self.setText(", ".join(titles) if titles else "(none)")
