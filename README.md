# Metadata Override

![Latest Version](https://img.shields.io/github/v/tag/mbeckh/picard-plugin-metadata-override?sort=semver&filter=v*&style=flat-square&label=latest)
![Supports](https://img.shields.io/badge/dynamic/regex?url=https%3A%2F%2Fraw.githubusercontent.com%2Fmbeckh%2Fpicard-plugin-metadata-override%2Frefs%2Fheads%2Fmain%2Fpyproject.toml&search=dependencies%5Cs*%3D%5Cs*%5C%5B%5B%5E%5D%5D*%22picard%5B%5E%22%5D*(%3E%3D.*%3F)%5B%2C%22%5D&replace=%241&flags=s&style=flat-square&label=picard&color=orange)
![Tested with](https://img.shields.io/badge/dynamic/regex?url=https%3A%2F%2Fraw.githubusercontent.com%2Fmbeckh%2Fpicard-plugin-metadata-override%2Frefs%2Fheads%2Fmain%2Fpyproject.toml&search=dependencies%5Cs*%3D%5Cs*%5C%5B%5B%5E%5D%5D*%22picard%5B%5E%22%5D*(%3C%3D.*%3F)%5B%2C%22%5D&replace=%241&flags=s&style=flat-square&label=tested+with&color=green)

A plugin for [MusicBrainz Picard](https://picard.musicbrainz.org) to override
data from MusicBrainz with own values.

## What it Does

The plugin reads a YAML config file to supply new values for tags. This allows
updating a file from MusicBrainz without having to apply manual modifications
each time.

Additionally, the plugin allows mapping genres and has a white and black list
for adding release series to tags.

Sample configuration files can be found in [example](example). When using the
plugin, please create own copies and select the respective path in the options.

## Unsupported Modifications of Picard

> [!IMPORTANT]
> This plugin requires the
> [Monkey Plugin](https://github.com/mbeckh/picard-plugin-monkey/) as a
> prerequisite. Please install this plugin first.

This plugin modifies Picard _way beyond_ the level that was intended by the
implementers of the official API. It relies heavily on internal and private
implementation details and monkey patches its way across the Picard code base to
achieve its goals.

> [!WARNING]
> **Even a minor update of Picard can break this plugin** until I'm able to
> supply an updated version. The plugin is typically tested with the latest
> version of Picard only.

## License

The code is released under the Apache License Version 2.0. Please see
[LICENSE](LICENSE) for details and [NOTICE](NOTICE) for the required information
when using picard-plugin-metadata-override in your own work.
