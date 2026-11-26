"""Snapshot archive (P0.1): append-only captures of book prices, event state, prop offers
and lineup or news status, readable as of a time T.

- ``capture``: the capture pass run by ``scripts/capture_snapshots.py`` in the worker loop.
- ``view``: :class:`ArchiveView`, a read-only provider that answers as of T from the archive.
- ``placement``: the best price at the user's books when a stored bet was placed.
- ``prune``: the retention prune, the only code that deletes archive rows.
- ``guard``: refuses any update or ORM delete of an archive row.

Everything sits behind the ``snapshot_archive`` flag, off by default.
"""
