import PyQt5.QtWidgets as W
from typing import Any, cast, Optional
import os

import chooser
import config
import mypy


class ApplyDialog(W.QDialog):
    def __init__(self, *args: Any, **kwargs: Any):
        self.max_decimals = 10

        super(ApplyDialog, self).__init__(*args, **kwargs)
        self.setWindowTitle('Apply Modifications')
        form_layout = W.QGridLayout()
        form_layout.addWidget(W.QLabel('Target directory'), 0, 0)
        form_layout.addWidget(W.QLabel('Prefix'), 1, 0)
        form_layout.addWidget(W.QLabel('Starting number'), 2, 0)
        form_layout.addWidget(W.QLabel('Decimals'), 3, 0)

        target_directory_layout = W.QHBoxLayout()
        self.target_directory_edit = W.QLineEdit()
        path = config.config.get('last_target_dir')
        if path is None or not os.path.exists(path):
            path = config.config.get('last_dir')
        if path is None or not os.path.exists(path):
            path = os.getcwd()
        self.target_directory_edit.setText(path)

        def calculate_dir(value: str) -> None:  # mypy...
            self._calculate_dir(value)
        self.target_directory_edit.textChanged.connect(calculate_dir)
        target_directory_layout.addWidget(self.target_directory_edit)

        set_dir_button = W.QToolButton()
        set_dir_button.setText('Set')

        set_dir_button.clicked.connect(
            mypy.click_callback(self._set_directory))
        target_directory_layout.addWidget(set_dir_button)
        form_layout.addLayout(target_directory_layout, 0, 1)

        self.prefix_edit = W.QLineEdit()
        self.prefix_edit.setText(config.config.get('prefix', ''))
        form_layout.addWidget(self.prefix_edit, 1, 1)

        starting_number_layout = W.QHBoxLayout()
        self.starting_number_edit = W.QSpinBox()
        starting_number_layout.addWidget(self.starting_number_edit)

        self.calculate_starting_number_button = W.QToolButton()
        self.calculate_starting_number_button.setText('Calculate')

        self.calculate_starting_number_button.clicked.connect(
            mypy.click_callback(self._calculate_starting_number))
        starting_number_layout.addWidget(self.calculate_starting_number_button)
        form_layout.addLayout(starting_number_layout, 2, 1)

        self.decimals_edit = W.QSpinBox()
        self.decimals_edit.setRange(1, self.max_decimals)
        decimals = min(self.max_decimals, config.config.get('decimals', 4))
        self.decimals_edit.setValue(decimals)
        self.decimals_edit.valueChanged.connect(
            self._calculate_starting_number_limits)
        form_layout.addWidget(self.decimals_edit, 3, 1)

        layout = W.QVBoxLayout()
        layout.addLayout(form_layout)

        self.button_box = W.QDialogButtonBox(cast(
            W.QDialogButtonBox.StandardButtons,
            W.QDialogButtonBox.Ok | W.QDialogButtonBox.Cancel))
        self.button_box.accepted.connect(self.accept)
        self.button_box.rejected.connect(self.reject)
        self.button_box.button(W.QDialogButtonBox.Ok).clicked.connect(
            mypy.click_callback(self._commit))
        layout.addWidget(self.button_box)

        self.setLayout(layout)

        self._calculate_starting_number_limits(decimals)
        if self._calculate_dir(path):
            self._calculate_starting_number()

    def _commit(self) -> None:
        config.config['last_target_dir'] = self.get_target_directory()
        config.config['decimals'] = self.get_decimals()
        config.config['prefix'] = self.get_prefix()
        config.save_config()

    def _calculate_dir(self, value: str) -> bool:
        is_ok = os.path.isdir(value)
        self.calculate_starting_number_button.setEnabled(is_ok)
        self.button_box.button(W.QDialogButtonBox.Ok).setEnabled(is_ok)
        return is_ok

    def _set_directory(self) -> None:
        starting_dir: Optional[str] = self.get_target_directory()
        assert starting_dir is not None  # mypy...
        if not os.path.exists(starting_dir):
            starting_dir = None

        path = chooser.choose_directory(
            self, 'Choose Target Directory', 'last_target_dir',
            starting_dir=starting_dir)
        if path is None:
            return
        self.target_directory_edit.setText(path)

    def _calculate_starting_number_limits(self, value: int) -> None:
        self.starting_number_edit.setRange(0, 10 ** value - 1)

    def _calculate_starting_number(self) -> None:
        prefix = self.get_prefix()
        max_value = -1
        max_len = self.get_decimals()
        with os.scandir(self.get_target_directory()) as it:
            for entry in it:
                if entry.name.startswith(prefix):
                    num_str = ''
                    for i in range(len(prefix), len(entry.name)):
                        if entry.name[i] >= '0' and entry.name[i] <= '9':
                            num_str += entry.name[i]
                    if num_str:
                        value = int(num_str)
                        if value < 2**31:
                            max_value = max(max_value, value)
                            max_len = max(max_len, len(num_str))
        self.decimals_edit.setValue(min(self.max_decimals, max_len))
        self.starting_number_edit.setValue(max_value + 1)

    def get_decimals(self) -> int:
        return self.decimals_edit.value()

    def get_starting_number(self) -> int:
        return self.starting_number_edit.value()

    def get_prefix(self) -> str:
        return self.prefix_edit.text()

    def get_target_directory(self) -> str:
        return self.target_directory_edit.text()
