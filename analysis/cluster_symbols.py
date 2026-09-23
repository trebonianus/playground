#!/usr/bin/env python3
"""
cluster_symbols.py -- group demanded symbols into functional areas

Input is the target_symbol_demand block of chains.json: every symbol the target
exports that somebody references, and which libraries reference it. Raw, that is
a flat list of hundreds of mangled-then-demangled names. Grouped by owning class
and namespace, the shape of the library's real API surface shows up, which is
what a split proposal needs.

  python3 cluster_symbols.py chains.json
  python3 cluster_symbols.py chains.json --depth 4    coarser namespace rollup
  python3 cluster_symbols.py chains.json --md

IMPORTANT LIMITATION
  chains.json only records symbols crossing *introducing edges of inherited
  chains*. It does not include direct dependents, which are usually the bulk of
  real usage. Treat this as a first look at what the target is used for, not as
  the full demand picture. For that you need the object-level scan:

      symdeps.py scan  (over the .o files)  ->  splitplan.py

  which also tells you which parts of the library can move, not just which parts
  are wanted.
"""

import json
import re
import sys
import collections


def owner(sym):
    """Class or namespace a demangled symbol belongs to."""
    s = sym.split("(")[0].strip()
    if " " in s:
        s = s.split(" ")[-1]
    i = s.rfind("::")
    return s[:i] if i > 0 else "(free functions)"


def nspace(name, depth):
    parts = name.split("::")
    return "::".join(parts[:depth]) if len(parts) > depth else name


def main():
    argv = sys.argv[1:]
    as_md = "--md" in argv
    depth = 3
    if "--depth" in argv:
        depth = int(argv[argv.index("--depth") + 1])
    files = [a for a in argv if not a.startswith("--") and not a.isdigit()]
    path = files[0] if files else "chains.json"

    d = json.load(open(path))
    demand = d.get("target_symbol_demand", [])
    if not demand:
        sys.stderr.write("no target_symbol_demand in %s\n" % path)
        return 1

    by_owner = collections.defaultdict(lambda: {"syms": [], "libs": set(), "weak": 0})
    for s in demand:
        o = owner(s["symbol"])
        by_owner[o]["syms"].append(s["symbol"])
        by_owner[o]["libs"] |= set(s.get("referenced_by", []))
        if s.get("weak"):
            by_owner[o]["weak"] += 1

    rows = [{"owner": k, "symbols": len(v["syms"]), "consumers": len(v["libs"]),
             "weak": v["weak"], "libs": sorted(v["libs"]), "syms": sorted(v["syms"])}
            for k, v in by_owner.items()]
    rows.sort(key=lambda r: (-r["consumers"], -r["symbols"]))

    if as_md:
        print("| Consumers | Symbols | Class / namespace |")
        print("|---|---|---|")
        for r in rows:
            print("| %d | %d | `%s` |" % (r["consumers"], r["symbols"], r["owner"]))
        return 0

    print("=" * 78)
    print("DEMAND BY CLASS  (%d distinct symbols in %d groups)"
          % (len(demand), len(rows)))
    print("  NOTE: inherited chains only. Direct dependents are not counted.")
    print("=" * 78)
    print()
    print("%10s %8s %6s  %s" % ("consumers", "symbols", "weak", "class / namespace"))
    for r in rows:
        print("%10d %8d %6d  %s" % (r["consumers"], r["symbols"], r["weak"], r["owner"]))

    print()
    print("=" * 78)
    print("ROLLUP to namespace depth %d" % depth)
    print("=" * 78)
    ns = collections.defaultdict(lambda: {"syms": 0, "libs": set(), "classes": set()})
    for r in rows:
        k = nspace(r["owner"], depth)
        ns[k]["syms"] += r["symbols"]
        ns[k]["libs"] |= set(r["libs"])
        ns[k]["classes"].add(r["owner"])
    print("%10s %8s %8s  %s" % ("consumers", "symbols", "classes", "namespace"))
    for k, v in sorted(ns.items(), key=lambda x: -len(x[1]["libs"])):
        print("%10d %8d %8d  %s" % (len(v["libs"]), v["syms"], len(v["classes"]), k))

    print()
    print("=" * 78)
    print("CANDIDATE GROUPINGS -- classes wanted by the most consumers")
    print("  A class with many consumers and few symbols is a small, widely")
    print("  wanted piece: the best thing to pull into a leaf library.")
    print("=" * 78)
    for r in rows[:12]:
        print()
        print("%s   (%d consumers, %d symbols)" % (r["owner"], r["consumers"], r["symbols"]))
        for s in r["syms"][:6]:
            print("     %s" % s[:100])
        if len(r["syms"]) > 6:
            print("     ... +%d more" % (len(r["syms"]) - 6))
        print("     wanted by: %s" % ", ".join(r["libs"][:5])
              + (" ..." if len(r["libs"]) > 5 else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
