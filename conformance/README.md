# The conformance corpus

Example stamps with their expected outcome, **outside the library's code**, so
that any implementation can be run against them — this one today, a JavaScript
port tomorrow.

It is the only defence that works against two implementations drifting apart.
Reading the other one's source and promising to match does not work, and neither
does a shared prose specification: the specification says what should happen, and
a corpus says what *does*. It is the mechanism JSON Schema uses to keep its own
implementations together, for the same reason.

## The shape of a case

Every file is one JSON object. Three kinds, told apart by which key they carry:

| key | the case is about |
|---|---|
| `stamp` | one stamp: is it valid, how strong is its identity, does its empty parent list mean «born here» |
| `pair` | two stamps for the same artifact: do they agree, and if not exactly where |
| `stamp` + `resolvable` | a **walk**: `resolvable` is the world the resolver can see, keyed by digest |
| `members` | the **canonical list** of a resource of more than one file, byte for byte |
| `file_set` | an entry point and its files (`files`, written to a temporary folder): which members following the references finds |
| `tree` | a tileset as a folder (`files`) and as a `.3tz` (`archive`, a file under `data/`): one content digest for both |
| `stamp` + `blend` | a datablock, and the exact `blend://` locator for `blend.path` / `type` / `name` |

`files` maps a path (forward slashes) to `{"text": …}` (UTF-8) or
`{"base64": …}`. The binary archives live in `data/` and are referenced by a
path relative to this folder; they are fixtures, not cases.

`case` and `why` are prose for a human reading a failure at three in the morning.
`expect` is what an implementation has to produce.

## The keys of `expect`

| key | meaning |
|---|---|
| `valid` | whether `validate_stamp` accepts it |
| `error_contains` | a fragment of the refusal, when `valid` is false — the sentence matters, not just the failure |
| `identity_strength` | `verifiable` · `comparable` · `unknown` · `null` |
| `verifiable` | the boolean an interface may act on |
| `parents` | how many entries in `from` |
| `declared_origin` | whether `from: []` means «born here» (a `how` signs it) rather than «I do not know how» |
| `parent_0` | fields of the first parent that must read exactly so |
| `title` / `description` | what `stamp_title` / `stamp_description` read (`null` when the stamp has none worth showing) |
| `receipt` | the exact receipt a shelf keeps: `{id, checksum, stamp, parents, title?, description?}` |
| `preserved` | dotted paths of fields this version does not understand and **must not drop** |
| `agree` / `disagreements` | for a `pair`: whether they say the same thing, and the sorted paths where they do not |
| `walk_rungs` / `walk_reached` / `walk_unreached` | how far the ascent got |
| `walk_why` | the sorted, deduplicated reasons the unreached rungs were not reached |
| `walk_truncated` | whether the ceiling stopped it rather than the data |
| `packaging` | `self.packaging` as read |
| `members_canonical` | the canonical text (NUL separators, LF after every line) |
| `members_digest` | `sha256:` of that text |
| `canonical_members` / `members` | the normalised, sorted list `[{role, path, digest, size_bytes?}]` |
| `unclaimed` / `warnings` | files in the folder nobody calls; the warnings of the walk |
| `archive_sha256` | the sha256 of the `.3tz` file |
| `content_digest` / `files` | the identity of the tree's content, and how many files — the SAME for the folder and the archive |
| `canonical` / `failed_criteria` / `reasons_contain` | what `is_canonical_3tz` says, which criteria fail, fragments its reasons must carry |
| `blend_locator` / `hint_kind` / `hint_scope` | the locator string, and how a hint for it is classified |
| `parent_0_state` | what `parent_state` reads from the first parent, **after a write and a read** (01-11-2026) |
| `revision_of` | what `revision_of` reads, after a write and a read: `{resource_id, digest?}` |

## The case every 3tz writer reproduces

`20-tileset-folder-and-3tz.json` is the common case of the one `.3tz` profile
(`../profiles/3tz.md`, 3DSC's). To check a writer — 3DSC, EMStudio, anybody:

1. write every entry of `tree.files` into an empty folder (base64-decoded, or
   the `text` as UTF-8), paths as given;
2. pack that folder with your writer;
3. the sha256 of your archive must be `expect.archive_sha256`, and its content
   digest `expect.content_digest` — which is also the folder's.

A writer that gets the content digest right and the archive sha256 wrong writes
a valid 3tz that is **not canonical**: its bytes name the moment of packing. Case
`21` is exactly that archive, from `3d-tiles-tools` 0.5.4. Measured on 30-09-2026:
3DSC's `archive_3tz.write_3tz` (commit `1430128`) reproduces case 20.

## Adding a case

Add a file. The runner finds them by glob and there is no index to keep in step —
an index would be a second place to forget.

A new case should be a **sentence the format makes and that an implementation
could plausibly get wrong**, not another example of something already covered.
The ten that were here first each exist because the format says two things are
different and they are written almost the same way.
