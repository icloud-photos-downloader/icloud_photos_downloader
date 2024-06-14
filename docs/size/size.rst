.. _size:

Asset Sizes
===========

Basic Sizes
-------------

Each asset in iCloud may have multiple sizes available for downloading:
- original
- medium
- thumb

Size can be selected with ``--size`` parameter and multiple specifications are accepted (e.g. ``--size original --size medium``). Default is ``original``.

If size parameter is specified, but it is not available for the asset, then ``original`` is downloaded, unless ``--force-size`` is specified.

Assets for sizes other than original will have suffix added to their name, e.g. ``IMG-1234-medium.JPG``.

Special Sizes
-------------

Image edits are represented as a special size ``adjusted``. Two common use cases related to edits:
- Download only edited version      use ``--size adjusted`` parameter
- Download edit and original        use ``--size adjusted --size original`` parameters. Edits will have ``-adjusted`` suffix added if file extension is the same as original.

Portraits are represented in iCloud as edits.

  Since `1.19.0 <https://github.com/icloud-photos-downloader/icloud_photos_downloader/releases/tag/v1.19.0>`_

  See RAW_ for the use of ``alternative`` size