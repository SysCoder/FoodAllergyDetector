"""A vocabulary of common ingredients, used to propose attribution candidates.

This list does NOT decide anything. It never sets an allergen status and it is
never consulted for detection - Jev sees the raw recipe text for that. Its only
job is to turn a blob of recipe text into a short list of clean ingredient names
to offer as `Choice` options, so a source reads "ricotta" instead of the whole
line it happened to sit on.

Because it is only a candidate generator, gaps are cheap: an ingredient missing
from this list simply falls back to line-based segmentation. It does not cause a
missed allergen.

Multi-word entries are matched before single words, so "coconut milk" wins over
"milk" and "almond flour" wins over "flour".

The bulk of the terms in `vocabulary.json` are derived from the Open Food Facts
ingredients taxonomy (https://openfoodfacts.org), used and redistributed under
the Open Database License v1.0. Open Food Facts does not guarantee the accuracy
of its data. See "Data and attribution" in README.md.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

# Ordered loosely by category. Duplicates across categories are harmless.
VOCABULARY: tuple[str, ...] = (
    # --- dairy -------------------------------------------------------------
    "whole milk", "skim milk", "buttermilk", "evaporated milk", "condensed milk",
    "milk powder", "milk", "heavy cream", "sour cream", "whipping cream",
    "half and half", "half-and-half", "cream cheese", "creme fraiche", "cream",
    "unsalted butter", "salted butter", "clarified butter", "brown butter",
    "butter", "ghee", "yogurt", "greek yogurt", "kefir", "custard", "ice cream",
    "parmesan", "parmigiano", "pecorino", "mozzarella", "ricotta", "mascarpone",
    "cheddar", "gruyere", "feta", "goat cheese", "blue cheese", "provolone",
    "monterey jack", "cotija", "queso fresco", "paneer", "halloumi",
    "cream of tartar", "cheese", "whey", "casein", "lactose", "curds",
    # --- egg ---------------------------------------------------------------
    "egg yolk", "egg yolks", "egg white", "egg whites", "egg wash", "large eggs",
    "eggs", "egg", "mayonnaise", "mayo", "aioli", "hollandaise", "meringue",
    "albumin",
    # --- fish & shellfish --------------------------------------------------
    "fish sauce", "anchovy", "anchovies", "salmon", "tuna", "cod", "halibut",
    "haddock", "sea bass", "trout", "snapper", "mackerel", "sardines",
    "worcestershire sauce", "worcestershire", "caesar dressing", "fish stock",
    "dashi", "bonito", "surimi", "imitation crab", "caviar", "roe",
    "shrimp", "prawns", "prawn", "crab", "lobster", "crawfish", "crayfish",
    "langoustine", "krill", "shrimp paste", "clams", "mussels", "oysters",
    "scallops", "squid", "calamari", "octopus",
    # --- tree nuts & peanuts ----------------------------------------------
    "almond flour", "almond milk", "almond extract", "sliced almonds", "almonds",
    "almond", "walnuts", "walnut", "pecans", "pecan", "cashews", "cashew",
    "pistachios", "pistachio", "hazelnuts", "hazelnut", "macadamia",
    "brazil nuts", "pine nuts", "chestnuts", "marzipan", "praline", "nutella",
    "frangipane", "pesto", "nut butter",
    "peanut butter", "peanut oil", "peanuts", "peanut", "groundnuts",
    "satay sauce", "satay",
    # --- wheat & grains ----------------------------------------------------
    "all-purpose flour", "all purpose flour", "bread flour", "cake flour",
    "pastry flour", "whole wheat flour", "self-rising flour", "gluten-free flour",
    "almond flour", "coconut flour", "rice flour", "flour", "semolina", "durum",
    "farina", "spelt", "farro", "einkorn", "kamut", "bulgur", "couscous",
    "seitan", "vital wheat gluten", "panko", "breadcrumbs", "bread crumbs",
    "croutons", "croissants", "croissant", "puff pastry", "phyllo", "filo",
    "pasta", "spaghetti", "linguine", "penne", "lasagna noodles", "egg noodles",
    "rice noodles", "noodles", "tortillas", "pita", "baguette", "brioche",
    "oats", "rolled oats", "barley", "rye", "quinoa", "buckwheat", "cornstarch",
    "rice", "bread",
    # --- soy ---------------------------------------------------------------
    "soy sauce", "shoyu", "tamari", "miso", "tofu", "tempeh", "edamame", "natto",
    "soy milk", "soy flour", "soybean oil", "soy lecithin", "textured vegetable protein",
    "coconut aminos",
    # --- sesame ------------------------------------------------------------
    "sesame oil", "toasted sesame oil", "sesame seeds", "sesame", "tahini",
    "halva", "gomashio", "za'atar", "zaatar", "hummus", "baba ganoush",
    # --- meat & poultry ----------------------------------------------------
    "ground beef", "beef chuck", "beef brisket", "brisket", "short rib",
    "short ribs", "oxtail", "corned beef", "pastrami", "steak", "sirloin",
    "ribeye", "veal", "beef broth", "beef stock", "beef bouillon", "tallow",
    "suet", "demi-glace", "beef",
    "chicken breast", "chicken thighs", "chicken thigh", "ground chicken",
    "rotisserie chicken", "chicken broth", "chicken stock", "chicken bouillon",
    "schmaltz", "turkey", "duck", "chicken",
    "bacon", "pancetta", "guanciale", "prosciutto", "ham", "chorizo", "salami",
    "italian sausage", "breakfast sausage", "sausage", "pork shoulder",
    "pork belly", "pork chops", "pork loin", "lard", "pork",
    "lamb", "gelatin",
    # --- produce, aromatics, pantry ---------------------------------------
    "olive oil", "vegetable oil", "canola oil", "coconut oil", "sunflower oil",
    "coconut milk", "coconut cream", "coconut",
    "onion", "onions", "shallot", "shallots", "garlic", "ginger", "lemongrass",
    "scallions", "green onions", "leeks", "celery", "carrots", "carrot",
    "tomato", "tomatoes", "marinara", "marinara sauce", "tomato paste",
    "potatoes", "potato", "mushrooms", "spinach", "kale", "broccoli",
    "cauliflower", "bell pepper", "eggplant", "zucchini", "cucumber",
    "lettuce", "romaine", "cabbage", "avocado", "corn", "peas", "green beans",
    "chickpeas", "black beans", "kidney beans", "lentils", "beans",
    "lemon juice", "lime juice", "lemon", "lime", "orange", "apple", "banana",
    "mango", "strawberries", "blueberries", "raspberries", "pineapple",
    "vegetable broth", "vegetable stock", "stock", "broth", "white wine",
    "red wine", "vinegar", "balsamic", "rice vinegar",
    "sugar", "brown sugar", "powdered sugar", "coconut sugar", "honey",
    "maple syrup", "molasses", "vanilla extract", "vanilla",
    "baking powder", "baking soda", "yeast", "salt", "black pepper", "pepper",
    "cumin", "paprika", "turmeric", "cinnamon", "nutmeg", "oregano", "basil",
    "parsley", "cilantro", "thyme", "rosemary", "bay leaf", "chili flakes",
    "curry powder", "tamarind", "palm sugar", "bean sprouts", "nutritional yeast",
    "chocolate", "cocoa", "dark chocolate", "chocolate chips",
)

# ---------------------------------------------------------------------------
# Allergen alternate and "hidden" names.
#
# Compiled from published food-allergy label-reading guidance (FASTOIT's
# alternate-names list, plus FDA label guidance) and kept here rather than in
# vocabulary.json because these are the terms most worth reviewing by hand:
# they are exactly the names a recipe uses when it does NOT say "milk".
#
# Being in this list asserts nothing about allergens. Jev still decides. These
# only make sure the term can be offered as a source candidate.
# ---------------------------------------------------------------------------

ALLERGEN_ALIASES: tuple[str, ...] = (
    # milk
    "sodium caseinate", "calcium caseinate", "caseinate", "caseinates",
    "rennet casein", "lactalbumin", "lactoglobulin", "lactoferrin", "lactulose",
    "milk protein hydrolysate", "whey protein", "whey powder", "butter fat",
    "butterfat", "butter oil", "artificial butter flavor", "cheese flavor",
    "sour milk solids", "milk solids", "nougat", "pudding", "rennet", "diacetyl",
    "tagatose", "quark", "skyr", "burrata", "curd",
    # egg
    "ovalbumin", "ovovitellin", "globulin", "lysozyme", "egg lecithin",
    "egg solids", "dried egg", "powdered egg", "egg substitute", "eggnog",
    "egg noodles", "silici albuminate",
    # fish and shellfish
    "nam pla", "nuoc mam", "oyster sauce", "fish gelatine", "fish gelatin",
    "fish oil", "fish paste", "shrimp paste", "belacan", "bagoong",
    "barnacle", "crawdad", "ecrevisse", "langouste", "scampi", "tomalley",
    "crevette", "moreton bay bugs", "roe", "ikura", "tobiko", "katsuobushi",
    # tree nuts and peanut
    "gianduja", "nougatine", "nut meal", "nut meat", "nut paste", "nut pieces",
    "almond paste", "artificial nuts", "natural nut extract", "beechnut",
    "butternut", "chinquapin", "ginkgo nut", "hickory nut", "pili nut",
    "nangai nut", "shea nut", "filbert", "goobers", "monkey nuts", "beer nuts",
    "mixed nuts", "ground nuts", "peanut flour", "peanut protein",
    "lupin", "lupine",
    # wheat
    "hydrolyzed wheat protein", "wheat protein isolate", "wheat bran",
    "wheat germ", "wheat germ oil", "wheat grass", "wheat starch", "wheat berries",
    "cracker meal", "cereal extract", "matzo", "matzoh", "matzah", "matzo meal",
    "club wheat", "sprouted wheat", "triticale", "emmer", "freekeh",
    "malt extract", "malt flavoring", "malted barley", "graham flour",
    "enriched flour", "self rising flour", "high gluten flour",
    # soy
    "soy protein isolate", "soy protein concentrate", "hydrolyzed soy protein",
    "soy fiber", "soy grits", "soy nuts", "soy sprouts", "soy yogurt",
    "soy cheese", "soya", "soybeans", "okara", "yuba",
    # sesame
    "benne", "benne seed", "gingelly", "gingelly oil", "sim sim", "tahina",
    "halvah", "sesamol", "sesamum indicum", "til",
    # generic hidden vectors worth surfacing as candidates
    "natural flavoring", "natural flavouring", "artificial flavoring",
    "hydrolyzed vegetable protein", "hydrolyzed plant protein",
    "lecithin", "emulsifier", "brewer's yeast", "starch", "modified food starch",
    "vegetable broth", "bouillon", "seasoning", "spice blend",
)

def _load_bulk() -> set[str]:
    """Terms harvested from the Open Food Facts ingredients taxonomy.

    Product-label oriented, so it is strong on manufactured and derived names
    ("sodium caseinate", "malt extract") and weaker on home-cooking phrasing,
    which is what VOCABULARY above covers. The two are unioned, not swapped.
    """
    path = Path(__file__).resolve().parent / "vocabulary.json"
    try:
        with path.open(encoding="utf-8") as handle:
            return {str(t).strip().lower() for t in json.load(handle) if str(t).strip()}
    except (OSError, ValueError):
        # A missing or broken data file degrades to the curated list; it must
        # never take the app down, since this is only candidate generation.
        return set()


ALL_TERMS = {t.lower() for t in VOCABULARY} | {t.lower() for t in ALLERGEN_ALIASES} | _load_bulk()

# Longest first so "coconut milk" is consumed before "milk" can match inside it.
_ORDERED = sorted(ALL_TERMS, key=len, reverse=True)
_PATTERN = re.compile(
    r"(?<![\w-])(" + "|".join(re.escape(t) for t in _ORDERED) + r")(?![\w-])",
    re.IGNORECASE,
)

MAX_MATCHES = 60


def find(recipe: str) -> list[str]:
    """Return the ingredient terms present in the recipe, in order of appearance.

    Matching is word-boundary anchored, so "nutmeg" never matches "nut" and
    "eggplant" never matches "egg". Overlapping matches are resolved by the
    longest term, because `re` consumes the alternation greedily in the order
    given and the pattern is built longest-first.
    """
    found: list[str] = []
    seen: set[str] = set()
    for match in _PATTERN.finditer(recipe):
        # Preserve the recipe's own casing for display.
        surface = match.group(1)
        key = surface.lower()
        if key in seen:
            continue
        seen.add(key)
        found.append(surface)
        if len(found) >= MAX_MATCHES:
            break
    return found
