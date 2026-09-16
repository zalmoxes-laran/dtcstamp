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
| `preserved` | dotted paths of fields this version does not understand and **must not drop** |
| `agree` / `disagreements` | for a `pair`: whether they say the same thing, and the sorted paths where they do not |
| `walk_rungs` / `walk_reached` / `walk_unreached` | how far the ascent got |
| `walk_why` | the sorted, deduplicated reasons the unreached rungs were not reached |
| `walk_truncated` | whether the ceiling stopped it rather than the data |

## Adding a case

Add a file. The runner finds them by glob and there is no index to keep in step —
an index would be a second place to forget.

A new case should be a **sentence the format makes and that an implementation
could plausibly get wrong**, not another example of something already covered.
The ten that were here first each exist because the format says two things are
different and they are written almost the same way.
