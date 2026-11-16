"""Build the proposed audit_db.py patches WITHOUT touching the original.

Produces, in this directory:
    candidate_1_baseline.py          original + R8 (--baseline)
    candidate.py                     original + R8 + R7 (decimal precision)
    01_baseline_option.patch         original -> candidate_1_baseline.py
    02_decimal_precision.patch       candidate_1_baseline.py -> candidate.py

The two patches apply in order:
    git apply --check database/prep_phase1/proposed/01_baseline_option.patch
    git apply --check database/prep_phase1/proposed/02_decimal_precision.patch

The original database/audit_db.py is only ever READ. Run:
    python database/prep_phase1/proposed/build_candidate.py
"""

from __future__ import annotations

import difflib
from pathlib import Path

HERE = Path(__file__).resolve().parent
ORIGINAL = HERE.parents[1] / "audit_db.py"      # database/audit_db.py
PATCH_TARGET = "database/audit_db.py"


def load() -> tuple[str, str]:
    raw = ORIGINAL.read_text(encoding="utf-8", newline="")
    eol = "\r\n" if "\r\n" in raw else "\n"
    return raw, eol


def apply_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"anchor '{label}' matched {n} times, expected exactly 1")
    return text.replace(old, new, 1)


def apply_all(text: str, old: str, new: str, label: str, expected: int) -> str:
    n = text.count(old)
    if n != expected:
        raise SystemExit(f"anchor '{label}' matched {n} times, expected {expected}")
    return text.replace(old, new)


def diff(before: str, after: str) -> str:
    return "".join(difflib.unified_diff(
        before.splitlines(keepends=True),
        after.splitlines(keepends=True),
        fromfile=f"a/{PATCH_TARGET}",
        tofile=f"b/{PATCH_TARGET}",
        n=4,
    ))


def main() -> int:
    raw, eol = load()

    def E(s: str) -> str:
        return s.replace("\n", eol)

    # ---------------------------------------------------------------- R8 ----
    after_r8 = apply_once(
        raw,
        E("Exit codes\n----------\n"),
        E(
            "Usage\n"
            "-----\n"
            "    python database/audit_db.py [--baseline PATH] [--out PATH]\n"
            "                                [--self-test | --negative-probes]\n"
            "\n"
            "    --baseline PATH  Compare the live schema against a different\n"
            "                     reference export instead of the frozen\n"
            "                     database/schema.sql - for example the\n"
            "                     post-migration export created after an approved\n"
            "                     batch. The frozen original is never modified.\n"
            "\n"
            "Exit codes\n"
            "----------\n"
        ),
        "docstring usage",
    )

    after_r8 = apply_once(
        after_r8,
        E('SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"\n'),
        E(
            "# Frozen pre-migration reference export. Never rewritten by this script.\n"
            'DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parent / "schema.sql"\n'
            "\n"
            "# Active baseline for every structural comparison. Rebinding this global\n"
            "# is how --baseline switches references without touching the default.\n"
            "SCHEMA_PATH = DEFAULT_SCHEMA_PATH\n"
            "\n"
            "\n"
            "def set_baseline(path: str) -> Path:\n"
            '    """Point parse_schema()/compare_export() at `path` instead.\n'
            "\n"
            "    The default baseline is deliberately NOT replaced: database/schema.sql\n"
            "    stays the frozen pre-migration export, and a post-migration export is\n"
            "    a separate file passed here.\n"
            '    """\n'
            "    global SCHEMA_PATH\n"
            "    SCHEMA_PATH = Path(path).expanduser().resolve()\n"
            "    return SCHEMA_PATH\n"
        ),
        "SCHEMA_PATH constant",
    )

    after_r8 = apply_once(
        after_r8,
        E('    if "--self-test" in args:\n        return run_self_test()\n'),
        E(
            '    if "--baseline" in args:\n'
            '        i = args.index("--baseline")\n'
            "        if i + 1 >= len(args):\n"
            '            print("--baseline needs a path", file=sys.stderr)\n'
            "            return 1\n"
            "        if not Path(args[i + 1]).expanduser().is_file():\n"
            '            print(f"ERROR: --baseline {args[i + 1]} not found",\n'
            "                  file=sys.stderr)\n"
            "            return 1\n"
            "        set_baseline(args[i + 1])\n"
            "\n"
            '    if "--self-test" in args:\n'
            "        return run_self_test()\n"
        ),
        "--baseline parsing",
    )

    after_r8 = apply_once(
        after_r8,
        E(
            "        if not SCHEMA_PATH.exists():\n"
            '            print(f"ERROR: {SCHEMA_PATH} not found")\n'
            "            return 1\n"
            "\n"
            "        schema = parse_schema()\n"
            "        print_static(schema)\n"
        ),
        E(
            "        if not SCHEMA_PATH.exists():\n"
            '            print(f"ERROR: {SCHEMA_PATH} not found")\n'
            "            return 1\n"
            "\n"
            "        origin = (\"frozen original\" if SCHEMA_PATH == DEFAULT_SCHEMA_PATH\n"
            '                  else "override via --baseline")\n'
            '        print(f"BASELINE: {SCHEMA_PATH}  ({origin})")\n'
            "        schema = parse_schema()\n"
            "        print_static(schema)\n"
        ),
        "baseline echo",
    )

    # ---------------------------------------------------------------- R7 ----
    # CAST(... AS SIGNED) truncates fractional kilograms; DECIMAL(20,2) keeps them.
    after_r7 = apply_all(
        after_r8,
        E('                       "SELECT CAST(COALESCE(SUM(i.quantity_delivered_kg),0) '
          'AS SIGNED) AS n "\n'),
        E('                       "SELECT CAST(COALESCE(SUM(i.quantity_delivered_kg),0) '
          'AS DECIMAL(20,2)) AS n "\n'),
        "delivered-kg cast",
        2,
    )

    (HERE / "candidate_1_baseline.py").write_text(after_r8, encoding="utf-8", newline="")
    (HERE / "candidate.py").write_text(after_r7, encoding="utf-8", newline="")

    p1 = diff(raw, after_r8)
    p2 = diff(after_r8, after_r7)
    if not p1 or not p2:
        raise SystemExit("a patch came out empty - anchors are wrong")
    (HERE / "01_baseline_option.patch").write_text(p1, encoding="utf-8", newline="")
    (HERE / "02_decimal_precision.patch").write_text(p2, encoding="utf-8", newline="")

    print(f"original        : {ORIGINAL}")
    print(f"line endings    : {'CRLF' if eol == chr(13) + chr(10) else 'LF'}")
    print(f"01_baseline     : {len(p1.splitlines())} diff lines")
    print(f"02_decimal      : {len(p2.splitlines())} diff lines")
    print("written         : candidate_1_baseline.py, candidate.py, 01/02 patches")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
