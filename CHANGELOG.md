# Changelog

All notable changes to `dtcstamp` are recorded here. The format follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the versions
follow [PEP 440](https://peps.python.org/pep-0440/).

`STAMP_VERSION` and `HINTS_VERSION` are **not** this package's version: they
are the on-disk format versions, and they change only when a file written by
an older reader stops being readable. A release that leaves them untouched has
not changed the format.

## [0.1.4] — YYYY-MM-DD

An asset inside a Metashape project, and the names Metashape writes in quotes.
Asked by MICRO-IL-LETTORE-DI-METASHAPE (02-10-2026): 3DSC for Metashape stamps
its exports with the master's address written `kind: local` because this
package did not know the kind; s3Dgraphy now reads a `.psx` and needs the same
address.

**The format did not change.** `STAMP_VERSION = 1` and `HINTS_VERSION = 1`: a
`psx://` hint is a hint like any other (an open vocabulary, recorded by older
readers as it is), and following a quoted name finds members an older reader
called `missing` — the stamp it would write is the one that was wrong.

### Added
- `psx_locator(psx_path, chunk, asset_type, key)` → `psx://<path>#<chunk>/<asset
  type>/<key>`, percent-encoded like `blend_locator`, and `parse_psx_locator` →
  `(path, chunk, asset_type, key)` or None. `PSX_SCHEME`. The form 3DSC for
  Metashape writes (`dtc_stamp_ms.py`, e920b4b) and s3Dgraphy's
  `make_psx_locator` produces. Conformance case `28`.
- `"psx"` in `KNOWN_KINDS`; `kind_for` recognises it; `scope_for` says
  `private` (a path on somebody's disk).

### Changed
- `follow_references` reads `mtllib "name with spaces.mtl"` and
  `map_Kd "name with spaces.jpg"` (any `map_*` and the other file statements)
  without the quotes — Metashape's form. Several quoted names on one `mtllib`,
  and a bare one beside them, are read too. The unquoted forms (Blender's one
  name with spaces, the spec's several names) are unchanged. Conformance case
  `29`. 3DSC for Metashape's test that pins the 0.1.3 behaviour
  (`test_quoted_mtllib_is_not_followed_by_dtcstamp_013`) fails against this
  release, as it was written to.

## [0.1.3] — 2026-10-02

The stamp that is born in an authoring tool (decision of E.D., 01-10-2026, on
the four departures EM Tools had to make the day it began stamping Blender's
exports). Spec revision 01-11-2026, section «Il passo nato in uno strumento
d'autore».

**The format did not change.** `STAMP_VERSION = 1` and `HINTS_VERSION = 1`.
Measured: the 0.1.2 wheel from PyPI, with its own corpus runner, passes cases
24–26, and its `note_seen` rewrites a register carrying `from` without
touching it. By the rule at the top of this file, neither moves.

### Added
- `from[].state` — the parent's operational state at the moment of the
  gesture: `fingerprint` (structural, compares and does not prove), `sha256`
  (the container, the `.blend` on disk), `saved`, and a `note` for a human.
  `with_parent_state`, `parent_state` (reads the first-day spelling
  `blend`/`blend_saved` too), `PARENT_STATE_KEYS`. Not substance.
- `self.was_revision_of` — `{resource_id, digest?}` of the previous
  distribution of the same master. `mark_revision` (refuses the same bytes:
  the same fact is not a revision), `revision_of` (a bare string reads as the
  id). Not substance, not a parent: the walk does not follow it.
- The parents' hints in the asset's own `<asset>.hints.json`, under `from`,
  one key per parent `resource_id`: `note_parent_seen`, `parent_hints`.
  `for_export` lets out only their public hints, never the machine;
  `private_locators` lists theirs too. No `<asset>.from.hints.json`.
- `by.operator.auth` — how the operator had entered: `orcid`,
  `node_password` (+ `attested_by`) or `declared` (a local identity nobody
  checked). Optional. **Changed**: the operator enters `substance` by its `id`
  alone — before, the whole object (label included) did, so the same person
  named twice differently read as a contradiction, against the rule that a
  label is a courtesy. Conformance case 27.
- The spec lists `export`, `lod_generation`, `tiling`, `packing` among the
  `process` kinds (s3Dgraphy `em_visual_rules` 1.6.29). dtcstamp still does
  not validate kinds.
- Conformance cases 24 (a parent's state), 25 (a revision), 26 (a pair that
  differs only in those two, and agrees), 27 (the operator by id); the runner reads `parent_0_state`
  and `revision_of` after a write and a read.

## [0.1.2] — 2026-10-01

Everything since 0.1.1: the stamp's title and description, `decimation` in the
`dtc_kind` vocabulary, the resource of more than one file (`members_digest`,
`content_digest`), the one `.3tz` profile with NFC names and flag `0x800`, and
conformance cases 15–23.

**The format did not change.** Measured against `v0.1.1`: `STAMP_VERSION = 1`
and `HINTS_VERSION = 1` in both. Everything added is optional; nothing a 0.1.1
reader accepted is refused now. By the rule at the top of this file, neither
moves.

### Changed — the one `.3tz` profile: NFC names, flag `0x800` (22-10-2026)
- `profiles/3tz.md`: every name in **Unicode NFC** (macOS gives NFD: the same
  folder gave two sha256), and flags **0 on an ASCII name, `0x800` on a
  non-ASCII one**, nothing else. `is_canonical_3tz` gains the criterion
  `names_nfc`; `CANONICAL_3TZ["name_form"]`. s3Dgraphy's
  `CANONICAL_3TZ_PROFILE` is aligned the same day: the two verifiers no longer
  differ.
- The producer computes `self.content_digest` (`computed_by: producer`) while
  it packs: 3DSC's `write_3tz` does.
- Conformance case `23` (a non-ASCII name) and
  `conformance/data/small-tileset-non-ascii-canonical.3tz`, written by 3DSC.

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

## [0.1.1] — 2026-09-16

No change to the library or the format: only `__version__` moved.

### Changed
- The release workflow asks each question on an interpreter that can answer
  it: the suite on every Python from 3.9 to 3.13, the exact zero-dependency
  check on 3.12 (`sys.stdlib_module_names` does not exist before 3.10), and
  the publish waits for both.

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
