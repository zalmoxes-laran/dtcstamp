"""The library's own tests, plus the runner for the conformance corpus.

Plain `unittest`, standard library only, and that is not a style preference: a
library whose whole argument is «zero dependencies» cannot ask for pytest in
order to prove it.

    python3 -m unittest discover -p 'test_*.py'
    python3 test_dtcstamp.py            # the same, run directly

**Every structural assertion here has a deliberate counterexample** that must
make it fail. A test that can only pass is not a test: it is a decoration
carrying the trust of whoever reads it.
"""

import inspect
import json
import pathlib
import sys
import tempfile
import unittest

import dtcstamp as S

HERE = pathlib.Path(__file__).resolve().parent
CORPUS = HERE / "conformance"

SHA = lambda c: "sha256:" + c * 64          # noqa: E731 — a corpus shorthand


# ═════════════════════════════════════════════════════════════════════════════
# THE CORPUS — the cases live outside the code, and this reads them
# ═════════════════════════════════════════════════════════════════════════════

def _dotted(obj, path):
    """`self.x_colour_profile` → the value, or a marker that says it is gone."""
    cursor = obj
    for part in path.split("."):
        if not isinstance(cursor, dict) or part not in cursor:
            return _MISSING
        cursor = cursor[part]
    return cursor


_MISSING = object()


def _materialise(files, root):
    """Write a case's `files` ({path: {text} | {base64}}) under `root`."""
    import base64
    for rel, value in files.items():
        target = pathlib.Path(root, *rel.split("/"))
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(value["text"].encode("utf-8") if "text" in value
                           else base64.b64decode(value["base64"]))


class Corpus(unittest.TestCase):
    """Every file in `conformance/`, checked against what it says it expects."""

    def test_the_corpus_is_not_empty(self):
        # A runner that silently finds no cases passes for ever. It has happened
        # to better test suites than this one.
        self.assertGreaterEqual(len(list(CORPUS.glob("*.json"))), 10,
                                "the corpus glob found (almost) nothing")

    def test_every_case(self):
        cases = sorted(CORPUS.glob("*.json"))
        for path in cases:
            with self.subTest(case=path.name):
                self._run_case(json.loads(path.read_text(encoding="utf-8")))

    def _run_case(self, case):
        expect = case["expect"]
        if "members" in case:
            return self._run_members(case["members"], expect)
        if "file_set" in case:
            return self._run_file_set(case["file_set"], expect)
        if "tree" in case:
            return self._run_tree(case["tree"], expect)
        if "psx" in case:
            return self._run_psx(case["psx"], expect)
        if "blend" in case:
            self._run_blend(case["blend"], expect)
        if "pair" in case:
            return self._run_pair(case["pair"], expect)
        if "resolvable" in case:
            return self._run_walk(case, expect)
        return self._run_single(case["stamp"], expect)

    def _run_single(self, stamp, expect):
        if expect.get("valid") is False:
            with self.assertRaises(S.BadStamp) as caught:
                S.validate_stamp(stamp)
            if "error_contains" in expect:
                self.assertIn(expect["error_contains"], str(caught.exception))
            return
        validated = S.validate_stamp(stamp)

        if "identity_strength" in expect:
            self.assertEqual(
                S.identity_strength((validated.get("self") or {}).get("digest")),
                expect["identity_strength"])
        if "verifiable" in expect:
            self.assertEqual(S.is_verifiable_stamp(validated),
                             expect["verifiable"])
        if "packaging" in expect:
            self.assertEqual((validated.get("self") or {}).get("packaging"),
                             expect["packaging"])
        if "parents" in expect:
            self.assertEqual(len(validated.get("from") or []),
                             expect["parents"])
        if "declared_origin" in expect:
            self.assertEqual(S.declared_origin(validated),
                             expect["declared_origin"])
        if "parent_0" in expect:
            parent = (validated.get("from") or [])[0]
            for key, value in expect["parent_0"].items():
                self.assertEqual(parent.get(key), value)
        if "title" in expect:
            self.assertEqual(S.stamp_title(validated), expect["title"])
        if "description" in expect:
            self.assertEqual(S.stamp_description(validated),
                             expect["description"])
        if "receipt" in expect:
            self.assertEqual(S.receipt(validated), expect["receipt"])
        if "parent_0_state" in expect or "revision_of" in expect:
            # read AFTER a round trip: kept on read and dropped on write is lost
            with tempfile.TemporaryDirectory() as tmp:
                target = str(pathlib.Path(tmp) / "x.stamp.json")
                S.write_stamp(validated, target)
                back = S.read_stamp(target)
            if "parent_0_state" in expect:
                self.assertEqual(S.parent_state((back.get("from") or [])[0]),
                                 expect["parent_0_state"])
            if "revision_of" in expect:
                self.assertEqual(S.revision_of(back), expect["revision_of"])
        for path in expect.get("preserved", []):
            # THE ROUND TRIP, not just the read: an implementation that keeps a
            # field on read and drops it on write loses it just the same.
            with tempfile.TemporaryDirectory() as tmp:
                target = str(pathlib.Path(tmp) / "x.stamp.json")
                S.write_stamp(validated, target)
                back = S.read_stamp(target)
            self.assertIsNot(_dotted(back, path), _MISSING,
                             f"{path} did not survive the round trip")

    def _run_members(self, members, expect):
        self.assertEqual(S.members_canonical(members).decode("utf-8"),
                         expect["members_canonical"])
        self.assertEqual(S.members_digest(members), expect["members_digest"])
        if "canonical_members" in expect:
            self.assertEqual(S.canonical_members(members),
                             expect["canonical_members"])

    def _run_file_set(self, spec, expect):
        with tempfile.TemporaryDirectory() as tmp:
            _materialise(spec["files"], tmp)
            found = S.follow_references(str(pathlib.Path(tmp) / spec["entry_point"]))
            self.assertEqual(found["members"], expect["members"])
            self.assertEqual(S.members_digest(found["members"]),
                             expect["members_digest"])
            if "unclaimed" in expect:
                self.assertEqual(S.unclaimed_files(tmp, [found]),
                                 expect["unclaimed"])
            if "warnings" in expect:
                self.assertEqual(found["warnings"], expect["warnings"])

    def _run_tree(self, spec, expect):
        archive = str(CORPUS / spec["archive"])
        self.assertEqual(S.file_digest(archive), expect["archive_sha256"])
        self.assertEqual(S.content_digest(archive), expect["content_digest"])
        verdict = S.is_canonical_3tz(archive)
        self.assertEqual(verdict["canonical"], expect["canonical"])
        if "failed_criteria" in expect:
            self.assertEqual(sorted(k for k, v in verdict.items() if v is False),
                             expect["failed_criteria"])
        for fragment in expect.get("reasons_contain", []):
            self.assertTrue(any(fragment in r for r in verdict["reasons"]),
                            f"no reason mentions {fragment!r}")
        with tempfile.TemporaryDirectory() as tmp:
            _materialise(spec["files"], tmp)
            # ONE CONTENT, TWO FORMS: the folder gives what the archive gives
            self.assertEqual(S.content_digest(tmp), expect["content_digest"])
            if "members" in expect:
                self.assertEqual(S.tree_members(tmp), expect["members"])
            if "files" in expect:
                self.assertEqual(len(S.tree_members(tmp)), expect["files"])

    def _run_blend(self, spec, expect):
        locator = S.blend_locator(spec["path"], spec["type"], spec["name"])
        self.assertEqual(locator, expect["blend_locator"])
        self.assertEqual(S.parse_blend_locator(locator),
                         (spec["path"], spec["type"], spec["name"]))
        self.assertEqual(S.kind_for(locator), expect.get("hint_kind", "blend"))
        self.assertEqual(S.scope_for(locator), expect.get("hint_scope", "private"))

    def _run_psx(self, spec, expect):
        locator = S.psx_locator(spec["path"], spec["chunk"], spec["asset_type"],
                                spec["key"])
        self.assertEqual(locator, expect["psx_locator"])
        self.assertEqual(S.parse_psx_locator(locator),
                         (spec["path"], spec["chunk"], spec["asset_type"],
                          spec["key"]))
        self.assertEqual(S.kind_for(locator), expect.get("hint_kind", "psx"))
        self.assertEqual(S.scope_for(locator), expect.get("hint_scope", "private"))

    def _run_pair(self, pair, expect):
        mine, theirs = S.validate_stamp(pair[0]), S.validate_stamp(pair[1])
        found = sorted(d.path for d in S.compare_stamps(mine, theirs))
        self.assertEqual(found, sorted(expect["disagreements"]))
        self.assertEqual(S.stamps_agree(mine, theirs), expect["agree"])
        # …and the comparison is SYMMETRIC: which one you call «mine» is an
        # accident of who is reading, and a rule that depended on it would give
        # two different answers to one question.
        back = sorted(d.path for d in S.compare_stamps(theirs, mine))
        self.assertEqual(found, back, "compare_stamps is not symmetric")

    def _run_walk(self, case, expect):
        world = {k: S.validate_stamp(v) for k, v in case["resolvable"].items()}
        walk = S.walk_chain(S.validate_stamp(case["stamp"]), world.get)
        self.assertEqual(len(walk.rungs), expect["walk_rungs"])
        self.assertEqual(len(walk.reached), expect["walk_reached"])
        self.assertEqual(len(walk.unreached), expect["walk_unreached"])
        self.assertEqual(walk.truncated, expect["walk_truncated"])
        if "walk_why" in expect:
            self.assertEqual(sorted({r.why for r in walk.unreached}),
                             sorted(expect["walk_why"]))


# ═════════════════════════════════════════════════════════════════════════════
# THE WALK — the piece that decides whether this library serves everybody
# ═════════════════════════════════════════════════════════════════════════════

#: The functions that do the walking. Named here so the structural test measures
#: WHAT WALKS rather than a file boundary — which, in a single-file library, is
#: the only honest way to ask the question, and is also more precise.
WALKING = (S.walk_chain, S.Rung.as_dict, S.Walk.as_dict)

#: What must not appear in them. Each one is a way of knowing where things are,
#: which is the caller's knowledge and never the library's.
FORBIDDEN_IN_THE_WALK = ("open(", "requests", "urllib", "boto3", "pathlib",
                         "os.path", "Path(", "/Users/", "C:\\\\", "http://",
                         "https://", "s3://")


def _offences(source, forbidden=FORBIDDEN_IN_THE_WALK):
    return [token for token in forbidden if token in source]


class TheWalkKnowsNothingAboutWhereThingsAre(unittest.TestCase):

    def test_the_walking_functions_touch_no_world(self):
        for fn in WALKING:
            with self.subTest(fn=getattr(fn, "__qualname__", fn)):
                self.assertEqual(_offences(inspect.getsource(fn)), [],
                                 "the walk must not know where things live")

    def test_THE_COUNTEREXAMPLE_a_walk_that_opened_a_file_is_caught(self):
        # Written the way somebody would write it in good faith in six months:
        # «I have the digest, the stamps are on disk, I will just go and read
        # it». That one line turns a library anybody can embed into ours.
        bad = (
            "def walk_chain(stamp, resolve):\n"
            "    for parent in stamp.get('from') or []:\n"
            "        with open('/Users/me/stamps/' + parent['digest']) as fh:\n"
            "            parent_stamp = json.load(fh)\n")
        self.assertTrue(_offences(bad), "the guard must see this")
        self.assertIn("open(", _offences(bad))

    def test_the_resolver_is_asked_only_for_things_that_have_bytes(self):
        asked = []

        def resolve(digest):
            asked.append(digest)
            return None

        stamp = {"stamp": 1, "self": {"resource_id": "r", "digest": SHA("1")},
                 "from": [{"resource_id": "acq:1", "kind": "acquisition"},
                          {"resource_id": "res:2", "digest": SHA("2")}]}
        walk = S.walk_chain(stamp, resolve)
        # An acquisition has no bytes to hash: asking a resolver for it would
        # make every caller invent an answer to a question that has none.
        self.assertEqual(asked, [SHA("2")])
        self.assertEqual(sorted(r.why for r in walk.unreached),
                         sorted([S.NOT_A_FILE, S.NOT_RESOLVED]))

    def test_a_resolver_may_answer_with_bytes(self):
        # The reason: a caller holding bytes from an object store must not have
        # to write them to a temporary file to use this library.
        parent = {"stamp": 1, "self": {"resource_id": "p", "digest": SHA("2")},
                  "from": []}
        raw = json.dumps(parent).encode("utf-8")
        stamp = {"stamp": 1, "self": {"resource_id": "r", "digest": SHA("1")},
                 "from": [{"resource_id": "p", "digest": SHA("2")}]}
        walk = S.walk_chain(stamp, lambda d: raw)
        self.assertEqual(len(walk.reached), 1)
        self.assertEqual(walk.reached[0].stamp["self"]["resource_id"], "p")

    def test_something_that_is_not_a_stamp_is_a_rung_and_not_a_crash(self):
        stamp = {"stamp": 1, "self": {"resource_id": "r", "digest": SHA("1")},
                 "from": [{"resource_id": "p", "digest": SHA("2")}]}
        walk = S.walk_chain(stamp, lambda d: {"header": {"format": "em.json"}})
        self.assertEqual(len(walk.unreached), 1)
        self.assertEqual(walk.unreached[0].why, S.UNREADABLE)
        self.assertIn("em.json", walk.unreached[0].detail)

    def test_a_defect_in_the_resolver_reaches_whoever_wrote_it(self):
        # The counterexample to a `except Exception` that would have swallowed
        # it: a typo in somebody's resolver must NOT come back looking like a
        # missing parent, or they will go looking for the file for an hour.
        def broken(digest):
            raise AttributeError("'NoneType' object has no attribute 'get'")

        stamp = {"stamp": 1, "self": {"resource_id": "r", "digest": SHA("1")},
                 "from": [{"resource_id": "p", "digest": SHA("2")}]}
        with self.assertRaises(AttributeError):
            S.walk_chain(stamp, broken)

    def test_the_ceiling_says_truncated_instead_of_pretending_to_have_finished(self):
        # A LONG chain, not a circular one: every parent is a NEW digest, so
        # what stops the walk is the ceiling and not the cycle detector. The
        # first version of this test read the wrong end of the hex and generated
        # the same digest twice — it measured the cycle guard while claiming to
        # measure the ceiling, and passed for the wrong reason.
        link = lambda n: "sha256:%064x" % n          # noqa: E731

        def resolve(digest):
            n = int(digest.split(":")[1], 16)
            return {"stamp": 1,
                    "self": {"resource_id": f"r{n}", "digest": digest},
                    "from": [{"resource_id": f"r{n + 1}", "digest": link(n + 1)}]}

        start = {"stamp": 1, "self": {"resource_id": "r0", "digest": link(0)},
                 "from": [{"resource_id": "r1", "digest": link(1)}]}
        walk = S.walk_chain(start, resolve, max_rungs=8)
        self.assertTrue(walk.truncated)
        self.assertEqual(walk.rungs[-1].why, S.CEILING)
        self.assertLessEqual(len(walk.rungs), 8)


# ═════════════════════════════════════════════════════════════════════════════
# ZERO DEPENDENCIES — measured, not asserted
# ═════════════════════════════════════════════════════════════════════════════

#: `sys.stdlib_module_names` arrived in Python 3.10, and below it there is no
#: exact substitute: a hand-written list of standard modules would be wrong the
#: day Python moves one, which is the opposite of what this check is for.
#:
#: So the two tests below SKIP under 3.9 — and that is only defensible because
#: THE RELEASE DOES NOT RIDE ON A RUN WHERE THEY SKIPPED: `publish.yml` gates on
#: a job that runs them on a modern interpreter. A skip without that gate would
#: turn the loudest guard in this package into a silent one, which is worse than
#: the failure it replaces.
#:
#: They carry the SAME guard, on purpose. The failure that produced this comment
#: was precisely the two of them disagreeing — the check refusing to run, its
#: counterexample running on and crashing. A counterexample that can outlive the
#: assertion it defends is not defending anything.
_EXACT_STDLIB = hasattr(sys, "stdlib_module_names")
_NEEDS_310 = "needs Python 3.10+ (sys.stdlib_module_names) to be exact"


def _toplevel_imports(source):
    """The top-level module names a piece of Python imports, read from its AST.

    Shared by the check and its counterexample so the two cannot drift: a
    counterexample that scans differently from the assertion proves nothing
    about the assertion.
    """
    import ast

    modules = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            modules.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            modules.add((node.module or "").split(".")[0])
    modules.discard("")
    return modules


class ZeroDependencies(unittest.TestCase):

    @unittest.skipUnless(_EXACT_STDLIB, _NEEDS_310)
    def test_every_import_is_standard_library(self):
        # `sys.stdlib_module_names` is the interpreter's own answer, which beats
        # any list written here.
        modules = _toplevel_imports(
            (HERE / "dtcstamp.py").read_text(encoding="utf-8"))
        outside = sorted(m for m in modules if m not in sys.stdlib_module_names)
        self.assertEqual(outside, [], f"third-party imports: {outside}")

    @unittest.skipUnless(_EXACT_STDLIB, _NEEDS_310)
    def test_THE_COUNTEREXAMPLE_a_third_party_import_would_be_seen(self):
        bad = "import json\nimport numpy as np\nfrom pandas import DataFrame\n"
        outside = sorted(m for m in _toplevel_imports(bad)
                         if m not in sys.stdlib_module_names)
        self.assertEqual(outside, ["numpy", "pandas"])

    def test_it_is_ONE_file(self):
        # The vendoring promise is «copy a file», and it is only true while there
        # is one. A second module beside this one would break it silently — the
        # tests would still pass, and the Blender add-on would fail at import.
        siblings = [p.name for p in HERE.glob("*.py")
                    if not p.name.startswith("test_")]
        self.assertEqual(siblings, ["dtcstamp.py"])


# ═════════════════════════════════════════════════════════════════════════════
# VALUES, NEVER TYPES — the constraint the whole extraction rests on
# ═════════════════════════════════════════════════════════════════════════════
#
# A stamp carries coordinates as numbers plus an EPSG code, and a device as an id
# plus a label. It does NOT carry «a GeoPositionNode» or «a DTCDeviceNode»,
# because somebody writing a Metashape script has no reason to learn what those
# are in order to read where a camera was standing. Turning values into typed
# nodes is s3Dgraphy's job, on the side that has a graph.
#
# The moment this module learns one class name, the promise «copy one file» quietly
# becomes «copy one file and also understand our data model».

#: The shapes of an s3Dgraphy type. A class name always ends in `Node`; a
#: `node_type` string is what travels in an em.json. Both are checked, because a
#: leak can take either form and they are written differently.
#:
#: THE SECOND LIST IS DELIBERATELY SHORT, and the first version was wrong: it
#: included `license`, `author`, `resource` and `embargo`, and immediately
#: flagged `declared.get("license")` — which is a FIELD OF THIS FORMAT and has
#: every right to be here. Those four words are s3Dgraphy node types only in
#: s3Dgraphy's context; here they are the format's own vocabulary. A guard that
#: flags something legitimate is a guard somebody disables, and then it catches
#: nothing at all. What is left cannot be anything but a node type.
S3DGRAPHY_TYPE_SHAPES = (
    r"\b[A-Za-z_]+Node\b",                 # ResourceNode, DTCDeviceNode, …
    r"[\"']\s*(?:dtc_device|dtc_process|dtc_acquisition|geo_position)\s*[\"']",
)


def _type_leaks(source):
    import re
    out = []
    for shape in S3DGRAPHY_TYPE_SHAPES:
        out.extend(m.group(0) for m in re.finditer(shape, source))
    return out


class ValuesNeverTypes(unittest.TestCase):

    def test_no_s3dgraphy_type_name_appears_in_this_module(self):
        source = (HERE / "dtcstamp.py").read_text(encoding="utf-8")
        self.assertEqual(_type_leaks(source), [],
                         "a type name of s3Dgraphy reached the format library")

    def test_and_no_s3dgraphy_is_imported_either(self):
        import ast
        source = (HERE / "dtcstamp.py").read_text(encoding="utf-8")
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    self.assertNotIn("s3dgraphy", alias.name.lower())
            elif isinstance(node, ast.ImportFrom):
                self.assertNotIn("s3dgraphy", (node.module or "").lower())

    def test_THE_COUNTEREXAMPLE_a_leaked_type_is_caught(self):
        # Written the way it would actually happen: somebody adds a convenience
        # that «just returns the node», and the library has learned a data model.
        bad = (
            "def location_node(stamp):\n"
            "    place = stamp['how']['acquisition']['location']\n"
            "    return GeoPositionNode(place['crs'], place['lat'])\n")
        leaks = _type_leaks(bad)
        self.assertTrue(leaks, "the guard must see this")
        self.assertIn("GeoPositionNode", leaks)

    def test_THE_COUNTEREXAMPLE_a_leaked_node_type_STRING_is_caught_too(self):
        # The subtler half: no class name, just the string an em.json carries.
        bad = 'def is_device(entry):\n    return entry.get("type") == "dtc_device"\n'
        self.assertTrue(_type_leaks(bad), "the guard must see the string form")

    def test_a_device_reads_as_an_identity_with_no_type_anywhere(self):
        # …and the positive side: what the format DOES carry is usable without
        # knowing anything about a graph.
        stamp = {"stamp": 1, "self": {"resource_id": "r", "digest": SHA("1")},
                 "from": [],
                 "how": {"process_id": "p", "dtc_kind": "photogrammetry",
                         "acquisition": {
                             "device": {"id": "dev:3004afbb", "label": "Nikon D850",
                                        "make": "Nikon", "model": "D850",
                                        "distinguishes": "serial"},
                             "location": {"lat": 43.1102, "lon": 11.8423,
                                          "crs": "EPSG:4326", "source": "exif"}}}}
        S.validate_stamp(stamp)
        acquisition = stamp["how"]["acquisition"]
        self.assertEqual(acquisition["device"]["id"], "dev:3004afbb")
        self.assertEqual(acquisition["location"]["crs"], "EPSG:4326")
        # a reader can tell a measured position from a stated one, which is the
        # same discipline identity_strength applies to a digest
        self.assertIn(acquisition["location"]["source"], ("exif", "stated"))
        # …and the honest half of the device id travels with it
        self.assertIn(acquisition["device"]["distinguishes"],
                      ("serial", "make+model"))


# ═════════════════════════════════════════════════════════════════════════════
# THE NAME IS CONFINED — renaming this package must cost a `sed`
# ═════════════════════════════════════════════════════════════════════════════

class TheNameIsProvisional(unittest.TestCase):

    def test_the_name_is_never_inside_the_format(self):
        # If the package name ends up in a field of the format, or in a
        # predicate, renaming it invalidates every file anybody has written. It
        # is a design error, not a rename problem.
        for path in sorted(CORPUS.glob("*.json")):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn(S.PACKAGE, text,
                             f"{path.name} carries the package name")

    def test_the_name_appears_in_one_place_in_the_code(self):
        source = (HERE / "dtcstamp.py").read_text(encoding="utf-8")
        # …the `PACKAGE` assignment. The module's own docstring and file name
        # carry it too, and those are the file's identity rather than its
        # content.
        lines = [n for n, line in enumerate(source.splitlines(), 1)
                 if S.PACKAGE in line and not line.lstrip().startswith("#")]
        self.assertEqual(len(lines), 1, f"the name is on lines {lines}")


# ═════════════════════════════════════════════════════════════════════════════
# THE FORMAT — the sentences that are easy to write identically and mean opposites
# ═════════════════════════════════════════════════════════════════════════════

class TheFormat(unittest.TestCase):

    def test_an_absent_identity_is_None_and_not_a_word(self):
        # Returning a word where there is no string would make a reader believe
        # something had been said.
        self.assertIsNone(S.identity_strength(None))
        self.assertIsNone(S.identity_strength(""))
        self.assertIsNone(S.identity_strength("   "))

    def test_a_verifiable_one_is_also_comparable(self):
        self.assertTrue(S.is_comparable(SHA("a")))
        self.assertTrue(S.is_comparable("emstruct1:" + "9" * 40))
        self.assertFalse(S.is_comparable("6" * 64))
        self.assertFalse(S.is_comparable(None))

    def test_a_malformed_identity_is_read_whole_or_not_at_all(self):
        # `:abc` and `abc:` are not a scheme and a value: reading half of one
        # would be worse than not reading it.
        self.assertEqual(S.split_identity(":abc"), (None, ":abc"))
        self.assertEqual(S.split_identity("abc:"), (None, "abc:"))

    def test_the_notes_do_not_leave_but_everything_else_does(self):
        stamp = {"stamp": 1, "self": {"resource_id": "r"}, "_notes": ["a doubt"],
                 "x_unknown": "keep me"}
        clean = S.clean_stamp(stamp)
        self.assertNotIn("_notes", clean)
        self.assertIn("x_unknown", clean)

    def test_a_label_is_never_identity(self):
        # substance() reads parents by id and digest; two different labels for
        # the same parent are the same parent.
        a = {"resource_id": "p", "digest": SHA("2"), "label": "la nuvola"}
        b = {"resource_id": "p", "digest": SHA("2"), "label": "point cloud"}
        self.assertEqual(S._parent_key(a), S._parent_key(b))

    def test_the_two_meanings_of_an_empty_from(self):
        signed = {"stamp": 1, "self": {"resource_id": "r"}, "from": [],
                  "how": {"dtc_kind": "photo"}}
        unsigned = {"stamp": 1, "self": {"resource_id": "r"}, "from": []}
        self.assertTrue(S.declared_origin(signed))
        self.assertFalse(S.declared_origin(unsigned))
        # …and a step WITH parents is not an origin however it is signed
        withparents = dict(signed, **{"from": [{"resource_id": "p"}]})
        self.assertFalse(S.declared_origin(withparents))


class TitleAndDescription(unittest.TestCase):
    """`self.label` and `self.description` (04-10-2026): optional, a courtesy."""

    def test_a_long_description_is_kept_whole_and_never_refused(self):
        text = "x" * (S.DESCRIPTION_HINT_CHARS * 3)
        stamp = {"stamp": 1, "self": {"resource_id": "r", "description": text}}
        S.validate_stamp(stamp)
        self.assertEqual(S.stamp_description(stamp), text)

    def test_what_is_not_text_is_not_a_title(self):
        stamp = {"stamp": 1, "self": {"resource_id": "r", "label": 42,
                                      "description": ["a"]}}
        S.validate_stamp(stamp)          # still a stamp
        self.assertIsNone(S.stamp_title(stamp))
        self.assertIsNone(S.stamp_description(stamp))
        self.assertNotIn("title", S.receipt(stamp))

    def test_a_label_repeating_a_prefixed_id_is_no_title(self):
        stamp = {"stamp": 1, "self": {"resource_id": "https://x.org/res/abc",
                                      "label": "abc"}}
        self.assertIsNone(S.stamp_title(stamp))

    def test_the_receipt_refuses_what_is_not_a_stamp(self):
        with self.assertRaises(S.BadStamp):
            S.receipt({"self": {"resource_id": "r"}})

    def test_the_title_is_not_substance(self):
        a = {"stamp": 1, "self": {"resource_id": "r", "label": "uno",
                                  "description": "a"}}
        b = {"stamp": 1, "self": {"resource_id": "r", "label": "due"}}
        self.assertEqual(S.substance(a), S.substance(b))
        self.assertTrue(S.stamps_agree(a, b))


# ═════════════════════════════════════════════════════════════════════════════
# HINTS — a private hint never leaves
# ═════════════════════════════════════════════════════════════════════════════

PERSON = "mrossi"
CLIENT = "Fondazione Ansaldo"
LOCAL_PATH = f"/Users/{PERSON}/lavori/{CLIENT}/2015/nuvola.ply"


class HintsThatDoNotTravel(unittest.TestCase):

    def _register(self):
        hints = S.new_hints(SHA("a"))
        S.note_seen(hints, "s3://em-assets/res_91c2/nuvola.ply",
                    when="2026-09-14T09:12:00Z")
        S.note_seen(hints, LOCAL_PATH, machine="mbp-ed",
                    when="2026-09-14T18:40:11Z")
        return hints

    def test_none_of_the_three_strings_is_in_what_leaves(self):
        # ON THE WHOLE TEXT and not on the keys: a path can hide in a field
        # nobody thought to filter, and an assertion about keys would not see it.
        text = json.dumps(S.for_export(self._register()))
        self.assertNotIn(LOCAL_PATH, text)
        self.assertNotIn(PERSON, text)
        self.assertNotIn(CLIENT, text)
        self.assertNotIn("mbp-ed", text)
        self.assertIn("s3://em-assets/res_91c2/nuvola.ply", text)

    def test_the_home_register_keeps_them_all(self):
        # for_export returns a COPY: the local register is not emptied by the
        # act of exporting it.
        hints = self._register()
        S.for_export(hints)
        self.assertEqual(S.private_locators(hints), [LOCAL_PATH])

    def test_the_door_outwards_has_no_switch(self):
        import inspect as _i
        params = list(_i.signature(S.for_export).parameters)
        self.assertEqual(params, ["hints"],
                         "a door that can be opened halfway gets opened halfway")

    def test_the_doubt_always_falls_towards_private(self):
        self.assertEqual(S.scope_for("s3://bucket/key"), "public")
        self.assertEqual(S.scope_for("https://em.example/asset/x"), "public")
        self.assertEqual(S.scope_for("/Users/x/y"), "private")
        self.assertEqual(S.scope_for("blend://Scene/US01"), "private")
        self.assertEqual(S.scope_for("something-I-do-not-recognise"), "private")

    def test_the_same_place_seen_twice_is_one_hint(self):
        hints = S.new_hints(SHA("a"))
        S.note_seen(hints, "/tmp/x.ply", when="2026-01-01T00:00:00Z")
        S.note_seen(hints, "/tmp/x.ply", when="2026-06-01T00:00:00Z")
        self.assertEqual(len(hints["seen"]), 1)
        self.assertEqual(hints["seen"][0]["when"], "2026-06-01T00:00:00Z")
        # …but the same path on ANOTHER machine is another hint
        S.note_seen(hints, "/tmp/x.ply", machine="altro",
                    when="2026-06-01T00:00:00Z")
        self.assertEqual(len(hints["seen"]), 2)

    def test_a_scope_that_is_not_one_of_the_two_is_refused(self):
        hints = S.new_hints(SHA("a"))
        with self.assertRaises(ValueError):
            S.note_seen(hints, "/tmp/x", scope="maybe")


# ═════════════════════════════════════════════════════════════════════════════
# THE RESOURCE OF MORE THAN ONE FILE (21-10-2026)
# ═════════════════════════════════════════════════════════════════════════════

def _obj_set(root, name="m", textures=("a.png",), mtl_extra=""):
    root = pathlib.Path(root)
    (root / "textures").mkdir(parents=True, exist_ok=True)
    (root / f"{name}.obj").write_text(f"mtllib {name}.mtl\nv 0 0 0\n")
    lines = [f"newmtl {name}"] + [f"map_Kd textures/{t}" for t in textures]
    (root / f"{name}.mtl").write_text("\n".join(lines) + "\n" + mtl_extra)
    for t in textures:
        (root / "textures" / t).write_bytes(t.encode() * 3)
    return str(root / f"{name}.obj")


class TheCanonicalList(unittest.TestCase):

    def test_order_and_spelling_do_not_change_the_digest(self):
        a = [{"role": "entry_point", "path": "x.obj", "digest": SHA("a")},
             {"path": "t/y.png", "digest": SHA("b")}]
        b = [{"path": "t\\y.png", "digest": SHA("B")},
             {"role": "entry_point", "path": "/x.obj", "digest": SHA("a")}]
        self.assertEqual(S.members_digest(a), S.members_digest(b))

    def test_THE_COUNTEREXAMPLE_a_role_changes_it(self):
        a = [{"role": "entry_point", "path": "x.obj", "digest": SHA("a")}]
        b = [{"role": "member", "path": "x.obj", "digest": SHA("a")}]
        self.assertNotEqual(S.members_digest(a), S.members_digest(b))

    def test_nfc(self):
        composed = [{"path": "caf\u00e9.png", "digest": SHA("a")}]
        decomposed = [{"path": "cafe\u0301.png", "digest": SHA("a")}]
        self.assertEqual(S.members_canonical(composed),
                         S.members_canonical(decomposed))

    def test_what_has_no_canonical_form_is_refused(self):
        for bad in ([{"path": "a/../b", "digest": SHA("a")}],
                    [{"path": "a\x00b", "digest": SHA("a")}],
                    [{"path": "", "digest": SHA("a")}],
                    [{"path": "a", "digest": "md5:" + "a" * 32}],
                    [{"path": "a", "digest": "a" * 64}],
                    [{"path": "a", "digest": SHA("a")}, {"path": "/a", "digest": SHA("b")}],
                    [{"role": "entry_point", "path": "a", "digest": SHA("a")},
                     {"role": "entry_point", "path": "b", "digest": SHA("b")}],
                    [{"role": "door", "path": "a", "digest": SHA("a")}]):
            with self.subTest(bad=bad), self.assertRaises(S.BadMembers):
                S.members_digest(bad)

    def test_a_space_is_part_of_the_name_a_control_character_is_refused(self):
        # NUL separates, so a space never splits a field; control characters
        # (a tab, a newline) are refused rather than written
        one = [{"path": "stone normal.png", "digest": SHA("a")}]
        self.assertIn(b"\x00stone normal.png\x00", S.members_canonical(one))
        with self.assertRaises(S.BadMembers):
            S.members_canonical([{"path": "a\tb", "digest": SHA("a")}])


class FileSets(unittest.TestCase):

    def test_members_are_found_not_the_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            door = _obj_set(tmp, "m", ("a.png", "b.png"))
            _obj_set(tmp, "other", ("c.png",))
            found = S.follow_references(door)
            self.assertEqual([m["path"] for m in found["members"]],
                             ["m.mtl", "m.obj", "textures/a.png", "textures/b.png"])
            self.assertEqual(found["members"][1]["role"], "entry_point")

    def test_outside_and_absolute_are_warnings_not_members(self):
        with tempfile.TemporaryDirectory() as tmp:
            sub = pathlib.Path(tmp, "lod")
            door = _obj_set(sub, mtl_extra="map_Ks ../escape.png\nmap_Ns /abs/x.png\n")
            pathlib.Path(tmp, "escape.png").write_bytes(b"x")
            found = S.follow_references(door)
            self.assertEqual(len(found["outside"]), 2)
            self.assertEqual(len(found["warnings"]), 2)
            self.assertNotIn("../escape.png", [m["path"] for m in found["members"]])

    def test_gltf_buffers_and_images_in_subfolders(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "bin").mkdir(); (root / "img").mkdir()
            (root / "bin" / "m.bin").write_bytes(b"\0" * 8)
            (root / "img" / "base color.png").write_bytes(b"png")
            (root / "m.gltf").write_text(json.dumps({
                "asset": {"version": "2.0"},
                "buffers": [{"uri": "bin/m.bin"}, {"uri": "data:application/octet-stream;base64,AA=="}],
                "images": [{"uri": "img/base%20color.png"}]}))
            found = S.follow_references(str(root / "m.gltf"))
            self.assertEqual([m["path"] for m in found["members"]],
                             ["bin/m.bin", "img/base color.png", "m.gltf"])

    def test_glb_json_chunk(self):
        import struct
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "t.png").write_bytes(b"png")
            doc = json.dumps({"asset": {"version": "2.0"}, "buffers": [{"byteLength": 4}],
                              "images": [{"uri": "t.png"}]}).encode()
            doc += b" " * (-len(doc) % 4)
            body = struct.pack("<I4s", len(doc), b"JSON") + doc
            (root / "m.glb").write_bytes(struct.pack("<4sII", b"glTF", 2, 12 + len(body)) + body)
            found = S.follow_references(str(root / "m.glb"))
            self.assertEqual([m["path"] for m in found["members"]], ["m.glb", "t.png"])

    def test_verification_missing_changed_extra(self):
        with tempfile.TemporaryDirectory() as tmp:
            door = _obj_set(tmp, "m", ("a.png",))
            stamp = S.new_file_set_stamp(door, "res:m")
            self.assertTrue(S.verify_members(stamp, door)["ok"])
            tex = pathlib.Path(tmp, "textures", "a.png")
            tex.write_bytes(b"changed")
            self.assertEqual(S.verify_members(stamp, door)["changed"], ["textures/a.png"])
            mtl = pathlib.Path(tmp, "m.mtl")
            mtl.write_text(mtl.read_text() + "map_Ks textures/new.png\n")
            pathlib.Path(tmp, "textures", "new.png").write_bytes(b"n")
            report = S.verify_members(stamp, door)
            self.assertEqual(report["extra"], ["textures/new.png"])
            self.assertIn("m.mtl", report["changed"])
            mtl.unlink()
            self.assertEqual(S.verify_members(stamp, door)["missing"], ["m.mtl"])

    def test_a_hand_edited_list_is_seen(self):
        with tempfile.TemporaryDirectory() as tmp:
            door = _obj_set(tmp)
            stamp = S.new_file_set_stamp(door, "res:m")
            stamp["self"]["members"] = stamp["self"]["members"][:-1]
            report = S.verify_members(stamp, door)
            self.assertFalse(report["list_consistent"])
            self.assertFalse(report["ok"])

    def test_a_shared_texture_is_allowed_and_breaks_both(self):
        with tempfile.TemporaryDirectory() as tmp:
            one = _obj_set(tmp, "one", ("shared.png",))
            two = _obj_set(tmp, "two", ("shared.png",))
            s1, s2 = S.new_file_set_stamp(one, "res:1"), S.new_file_set_stamp(two, "res:2")
            self.assertTrue(S.verify_members(s1, one)["ok"])
            self.assertTrue(S.verify_members(s2, two)["ok"])
            self.assertEqual(S.unclaimed_files(tmp, [s1, s2]), [])
            pathlib.Path(tmp, "textures", "shared.png").write_bytes(b"x")
            self.assertFalse(S.verify_members(s1, one)["ok"])
            self.assertFalse(S.verify_members(s2, two)["ok"])

    def test_the_ceiling(self):
        with tempfile.TemporaryDirectory() as tmp:
            many = tuple(f"t{i:03d}.png" for i in range(S.MAX_FILE_SET_MEMBERS))
            door = _obj_set(tmp, "m", many)
            with self.assertRaises(S.BadMembers) as caught:
                S.new_file_set_stamp(door, "res:m")
            self.assertIn("content_digest", str(caught.exception))

    def test_the_sidecar_is_beside_the_door_and_notes_do_not_leave(self):
        with tempfile.TemporaryDirectory() as tmp:
            door = _obj_set(tmp, "OB_PODIO_LOD1")
            self.assertTrue(S.file_set_stamp_path(door).endswith("OB_PODIO_LOD1.obj.stamp.json"))
            stamp = S.new_file_set_stamp(door, "res:m")
            S.write_stamp(stamp, S.file_set_stamp_path(door))
            back = S.read_stamp(S.file_set_stamp_path(door))
            self.assertNotIn("_followed", back)
            self.assertEqual(back["self"]["digest_covers"], "members")
            self.assertEqual(S.identity_strength(back["self"]["digest"]), "verifiable")


def _small_tree(root):
    root = pathlib.Path(root)
    (root / "Data").mkdir(parents=True)
    (root / "tileset.json").write_text('{"asset": {"version": "1.0"}}')
    (root / "Data" / "città.b3dm").write_bytes(b"b3dm" + b"\1" * 50)
    (root / ".DS_Store").write_bytes(b"junk")
    return str(root)


def _zip(src, out, *, compress, date=(1980, 1, 1, 0, 0, 0)):
    import hashlib, struct, zipfile, os
    names = sorted(p.relative_to(src).as_posix() for p in pathlib.Path(src).rglob("*")
                   if p.is_file() and p.name not in S.SKIP_NAMES)
    records = []
    with zipfile.ZipFile(out, "w") as zf:
        for n in names:
            zi = zipfile.ZipInfo(n, date_time=date)
            zi.compress_type = zipfile.ZIP_DEFLATED if compress else zipfile.ZIP_STORED
            zi.create_system = 3
            zi.external_attr = 0o100644 << 16
            zf.writestr(zi, pathlib.Path(src, n).read_bytes())
            records.append((hashlib.md5(n.encode()).digest(), zi.header_offset))
        records.sort(key=lambda r: struct.unpack("<QQ", r[0]))
        index = b"".join(m + struct.pack("<Q", o) for m, o in records)
        zi = zipfile.ZipInfo(S.INDEX_NAME_3TZ, date_time=date)
        zi.create_system = 3
        zi.external_attr = 0o100644 << 16
        zf.writestr(zi, index)
    return out


class Trees(unittest.TestCase):

    def test_folder_and_archive_share_the_content_digest_whatever_the_packing(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = _small_tree(pathlib.Path(tmp, "src"))
            stored = _zip(src, str(pathlib.Path(tmp, "a.3tz")), compress=False)
            deflated = _zip(src, str(pathlib.Path(tmp, "b.3tz")), compress=True,
                            date=(2026, 9, 30, 20, 5, 54))
            digest = S.content_digest(src)
            self.assertEqual(S.content_digest(stored), digest)
            self.assertEqual(S.content_digest(deflated), digest)
            self.assertNotEqual(S.file_digest(stored), S.file_digest(deflated))
            self.assertTrue(S.is_canonical_3tz(stored)["canonical"],
                            S.is_canonical_3tz(stored)["reasons"])
            self.assertFalse(S.is_canonical_3tz(deflated)["canonical"])
            # the UTF-8 flag on the non-ASCII name is part of the profile
            self.assertEqual(S.tree_members(src)[0]["path"], "Data/città.b3dm")

    def test_a_name_in_nfd_is_not_canonical_and_the_content_does_not_care(self):
        # macOS hands «città» over as «citta» + U+0300: a writer that does not
        # normalise packs another name, and so another sha256.
        import hashlib, struct, unicodedata, zipfile
        with tempfile.TemporaryDirectory() as tmp:
            src = _small_tree(pathlib.Path(tmp, "src"))
            nfc = _zip(src, str(pathlib.Path(tmp, "nfc.3tz")), compress=False)
            nfd = str(pathlib.Path(tmp, "nfd.3tz"))
            with zipfile.ZipFile(nfc) as a:
                infos = [(i, a.read(i)) for i in a.infolist()]
            records = []
            with zipfile.ZipFile(nfd, "w") as b:
                for info, data in infos:
                    if info.filename == S.INDEX_NAME_3TZ:
                        records.sort(key=lambda r: struct.unpack("<QQ", r[0]))
                        data = b"".join(m + struct.pack("<Q", o) for m, o in records)
                    else:
                        info.filename = unicodedata.normalize("NFD", info.filename)
                        info.orig_filename = info.filename
                    b.writestr(info, data)
                    if info.filename != S.INDEX_NAME_3TZ:
                        records.append((hashlib.md5(info.filename.encode()).digest(),
                                        info.header_offset))
            verdict = S.is_canonical_3tz(nfd)
            self.assertFalse(verdict["canonical"])
            self.assertEqual(sorted(k for k, v in verdict.items() if v is False),
                             ["canonical", "names_nfc"])
            self.assertTrue(any("NFC" in r for r in verdict["reasons"]))
            self.assertTrue(S.is_canonical_3tz(nfc)["canonical"])
            self.assertNotEqual(S.file_digest(nfd), S.file_digest(nfc))
            self.assertEqual(S.content_digest(nfd), S.content_digest(nfc))

    def test_a_record_the_index_misses_is_not_a_3tz(self):
        import zipfile
        with tempfile.TemporaryDirectory() as tmp:
            src = _small_tree(pathlib.Path(tmp, "src"))
            arc = _zip(src, str(pathlib.Path(tmp, "a.3tz")), compress=False)
            broken = str(pathlib.Path(tmp, "broken.3tz"))
            with zipfile.ZipFile(arc) as a, zipfile.ZipFile(broken, "w") as b:
                for info in a.infolist():
                    if info.filename == S.INDEX_NAME_3TZ:
                        b.writestr(zipfile.ZipInfo("extra.b3dm"), b"x")
                    b.writestr(info, a.read(info))
            with self.assertRaises(ValueError):
                S.content_digest(broken)

    def test_two_forms_of_one_thing(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = _small_tree(pathlib.Path(tmp, "src"))
            arc = _zip(src, str(pathlib.Path(tmp, "a.3tz")), compress=False)
            folder = S.new_tree_stamp(src, "res:t_link", computed_by="producer")
            archive = S.new_tree_stamp(arc, "res:t_archive", computed_by="producer")
            self.assertEqual(folder["self"]["packaging"], "directory")
            self.assertEqual(folder["self"]["digest_covers"], "members")
            self.assertEqual(archive["self"]["packaging"], "archive")
            self.assertEqual(archive["self"]["digest_covers"], "artifact")
            self.assertEqual(archive["self"]["content_digest"]["files"], 2)
            self.assertTrue(S.same_content(folder, archive))
            self.assertTrue(S.verify_tree(folder, src)["ok"])
            self.assertTrue(S.verify_tree(archive, arc)["ok"])
            pathlib.Path(src, "tileset.json").write_text("{}")
            self.assertFalse(S.verify_tree(folder, src)["ok"])

    def test_THE_COUNTEREXAMPLE_other_content_is_not_the_same(self):
        a = {"stamp": 1, "self": {"resource_id": "a", "content_digest": {"digest": SHA("1")}}}
        b = {"stamp": 1, "self": {"resource_id": "b", "content_digest": {"digest": SHA("2")}}}
        self.assertFalse(S.same_content(a, b))
        self.assertEqual([d.path for d in S.compare_stamps(a, b)],
                         ["self.content_digest"])


class Datablocks(unittest.TestCase):

    def test_no_digest_of_bytes_and_no_path_in_the_stamp(self):
        stamp, hints = S.new_datablock_stamp("res:ob", "/Users/x/a.blend", "OB")
        self.assertNotIn("digest", stamp["self"])
        self.assertIsNone(S.identity_strength(stamp["self"].get("digest")))
        self.assertNotIn("a.blend", json.dumps(stamp))
        self.assertEqual(hints["seen"][0]["scope"], "private")
        self.assertEqual(S.for_export(hints)["seen"], [])

    def test_a_byte_digest_is_refused_for_a_datablock(self):
        with self.assertRaises(ValueError):
            S.new_datablock_stamp("res:ob", "a.blend", "OB", structural_digest=SHA("1"))


# ═════════════════════════════════════════════════════════════════════════════
# THE STEP BORN IN AN AUTHORING TOOL (01-11-2026)
# ═════════════════════════════════════════════════════════════════════════════

BLEND_LOCATOR = "blend:///Users/mrossi/lavori/scavo.blend#Object/TILE"


class TheParentsState(unittest.TestCase):

    def test_written_and_read_back(self):
        entry = S.with_parent_state({"resource_id": "blend:1"}, fingerprint="struct:f=6",
                                    sha256=SHA("f"), saved=True)
        self.assertEqual(S.parent_state(entry),
                         {"fingerprint": "struct:f=6", "sha256": SHA("f"), "saved": True})

    def test_THE_COUNTEREXAMPLE_a_container_digest_that_is_not_one(self):
        with self.assertRaises(ValueError):
            S.with_parent_state({}, sha256="md5:abc")
        with self.assertRaises(ValueError):
            S.with_parent_state({}, saved="yes")

    def test_a_wrong_shape_is_left_out_of_the_reading_not_refused(self):
        entry = {"resource_id": "blend:1",
                 "state": {"sha256": "nope", "saved": "no", "fingerprint": "struct:f=1"}}
        self.assertEqual(S.parent_state(entry), {"fingerprint": "struct:f=1"})
        S.validate_stamp({"stamp": 1, "self": {"resource_id": "r"}, "from": [entry]})

    def test_the_spelling_of_the_first_day_is_read(self):
        entry = {"state": {"blend": SHA("f"), "blend_saved": False}}
        self.assertEqual(S.parent_state(entry), {"sha256": SHA("f"), "saved": False})

    def test_the_state_is_not_substance(self):
        a = {"stamp": 1, "self": {"resource_id": "r", "digest": SHA("1")},
             "from": [S.with_parent_state({"resource_id": "blend:1"}, saved=False)],
             "how": {"dtc_kind": "export"}}
        b = json.loads(json.dumps(a))
        b["from"][0]["state"] = {"saved": True, "sha256": SHA("2")}
        self.assertTrue(S.stamps_agree(a, b))
        # …and the COUNTEREXAMPLE: another parent is a disagreement
        b["from"][0]["resource_id"] = "blend:2"
        self.assertFalse(S.stamps_agree(a, b))


class TheRevision(unittest.TestCase):

    def _stamp(self, digest, rid="res:new"):
        return {"stamp": 1, "self": {"resource_id": rid, "digest": digest}}

    def test_marked_from_the_previous_stamp(self):
        new = S.mark_revision(self._stamp(SHA("2")), self._stamp(SHA("1"), "res:old"))
        self.assertEqual(S.revision_of(new), {"resource_id": "res:old", "digest": SHA("1")})

    def test_THE_COUNTEREXAMPLE_the_same_bytes_are_not_a_revision(self):
        with self.assertRaises(ValueError):
            S.mark_revision(self._stamp(SHA("1")), self._stamp(SHA("1"), "res:old"))

    def test_a_bare_id_is_read_and_nonsense_is_not(self):
        stamp = self._stamp(SHA("2"))
        stamp["self"]["was_revision_of"] = "res:old"
        self.assertEqual(S.revision_of(stamp), {"resource_id": "res:old"})
        stamp["self"]["was_revision_of"] = 7
        self.assertIsNone(S.revision_of(stamp))

    def test_a_revision_is_not_a_parent_and_not_walked(self):
        asked = []
        stamp = S.mark_revision(self._stamp(SHA("2")), self._stamp(SHA("1"), "res:old"))
        S.walk_chain(stamp, lambda d: asked.append(d))
        self.assertEqual(asked, [])

    def test_the_revision_is_not_substance(self):
        a = S.mark_revision(self._stamp(SHA("2")), self._stamp(SHA("1"), "res:old"))
        b = self._stamp(SHA("2"))
        self.assertTrue(S.stamps_agree(a, b))


class TheOperatorByIdentity(unittest.TestCase):

    def _stamp(self, operator):
        return {"stamp": 1, "self": {"resource_id": "r", "digest": SHA("1")},
                "how": {"dtc_kind": "export"}, "by": {"operator": operator}}

    def test_label_and_auth_are_not_substance(self):
        a = self._stamp({"id": "https://orcid.org/0000-0002-1825-0097", "label": "E.D.",
                         "auth": {"mode": "declared"}})
        b = self._stamp({"id": "https://orcid.org/0000-0002-1825-0097",
                         "auth": {"mode": "orcid"}})
        self.assertTrue(S.stamps_agree(a, b))

    def test_THE_COUNTEREXAMPLE_another_id_disagrees(self):
        a = self._stamp({"id": "https://orcid.org/0000-0002-1825-0097"})
        b = self._stamp({"id": "https://orcid.org/0000-0001-5109-3700"})
        self.assertEqual([d.path for d in S.compare_stamps(a, b)], ["by.operator"])


class TheParentsHints(unittest.TestCase):

    def _register(self):
        hints = S.new_hints(SHA("5"))
        S.note_seen(hints, "/Users/mrossi/export/TILE.glb", when="2026-11-01T10:00:00Z")
        S.note_parent_seen(hints, "blend:1", BLEND_LOCATOR, machine="mbp-ed",
                           when="2026-11-01T10:00:00Z")
        S.note_parent_seen(hints, "blend:2", "blend:///Users/mrossi/b.blend#Object/B",
                           when="2026-11-01T10:00:00Z")
        S.note_parent_seen(hints, "res:9", "s3://em-assets/res_9/x.glb",
                           when="2026-11-01T10:00:00Z")
        return hints

    def test_one_key_per_parent_and_the_assets_own_register_untouched(self):
        hints = self._register()
        self.assertEqual(hints["digest"], SHA("5"))
        self.assertEqual(sorted(hints["from"]), ["blend:1", "blend:2", "res:9"])
        self.assertEqual(S.parent_hints(hints, "blend:1")["seen"][0]["kind"], "blend")
        self.assertEqual(S.parent_hints(hints, "blend:1")["seen"][0]["scope"], "private")

    def test_seen_twice_is_one_hint(self):
        hints = self._register()
        S.note_parent_seen(hints, "blend:1", BLEND_LOCATOR, machine="mbp-ed",
                           when="2026-11-02T10:00:00Z")
        self.assertEqual(len(hints["from"]["blend:1"]), 1)
        self.assertEqual(hints["from"]["blend:1"][0]["when"], "2026-11-02T10:00:00Z")

    def test_none_of_the_private_ones_leaves_by_the_one_door(self):
        out = S.for_export(self._register())
        text = json.dumps(out)
        self.assertNotIn("mrossi", text)
        self.assertNotIn("mbp-ed", text)
        self.assertEqual(out["from"], {"res:9": [
            {"locator": "s3://em-assets/res_9/x.glb", "kind": "s3",
             "scope": "public", "when": "2026-11-01T10:00:00Z"}]})

    def test_the_private_locators_include_the_parents(self):
        self.assertEqual(sorted(S.private_locators(self._register())),
                         sorted(["/Users/mrossi/export/TILE.glb", BLEND_LOCATOR,
                                 "blend:///Users/mrossi/b.blend#Object/B"]))

    def test_THE_COUNTEREXAMPLE_a_parent_with_no_id(self):
        with self.assertRaises(ValueError):
            S.note_parent_seen(S.new_hints(SHA("5")), "", BLEND_LOCATOR)



# ═════════════════════════════════════════════════════════════════════════════
# AN ASSET INSIDE A METASHAPE PROJECT, AND THE NAMES IN QUOTES (0.1.4)
# ═════════════════════════════════════════════════════════════════════════════

class ThePsxLocator(unittest.TestCase):

    def test_a_key_counted_per_type_keeps_two_assets_apart(self):
        model = S.psx_locator("/p/a.psx", "Chunk 1", "model", 1)
        cloud = S.psx_locator("/p/a.psx", "Chunk 1", "point_cloud", 1)
        self.assertNotEqual(model, cloud)
        self.assertEqual(S.parse_psx_locator(model)[2:], ("model", "1"))

    def test_an_empty_chunk_label_goes_and_comes_back(self):
        loc = S.psx_locator("/p/a.psx", "", "model", 0)
        self.assertEqual(S.parse_psx_locator(loc), ("/p/a.psx", "", "model", "0"))

    def test_it_is_its_own_kind_and_always_private(self):
        loc = S.psx_locator("/p/a.psx", "Chunk 1", "model", 2)
        self.assertIn("psx", S.KNOWN_KINDS)
        self.assertEqual(S.kind_for(loc), "psx")
        self.assertEqual(S.scope_for(loc), "private")
        # a hint noted without a kind classifies itself
        seen = S.note_seen(S.new_hints(SHA("p")), loc, when="2026-10-02T10:00:00Z")
        self.assertEqual((seen["kind"], seen["scope"]), ("psx", "private"))

    def test_parse_answers_None_and_never_raises(self):
        for bad in ("", None, "psx://a.psx", "psx://a.psx#c/model",
                    "psx://a.psx#c/model/1/extra", "psx://#c/model/1",
                    "psx://a.psx#c//1", "psx://a.psx#c/model/",
                    "blend://a.blend#Object/x"):
            self.assertIsNone(S.parse_psx_locator(bad), bad)

    def test_nothing_to_point_at_is_an_empty_locator(self):
        self.assertEqual(S.psx_locator("", "c", "model", 1), "")
        self.assertEqual(S.psx_locator("/a.psx", "c", "", 1), "")
        self.assertEqual(S.psx_locator("/a.psx", "c", "model", None), "")


class TheNamesInQuotes(unittest.TestCase):

    def _follow(self, obj_text, mtl_name, mtl_text, files):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "m.obj").write_text(obj_text)
            (root / mtl_name).write_text(mtl_text)
            for name in files:
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_bytes(name.encode())
            return S.follow_references(str(root / "m.obj"))

    def test_mtllib_and_map_Kd_in_quotes_are_followed(self):
        found = self._follow('mtllib "a b.mtl"\nv 0 0 0\n', "a b.mtl",
                             'newmtl x\nmap_Kd "t/a b.jpg"\n', ["t/a b.jpg"])
        self.assertEqual(sorted(m["path"] for m in found["members"]),
                         ["a b.mtl", "m.obj", "t/a b.jpg"])
        self.assertEqual(found["missing"], [])

    def test_several_quoted_names_and_a_bare_one(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = pathlib.Path(tmp)
            (root / "m.obj").write_text('mtllib "a b.mtl" c.mtl\n')
            (root / "a b.mtl").write_text("newmtl a\n")
            (root / "c.mtl").write_text("newmtl c\n")
            found = S.follow_references(str(root / "m.obj"))
        self.assertEqual(sorted(m["path"] for m in found["members"]),
                         ["a b.mtl", "c.mtl", "m.obj"])

    def test_options_before_a_quoted_texture(self):
        found = self._follow("mtllib m.mtl\n", "m.mtl",
                             'newmtl x\nmap_Bump -bm 0.5 "n m.png"\n', ["n m.png"])
        self.assertIn("n m.png", [m["path"] for m in found["members"]])

    def test_the_unquoted_forms_did_not_change(self):
        """Blender's one name with spaces, and the spec's several names."""
        found = self._follow("mtllib a b.mtl\n", "a b.mtl", "newmtl x\n", [])
        self.assertEqual(found["missing"], [])
        found = self._follow("mtllib x.mtl y.mtl\n", "x.mtl", "newmtl x\n", [])
        self.assertEqual(found["missing"], ["y.mtl"])

if __name__ == "__main__":
    unittest.main(verbosity=2)
