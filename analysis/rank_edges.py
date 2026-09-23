import json
import sys

# python3 rank_edges.py chains.json [--md]


def owner(sym):
    s = sym.split("(")[0].strip()
    if " " in s:
        s = s.split(" ")[-1]
    i = s.rfind("::")
    return s[:i] if i > 0 else "(free)"


args = [a for a in sys.argv[1:] if not a.startswith("--")]
md = "--md" in sys.argv
path = args[0] if args else "chains.json"
d = json.load(open(path))

agg = {}
for c in d["chains"]:
    for e in c["edges"]:
        if not e["introduces_target"]:
            continue
        k = (e["from"], e["to"])
        if k not in agg:
            agg[k] = {"libs": set(), "syms": e["count"], "weak": e["weak_count"],
                      "all_weak": e.get("all_weak", False),
                      "symbols": e.get("symbols", [])}
        agg[k]["libs"].add(c["lib"])

rows = []
for (a, b), v in agg.items():
    cls = sorted(set(owner(s) for s in v["symbols"]))
    rows.append((v["syms"], -len(v["libs"]), a, b, len(v["libs"]), v["weak"],
                 v["all_weak"], cls, sorted(v["libs"]), v["symbols"]))
rows.sort()

if md:
    print("| Chains | Symbols | Weak | Classes | Edge |")
    print("|---|---|---|---|---|")
    for r in rows:
        print("| %d | %d | %d | %d | `%s` -> `%s` |" % (r[4], r[0], r[5], len(r[7]), r[2], r[3]))
    sys.exit(0)

print("%7s %6s %5s %8s  %s" % ("chains", "syms", "weak", "classes", "edge"))
for r in rows:
    tag = ""
    if r[0] == 0:
        tag = "  none referenced"
    elif r[6]:
        tag = "  all weak"
    print("%7d %6d %5d %8d  %s -> %s%s" % (r[4], r[0], r[5], len(r[7]), r[2], r[3], tag))

print("")
for r in rows[:10]:
    print("%s -> %s" % (r[2], r[3]))
    print("  frees %d: %s" % (r[4], ", ".join(r[8][:6])))
    for c in r[7][:10]:
        print("  %s" % c)
    for s in r[9][:5]:
        print("    %s" % s[:100])
    print("")
