import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import integrity as i
f = []
def check(n, c):
    print(("PASS  " if c else "FAIL  ") + n)
    if not c: f.append(n)
notes = "the light dependent reactions split water and release oxygen making atp and nadph in the thylakoid membranes of the chloroplast"
own = "plants use sunlight to make sugar and they give out oxygen from the water they take in through their roots every day"
check("a copied answer has high overlap", i.copy_overlap(notes, notes) >= 0.9)
check("an own-words answer has no overlap", i.copy_overlap(own, notes) < 0.1)
check("short answers are not checked", i.copy_overlap("split water", notes) == 0)
st = i.add_answer(i.empty(), own, notes, 0, 1)
check("one tab switch is fine", not i.verdict(st)["flagged"])
st = i.add_answer(st, own, notes, 0, 2)
check("three tab switches flag the session", i.verdict(st)["flagged"])
check("a paste attempt flags the session", i.verdict(i.add_answer(i.empty(), own, notes, 1, 0))["flagged"])
check("a copied answer flags the session", i.verdict(i.add_answer(i.empty(), notes, notes, 0, 0))["flagged"])
check("flagged sessions earn no badge", i.badge(95, True)["tier"] == "flagged")
check("badge tiers", [i.badge(x, False)["tier"] for x in (95, 85, 65, 45, 10)] == ["platinum", "gold", "silver", "bronze", "start"])
print("\n" + ("ALL TESTS PASSED" if not f else f"{len(f)} FAILED: {f}"))
sys.exit(1 if f else 0)
