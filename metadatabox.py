# Copyright 2023-2026 Michael Beckh (mbeckh)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
# http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Patch MetadataBox to show overridden values."""

from __future__ import annotations

from typing import TYPE_CHECKING

from PyQt6 import QtCore, QtGui, QtWidgets

from picard.ui.metadatabox import (
    DiffColors,
    MetadataBox,
    TableTagEditorDelegate,
    TagDiff,
)

from . import monkey


if TYPE_CHECKING:
    from collections.abc import Callable

    from picard.plugin3.api import PluginApi


_api: PluginApi
_enabled = False

_overrides: dict[str, bool] = {}

_NEW_VALUE_COLUMN = 2
"""Column showing the new value."""


@monkey.patch(MetadataBox, MetadataBox._update_tags)
def _monkey_MetadataBox_update_tags(
    wrapped: Callable[[MetadataBox, bool, bool, DiffColors | None], TagDiff | None],
    self: MetadataBox,
    new_selection: bool = True,  # ruff: ignore[boolean-default-value-positional-argument, boolean-type-hint-positional-argument]
    drop_album_caches: bool = False,  # ruff: ignore[boolean-default-value-positional-argument, boolean-type-hint-positional-argument]
    diff_colors: DiffColors | None = None,
) -> TagDiff | None:
    global _overrides

    if _enabled:
        self.selection_mutex.lock()
        files = self.files
        tracks = self.tracks
        self.selection_mutex.unlock()

        _overrides = {}
        for file in files:
            if hasattr(file, '_mo_overrides'):
                metadata = file.metadata
                orig = file._mo_orig
                for k in file._mo_overrides:
                    _overrides[k] = metadata.getall(k) != orig.get(k)

        for track in tracks:
            # process tracks WITHOUT files
            if track.num_linked_files == 0 and hasattr(track, '_mo_overrides'):
                metadata = track.metadata
                orig = track._mo_orig
                for k in track._mo_overrides:
                    _overrides[k] = metadata.getall(k) != orig.get(k)

    return wrapped(self, new_selection, drop_album_caches, diff_colors)


_override_brush = QtGui.QBrush(QtGui.QColor(255, 230, 201))
_same_brush = QtGui.QBrush(QtGui.QColor(230, 255, 201))


@monkey.patch(MetadataBox, MetadataBox._update_items)
def _monkey_MetadataBox_update_items(
    wrapped: Callable[[MetadataBox, TagDiff | None, BaseException | None], None],
    self: MetadataBox,
    result: TagDiff | None = None,
    error: BaseException | None = None,
) -> None:
    wrapped(self, result, error)

    if not _enabled or self.editing or not result or not (self.files or self.tracks):
        return

    self.tag_diff = result

    for row, tag in enumerate(self.tag_diff.tag_names):
        status = _overrides.get(tag)
        if status is not None:
            item = self.item(row, _NEW_VALUE_COLUMN)
            if item:
                item.setBackground(_override_brush if status else _same_brush)
                # setting font here does not work because of diff_html


@monkey.patch(TableTagEditorDelegate, TableTagEditorDelegate.paint)
def _monkey_TableTagEditorDelegate_paint(
    wrapped: Callable[
        [TableTagEditorDelegate, QtGui.QPainter | None, QtWidgets.QStyleOptionViewItem, QtCore.QModelIndex], None
    ],
    self: TableTagEditorDelegate,
    painter: QtGui.QPainter | None,
    option: QtWidgets.QStyleOptionViewItem,
    index: QtCore.QModelIndex,
) -> None:
    if _enabled and index.column() == _NEW_VALUE_COLUMN:
        tag = self.get_tag_name(index)
        status = _overrides.get(tag)
        if status is not None:
            option.font.setBold(True)
            # setting background does not work here

    wrapped(self, painter, option, index)


def enable(api: PluginApi) -> None:
    """Set up (called from main module)."""
    global _api, _enabled
    _api = api

    _enabled = True


def disable() -> None:
    """Tear down (called from main module)."""
    global _api, _enabled

    _enabled = False
    _overrides.clear()
    del _api
