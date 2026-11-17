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

"""Read data from config files with automatic reloading.

Available data is genres, series and overrides.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
import os
from pathlib import Path
import threading
from typing import TYPE_CHECKING, cast, override

from typing_extensions import TypedDict

import yaml

from PyQt6.QtCore import (
    QFileSystemWatcher,
    QObject,
    pyqtSignal,
)


if TYPE_CHECKING:
    from picard.plugin3.api import (
        PluginApi,
        ScriptParser,
    )


_api: PluginApi


type YamlData = Mapping[str, YamlData | str | None] | Sequence[YamlData | str]

type GenreData = Mapping[str, GenreData | Sequence[str] | None]
"""Data for genres.

Maps to data from genres.yml.
"""


class SeriesData(TypedDict, closed=True):
    """Data for release series.

    Maps to data from series.yml.
    """

    known: Mapping[str, str]
    ignored: Mapping[str, str]


class OverridesData(TypedDict, closed=True):
    """Data for manual overrides.

    Maps to data from overrides.yml.
    """

    albumartist: Mapping[str, Mapping[str, str | list[str]]]
    releasegroup: Mapping[str, Mapping[str, str | list[str]]]
    album: Mapping[str, Mapping[str, str | list[str]]]
    artist: Mapping[str, Mapping[str, str | list[str]]]
    work: Mapping[str, Mapping[str, str | list[str]]]
    recording: Mapping[str, Mapping[str, str | list[str]]]
    track: Mapping[str, Mapping[str, str | list[str]]]


class Reloadable(QObject):
    """Base class to load YAML data and trigger events on file changes."""

    changed = pyqtSignal(dict)
    """Event fired when data is changed on disk."""

    def __init__(self, name: str) -> None:
        """Creates a new data mapping with auto reloading."""
        super().__init__()
        self.name = name
        self.filepath = Path(_api.plugin_config['data_folder']) / (self.name + '.yml')
        _api.plugin_config.setting_changed.connect(self._setting_changed)
        self._watcher = QFileSystemWatcher([os.path.realpath(self.filepath) if self.filepath.is_file() else None])
        self._watcher.fileChanged.connect(self._file_changed)
        self._lock = threading.Lock()
        self._data: YamlData
        self._reload()

    def _setting_changed(self, name: str, _old_value, value: str) -> None:
        if name == 'data_folder':
            _api.logger.info("Folder for %s has changed to %r", self.name, value)
            with self._lock:
                files = self._watcher.files()
                if files:
                    self._watcher.removePaths(files)
                self.filepath = Path(_api.plugin_config['data_folder']) / (self.name + '.yml')
                if self.filepath.is_file():
                    self._watcher.addPath(os.path.realpath(self.filepath))
            self.changed.emit(self._reload())

    def disable(self) -> None:
        """Removes any update notifications."""
        with self._lock:
            self._watcher.disconnect()
            files = self._watcher.files()
            if files:
                self._watcher.removePaths(files)

    def _reload(self) -> YamlData:
        with self._lock:
            if not self.filepath.is_file():
                _api.logger.error("File for %s does not exist: %r", self.name, self.filepath)
                self._data = {}
                return self._data
            with self.filepath.open(mode='r', encoding='utf-8') as file:
                self._data = cast('YamlData', yaml.safe_load(file))
            return self._data

    def _file_changed(self, filepath: str) -> None:
        _api.logger.info("Data for %s has changed in %r", self.name, filepath)
        self.changed.emit(self._reload())

    @property
    def data(self) -> YamlData:
        """Provides the current data."""
        with self._lock:
            return self._data


class Genres(Reloadable):
    """Mapping of genres.yml to a class with auto reloading."""

    def __init__(self) -> None:
        """Creates a new reloadable mapping of genres.yml."""
        super().__init__('genres')

    @staticmethod
    def _find(genre_casefold: str, genres: GenreData) -> str:
        for k, v in genres.items():
            if k == '=':
                continue
            if k.casefold() == genre_casefold:
                return k
            if v:
                if '=' in v:
                    # check aliases
                    for a in cast('Mapping[str, Sequence[str]]', v)['=']:
                        if a.casefold() == genre_casefold:
                            return k
                result = Genres._find(genre_casefold, cast('GenreData', v))
                if result:
                    return result
        return ''

    @staticmethod
    def _find_path(genre_casefold: str, genres: GenreData, path: tuple[str, ...] = ()) -> tuple[str, ...]:
        for k, v in genres.items():
            if k == '=':
                continue
            if k.casefold() == genre_casefold:
                return (*path, k)
            if v:
                if '=' in v:
                    # check aliases
                    for a in cast('Mapping[str, Sequence[str]]', v)['=']:
                        if a.casefold() == genre_casefold:
                            return (k,)
                result = Genres._find_path(genre_casefold, cast('GenreData', v), (*path, k))
                if result:
                    return result
        return ()

    def get(self, name: str) -> str | None:
        """Gets the mapped name of a genre.

        Returns:
            The mapped name if found else None.
        """
        if not name:
            return name

        result = Genres._find(name.casefold(), self.data)
        return result or None

    def get_path(self, name: str, sep: str = ' > ') -> str | None:
        """Gets the full path of mapped genres.

        Returns:
            The path as a string or None if genre is unknown.
        """
        if not name:
            return name

        result = sep.join(Genres._find_path(name.casefold(), self.data))
        return result or None

    @property
    @override
    def data(self) -> GenreData:
        return cast('GenreData', super().data)


# Genre wrappers for scripting


def _script_get_genre(_parser: ScriptParser, genre: str = '', default: str = 'GENRE_NOT_FOUND') -> str:
    try:
        return genres.get(genre) or default
    except Exception:
        _api.logger.exception("Error mapping genre %r", genre)
        return 'ERROR'


def _script_get_genre_path(
    _parser: ScriptParser, genre: str = '', sep: str = ' > ', default: str = 'GENRE_NOT_FOUND'
) -> str:
    try:
        return genres.get_path(genre, sep) or default
    except Exception:
        _api.logger.exception("Error mapping genre %r", genre)
        return 'ERROR'


#
# Series
#


class Series(Reloadable):
    """Mapping of series.yml to a class with auto reloading."""

    def __init__(self) -> None:
        """Creates a new reloadable mapping of series.yml."""
        super().__init__('series')

    def get_known(self, series_id: str) -> str | None:
        """Gets the name of series if it is known.

        Returns:
            The name or None if the series is not known.
        """
        known = self.data['known']
        return known.get(series_id, None) if known else None

    def get_ignored(self, series_id: str) -> str | None:
        """Gets the name of series if it is ignored.

        Returns:
            The name or None if the series is not ignored.
        """
        ignored = self.data['ignored']
        return ignored.get(series_id, None) if ignored else None

    @property
    @override
    def data(self) -> SeriesData:
        return cast('SeriesData', super().data)


# Series wrappers for scripting


def _script_series_get_known(_parser: ScriptParser, series_id: str) -> str:
    try:
        return series.get_known(series_id) or ''
    except Exception:
        _api.logger.exception("Error getting series %r", series_id)
        return 'ERROR'


def _script_series_get_ignored(_parser: ScriptParser, series_id: str) -> str:
    try:
        return series.get_ignored(series_id) or ''
    except Exception:
        _api.logger.exception("Error getting series %r", series_id)
        return 'ERROR'


class Overrides(Reloadable):
    """Mapping of overrides.yml to a class with auto reloading."""

    def __init__(self) -> None:
        """Creates a new reloadable mapping of overrides.yml."""
        super().__init__('overrides')

    @property
    @override
    def data(self) -> OverridesData:
        return cast('OverridesData', super().data)


genres: Genres
"""Data from genres.yml."""
series: Series
"""Data from series.yml."""
overrides: Overrides
"""Data from overrides.yml."""


def enable(api: PluginApi) -> None:
    """Set up (called from main module)."""
    global _api, genres, series, overrides

    _api = api
    _api.plugin_config.register_option(
        'data_folder',
        default=str(api.plugin_dir.joinpath('example')),
        title=api.tr('options.data_folder', "Folder containing user data files for genres, series and overrides"),
        in_profile=True,
    )

    genres = Genres()
    series = Series()
    overrides = Overrides()

    api.register_script_function(
        _script_get_genre,
        name='get_genre',
        documentation=api.tr('help.script.get_genre', "Performs genre mapping"),
        signature=api.tr('help.script.get_genre.signature', "$get_genre(genre[, default=GENRE_NOT_FOUND])"),
    )
    api.register_script_function(
        _script_get_genre_path,
        name='get_genre_path',
        documentation=api.tr('help.script.get_genre_path', "Get hierarchical genre data"),
        signature=api.tr(
            'help.script.get_genre_path.signature', "$get_genre_path(genre[, separator= > [, default=GENRE_NOT_FOUND]])"
        ),
    )

    api.register_script_function(
        _script_series_get_known,
        name='series_get_known',
        documentation=api.tr('help.script.series_get_known', "Lookup a known series by id"),
        signature=api.tr('help.script.series_get_known.signature', "$series_get_known(series_id)"),
    )
    api.register_script_function(
        _script_series_get_ignored,
        name='series_get_ignored',
        documentation=api.tr('help.script.series_get_ignored', "Lookup an ignored series by id"),
        signature=api.tr('help.script.series_get_ignored.signature', "$series_get_ignored(series_id)"),
    )


def disable() -> None:
    """Tear down (called from main module)."""
    global _api, genres, series, overrides

    if genres:
        genres.disable()
        del genres
    if series:
        series.disable()
        del series
    if overrides:
        overrides.disable()
        del overrides
    del _api
