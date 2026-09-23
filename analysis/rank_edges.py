#!/usr/bin/env python3
"""
rank_edges.py -- rank removal candidates from chains.json

An inherited dependency is acquired through exactly one edge: the last hop in
the chain, where the target finally appears. Many chains usually share the same
introducing edge, so fixing one edge can free a whole set of libraries at once.

This aggregates by that edge and ranks them. The ordering is deliberate:
fewest symbols first, then most chains freed. The top of the list is where
effort pays off most.

  python3 rank_edges.py chains.json
  python3 rank_edges.py chains.json --md      markdown table for a write-up

Columns:
  chains   how many inherited libraries route through this edge
  syms     symbols the consumer references across it
  weak     how many of those are weak ("use if present")
  classes  distinct classes/namespaces the symbols belong to

Reading it:
  syms 0            declares the dependency, references nothing. Cheapest fix,
                    usually a stale link line. Still needs a relink to confirm.
  syms low, classes 1   thin coupling to a single concept. Good split candidate.
  syms high, classes 1  heavy use of one class. Separable, but real work.
  classes high      pervasive coupling. Hardest, lowest priority.
"""

import json
import re
import sys
import collections


def owner(sym):
    """Class or namespace a demangled symbol belongs to."""
    s = sym.split("(")[0].strip()
    if " " in s:
        s = s.split(" ")[-1]          # drop a leading return type
    i = s.rfind("::")
    return s[:i] if i > 0 else "(free functions)"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    as_md = "--md" in sys.argv
    path = args[0] if args else "chains.json"
    d = json.load(open(path))

    agg = {}
    for c in d.get("chains", []):
        for e in c.get("edges", []):
            if not e.get("introduces_target"):
                continue
            k = (e["from"], e["to"])
            if k not in agg:
                agg[k] = {"chains": set(), "count": e["count"],
                          "weak": e.get("weak_count", 0),
                          "all_weak": e.get("all_weak", False),
                          "symbols": e.get("symbols", [])}
            agg[k]["chains"].add(c["lib"])

    rows = []
    for (a, b), v in agg.items():
        cls = set(owner(s) for s in v["symbols"])
        rows.append({"from": a, "to": b, "chains": len(v["chains"]),
                     "syms": v["count"], "weak": v["weak"],
                     "all_weak": v["all_weak"], "classes": sorted(cls),
                     "libs": sorted(v["chains"])})
    rows.sort(key=lambda r: (r["syms"], -r["chains"]))

    if as_md:
        print("| Chains freed | Symbols | Weak | Classes | Edge |")
        print("|---|---|---|---|---|")
        for r in rows:
            print("| %d | %d | %d | %d | `%s` -> `%s` |"
                  % (r["chains"], r["syms"], r["weak"], len(r["classes"]),
                     r["from"], r["to"]))
        return 0

    total = sum(r["chains"] for r in rows)
    print("=" * 78)
    print("INTRODUCING EDGES  (%d edges, %d chain-attachments)" % (len(rows), total))
    print("  ranked: fewest symbols first, then most chains freed")
    print("=" * 78)
    print()
    print("%7s %6s %5s %8s  %s" % ("chains", "syms", "weak", "classes", "edge"))
    for r in rows:
        flag = ""
        if r["syms"] == 0:
            flag = "   <-- nothing referenced"
        elif r["all_weak"]:
            flag = "   <-- all weak"
        print("%7d %6d %5d %8d  %s -> %s%s"
              % (r["chains"], r["syms"], r["weak"], len(r["classes"]),
                 r["from"], r["to"], flag))

    print()
    print("=" * 78)
    print("DETAIL for the 10 best candidates")
    print("=" * 78)
    for r in rows[:10]:
        print()
        print("%s -> %s" % (r["from"], r["to"]))
        print("  frees %d chain(s): %s" % (r["chains"], ", ".join(r["libs"][:6])
                                           + (" ..." if len(r["libs"]) > 6 else "")))
        if not r["classes"]:
            print("  no symbols referenced across this edge")
            continue
        print("  touches %d class(es):" % len(r["classes"]))
        for c in r["classes"][:10]:
            print("      %s" % c)
        if len(r["classes"]) > 10:
            print("      ... +%d more" % (len(r["classes"]) - 10))
    return 0


if __name__ == "__main__":
    sys.exit(main())
