"""A tree item that sorts its text in natural order ("2" before "10") when a column header is clicked."""

from PyQt6.QtWidgets import QTreeWidgetItem

from utils.natural_sort import natural_key


class NaturalSortItem(QTreeWidgetItem):
    """Use instead of QTreeWidgetItem in a tree with setSortingEnabled(True)."""

    def __lt__(self, other: QTreeWidgetItem) -> bool:
        tree = self.treeWidget()
        column = tree.sortColumn() if tree is not None else 0
        return natural_key(self.text(column)) < natural_key(other.text(column))
