"""Public creative collection for the OMA creatives skill.

Modules:
- ``browser``: page drivers (Camofox REST, or the Hermes browser inside ``browser_exec``),
  settle waits, page classification and screenshots.
- ``web``: plain HTTP with size limits and public-URL checks.
- ``media``: media download, image compression and video transcoding.
- ``values``: count, date and post-ID time parsing shared by every source.
- ``store``: ``index.yaml`` records, selection, winner and rerun rules, pruning and locks.
- ``social``: one organic collector per platform, in the ``PLATFORMS`` table.
- ``ads``: one ad-library collector per library, in the ``LIBRARIES`` table.
- ``landing``: one capture per distinct ad landing page.
- ``run``: the command entry points used by ``collect.py``.
"""
