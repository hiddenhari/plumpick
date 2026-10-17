"""Confirm-and-choose dialog shown before a commit."""

from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import (
    QButtonGroup,
    QCheckBox,
    QDialog,
    QDialogButtonBox,
    QLabel,
    QRadioButton,
    QVBoxLayout,
    QWidget,
)

from plumpick.commit import (
    KEPT_DIR,
    REJECTED_DIR,
    CommitPlan,
    Destination,
    format_bytes,
    plan_commit,
)
from plumpick.library import Library, Mark

DESTINATION_KEY = "commit/destination"


def files(n: int) -> str:
    return f"{n} file" if n == 1 else f"{n} files"


class CommitDialog(QDialog):
    def __init__(self, library: Library, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.library = library
        self.settings = QSettings("plumpick", "plumpick")
        self.setWindowTitle("Commit")

        deletes = plan_commit(library)
        self.summary = QLabel(
            f"{files(len(deletes.deletes))} marked for delete "
            f"({format_bytes(deletes.delete_bytes)})."
        )

        self.to_bin = QRadioButton("Send to Recycle Bin")
        self.to_rejected = QRadioButton(f"Move to {REJECTED_DIR}/ subfolder")
        group = QButtonGroup(self)
        group.addButton(self.to_bin)
        group.addButton(self.to_rejected)
        saved = self.settings.value(DESTINATION_KEY, Destination.RECYCLE_BIN.value)
        if saved == Destination.REJECTED_FOLDER.value:
            self.to_rejected.setChecked(True)
        else:
            self.to_bin.setChecked(True)

        self.move_kept = QCheckBox(
            f"Also move {files(library.count(Mark.APPROVE))} approved to {KEPT_DIR}/"
        )
        self.move_kept.setEnabled(library.count(Mark.APPROVE) > 0)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        self.ok = buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.ok.setText("Commit")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        self.move_kept.toggled.connect(self._update_ok)

        layout = QVBoxLayout(self)
        for widget in (self.summary, self.to_bin, self.to_rejected, self.move_kept, buttons):
            layout.addWidget(widget)
        self._update_ok()

    @property
    def destination(self) -> Destination:
        if self.to_rejected.isChecked():
            return Destination.REJECTED_FOLDER
        return Destination.RECYCLE_BIN

    def plan(self) -> CommitPlan:
        return plan_commit(self.library, move_kept=self.move_kept.isChecked())

    def accept(self) -> None:
        self.settings.setValue(DESTINATION_KEY, self.destination.value)
        super().accept()

    def _update_ok(self) -> None:
        plan = self.plan()
        self.ok.setEnabled(bool(plan.deletes or plan.keeps))
