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
        for path in expect.get("preserved", []):
            # THE ROUND TRIP, not just the read: an implementation that keeps a
            # field on read and drops it on write loses it just the same.
            with tempfile.TemporaryDirectory() as tmp:
                target = str(pathlib.Path(tmp) / "x.stamp.json")
                S.write_stamp(validated, target)
                back = S.read_stamp(target)
            self.assertIsNot(_dotted(back, path), _MISSING,
                             f"{path} did not survive the round trip")

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


if __name__ == "__main__":
    unittest.main(verbosity=2)
