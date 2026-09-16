# The stamp — one file, no dependencies

A **stamp** is the immutable record of **one step**: an agent, with a process and
its parameters, consumed one or more inputs and produced **one** artifact. This
library reads, writes, validates and compares stamps, says how strong an
identity is, keeps the mutable **hints** apart from the immutable record, and
**walks a chain backwards** using a resolver you supply.

The format is specified in [`stamp-format.md`](stamp-format.md).

## This is not a distributed ledger

No consensus, no global ordering, no network, no tokens, nothing to mine and
nobody to agree with. «Chain» plus «hash» plus «immutable» reads *blockchain*,
the question arrives every time, and it is better answered before it is asked: a
stamp is a JSON file somebody writes next to a file they made, and a chain is
what you get when you follow the digests backwards.

Two people can write contradicting stamps for the same artifact and **both are
kept**, because a contradiction is a discovery. This library will tell you
exactly where they disagree and will **never pick a winner** — choosing is a
decision a person makes with a reason, and a library that chose quietly would
make that decision invisible.

## Install, or do not

```bash
pip install dtcstamp
```

Or **copy `dtcstamp.py` next to your code**. That is not a fallback, it is the
design: whoever writes an add-on for Blender or a script for Metashape will not
add a dependency on a large library to write two kilobytes of JSON. One module,
standard library only, Python 3.9 and up.

There is a test that copies the file into an empty directory, with no package,
no installation and no third-party packages reachable at all, and runs the whole
conformance corpus against it. If that ever fails, the shape is wrong.

## Five minutes

```python
import dtcstamp

stamp = dtcstamp.read_stamp("model.glb.stamp.json")

dtcstamp.stamp_identity(stamp)["claim"]
# "these are those bytes, and anyone can check"

dtcstamp.declared_origin(stamp)
# False — `from: []` WITH a `how` means «born here»; without one it means
# «I do not know how this was made», and they are written identically

for d in dtcstamp.compare_stamps(mine, theirs):
    print(d.path, d.mine, "vs", d.theirs)     # …and no winner is chosen
```

### Walking a chain

The library **does not know where things are**. It knows how to walk: give it a
stamp and a function «give me the stamp (or the bytes) for this digest», and it
goes back one rung at a time.

```python
def from_my_folder(digest):                   # the file system…
    path = index.get(digest)
    return dtcstamp.read_stamp(path) if path else None

def from_the_store(digest):                   # …or an object store…
    answer = bucket.get(digest)
    return answer.read() if answer else None  # bytes are fine

walk = dtcstamp.walk_chain(stamp, from_my_folder)

len(walk.reached)                             # how far it got
[r.as_dict() for r in walk.unreached]         # and where it could not
```

`unreached` is not an error list. **«There was a parent with this id and this
digest, and I do not have it» is a result**, and it is the edge of what this
caller can see from where it is standing — the same walk on the machine that
holds the archive reaches further, and the difference between the two is the
useful part.

The walk terminates on a cycle (two stamps citing each other is a thing that
should not exist, which is exactly why it is tested) and has a ceiling that says
`truncated` rather than pretending to have finished.

## Hints, and why they are a separate file

An immutable record cannot contain a mutable field: rewriting it would change its
content and therefore its identity. So «I saw this digest in this place, at this
moment» lives in `<asset>.hints.json`, plural, non-authoritative, **never covered
by any digest**.

The gain is the opposite of what it looks like: **a wrong hint is harmless**. You
follow it, recompute the fingerprint, and either it is the right thing or you
find out immediately. A system that points by *name* hands you the wrong file in
silence.

`scope` decides what travels. A `public` hint (a store URI) may accompany a
published artifact; a `private` one **never leaves**, because an absolute path
carries a user name, a folder structure and sometimes a client's name.
`for_export()` is the only door outwards and **has no parameter to disable the
filter** — a door that can be opened halfway is a door somebody opens halfway.

## The conformance corpus

[`conformance/`](conformance/) holds example stamps with their expected outcome,
**outside the library's code**. It is the only defence that works against two
implementations drifting apart, and it is what a JavaScript port will be run
against the day there is one.

```bash
python3 -m unittest discover -p 'test_*.py'
```

## The name

`dtcstamp` is **provisional**. It was needed in order to write the code, not
decided. It appears in `pyproject.toml`, in this module's file name, and in one
constant — and **never inside a field of the format**, so changing it costs a
`sed` over a small repository and invalidates no file anybody has already
written. A test asserts that last part.

**DTC is _Data Transformation Chain_.** «Digital Twin Chain» is a typo that was
propagated from one place, and it is unrelated to the *Heritage Digital Twin*
(HDT-O, ECHOES D7.1), which is a real and different thing.

## The licence is not decided

There is deliberately no `LICENSE` file yet, and that is a flag rather than an
oversight. The whole purpose of this library is that somebody vendors it into a
Blender add-on or a Metashape script by copying one file — and which licence
permits that, and on what terms for them, is a decision for the author to make
rather than something a repository should acquire by default. Until it is made,
this is unpublished work.

## Who uses it

* **s3Dgraphy** builds a stamp *from a graph* (`emit`) and merges one back into a
  graph (`absorb`). Those two need a graph, so they stay there and import this.
* **EMStudio** reads stamps from the disk and from a room's object store, and
  emits ingestion records.
* **StratiGraph Server** serves assets and consults their provenance.

And the reason this is a separate repository: anybody else, with none of the
three installed.
