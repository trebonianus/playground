#!/usr/bin/env python3
"""
thin_edges.py -- find every thin edge in every chain, not just the introducing one

rank_edges.py only looks at the last hop, where the target appears. That misses a
whole class of opportunity: a library may depend very weakly on a library that in
turn depends heavily on the target. You cannot remove the heavy introducing edge,
but you may be able to remove the thin one earlier in the chain, which frees
everything upstream of it.

    libA.so -> libB.so         1 symbol    <- thin, cuttable
            -> libimageproc.so 83 symbols  <- heavy, not cuttable

Cutting A->B frees A (and anything whose chain runs through A->B) even though the
B->imageproc relationship is untouched and legitimate.

  python3 thin_edges.py chains.json
  python3 thin_edges.py chains.json --max 5      only edges with <= 5 symbols
  python3 thin_edges.py chains.json --md

Columns:
  frees    libraries whose recorded chain runs through this edge
  syms     symbols referenced across it
  weak     how many of those are weak
  classes  distinct classes/namespaces involved
  lev      leverage: frees / (syms + 1). High = cheap cut, wide effect.

IMPORTANT -- "frees" is an UPPER BOUND
  chains.json records only the SHORTEST path from each library to the target.
  If a library reaches the target by more than one route, cutting the edge on
  its shortest path will not actually free it; it will just take the other
  route, and the count here overstates the benefit.

  Verify a candidate before relying on the number:

      readelf -d libA.so | grep NEEDED     # what else does A pull in?
      # cut the edge, rebuild, then:
      ldd libA.so | grep -E 'imageproc|gpu_mgr'

  If the target still appears, there was another path.

The two kinds of fix are not interchangeable:
  introducing edge  -- the target dependency itself is wrong or removable
  earlier edge      -- the target dependency is legitimate, but THIS consumer
                       barely uses the library carrying it, so the consumer
                       should not be coupled to it at all. That is a component
                       design argument, and it needs its own justification.
"""

import json
import re
import sys
import collections


def owner(sym):
    s = sym.split("(")[0].strip()
    if " " in s:
        s = s.split(" ")[-1]
    i = s.rfind("::")
    return s[:i] if i > 0 else "(free functions)"


def main():
    argv = sys.argv[1:]
    as_md = "--md" in argv
    maxs = None
    if "--max" in argv:
        maxs = int(argv[argv.index("--max") + 1])
    files = [a for a in argv if not a.startswith("--") and not a.isdigit()]
    path = files[0] if files else "chains.json"
    d = json.load(open(path))

    # every edge, with the set of chain subjects whose path traverses it
    agg = {}
    for c in d.get("chains", []):
        for e in c.get("edges", []):
            k = (e["from"], e["to"])
            if k not in agg:
                agg[k] = {"frees": set(), "syms": e["count"],
                          "weak": e.get("weak_count", 0),
                          "all_weak": e.get("all_weak", False),
                          "intro": e.get("introduces_target", False),
                          "symbols": e.get("symbols", [])}
            agg[k]["frees"].add(c["lib"])

    rows = []
    for (a, b), v in agg.items():
        if maxs is not None and v["syms"] > maxs:
            continue
        cls = sorted(set(owner(s) for s in v["symbols"]))
        rows.append({"from": a, "to": b, "frees": len(v["frees"]),
                     "syms": v["syms"], "weak": v["weak"],
                     "all_weak": v["all_weak"], "intro": v["intro"],
                     "classes": cls, "libs": sorted(v["frees"]),
                     "lev": round(len(v["frees"]) / float(v["syms"] + 1), 2),
                     "symbols": v["symbols"]})
    rows.sort(key=lambda r: (-r["lev"], r["syms"]))

    if as_md:
        print("| Frees | Symbols | Weak | Classes | Leverage | Kind | Edge |")
        print("|---|---|---|---|---|---|---|")
        for r in rows:
            print("| %d | %d | %d | %d | %s | %s | `%s` -> `%s` |"
                  % (r["frees"], r["syms"], r["weak"], len(r["classes"]), r["lev"],
                     "introducing" if r["intro"] else "upstream", r["from"], r["to"]))
        return 0

    print("=" * 78)
    print("ALL EDGES BY LEVERAGE  (%d edges%s)"
          % (len(rows), ", filtered to <= %d symbols" % maxs if maxs else ""))
    print("  leverage = libraries freed / (symbols + 1)")
    print("  'frees' is an UPPER BOUND: shortest paths only, alternate routes")
    print("  are not accounted for. Verify with ldd after cutting.")
    print("=" * 78)
    print()
    print("%6s %6s %5s %8s %7s  %-12s %s" %
          ("frees", "syms", "weak", "classes", "lev", "kind", "edge"))
    for r in rows:
        flag = ""
        if r["syms"] == 0:
            flag = "  <-- nothing referenced"
        elif r["all_weak"]:
            flag = "  <-- all weak"
        print("%6d %6d %5d %8d %7s  %-12s %s -> %s%s"
              % (r["frees"], r["syms"], r["weak"], len(r["classes"]), r["lev"],
                 "introducing" if r["intro"] else "upstream",
                 r["from"], r["to"], flag))

    print()
    print("=" * 78)
    print("DETAIL -- top 12 by leverage")
    print("=" * 78)
    for r in rows[:12]:
        print()
        kind = "INTRODUCING EDGE" if r["intro"] else "UPSTREAM EDGE"
        print("%s -> %s   [%s]" % (r["from"], r["to"], kind))
        print("  frees up to %d: %s" % (r["frees"], ", ".join(r["libs"][:6])
                                        + (" ..." if len(r["libs"]) > 6 else "")))
        if r["syms"] == 0:
            print("  no symbols referenced -- stale link line or header-only use")
        else:
            print("  %d symbol(s) across %d class(es):" % (r["syms"], len(r["classes"])))
            for s in r["symbols"][:6]:
                print("      %s" % s[:100])
            if r["syms"] > 6:
                print("      ... +%d more" % (r["syms"] - 6))
        if not r["intro"]:
            print("  NOTE: upstream edge. Removing this does not fix the target")
            print("        dependency itself -- it decouples this consumer from the")
            print("        library that carries it. Justify on its own terms.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
