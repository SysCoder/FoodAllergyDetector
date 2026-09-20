"""Offline keyword detection, used only when Jev cannot be reached.

This is deliberately a second-class citizen, but not in the way you would
expect. Its vocabulary carries dish names as well as ingredients, so it does
catch some allergens that are never written out - "carbonara" is mapped to egg
and pork, "hummus" to sesame. That makes it read as closer to the real detector
than it is.

The gap shows up on dishes nobody happened to add to the list - moussaka,
okonomiyaki, bibimbap, baklava, tarte tatin, pasteis de nata, beef wellington -
where it finds nothing at all. Even carbonara is only half known here: the egg
and the pork are mapped, the dairy is not.

So the failure mode is not "cannot see implied allergens". It is "sees the
implied allergens someone remembered to write down, and goes silent on the
rest" - which is harder to notice, because the hits it does get make it look
like it is working.

So the rules here are:

  * A keyword hit is reported as detected.
  * A hit sitting next to a free-from phrase ("dairy-free butter") is reported
    as POSSIBLE, not cleared. In a degraded mode the safe direction is to
    over-flag and make the user check.
  * A miss is never described as "not found". The caller renders a different,
    weaker word for it, because absence of a keyword is not evidence of absence.

The vocabulary in ingredients.py is not allergen-tagged, so this keeps its own
per-allergen map.
"""

from __future__ import annotations

import re

from allergens import ALLERGENS, MEATS

TERMS: dict[str, tuple[str, ...]] = {
    "milk": (
        "milk", "butter", "buttered", "ghee", "cream", "creamy", "half and half",
        "half-and-half", "cheese", "cheddar", "parmesan", "parmigiano", "pecorino",
        "mozzarella", "ricotta", "mascarpone", "feta", "gruyere", "provolone",
        "paneer", "halloumi", "burrata", "yogurt", "kefir", "custard", "ice cream",
        "whey", "casein", "caseinate", "caseinates", "lactose", "curds", "quark",
        "skyr", "buttermilk", "sour cream", "creme fraiche", "lactalbumin",
        "nougat", "butterfat", "dairy", "alfredo", "bechamel", "buttercream",
    ),
    "egg": (
        "egg", "eggs", "egg white", "egg whites", "egg yolk", "egg yolks",
        "albumin", "ovalbumin", "globulin", "lysozyme", "mayonnaise", "mayo",
        "aioli", "hollandaise", "meringue", "eggnog", "surimi", "egg noodles",
        "egg wash", "frittata", "omelette", "omelet", "custard", "carbonara",
    ),
    "fish": (
        "fish", "salmon", "tuna", "cod", "halibut", "haddock", "sea bass",
        "trout", "snapper", "mackerel", "sardine", "sardines", "anchovy",
        "anchovies", "fish sauce", "nam pla", "nuoc mam", "worcestershire",
        "caesar dressing", "dashi", "bonito", "katsuobushi", "surimi", "caviar",
        "roe", "fish stock", "fish oil", "ceviche",
    ),
    "shellfish": (
        "shrimp", "prawn", "prawns", "crab", "lobster", "crawfish", "crayfish",
        "langoustine", "krill", "scampi", "shrimp paste", "imitation crab",
        "surimi", "barnacle", "crevette", "bisque",
    ),
    "tree_nuts": (
        "almond", "almonds", "walnut", "walnuts", "pecan", "pecans", "cashew",
        "cashews", "pistachio", "pistachios", "hazelnut", "hazelnuts", "filbert",
        "macadamia", "brazil nut", "pine nut", "pine nuts", "chestnut",
        "marzipan", "praline", "nutella", "frangipane", "gianduja", "pesto",
        "nut butter", "almond flour", "almond milk", "almond extract", "amaretto",
    ),
    "peanuts": (
        "peanut", "peanuts", "peanut butter", "peanut flour", "peanut oil",
        "groundnut", "groundnuts", "monkey nuts", "beer nuts", "goobers", "satay",
    ),
    "wheat": (
        "wheat", "flour", "all-purpose flour", "bread flour", "semolina", "durum",
        "farina", "spelt", "farro", "einkorn", "kamut", "emmer", "triticale",
        "bulgur", "couscous", "seitan", "panko", "breadcrumbs", "bread crumbs",
        "croutons", "croissant", "croissants", "pasta", "spaghetti", "linguine",
        "penne", "macaroni", "lasagna", "noodles", "bread", "baguette", "brioche",
        "phyllo", "puff pastry", "matzo", "malt extract", "graham flour",
        "tortilla", "roux", "pastry",
    ),
    "soy": (
        "soy", "soya", "soybean", "soybeans", "soy sauce", "shoyu", "tamari",
        "miso", "tofu", "tempeh", "edamame", "natto", "soy milk", "soy flour",
        "soy lecithin", "soybean oil", "textured vegetable protein", "okara", "yuba",
    ),
    "sesame": (
        "sesame", "sesame oil", "sesame seeds", "tahini", "tahina", "halva",
        "halvah", "gomashio", "za'atar", "zaatar", "benne", "gingelly", "hummus",
        "baba ganoush",
    ),
    "beef": (
        "beef", "steak", "brisket", "veal", "oxtail", "corned beef", "pastrami",
        "sirloin", "ribeye", "short rib", "short ribs", "ground beef",
        "beef broth", "beef stock", "tallow", "suet", "bolognese", "bourguignon",
    ),
    "chicken": (
        "chicken", "poultry", "turkey", "duck", "chicken broth", "chicken stock",
        "schmaltz", "rotisserie",
    ),
    "pork": (
        "pork", "bacon", "ham", "prosciutto", "pancetta", "guanciale", "chorizo",
        "salami", "sausage", "lard", "pork belly", "pork shoulder", "carbonara",
    ),
}

# A free-from phrase near a hit downgrades it to "possible" rather than clearing
# it. "turkey bacon" is here because a pork keyword next to turkey is not pork.
NEGATORS = (
    "free", "dairy-free", "gluten-free", "non-dairy", "nondairy", "vegan",
    "substitute", "replacer", "plant-based", "plant based", "imitation",
    "alternative", "without", "meatless", "turkey", "veggie", "mock",
)

# "turkey" negates pork ("turkey bacon") but must not negate poultry itself.
NEGATOR_EXCEPTIONS: dict[str, frozenset[str]] = {"chicken": frozenset({"turkey"})}

NEGATION_WINDOW_BEFORE = 28
NEGATION_WINDOW_AFTER = 18

_LABELS = {a["id"]: a["label"] for a in ALLERGENS + MEATS}
_PATTERNS = {
    key: re.compile(
        r"(?<![\w-])(" + "|".join(re.escape(t) for t in sorted(terms, key=len, reverse=True)) + r")(?![\w-])",
        re.IGNORECASE,
    )
    for key, terms in TERMS.items()
}


def detect(recipe: str, ids: tuple[str, ...]) -> list[dict]:
    """Keyword-match one group. Returns rows shaped like the Jev path's rows."""
    results = []
    for item_id in ids:
        pattern = _PATTERNS.get(item_id)
        negators = [n for n in NEGATORS if n not in NEGATOR_EXCEPTIONS.get(item_id, ())]
        hit, negated_hit = None, None
        if pattern:
            for match in pattern.finditer(recipe):
                window = recipe[
                    max(0, match.start() - NEGATION_WINDOW_BEFORE) : match.end() + NEGATION_WINDOW_AFTER
                ].lower()
                if any(n in window for n in negators):
                    negated_hit = negated_hit or match.group(1)
                    continue
                hit = match.group(1)
                break

        if hit:
            status, matched = "detected", hit
        elif negated_hit:
            # Matched, but a free-from phrase was nearby. Do not clear it.
            status, matched = "possible", negated_hit
        else:
            status, matched = "clear", None

        results.append(
            {
                "id": item_id,
                "label": _LABELS[item_id],
                "probability": None,
                "status": status,
                "source": {"texts": [matched], "implied": False, "confidence": None}
                if matched
                else None,
            }
        )
    return results
