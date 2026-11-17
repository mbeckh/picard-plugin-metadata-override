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

"""Override metadata."""

from __future__ import annotations

from functools import partial
import os
from typing import (
    TYPE_CHECKING,
    ClassVar,
    Protocol,
    cast,
    override,
)

from PyQt6 import QtWidgets

from picard.album import Album
from picard.plugin3.api import (
    File,
    OptionsPage,
    PageOptionConfigs,
    PluginApi,
    Track,
    t_,
)

from . import data, metadatabox, monkey
from .ui_compiled.ui_options import Ui_MetadataOverrideOptionsPage


if TYPE_CHECKING:
    from collections.abc import Callable


_api: PluginApi
_enabled = False


class Overridable(Protocol):
    """File or track with additional data."""

    _mo_orig: dict
    _mo_overrides: set


def _set_overrides(obj: Track | File, overrides: data.OverridesData | None = None) -> None:
    """Calculate override values."""
    if not _enabled:
        return

    metadata = obj.metadata
    changed = False

    objx = cast('Overridable', obj)
    if hasattr(obj, '_mo_orig'):
        orig = objx._mo_orig
        changed |= len(orig) > 0
        metadata.update(orig)
    else:
        objx._mo_orig = orig = {}
        data.overrides.changed.connect(partial(_set_overrides, obj))
        data.series.changed.connect(obj.update)
        data.genres.changed.connect(obj.update)

    manual = overrides is None
    overrides = data.overrides.data if manual else overrides

    objx._mo_overrides = override_keys = set()

    for name in ('albumartist', 'releasegroup', 'album', 'artist', 'work', 'recording', 'track'):
        ids = metadata[f'musicbrainz_{name}id']
        if ids and (ov_for_name := overrides.get(name)):
            for ov_for_id in filter(
                None, map(ov_for_name.get, ids if isinstance(ids, (list, tuple, set, dict)) else [ids])
            ):
                keys = ov_for_id.keys()
                override_keys.update(keys)

                for k in keys - orig.keys():
                    orig[k] = metadata[k]
                metadata.update(ov_for_id)

    for k in orig.keys() - override_keys:
        del orig[k]

    changed |= len(override_keys) > 0
    if not manual and changed:
        if isinstance(obj, Track):
            obj.update()
        else:
            cast('File', obj).update(update_selection=False)


@monkey.patch(Album, Album._finalize_loading_album)
def _monkey_Album_finalize_loading_album(wrapped: Callable[[Album], None], self: Album) -> None:
    if _enabled:
        on_exit_previous = self.suspend_metadata_images_update._on_exit

        def on_exit() -> None:
            for track in self.tracks:
                _set_overrides(track)
            # call only once
            self.suspend_metadata_images_update._on_exit = on_exit_previous
            if on_exit_previous:
                on_exit_previous()

        self.suspend_metadata_images_update._on_exit = on_exit

    wrapped(self)


@monkey.patch(File, File.update)
def _monkey_File_update(
    wrapped: Callable[[File, bool, bool], None],
    self: File,
    signal: bool = True,  # ruff: ignore[boolean-default-value-positional-argument, boolean-type-hint-positional-argument]
    update_selection: bool = True,  # ruff: ignore[boolean-default-value-positional-argument, boolean-type-hint-positional-argument]
) -> None:
    """Apply overrides."""
    if _enabled:
        _set_overrides(self)
    wrapped(self, signal, update_selection)


class MetadataOverrideOptionsPage(OptionsPage):
    """Options dialog."""

    NAME = 'metadata_override'
    TITLE = t_('ui.metadata_override.title', "Metadata Override")
    PARENT = 'plugins'

    OPTIONS: ClassVar[PageOptionConfigs] = {
        'data_folder': {'widgets': ['data_folder_edit']},
    }

    @override
    def __init__(self, parent: QtWidgets.QWidget | None = None) -> None:
        super().__init__(parent)
        self.ui = Ui_MetadataOverrideOptionsPage()
        self.ui.setupUi(self)

        self.ui.data_folder_browse.clicked.connect(self._data_folder_browse)

    @override
    def load(self) -> None:
        plugin_config = self.api.plugin_config
        self.ui.data_folder_edit.setText(plugin_config['data_folder'])

    @override
    def save(self) -> None:
        plugin_config = self.api.plugin_config
        plugin_config['data_folder'] = self.ui.data_folder_edit.text()

    def _data_folder_browse(self) -> None:
        path = QtWidgets.QFileDialog.getExistingDirectory(
            self, self.api.tr('ui.data_folder.browse.title', "Select data folder"), self.ui.data_folder_edit.text()
        )
        if path:
            path = os.path.normpath(path)
            self.ui.data_folder_edit.setText(path)


def enable(api: PluginApi) -> None:
    """Enable the plugin and set up sub modules."""
    global _api, _enabled

    _api = api
    _enabled = True

    data.enable(api)
    metadatabox.enable(api)
    api.register_options_page(MetadataOverrideOptionsPage)


def disable() -> None:
    """Disable the plugin and tear down sub modules."""
    global _api, _enabled

    data.disable()
    metadatabox.disable()

    monkey.unpatch_module(__name__)

    _enabled = False
    del _api
