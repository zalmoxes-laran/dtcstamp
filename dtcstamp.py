"""The stamp: the immutable record of one step of a chain.

A stamp attests **one step**. An agent, with a process and its parameters,
consumes one or more inputs and produces **one** artifact; the stamp is the
record of that, written to stand on its own. The **chain** is the whole; a
**step** is the single transformation; a **stamp** is the file that records it.

**This is not a distributed ledger.** No consensus, no global ordering, no
network, no tokens, nothing to mine and nobody to agree with. «Chain» plus
«hash» plus «immutable» reads *blockchain* and the question will arrive every
time, so here is the answer first: a stamp is a JSON file somebody writes next
to a file they made, and a chain is what you get when you follow the digests
backwards. Two people can write contradicting stamps for the same artifact and
**both are kept**, because a contradiction is a discovery and this library has
no opinion about who is right.

## Why one file

Whoever writes an add-on for Blender, or a script for Metashape, will not add a
dependency on a large library to write two kilobytes of JSON. So this is **one
module, standard library only**: copy it next to your code and import it. That
constraint is the design, not an accident, and there is a test that copies this
file into an empty directory and runs the conformance corpus against it.

## What is here, and what is deliberately not

Here: the **format** (read, write, validate), the **identity** of an artifact
and how strong it is, the **hints**, **comparing** two stamps for the same
artifact, and **walking** a chain backwards.

Not here: anything that knows where files live. The walk takes a **resolver**
from the caller — the file system for a Blender plugin, an object store for a
server, a graph for s3Dgraphy, an index for a catalogue — and this module knows
none of the four. Also not here: building a stamp *from a graph*, which needs a
graph and therefore belongs to whoever has one.

## Reading rule that matters more than it looks

**Keep the fields you do not understand.** An implementation that drops the
unknown destroys provenance on the first round trip, silently, and the loss is
discovered years later by somebody who needed exactly that field. Everything
here copies whole objects rather than rebuilding them from known keys.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import (Any, Callable, Dict, Iterable, List, Optional, Sequence,
                    Tuple, Union)

#: The name of this package, in **one place**. It appears in `pyproject.toml`
#: and in this line, and nowhere else — never inside a field of the format, so
#: renaming it costs a `sed` over a small repository and changes no file anyone
#: has already written.
PACKAGE = "dtcstamp"

__version__ = "0.1.1"

#: The stamp format version. A record that declares another one is not broken:
#: it is from another epoch, and is refused with that word.
STAMP_VERSION = 1

#: The hints format version, separate on purpose: two files with two lives —
#: one never changes, the other changes all the time.
HINTS_VERSION = 1

STAMP_SUFFIX = ".stamp.json"
HINTS_SUFFIX = ".hints.json"


# ═════════════════════════════════════════════════════════════════════════════
# IDENTITY — and how strong it is, which is a separate question
# ═════════════════════════════════════════════════════════════════════════════
#
# A chain is strong at the published end and soft at the authoring end. A glTF
# file in a store has canonical bytes and its `sha256:` **proves it is the one**;
# a datablock inside a `.blend` has no canonical bytes — the file changes for
# reasons that have nothing to do with that mesh — and what can be computed is a
# structural fingerprint, enough to **notice that it changed**, not to verify
# that it is the same one.
#
# The format says so with the prefix. But a consumer deciding by looking inside
# the string — `digest.startswith(...)` in five places — is five places where the
# rule can drift, and one of those five will eventually treat a structural
# fingerprint as proof. So: one function.

#: Fingerprints that **prove**: there is a canonical byte sequence and anybody
#: can redo the arithmetic and get the same value.
VERIFIABLE_SCHEMES = ("sha256",)

#: Fingerprints that **compare**: they say whether it changed, not that it is the
#: same one. The `1` in `emstruct1` is in the name because the day a different
#: one is computed that one is `emstruct2`, and an old stamp goes on saying which
#: rule its own was taken by.
COMPARABLE_SCHEMES = ("emstruct1",)

VERIFIABLE = "verifiable"
COMPARABLE = "comparable"
UNKNOWN = "unknown"


def split_identity(value: Any) -> Tuple[Optional[str], Optional[str]]:
    """``("sha256", "6e4a…")`` — the scheme and the value, or ``(None, …)``.

    Separate from :func:`identity_strength` because whoever writes a stamp has to
    be able to put the two halves back together, and recomposing them with a
    hand-written ``:`` in two different places is how one of the two eventually
    loses its prefix.
    """
    if value is None:
        return None, None
    text = str(value).strip()
    if not text:
        return None, None
    if ":" not in text:
        return None, text
    scheme, _, rest = text.partition(":")
    scheme = scheme.strip().lower()
    rest = rest.strip()
    if not scheme or not rest:
        # `:abc` or `abc:` are not a scheme and a value: they are a malformed
        # string, and reading half of it would be worse than not reading it.
        return None, text
    return scheme, rest


def identity_strength(value: Any) -> Optional[str]:
    """``verifiable``, ``comparable``, ``unknown`` — or ``None`` if there is none.

    Three answers and not two, and the third is the important one. Bare digests
    exist in the real corpus: sixty-four hex characters and nothing else. Calling
    that ``verifiable`` would be **guessing the algorithm** and then asserting it.

    An absence is not ``unknown``: it is ``None``. There is no identity whose
    strength could be measured, and returning a word where there is no string
    would make a reader believe something had been said.
    """
    scheme, rest = split_identity(value)
    if rest is None:
        return None
    if scheme in VERIFIABLE_SCHEMES:
        return VERIFIABLE
    if scheme in COMPARABLE_SCHEMES:
        return COMPARABLE
    return UNKNOWN


def is_verifiable(value: Any) -> bool:
    """Whether anybody can **redo the arithmetic** and prove these are the bytes.

    False for an absence and false for an ``unknown``: the question has one safe
    answer, and without it the answer is no.
    """
    return identity_strength(value) == VERIFIABLE


def is_comparable(value: Any) -> bool:
    """Whether it is enough to notice a change — verifiable included.

    **A verifiable one is also comparable**, and that line is why this function
    exists instead of being ``strength == "comparable"`` written by the caller:
    somebody asking «can I at least notice an edit?» must get ``True`` from a
    sha256 too, and the opposite question is :func:`is_verifiable`.
    """
    return identity_strength(value) in (VERIFIABLE, COMPARABLE)


def describe_identity(value: Any) -> Dict[str, Any]:
    """What an interface has the right to say, in a dictionary.

    ``claim`` is the sentence, and it is not a courtesy: the whole point is that
    a panel must not write «verified» next to a structural fingerprint, and
    handing it the right words works better than hoping it will derive them.
    """
    scheme, rest = split_identity(value)
    strength = identity_strength(value)
    claim = {
        VERIFIABLE: "these are those bytes, and anyone can check",
        COMPARABLE: "this tells you if it changed, not that it is the same one",
        UNKNOWN: "an identity with no stated algorithm: not checkable",
        None: "no identity recorded",
    }[strength]
    return {"scheme": scheme, "value": rest, "strength": strength,
            "verifiable": strength == VERIFIABLE, "claim": claim}


# ═════════════════════════════════════════════════════════════════════════════
# THE STAMP — validate, read, write
# ═════════════════════════════════════════════════════════════════════════════

class BadStamp(ValueError):
    """This is not readable as a stamp."""


def validate_stamp(stamp: Any) -> Dict[str, Any]:
    """The minimum for it to be a stamp, and the sentences for when it is not.

    The **version** and the **identity of the output** are checked, and nothing
    else: a validator that demanded ``how`` would refuse the empty step, which is
    half of the real world.

    Returns the stamp itself, unchanged — **not a copy rebuilt from known keys**.
    Whatever it carries that this version does not understand travels on.
    """
    if not isinstance(stamp, dict):
        raise BadStamp(f"a stamp is a JSON object, got {type(stamp).__name__}")
    version = stamp.get("stamp")
    if version is None:
        raise BadStamp(
            "no `stamp` version key: this may be an em.json fragment, which is a "
            "different species — a stamp is a record and not a document to merge, "
            "edit and version")
    if version != STAMP_VERSION:
        raise BadStamp(
            f"stamp version {version!r}: this build reads version "
            f"{STAMP_VERSION}")
    itself = stamp.get("self")
    if not isinstance(itself, dict) or not str(itself.get("resource_id") or "").strip():
        raise BadStamp(
            "a stamp with no `self.resource_id` names no artifact: it is the "
            "output that gives the record its identity")
    return stamp


def clean_stamp(stamp: Dict[str, Any]) -> Dict[str, Any]:
    """The stamp **without the notes**, which is what leaves.

    Notes are for whoever emitted it. A file leaving the perimeter must not carry
    the doubts of its writer disguised as content. Keys are dropped only when
    they start with ``_``: everything else survives, including what this version
    does not understand.
    """
    return {k: v for k, v in stamp.items() if not str(k).startswith("_")}


def stamp_filename(stamp: Dict[str, Any], *, asset: Optional[str] = None) -> str:
    """``<asset>.stamp.json``.

    The asset's name when there is one, otherwise the resource id: never
    ``em.json`` (a different species — it would invite merging, editing and
    versioning a record) and never ``dtc.json`` (it would promise a chain and
    deliver one link).
    """
    base = str(asset or (stamp.get("self") or {}).get("resource_id") or "stamp")
    return _safe_name(base) + STAMP_SUFFIX


def stamp_identity(stamp: Dict[str, Any]) -> Dict[str, Any]:
    """How strong this stamp's identity is — see :func:`describe_identity`.

    Here, rather than left to the reader, because it is the question an interface
    has to ask **before** writing «verified» next to a row.
    """
    return describe_identity((stamp.get("self") or {}).get("digest"))


def is_verifiable_stamp(stamp: Dict[str, Any]) -> bool:
    return is_verifiable((stamp.get("self") or {}).get("digest"))


def declared_origin(stamp: Dict[str, Any]) -> bool:
    """Whether ``from: []`` means «born here» or «I do not know how».

    The two are written the same way and mean opposite things, and the format
    warns about exactly this: an empty parent list **with** a ``how`` that signs
    it is a complete declaration, **without** one it says nothing was declared.
    Asked here so that no caller has to remember the rule.
    """
    parents = stamp.get("from")
    if parents:
        return False
    return bool(stamp.get("how"))


# ── the filesystem, kept to three functions on purpose ───────────────────────
#
# Everything above is pure: given a dictionary it answers. These three are the
# only ones that touch a disk, and they are separate so the rest can be tested
# without one — and so a caller whose bytes come from an object store or a
# database never goes near them.

def read_stamp(path: str) -> Dict[str, Any]:
    """Read ``<asset>.stamp.json`` from a path and validate it."""
    with open(path, "r", encoding="utf-8") as handle:
        return validate_stamp(json.load(handle))


def parse_stamp(raw: Union[str, bytes, bytearray]) -> Dict[str, Any]:
    """The same, from bytes somebody else fetched — a store, a socket, a row.

    Exists so that a caller with the bytes in hand does not have to write them to
    a temporary file to use this library, which is what an object-store client
    would otherwise do.
    """
    if isinstance(raw, (bytes, bytearray)):
        raw = raw.decode("utf-8")
    return validate_stamp(json.loads(raw))


def write_stamp(stamp: Dict[str, Any], path: str) -> str:
    """Write the stamp to disk.

    ``indent=1`` and ``ensure_ascii=False``: **the reader of last resort is a
    human with a text editor, thirty years from now**, and that is also why it is
    not written compact.
    """
    return _write_json(clean_stamp(stamp), path)


def _safe_name(base: str) -> str:
    return "".join(c if c.isalnum() or c in "-_." else "_" for c in str(base))


def _write_json(payload: Dict[str, Any], path: str) -> str:
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, ensure_ascii=False, indent=1)
        handle.write("\n")
    return path


def now_iso() -> str:
    """The current instant, UTC, second precision, ISO-8601 with a ``Z``.

    Second precision on purpose: these instants order observations, and
    microseconds would only add noise to every diff.
    """
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z")


# ═════════════════════════════════════════════════════════════════════════════
# COMPARING — two stamps for the same artifact, and never a winner
# ═════════════════════════════════════════════════════════════════════════════
#
# Two stamps for the same output digest that contradict each other in substance —
# different parents, a different process — **are not an error, they are a
# discovery**, and they are made to surface. Two that differ only in the instant
# are the same fact recorded twice, and deduplicate.
#
# Nothing here chooses. Choosing is a decision somebody makes with a reason,
# and a library that quietly picked one would make that decision invisible.

@dataclass
class Disagreement:
    """One point where two stamps do not agree. **Without a winner.**"""

    path: str
    mine: Any
    theirs: Any

    def as_dict(self) -> Dict[str, Any]:
        return {"path": self.path, "mine": self.mine, "theirs": self.theirs}


def substance(stamp: Dict[str, Any]) -> Dict[str, Any]:
    """The facts of the stamp, reduced to a comparable shape.

    Lists with no meaningful order — the parents, the software — become
    **canonically sorted sets**: a tileset coming out of N meshes is not a
    different fact because the meshes are listed in another order, and calling
    that a disagreement would be noise.
    """
    itself = dict(stamp.get("self") or {})
    how = dict(stamp.get("how") or {})
    by = dict(stamp.get("by") or {})
    declared = dict(stamp.get("declared") or {})

    out: Dict[str, Any] = {}
    out["self.digest"] = itself.get("digest")
    out["self.digest_covers"] = itself.get("digest_covers")
    out["self.media_type"] = itself.get("media_type")
    out["self.format"] = itself.get("format")
    out["self.packaging"] = itself.get("packaging")
    out["self.tier"] = itself.get("tier")
    out["self.measures"] = itself.get("measures")

    # The parents by identity, never by label: a `label` is a courtesy.
    parents = stamp.get("from")
    if isinstance(parents, list):
        out["from"] = sorted(
            _parent_key(p) for p in parents if isinstance(p, dict))
    else:
        out["from"] = None

    out["how.process_id"] = how.get("process_id")
    out["how.technique"] = how.get("technique")
    out["how.dtc_kind"] = how.get("dtc_kind")
    out["how.parameters"] = how.get("parameters")
    out["how.acquisition"] = how.get("acquisition")
    software = how.get("software")
    out["how.software"] = (sorted(_canonical(s) for s in software)
                           if isinstance(software, list) else None)

    operator = by.get("operator")
    out["by.operator"] = _canonical(operator) if operator else None

    out["declared.license"] = declared.get("license")
    out["declared.embargo_until"] = declared.get("embargo_until")
    return out


def _parent_key(parent: Dict[str, Any]) -> str:
    return "|".join([str(parent.get("resource_id") or ""),
                     str(parent.get("digest") or ""),
                     str(parent.get("kind") or "")])


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False,
                      separators=(",", ":"))


def compare_stamps(mine: Dict[str, Any], theirs: Dict[str, Any]
                   ) -> List[Disagreement]:
    """The points where two stamps about the same artifact do not agree.

    **Silence is not a disagreement**: both have to speak. The one exception is
    ``from`` when a ``how`` signs it — there the empty list IS a declaration
    («born here») and saying nothing is a different thing.
    """
    a, b = substance(mine), substance(theirs)
    mine_claims_origin = bool(mine.get("how"))
    theirs_claims_origin = bool(theirs.get("how"))
    out: List[Disagreement] = []
    for path in a:
        left, right = a.get(path), b.get(path)
        if path == "from":
            # an empty list speaks only when a `how` signs it
            left_speaks = left is not None and (left or mine_claims_origin)
            right_speaks = right is not None and (right or theirs_claims_origin)
            if not (left_speaks and right_speaks):
                continue
        elif left in (None, "", {}, []) or right in (None, "", {}, []):
            continue
        if left != right:
            out.append(Disagreement(path=path, mine=left, theirs=right))
    return out


def stamps_agree(mine: Dict[str, Any], theirs: Dict[str, Any]) -> bool:
    """Whether the two say the same thing about the same artifact.

    Differing only in ``by.at`` is not a disagreement and never reaches here:
    the instant is not part of :func:`substance`, because the same fact recorded
    twice at two moments is one fact.
    """
    return not compare_stamps(mine, theirs)


# ═════════════════════════════════════════════════════════════════════════════
# THE WALK — one rung at a time, and it says where it could not get to
# ═════════════════════════════════════════════════════════════════════════════
#
# **This library does not know where things are.** It knows how to walk: given a
# stamp and a function «give me the stamp (or the bytes) for this digest», it
# goes back one rung at a time and **stops saying where it did not arrive** —
# «there was a parent with this id and this digest, and I do not have it» is a
# RESULT, not an error.
#
# The caller supplies the resolver: the file system for a Blender plugin, an
# object store for a server, a graph for s3Dgraphy, an index for a catalogue.
# None of the four is in here, and a test asserts it by reading the source of
# these functions.

#: What the caller passes: given a parent's digest, return its stamp (a dict), or
#: the bytes/text of its `.stamp.json`, or ``None`` for «I do not have it».
Resolver = Callable[[str], Union[None, Dict[str, Any], str, bytes]]

#: Why a rung is where the walk stopped. Each one is a different fact, and a
#: single «missing» would have flattened four different situations into one.
NOT_RESOLVED = "not resolved"
NOT_A_FILE = "not a file"
ALREADY_WALKED = "already walked"
CEILING = "ceiling reached"
UNREADABLE = "unreadable"


@dataclass
class Rung:
    """One rung of the ascent: a parent, and whether it was reached."""

    resource_id: Optional[str] = None
    digest: Optional[str] = None
    #: ``"acquisition"`` when the input is a campaign rather than a file
    kind: Optional[str] = None
    label: Optional[str] = None
    #: how many links away from the artifact the walk started at
    depth: int = 1
    stamp: Optional[Dict[str, Any]] = None
    reached: bool = False
    #: when it was not reached, WHICH of the reasons above
    why: Optional[str] = None
    detail: Optional[str] = None

    def as_dict(self) -> Dict[str, Any]:
        out = {"resource_id": self.resource_id, "digest": self.digest,
               "depth": self.depth, "reached": self.reached}
        for key in ("kind", "label", "why", "detail"):
            value = getattr(self, key)
            if value:
                out[key] = value
        return out


@dataclass
class Walk:
    """What the ascent found, and what it did not.

    ``unreached`` is not an error list: it is the edge of what this caller can
    see from where it is standing. The same walk run on a machine that holds the
    archive reaches further, and the difference between the two is exactly the
    useful information.
    """

    root: Dict[str, Any] = field(default_factory=dict)
    rungs: List[Rung] = field(default_factory=list)
    #: true when the ceiling stopped the walk rather than the data
    truncated: bool = False

    @property
    def reached(self) -> List[Rung]:
        return [r for r in self.rungs if r.reached]

    @property
    def unreached(self) -> List[Rung]:
        return [r for r in self.rungs if not r.reached]

    @property
    def depth(self) -> int:
        return max((r.depth for r in self.rungs), default=0)

    def as_dict(self) -> Dict[str, Any]:
        return {"root": (self.root.get("self") or {}).get("digest"),
                "truncated": self.truncated,
                "rungs": [r.as_dict() for r in self.rungs]}


def walk_chain(stamp: Dict[str, Any], resolve: Resolver, *,
               max_rungs: int = 512) -> Walk:
    """Walk backwards from one stamp, one rung at a time.

    ``resolve(digest)`` may return a stamp, the bytes or text of one, or ``None``
    for «I do not have it». Returning ``None`` is an ordinary answer and the walk
    records it as a rung that was not reached.

    **It terminates on a cycle.** Two stamps citing each other must not spin
    forever — a thing that should not exist in reality, which is exactly why it
    is tested. Each digest is walked once; a second sighting is a rung with
    ``why=ALREADY_WALKED``. ``max_rungs`` is the second net, for a chain that is
    long rather than circular, and when it bites the walk says ``truncated``
    instead of pretending it finished.
    """
    walk = Walk(root=stamp)
    root_digest = (stamp.get("self") or {}).get("digest")
    seen = {root_digest} if root_digest else set()
    # the frontier, as (stamp-to-expand, depth of its parents)
    frontier: List[Tuple[Dict[str, Any], int]] = [(stamp, 1)]

    while frontier:
        current, depth = frontier.pop(0)
        for parent in current.get("from") or []:
            if not isinstance(parent, dict):
                continue
            rung = Rung(resource_id=_text(parent.get("resource_id")),
                        digest=_text(parent.get("digest")),
                        kind=_text(parent.get("kind")),
                        label=_text(parent.get("label")),
                        depth=depth)
            walk.rungs.append(rung)

            if len(walk.rungs) >= max_rungs:
                rung.why = CEILING
                walk.truncated = True
                return walk

            # An input that is not a file has no bytes to hash and nothing to
            # resolve: an acquisition campaign is a legitimate parent and the
            # missing digest is not a defect. Asking the resolver for it would
            # make every caller invent an answer for a question with none.
            if not rung.digest:
                rung.why = NOT_A_FILE if rung.kind else NOT_RESOLVED
                continue

            if rung.digest in seen:
                rung.why = ALREADY_WALKED
                continue
            seen.add(rung.digest)

            answer = resolve(rung.digest)
            if answer is None:
                rung.why = NOT_RESOLVED
                continue
            try:
                parent_stamp = (validate_stamp(answer)
                                if isinstance(answer, dict)
                                else parse_stamp(answer))
            except (BadStamp, ValueError) as exc:
                # BadStamp and ValueError, not Exception: a malformed or foreign
                # file is this, and it is a fact about the data. Anything else is
                # a defect in the resolver and must reach whoever wrote it.
                rung.why = UNREADABLE
                rung.detail = str(exc)
                continue
            rung.stamp = parent_stamp
            rung.reached = True
            frontier.append((parent_stamp, depth + 1))
    return walk


def _text(value: Any) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


# ═════════════════════════════════════════════════════════════════════════════
# HINTS — «I saw this digest in this place, at this moment»
# ═════════════════════════════════════════════════════════════════════════════
#
# A mutable, plural, non-authoritative register, in a separate file
# (`<asset>.hints.json`) and **never covered by any digest**. The file is
# separate out of necessity and not for tidiness: an immutable record cannot
# contain a mutable field, because rewriting it would change its content.
#
# The gain is the opposite of what it looks like: **a wrong hint is harmless.**
# You follow it, recompute the fingerprint, and either it is the right thing or
# you find out immediately. A system that points by NAME hands you the wrong file
# in silence, which is the worst way there is to be wrong.

#: Who may travel and who may not. **Two values and not three**: «maybe» is not
#: an answer to a question about privacy.
SCOPES = ("public", "private")

#: How that place is reached. Open vocabulary — a `kind` that is not here is
#: recorded anyway, because a hint is an observation and not a declaration of
#: conformance — but these four write themselves.
KNOWN_KINDS = ("s3", "http", "local", "blend")

#: Which kinds are public when nobody says. A store URI is an address;
#: **everything else is private by default**, and the direction of this default
#: is the decision: erring towards «private» costs a hint that does not travel,
#: erring towards «public» costs somebody's user name.
_PUBLIC_BY_DEFAULT = ("s3", "http")


def new_hints(digest: str) -> Dict[str, Any]:
    """An empty register for this digest."""
    return {"hints": HINTS_VERSION, "digest": str(digest), "seen": []}


def kind_for(locator: str) -> str:
    """How that place is reached, read off the shape of the locator."""
    text = str(locator or "")
    if text.startswith("s3://"):
        return "s3"
    if text.startswith(("http://", "https://")):
        return "http"
    if text.startswith("blend://"):
        return "blend"
    return "local"


def scope_for(locator: str, kind: Optional[str] = None) -> str:
    """``public`` or ``private`` when nobody has said.

    The direction of the doubt is towards ``private``, always.
    """
    guessed = kind or kind_for(locator)
    return "public" if guessed in _PUBLIC_BY_DEFAULT else "private"


def note_seen(hints: Dict[str, Any], locator: str, *,
              kind: Optional[str] = None,
              scope: Optional[str] = None,
              machine: Optional[str] = None,
              when: Optional[str] = None) -> Dict[str, Any]:
    """Note «seen here, now». **Updates, does not duplicate, does not delete.**

    The same locator on the same machine is **the same hint re-observed**: its
    ``when`` is updated and it stays where it was. A row per glance would grow
    the file without adding a fact.

    ``when`` can be passed — and it needs to be, because a function that asks the
    clock cannot be tested twice with the same outcome. Absent, it is now: the
    clock belongs here, because **observing is an act that happens at a moment**,
    unlike emitting a stamp, which is a reading.

    **Hints are not deleted, they age.** There is nothing here, and there will be
    nothing here, that asks a person to tidy up a path: a moved file is not an
    error to correct, it is a fact to re-observe.
    """
    if scope is not None and scope not in SCOPES:
        raise ValueError(f"scope must be one of {list(SCOPES)}, got {scope!r}")
    seen = hints.setdefault("seen", [])
    resolved_kind = kind or kind_for(locator)
    entry = {
        "locator": str(locator),
        "kind": resolved_kind,
        "scope": scope or scope_for(locator, resolved_kind),
        "when": when or now_iso(),
    }
    if machine:
        entry["machine"] = machine
    for existing in seen:
        if existing.get("locator") == entry["locator"] \
                and existing.get("machine") == entry.get("machine"):
            existing.update(entry)
            return existing
    seen.append(entry)
    return entry


def for_export(hints: Dict[str, Any]) -> Dict[str, Any]:
    """The hints that may travel: **only ``public``**.

    The one door outwards, and **it has no switch**: a door that can be opened
    halfway is a door somebody opens halfway one day. Returns a well-formed
    register even when it stays empty — «I know no public place for this digest»
    is an honest answer, while no file at all would suggest the register does not
    exist.
    """
    out = {"hints": HINTS_VERSION, "digest": hints.get("digest"), "seen": []}
    for entry in hints.get("seen") or []:
        if not isinstance(entry, dict):
            continue
        if entry.get("scope") != "public":
            continue
        # `machine` does not leave even in a public hint: the name of somebody's
        # computer is not part of an address, and in a file that travels it is
        # just one more thing that is known about them.
        out["seen"].append({k: v for k, v in entry.items() if k != "machine"})
    return out


def private_locators(hints: Dict[str, Any]) -> List[str]:
    """The locators that must not leave. To **prove** it, not to use them."""
    return [str(e.get("locator") or "") for e in hints.get("seen") or []
            if isinstance(e, dict) and e.get("scope") != "public"]


def hints_filename(digest: str, *, asset: Optional[str] = None) -> str:
    """``<asset>.hints.json``, beside the stamp and by the same naming rule."""
    return _safe_name(str(asset or digest or "hints")) + HINTS_SUFFIX


def write_hints(hints: Dict[str, Any], path: str) -> str:
    """Write the **whole** register, private hints included: it is the home file."""
    return _write_json(hints, path)


def write_public_hints(hints: Dict[str, Any], path: str) -> str:
    """Write **only** what may travel. No parameter disables the filter."""
    return _write_json(for_export(hints), path)


def read_hints(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def file_digest(path: str, *, chunk: int = 1024 * 1024) -> str:
    """``sha256:<hex>`` of a file's bytes, read in blocks.

    In blocks because a point cloud does not fit in memory, and a digest that
    works on small files and dies on large ones is worse than no digest: it fails
    on exactly the data that was worth identifying.
    """
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            block = handle.read(chunk)
            if not block:
                break
            digest.update(block)
    return f"sha256:{digest.hexdigest()}"


def scan_directory(root: str, *, machine: Optional[str] = None,
                   when: Optional[str] = None,
                   suffixes: Optional[Iterable[str]] = None,
                   into: Optional[Dict[str, Dict[str, Any]]] = None
                   ) -> Dict[str, Any]:
    """Scan a directory and note where it saw what.

    Returns ``{"found": {digest: hints}, "unreadable": [...]}`` — **two keys and
    not one dictionary**, because a file that could not be read has no digest to
    live under, and slipping it into the same map with a fake key would put a
    word among the addresses of whoever iterates.

    ``into`` continues a register that already existed, because a scan **adds
    to** previous observations rather than replacing them: a file that is not
    there today does not stop having been seen elsewhere yesterday.

    The ``scope`` is not a parameter: a path on a disk is ``local``, and ``local``
    is ``private``. Letting the caller choose would mean somebody one day passes
    ``public`` for a scan of their own laptop.
    """
    base = pathlib.Path(root)
    if not base.is_dir():
        raise NotADirectoryError(f"{root} is not a directory to scan")
    found: Dict[str, Dict[str, Any]] = into if into is not None else {}
    unreadable: List[str] = []
    wanted = tuple(s.lower() for s in suffixes) if suffixes else None
    host = machine if machine is not None else _this_machine()
    for path in sorted(base.rglob("*")):
        if not path.is_file():
            continue
        if wanted and path.suffix.lower() not in wanted:
            continue
        try:
            digest = file_digest(str(path))
        except OSError as exc:
            # OSError and not Exception: a denied permission or a broken link is
            # this; anything else is a defect and must reach the reader instead
            # of ending up in a list of warnings.
            unreadable.append(f"{path}: {exc}")
            continue
        register = found.setdefault(digest, new_hints(digest))
        note_seen(register, str(path), kind="local", scope="private",
                  machine=host, when=when)
    return {"found": found, "unreadable": unreadable}


def _this_machine() -> Optional[str]:
    """The name of this machine, when the system says.

    It lives in a ``private`` hint and never leaves (:func:`for_export` strips it
    even from a public one): it tells «I saw it on the laptop» from «I saw it on
    the desktop», which is the only reason two hints to the same path are two
    hints.
    """
    uname = getattr(os, "uname", None)
    return uname().nodename if callable(uname) else None


__all__ = [
    "ALREADY_WALKED", "BadStamp", "CEILING", "COMPARABLE", "COMPARABLE_SCHEMES",
    "Disagreement", "HINTS_SUFFIX", "HINTS_VERSION", "KNOWN_KINDS", "NOT_A_FILE",
    "NOT_RESOLVED", "PACKAGE", "Resolver", "Rung", "SCOPES", "STAMP_SUFFIX",
    "STAMP_VERSION", "UNKNOWN", "UNREADABLE", "VERIFIABLE", "VERIFIABLE_SCHEMES",
    "Walk", "__version__", "clean_stamp", "compare_stamps", "declared_origin",
    "describe_identity", "file_digest", "for_export", "hints_filename",
    "identity_strength", "is_comparable", "is_verifiable", "is_verifiable_stamp",
    "kind_for", "new_hints", "note_seen", "now_iso", "parse_stamp",
    "private_locators", "read_hints", "read_stamp", "scan_directory",
    "scope_for", "split_identity", "stamp_filename", "stamp_identity",
    "stamps_agree", "substance", "validate_stamp", "walk_chain", "write_hints",
    "write_public_hints", "write_stamp",
]
