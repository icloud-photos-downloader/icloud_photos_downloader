.. _raw:

Support for RAW assets
======================

Apple ProRAW/ProRes
-------------------

Apple supports shooting stills and video in `DNG <https://en.wikipedia.org/wiki/Digital_Negative>`_ format and 
they can be downloaded by ``icloudpd`` as any other supported format.

Imported RAW images
-------------------

RAW images from thrid party cameras can be imported into Apple Photos or uploaded to iCloud.com. 
These type of assets can also be downloaded by ``icloudpd``. The following formats are recognized:
- Adobe DNG - same as Apple ProRAW
- Canon CR2, CR3, and CRW
- Sony ARW
- Fuji RAF
- Panasonic RW2
- Nikon NRF, NEF
- Pentax PEF
- Olympus ORF

  Since `1.19.0 <https://github.com/icloud-photos-downloader/icloud_photos_downloader/releases/tag/v1.19.0>`_

RAW+JPEG and JPEG+RAW
---------------------

iCloud supports images with two represenations. ``icloudpd`` can download one or both representations.

One represenation will be ``original`` size_ and another ``alternative``.

As of June 2024, icloud.com always shows assets with two representations as RAW+JPEG. Photo app on Mac
allows choosing which representation to treat as original, but it is not clear what that setting impacts. 
``icloudpd`` diambiguates behavior with `--align-raw` parameter:
- *original*        always treat RAW as original size_
- *alternative*     always treat RAW as alternative size_
- *as-is*           treat RAW as it is in icloud data

  Since `1.19.0 <https://github.com/icloud-photos-downloader/icloud_photos_downloader/releases/tag/v1.19.0>`_
