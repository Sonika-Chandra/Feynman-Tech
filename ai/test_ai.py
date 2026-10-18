"""
Test harness for the AI module. Run from inside the ai/ folder:

    python test_ai.py question              # Milestone 2: one question per topic
    python test_ai.py loop [topic or notes.txt]   # Milestone 3: interactive 5-round loop (uses input(), test only)
    python test_ai.py score [topic]         # Milestone 4: stability + wrong-answer check
    python test_ai.py package [topic]       # Milestones 6-7: full report, fact-check, notes
Topics: photosynthesis, supply_demand, public_key

Free-tier keys allow only a few requests per minute. If you see 429 errors, set TEST_PAUSE=15.
"""
import os
import sys
import time

import ai_module as ai

PAUSE = int(os.getenv("TEST_PAUSE", "0"))


def pause():
    if PAUSE:
        time.sleep(PAUSE)


TOPICS = {
    "photosynthesis": {
        "source": (
            "Photosynthesis is the process by which plants, algae and some bacteria turn light energy into chemical "
            "energy. In plants it happens in chloroplasts, which contain chlorophyll. In the light-dependent reactions, "
            "chlorophyll absorbs sunlight and uses it to split water, releasing oxygen and producing ATP and NADPH. "
            "In the Calvin cycle (light-independent reactions), the plant uses ATP and NADPH to turn carbon dioxide "
            "into glucose. The overall result is glucose plus oxygen, made from carbon dioxide, water and light."
        ),
        "vague": "Plants use sunlight to make food. They take in air and water and it happens in the green parts of the leaf.",
        "good": [
            "Photosynthesis is how plants turn light into chemical energy. It happens in chloroplasts, where chlorophyll absorbs sunlight.",
            "In the first stage the light splits water, which releases oxygen and makes ATP and NADPH. In the second stage, the Calvin cycle, "
            "the plant uses that ATP and NADPH to turn carbon dioxide into glucose.",
        ],
        "wrong": [
            "Photosynthesis is when plants breathe in oxygen and release carbon dioxide, mostly at night, using their roots.",
            "The plant uses sunlight to split carbon dioxide and the energy is stored as protein in the leaves. Chlorophyll is not really needed.",
        ],
        "contradictory": [
            "Photosynthesis happens in chloroplasts, and chlorophyll absorbs sunlight. It splits water and releases oxygen.",
            "Actually, photosynthesis happens in the roots, not the chloroplasts, and oxygen comes from carbon dioxide, not water.",
        ],
        "q": "What happens in the two stages of photosynthesis, and what does each one produce?",
    },
    "supply_demand": {
        "source": (
            "Supply and demand explains how prices are set in a market. Demand is how much of a good buyers want at each "
            "price; when the price rises, the quantity demanded usually falls. Supply is how much sellers offer at each "
            "price; when the price rises, the quantity supplied usually rises. The equilibrium price is where quantity "
            "demanded equals quantity supplied. If the price is above equilibrium there is a surplus and prices tend to "
            "fall; if it is below equilibrium there is a shortage and prices tend to rise."
        ),
        "vague": "Prices depend on how many people want something and how much of it there is.",
        "good": [
            "Demand is how much buyers want at each price and it falls as price rises. Supply is how much sellers offer and it rises as price rises.",
            "The equilibrium price is where the two quantities are equal. Above it there is a surplus, so prices fall. Below it there is a shortage, so prices rise.",
        ],
        "wrong": [
            "When the price goes up, people want to buy more, and sellers offer less.",
            "Equilibrium is the highest price the government allows. A surplus makes prices rise and a shortage makes them fall.",
        ],
        "q": "What happens to the price if there is a surplus?",
    },
    "public_key": {
        "source": (
            "Public-key cryptography uses a pair of mathematically linked keys: a public key that anyone can know and a "
            "private key that is kept secret. Data encrypted with the public key can only be decrypted with the matching "
            "private key, so anyone can send a secret message to the key owner. For digital signatures the roles reverse: "
            "the owner signs with the private key and anyone can verify the signature with the public key. Its security "
            "relies on problems that are easy to compute in one direction but extremely hard to reverse, such as "
            "factoring the product of two large primes."
        ),
        "vague": "It is a way of locking messages with keys so only the right person can read them.",
        "good": [
            "There are two linked keys. The public key is shared with everyone and the private key stays secret. Anything encrypted with the public key can only be opened with the private key.",
            "For signatures it is reversed: you sign with your private key and anyone can check it with your public key. It is secure because some maths, like factoring huge primes, is easy forwards and very hard backwards.",
        ],
        "wrong": [
            "Both people share the same secret key, and the public key is used to hide the message from the internet.",
            "Signatures are made with the public key. It is secure because the keys are very long passwords that nobody has guessed yet.",
        ],
        "q": "How do digital signatures use the two keys?",
    },
}


def make_transcript(topic, variant):
    """Builds a student/ai/student transcript from the canned data above."""
    t = TOPICS[topic]
    first, second = t[variant]
    return [
        {"role": "student", "text": first},
        {"role": "ai", "text": t["q"]},
        {"role": "student", "text": second},
    ]


def pick_topics(arg):
    if arg:
        if arg not in TOPICS:
            sys.exit(f"Unknown topic '{arg}'. Choose from: {', '.join(TOPICS)}")
        return [arg]
    return list(TOPICS)


# ---------------------------------------------------------------- Milestone 2
def cmd_question(topic_arg):
    for name in pick_topics(topic_arg):
        t = TOPICS[name]
        first = ai.opening_question(t["source"])
        print(f"\n[{name}] AI opens: {first['next_question']}   (needs_whiteboard={first['needs_whiteboard']})")
        history = [{"role": "ai", "text": first["next_question"]}]
        out = ai.next_question(t["source"], history, t["vague"])
        print(f"[{name}] student said: {t['vague']}")
        print(f"[{name}] AI asks: {out['next_question']}   (round {out['round']}, should_stop={out['should_stop']}, needs_whiteboard={out['needs_whiteboard']})")
        q_marks = out["next_question"].count("?")
        print("   check: exactly one question mark ->", "OK" if q_marks == 1 else f"CHECK MANUALLY ({q_marks} found)")
        pause()


# ---------------------------------------------------------------- Milestone 3
def cmd_loop(topic_arg):
    arg = topic_arg or "photosynthesis"
    if arg.endswith(".txt"):          # your own notes: python test_ai.py loop mynotes.txt
        name = arg
        with open(arg, encoding="utf-8") as f:
            source = f.read()
    else:
        name = pick_topics(arg)[0]
        source = TOPICS[name]["source"]
    print(f"\nTOPIC: {name}\n\nREFERENCE TEXT:\n{source}\n")
    first = ai.opening_question(source)
    print(f"AI (round 1): {first['next_question']}" + ("   [whiteboard]" if first["needs_whiteboard"] else ""))
    history = [{"role": "ai", "text": first["next_question"]}]
    while True:
        reply = input("> ")
        out = ai.next_question(source, history, reply)
        history.append({"role": "student", "text": reply})
        if out["should_stop"]:
            print("\n(that was question 5: the quiz is over)")
            break
        print(f"\nAI (round {out['round']}): {out['next_question']}" + ("   [whiteboard]" if out["needs_whiteboard"] else ""))
        history.append({"role": "ai", "text": out["next_question"]})
    print("\nFinal score:")
    print_score(ai.final_score(source, history))


# ---------------------------------------------------------------- Milestone 4
def print_score(result):
    for name, s in result["scores"].items():
        print(f"  {name:<13}{s['score']:>2}/10  {s['justification']}")
    print(f"  OVERALL      {result['overall']}/100")
    print(f"  summary: {result['summary']}")
    for m in result["mistakes"]:
        print(f"  mistake: {m}")


def cmd_score(topic_arg):
    for name in pick_topics(topic_arg):
        t = TOPICS[name]
        good, wrong = make_transcript(name, "good"), make_transcript(name, "wrong")
        good_scores = []
        print(f"\n===== {name} =====")
        for run in range(3):
            r = ai.final_score(t["source"], good)
            good_scores.append(r["overall"])
            print(f"good run {run + 1}: overall {r['overall']}  " + str({k: v['score'] for k, v in r['scores'].items()}))
            pause()
        spread = max(good_scores) - min(good_scores)
        wrong_result = ai.final_score(t["source"], wrong)
        print(f"wrong answer: overall {wrong_result['overall']}  " + str({k: v['score'] for k, v in wrong_result['scores'].items()}))
        pause()
        print(f"stability: spread across 3 good runs = {spread} points ->", "OK" if spread <= 10 else "TOO WOBBLY (tighten rubric or see notes)")
        gap = min(good_scores) - wrong_result["overall"]
        print(f"separation: good minus wrong = {gap} points ->", "OK" if gap >= 25 else "TOO CLOSE (rubric not strict enough)")
        if name == "photosynthesis":
            c = ai.final_score(t["source"], make_transcript(name, "contradictory"))
            print(f"contradictory transcript: consistency = {c['scores']['consistency']['score']}/10 (should be low)")
            pause()


# ---------------------------------------------------------------- Milestones 6-7
def cmd_package(topic_arg):
    name = pick_topics(topic_arg or "photosynthesis")[0]
    t = TOPICS[name]
    transcript = make_transcript(name, "wrong")
    pkg = ai.full_package(t["source"], transcript, language="Kannada")
    print("\nSCORE"); print_score(pkg["score"])
    print("\nFACT-CHECK FINDINGS\n" + pkg["fact_check"]["findings"])
    print("SOURCES:", pkg["fact_check"]["sources"])
    print("\nREPORT\n" + pkg["report_markdown"])
    print("\nNOTES (English)\n" + pkg["notes"]["notes"])
    print("\nNOTES (translated)\n" + pkg["notes"]["notes_translated"])
    with open("sample_report.md", "w", encoding="utf-8") as f:
        f.write(pkg["report_markdown"])
    print("\nSaved sample_report.md")


COMMANDS = {"question": cmd_question, "loop": cmd_loop, "score": cmd_score, "package": cmd_package}

if __name__ == "__main__":
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        sys.exit(__doc__)
    COMMANDS[sys.argv[1]](sys.argv[2] if len(sys.argv) > 2 else None)
