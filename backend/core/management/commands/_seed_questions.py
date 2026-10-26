"""Question content for the demo question bank (used by seed_connect_school's question_bank step).

Class 10 Mathematics questions are generated from parameters with the answer computed, so every answer is right
and there are enough for two non-overlapping sets per examination. Science and English questions are written out.
Each entry is a dict ready for ``question_bank.services.check_content`` (subject, chapter and topic are added later).
"""
import math
import random

MATHS_CHAPTERS = [
    ("Real Numbers", ["HCF and LCM", "Prime factorisation"]),
    ("Polynomials", ["Zeroes of a polynomial"]),
    ("Pair of Linear Equations", ["Substitution and elimination", "Word problems"]),
    ("Quadratic Equations", ["Factorisation", "Nature of roots"]),
    ("Arithmetic Progressions", ["nth term", "Sum of n terms"]),
    ("Introduction to Trigonometry", ["Trigonometric ratios"]),
    ("Some Applications of Trigonometry", ["Heights and distances"]),
    ("Statistics", ["Mean of data"]),
    ("Surface Areas and Volumes", ["Cylinder and cone"]),
]

SCIENCE_CHAPTERS = [
    ("Chemical Reactions and Equations", ["Types of reactions", "Balancing equations"]),
    ("Acids, Bases and Salts", ["pH scale", "Common salts"]),
    ("Life Processes", ["Nutrition", "Respiration"]),
    ("Light - Reflection and Refraction", ["Mirrors", "Lenses"]),
    ("Electricity", ["Ohm's law", "Resistance in series and parallel"]),
]

SCIENCE8_CHAPTERS = [("Crop Production and Management", ["Agricultural practices"]), ("Force and Pressure", ["Pressure"])]
ENGLISH8_CHAPTERS = [("Grammar", ["Tenses", "Voice"])]


def _mcq(body, right, wrong, **kw):
    """One correct option and three wrong ones, in a shuffled but repeatable order."""
    options = [{"text": str(right), "is_correct": True}] + [{"text": str(w), "is_correct": False} for w in wrong]
    random.Random(body).shuffle(options)
    return {"question_type": "mcq", "marks": "1", "body": body, "options": options, **kw}


def _written(kind, marks, body, answer, scheme="", **kw):
    return {"question_type": kind, "marks": str(marks), "body": body, "answer": answer, "marking_scheme": scheme, **kw}


def _distinct(right, *candidates):
    """Wrong options: the candidates that differ from the answer and each other, topped up if needed."""
    seen, out = {str(right)}, []
    for c in list(candidates) + [right + k for k in (1, 2, 3, -1, -2, 5, 7)]:
        if str(c) not in seen:
            seen.add(str(c))
            out.append(c)
        if len(out) == 3:
            return out
    return out


def maths_questions(rng):
    """Class 10 Mathematics: 48 MCQs (24 easy, 24 medium), 22 short answers, 16 long answers."""
    out = []
    # --- MCQs, easy -----------------------------------------------------------------------------------
    pairs = [(12, 18), (24, 36), (15, 25), (28, 42), (16, 40), (45, 75), (27, 63), (32, 48)]
    for a, b in pairs:
        h = math.gcd(a, b)
        out.append(_mcq(f"What is the HCF of {a} and {b}?", h, _distinct(h, h * 2, h // 2 if h > 2 else h + 4, a - b if a > b else b - a),
                        difficulty="easy", chapter="Real Numbers", topic="HCF and LCM", learning_outcome="Finds the HCF of two numbers"))
    for a, d, n in [(3, 4, 10), (5, 3, 12), (2, 5, 8), (7, 2, 15), (10, -3, 6), (1, 6, 9), (4, 7, 11), (20, -2, 10)]:
        t = a + (n - 1) * d
        out.append(_mcq(f"The {n}th term of the AP {a}, {a + d}, {a + 2 * d}, ... is", t, _distinct(t, a + n * d, a + (n - 2) * d, t + d + 1),
                        difficulty="easy", chapter="Arithmetic Progressions", topic="nth term", learning_outcome="Uses a_n = a + (n - 1)d"))
    for b, c in [(5, 6), (7, 12), (9, 20), (3, -10), (1, -12), (8, 15), (11, 30), (2, -15)]:
        out.append(_mcq(f"The sum of the zeroes of the polynomial x^2 + {b}x + {c} is".replace("+ -", "- "), -b, _distinct(-b, b, c, -c),
                        difficulty="easy", chapter="Polynomials", topic="Zeroes of a polynomial", learning_outcome="Relates zeroes to coefficients"))
    # --- MCQs, medium ---------------------------------------------------------------------------------
    for a, b, c in [(1, -5, 6), (1, 4, 4), (2, 3, 5), (1, -2, 1), (3, -4, 7), (1, 1, -6), (4, 4, 1), (1, 3, 9)]:
        disc = b * b - 4 * a * c
        nature = "Two distinct real roots" if disc > 0 else "Two equal real roots" if disc == 0 else "No real roots"
        others = [n for n in ("Two distinct real roots", "Two equal real roots", "No real roots", "Exactly three real roots") if n != nature]
        eq = f"{a}x^2 + {b}x + {c} = 0".replace("+ -", "- ").replace("1x", "x")
        out.append(_mcq(f"The nature of the roots of {eq} is", nature, others, difficulty="medium", chapter="Quadratic Equations",
                        topic="Nature of roots", learning_outcome="Uses the discriminant to decide the nature of roots"))
    for values in ([4, 8, 6, 2], [10, 12, 14, 16, 18], [3, 7, 5, 9, 11], [20, 25, 30, 35], [6, 9, 12, 15, 18], [2, 4, 9, 13], [15, 5, 10, 20, 25], [7, 14, 21, 28]):
        mean = sum(values) / len(values)
        m = int(mean) if mean == int(mean) else round(mean, 2)
        out.append(_mcq(f"The mean of {', '.join(map(str, values))} is", m, _distinct(m, max(values), min(values), sum(values)),
                        difficulty="medium", chapter="Statistics", topic="Mean of data", learning_outcome="Finds the mean of ungrouped data"))
    trig = [("sin 30°", "1/2", ["√3/2", "1", "1/√2"]), ("cos 60°", "1/2", ["√3/2", "0", "1"]), ("tan 45°", "1", ["0", "√3", "1/√3"]),
            ("sin 90°", "1", ["0", "1/2", "√3/2"]), ("cos 0°", "1", ["0", "1/2", "-1"]), ("tan 60°", "√3", ["1/√3", "1", "√3/2"]),
            ("sin^2 30° + cos^2 30°", "1", ["0", "1/2", "2"]), ("sec 0°", "1", ["0", "√2", "2"])]
    for expr, right, wrong in trig:
        out.append(_mcq(f"The value of {expr} is", right, wrong, difficulty="medium", chapter="Introduction to Trigonometry",
                        topic="Trigonometric ratios", learning_outcome="Recalls values of standard angles"))
    # --- Short answers (3 marks) ----------------------------------------------------------------------
    for a, b in [(96, 404), (336, 54), (72, 120), (84, 126), (156, 208), (90, 144)]:
        h = math.gcd(a, b)
        lcm = a * b // h
        out.append(_written("short", 3, f"Find the HCF and LCM of {a} and {b} by prime factorisation, and verify that HCF × LCM = product of the numbers.",
                            f"HCF = {h}, LCM = {lcm}. Check: {h} × {lcm} = {a * b} = {a} × {b}.",
                            "1 mark each for the two prime factorisations, 1 mark for HCF, LCM and the check.",
                            difficulty="easy", chapter="Real Numbers", topic="Prime factorisation"))
    for x, y in [(7, 3), (9, 4), (12, 5), (6, 1), (15, 8), (11, 2)]:
        out.append(_written("short", 3, f"Solve the pair of equations: x + y = {x + y} and x - y = {x - y}.",
                            f"Adding gives 2x = {2 * x}, so x = {x}; then y = {y}.", "1 mark for eliminating a variable, 1 each for x and y.",
                            difficulty="easy", chapter="Pair of Linear Equations", topic="Substitution and elimination"))
    for p, q in [(2, 3), (4, 5), (1, 6), (3, 7), (2, 9)]:
        out.append(_written("short", 3, f"Find the roots of x^2 - {p + q}x + {p * q} = 0 by factorisation.",
                            f"x^2 - {p + q}x + {p * q} = (x - {p})(x - {q}) = 0, so x = {p} or x = {q}.",
                            "2 marks for the correct factors, 1 mark for both roots.", difficulty="medium", chapter="Quadratic Equations", topic="Factorisation"))
    for a, d, n in [(2, 3, 20), (5, 4, 15), (1, 2, 25), (10, 5, 12), (3, 6, 10)]:
        s = n * (2 * a + (n - 1) * d) // 2
        out.append(_written("short", 3, f"Find the sum of the first {n} terms of the AP {a}, {a + d}, {a + 2 * d}, ...",
                            f"S_n = n/2 [2a + (n - 1)d] = {n}/2 [{2 * a} + {(n - 1) * d}] = {s}.", "1 mark for the formula, 1 for substitution, 1 for the answer.",
                            difficulty="medium", chapter="Arithmetic Progressions", topic="Sum of n terms"))
    # --- Long answers (8 marks) -----------------------------------------------------------------------
    for length, width in [(20, 15), (24, 10), (30, 18), (16, 12)]:
        out.append(_written("long", 8, f"The perimeter of a rectangular park is {2 * (length + width)} m and its area is {length * width} m^2. Form a quadratic equation and find the length and breadth of the park.",
                            f"Let the length be x m; breadth = {length + width} - x. Then x({length + width} - x) = {length * width}, i.e. x^2 - {length + width}x + {length * width} = 0, so x = {length} or {width}. Length {length} m, breadth {width} m.",
                            "2 for setting up the equation, 3 for solving it, 2 for choosing the dimensions, 1 for the conclusion.",
                            difficulty="hard", chapter="Quadratic Equations", topic="Factorisation"))
    for first, step, months in [(500, 100, 12), (300, 50, 10), (1000, 200, 8), (250, 25, 20)]:
        total = months * (2 * first + (months - 1) * step) // 2
        out.append(_written("long", 8, f"Meena saves Rs {first} in the first month and increases her saving by Rs {step} every month. How much does she save in the {months}th month, and how much in total after {months} months?",
                            f"In month {months}: {first} + {months - 1} × {step} = Rs {first + (months - 1) * step}. Total: {months}/2 × [{2 * first} + {(months - 1) * step}] = Rs {total}.",
                            "2 for identifying the AP, 3 for the nth term, 3 for the sum.", difficulty="hard", chapter="Arithmetic Progressions", topic="Sum of n terms"))
    for distance in (20, 30, 40, 50):
        out.append(_written("long", 8, f"From a point on the ground {distance} m from the foot of a tower, the angle of elevation of the top of the tower is 60°. Draw a labelled figure and find the height of the tower.",
                            f"tan 60° = h/{distance}, so h = {distance}√3 m ≈ {round(distance * math.sqrt(3), 2)} m.",
                            "2 for the figure, 2 for the ratio, 3 for solving, 1 for the units.", difficulty="hard", chapter="Some Applications of Trigonometry", topic="Heights and distances"))
    for digits_sum, diff in [(9, 27), (11, 9), (12, 18), (10, 36)]:
        # A two-digit number whose digits add to digits_sum; reversing the digits changes it by diff.
        for tens in range(1, 10):
            ones = digits_sum - tens
            if 0 <= ones <= 9 and 9 * (tens - ones) == diff:
                break
        number = 10 * tens + ones
        out.append(_written("long", 8, f"The sum of the digits of a two-digit number is {digits_sum}. When the digits are reversed, the number decreases by {diff}. Form a pair of linear equations and find the number.",
                            f"Let tens digit = x, ones digit = y. x + y = {digits_sum} and 9(x - y) = {diff}, so x - y = {diff // 9}. Hence x = {tens}, y = {ones}; the number is {number}.",
                            "3 for the two equations, 3 for solving, 2 for the number and the check.", difficulty="hard", chapter="Pair of Linear Equations", topic="Word problems"))
    rng.shuffle(out)
    return out


SCIENCE10 = [
    _mcq("Which of the following is a displacement reaction?", "Fe + CuSO4 → FeSO4 + Cu", ["CaCO3 → CaO + CO2", "2H2 + O2 → 2H2O", "AgNO3 + NaCl → AgCl + NaNO3"], difficulty="easy", chapter="Chemical Reactions and Equations", topic="Types of reactions"),
    _mcq("The pH of pure water at room temperature is", "7", ["0", "14", "5"], difficulty="easy", chapter="Acids, Bases and Salts", topic="pH scale"),
    _mcq("Baking soda is the common name of", "Sodium hydrogen carbonate", ["Sodium carbonate", "Calcium oxychloride", "Sodium chloride"], difficulty="easy", chapter="Acids, Bases and Salts", topic="Common salts"),
    _mcq("The site of photosynthesis in a plant cell is the", "Chloroplast", ["Mitochondrion", "Nucleus", "Ribosome"], difficulty="easy", chapter="Life Processes", topic="Nutrition"),
    _mcq("The breakdown of glucose to pyruvate takes place in the", "Cytoplasm", ["Mitochondria", "Chloroplast", "Nucleus"], difficulty="medium", chapter="Life Processes", topic="Respiration"),
    _mcq("The image formed by a plane mirror is", "Virtual and erect", ["Real and inverted", "Real and erect", "Virtual and inverted"], difficulty="easy", chapter="Light - Reflection and Refraction", topic="Mirrors"),
    _mcq("A convex lens of focal length 20 cm has a power of", "+5 D", ["-5 D", "+0.05 D", "+20 D"], difficulty="medium", chapter="Light - Reflection and Refraction", topic="Lenses"),
    _mcq("The SI unit of electric resistance is the", "Ohm", ["Volt", "Ampere", "Watt"], difficulty="easy", chapter="Electricity", topic="Ohm's law"),
    _mcq("Two 6 Ω resistors joined in parallel have an equivalent resistance of", "3 Ω", ["12 Ω", "6 Ω", "1.5 Ω"], difficulty="medium", chapter="Electricity", topic="Resistance in series and parallel"),
    _mcq("A current of 0.5 A flows through a 10 Ω resistor. The potential difference across it is", "5 V", ["20 V", "0.05 V", "10.5 V"], difficulty="medium", chapter="Electricity", topic="Ohm's law"),
    _written("short", 3, "Balance the equation Fe + H2O → Fe3O4 + H2 and state the type of reaction.", "3Fe + 4H2O → Fe3O4 + 4H2. It is a displacement (redox) reaction.", "2 for balancing, 1 for the type.", difficulty="medium", chapter="Chemical Reactions and Equations", topic="Balancing equations"),
    _written("short", 3, "Why does a milkman add a small amount of baking soda to fresh milk?", "It makes the milk slightly alkaline so it does not sour (turn acidic) as quickly.", "2 for the reason, 1 for naming alkalinity.", difficulty="easy", chapter="Acids, Bases and Salts", topic="Common salts"),
    _written("short", 3, "State any three differences between aerobic and anaerobic respiration.", "Aerobic uses oxygen, anaerobic does not; aerobic gives CO2 and water, anaerobic gives ethanol and CO2 (or lactic acid); aerobic releases much more energy.", "1 mark for each difference.", difficulty="medium", chapter="Life Processes", topic="Respiration"),
    _written("short", 3, "An object 4 cm high is placed 15 cm from a concave mirror of focal length 10 cm. Find the position of the image.", "1/v + 1/u = 1/f with u = -15, f = -10 gives v = -30 cm: the image is 30 cm in front of the mirror, real and inverted.", "1 for the formula, 1 for substitution, 1 for the answer with sign.", difficulty="hard", chapter="Light - Reflection and Refraction", topic="Mirrors"),
    _written("long", 8, "Explain with a labelled diagram how three resistors R1, R2 and R3 connected in series give an equivalent resistance R = R1 + R2 + R3. Find the current when 2 Ω, 3 Ω and 5 Ω are connected in series to a 10 V battery.", "In series the same current flows and the voltages add: V = IR1 + IR2 + IR3, so R = R1 + R2 + R3. Here R = 10 Ω and I = 10/10 = 1 A.", "2 for the diagram, 3 for the derivation, 3 for the numerical.", difficulty="hard", chapter="Electricity", topic="Resistance in series and parallel"),
    _written("long", 8, "Describe the process of nutrition in human beings, from ingestion to egestion, naming the role of each organ.", "Mouth (chewing, salivary amylase), oesophagus (peristalsis), stomach (HCl, pepsin), small intestine (bile, pancreatic juice, absorption by villi), large intestine (water absorption), anus (egestion).", "1 mark per stage, 2 for a clear sequence.", difficulty="hard", chapter="Life Processes", topic="Nutrition"),
]

SCIENCE8 = [
    _mcq("The process of loosening and turning the soil is called", "Tilling", ["Sowing", "Harvesting", "Irrigation"], difficulty="easy", chapter="Crop Production and Management", topic="Agricultural practices"),
    _written("short", 3, "Why is it necessary to sow seeds at the correct depth and distance?", "Seeds sown too deep may not germinate and too close compete for light, water and nutrients; correct spacing gives each plant enough of these.", difficulty="easy", chapter="Crop Production and Management", topic="Agricultural practices"),
    _mcq("Pressure is defined as", "Force per unit area", ["Force × area", "Mass per unit volume", "Work per unit time"], difficulty="easy", chapter="Force and Pressure", topic="Pressure"),
    _written("short", 3, "Why are the straps of a school bag made wide?", "A wider strap spreads the weight over a larger area, so the pressure on the shoulder is less.", difficulty="easy", chapter="Force and Pressure", topic="Pressure"),
]

ENGLISH8 = [
    _mcq("Choose the correct passive form: 'The teacher praised the student.'", "The student was praised by the teacher.", ["The student is praised by the teacher.", "The student praised the teacher.", "The teacher was praised by the student."], difficulty="easy", chapter="Grammar", topic="Voice"),
    _written("short", 3, "Rewrite the paragraph in the past perfect tense: 'Rina finishes her homework. Then she goes to play.'", "Rina had finished her homework before she went to play.", difficulty="medium", chapter="Grammar", topic="Tenses"),
]
