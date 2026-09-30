# Changelog

All notable changes to `dtcstamp` are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the versions
follow [PEP 440](https://peps.python.org/pep-0440/).

`STAMP_VERSION` and `HINTS_VERSION` are **not** this package's version: they
are the on-disk format versions, and they change only when a file written by
an older reader stops being readable. A release that leaves them untouched has
not changed the format.

## [Unreleased]

### Added — the resource of more than one file (spec revision 21-10-2026)
- `self.packaging` is an enumerated vocabulary, `PACKAGINGS`: `file`,
  `file_set`, `directory`, `archive`, `datablock` (s3Dgraphy's). An unknown
  value is kept, not refused.
- `digest_covers: members`: the digest is the sha256 of the canonical list of
  the members — `role NUL path NUL sha256:<hex> LF`, NFC paths, sorted by
  UTF-8 bytes. `members_canonical`, `members_digest`, `canonical_members`,
  `member_path`, `BadMembers`.
- A `file_set` carries its list in `self.members`, found by following the
  entry point (`mtllib`/`map_*`, glTF `buffers`/`images`, glb):
  `follow_references`, `new_file_set_stamp`, `file_set_stamp_path`,
  `verify_members` (missing · changed · extra · list consistent),
  `unclaimed_files`; ceiling `MAX_FILE_SET_MEMBERS` = 64.
- `self.content_digest` `{digest, files, computed_by}` for a tree, the same for
  a folder and its `.3tz`: `tree_members`, `content_digest` (a 3tz read through
  its index, nothing extracted), `content_digest_block`, `new_tree_stamp`,
  `same_content`, `verify_tree`. `self.content_digest` is part of `substance`.
- The one `.3tz` profile, 3DSC's, in `profiles/3tz.md`, and
  `is_canonical_3tz` / `CANONICAL_3TZ`. Differs from s3Dgraphy's
  `CANONICAL_3TZ_PROFILE` on one measured point: flag `0x800` on a non-ASCII
  name is allowed (3DSC writes it).
- Datablocks: `new_datablock_stamp` (no byte digest; the `blend://` locator is
  a private hint), `blend_locator` / `parse_blend_locator` (s3Dgraphy's form).
- Conformance cases 18–22 and `conformance/data/` (two small `.3tz`).
- `STAMP_VERSION` stays 1: everything added is optional, nothing valid became
  invalid, and an old reader can only fail loudly on a members digest.

### Changed — the vocabulary of `dtc_kind` (spec text, 30-09-2026)
- `stamp-format.md` no longer says that «decimation» is not part of the
  vocabulary: since s3Dgraphy's `em_visual_rules` 1.6.22 it is a `process`
  kind, with georeferencing, format_conversion, classification and
  vectorization. The spec now lists the two axes a stamp uses — `acquisition`
  (capture / retrieval) and `process` — and says where a capture's kind goes
  (`how.dtc_kind`). The example uses `dtc_kind: "decimation"`. Text only: the
  format, `STAMP_VERSION` and the conformance vectors are unchanged.

### Added — the title and the description (spec revision 04-10-2026)
- `self.label` (the title) and `self.description`, both optional: a stamp
  without them is as valid as before and `STAMP_VERSION` stays 1. The title is
  spelled `label`, the word `from[]` already uses, so a child copies its
  parent's `self.label` into `from[].label`. Both a courtesy, never identity:
  neither is part of `substance`, so two stamps that differ only there agree.
- `stamp_title(stamp)` (None for a label that only repeats the id),
  `stamp_description(stamp)`, `DESCRIPTION_HINT_CHARS` (advice, never a
  refusal).
- `receipt(stamp)` — what a shelf keeps for a stamped file:
  `{id, checksum, stamp, parents, title?, description?}`, parents by identity
  only, title and description as a copy.
- Conformance 15–17 and the runner keys `title`, `description`, `receipt`.

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
