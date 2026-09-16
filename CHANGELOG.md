# Changelog

All notable changes to `dtcstamp` are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the versions
follow [PEP 440](https://peps.python.org/pep-0440/).

`STAMP_VERSION` and `HINTS_VERSION` are **not** this package's version: they
are the on-disk format versions, and they change only when a file written by
an older reader stops being readable. A release that leaves them untouched has
not changed the format.

## [Unreleased]

## [0.1.0] — 2026-09-16

First public release. Extracted from s3Dgraphy so that a Blender add-on, a
Metashape script or any other tool can read and write DTC stamps without
installing a graph library.

### Added
- `dtcstamp` — one module, zero third-party dependencies, measured against
  `sys.stdlib_module_names` rather than asserted.
- Read, write and validate a stamp; unknown fields are **preserved** across a
  round trip, which is the format's most important rule.
- Identity of an artefact and its strength: `verifiable` / `comparable` /
  `unknown`.
- Hints (`piste`) with their `scope`, kept out of the digest by design.
- `walk_chain(stamp, resolve, …)` — the resolver is **injected**, so the
  library never knows where anything is stored.
- Comparison of two stamps for the same digest, which reports agreement or
  disagreement and never picks a winner.
- `how.acquisition.device` as an identity, and `how.acquisition.location` as
  plain values (lat/lon/alt/crs + `source`) — values, never types.
- `conformance/` — 14 cases with their expected outcome, shared between
  implementations.
