"""The FDA "Big 9" major food allergens and the Jev questions that detect them.

Each allergen becomes one `Noul` question in a single batched System One call.

Question wording matters more than anything else in this file. Jev answers the
question you wrote, not the one you meant, so every question spells out:

  * `instructions` - the claim being evaluated, always phrased around whether a
    person allergic to X would react, not merely whether the word X appears.
  * `criteria.true`  - what counts as yes, including derived and "hidden" names
    and dishes that conventionally contain the allergen.
  * `criteria.false` - what counts as no, explicitly including free-from
    substitutes, which naive keyword matching gets backwards.
"""

from typesafe_sdk import Noul

# Display order is the 3x3 grid, read left to right, top to bottom.
ALLERGENS = (
    {
        "id": "milk",
        "label": "Milk",
        "instructions": (
            "This recipe contains milk or any milk-derived ingredient, such that a "
            "person with a milk allergy would react to eating it."
        ),
        "true": (
            "Any dairy is present, including butter, ghee, cream, half-and-half, "
            "cheese of any kind, yogurt, sour cream, buttermilk, condensed or "
            "evaporated milk, milk powder, custard, ice cream, whey, casein, "
            "caseinate, lactose, or curds. Also yes when a named dish or component "
            "conventionally contains dairy, such as bechamel, alfredo sauce, or "
            "buttercream, even if no dairy ingredient is listed separately."
        ),
        "false": (
            "No dairy is present. Deliberately dairy-free substitutes count as no: "
            "vegan butter, margarine labeled dairy-free, oat, soy, almond, coconut "
            "or rice milk, coconut cream, and nutritional yeast are not milk."
        ),
    },
    {
        "id": "egg",
        "label": "Egg",
        "instructions": (
            "This recipe contains egg or any egg-derived ingredient, such that a "
            "person with an egg allergy would react to eating it."
        ),
        "true": (
            "Any egg is present, including whole eggs, yolks, whites, dried or "
            "powdered egg, albumin, meringue, mayonnaise, aioli, hollandaise, "
            "custard, egg wash, or an egg glaze brushed on before baking."
        ),
        "false": (
            "No egg is present. Egg substitutes count as no: flax or chia eggs, "
            "commercial egg replacer, aquafaba, applesauce or mashed banana used as "
            "a binder. Eggplant is not egg."
        ),
    },
    {
        "id": "fish",
        "label": "Fish",
        "instructions": (
            "This recipe contains finned fish or any fish-derived ingredient, such "
            "that a person with a fish allergy would react to eating it."
        ),
        "true": (
            "Any finned fish is present, including salmon, tuna, cod, halibut, "
            "haddock, bass, trout, snapper, sardines, anchovies, and their derived "
            "ingredients: fish sauce, nam pla, nuoc mam, Worcestershire sauce, "
            "Caesar dressing, fish stock, dashi, bonito flakes, surimi, or caviar."
        ),
        "false": (
            "No finned fish is present. Shellfish alone does not count here, and "
            "neither do anchovy-free Worcestershire or vegan fish sauce."
        ),
    },
    {
        "id": "shellfish",
        "label": "Crustacean Shellfish",
        "instructions": (
            "This recipe contains crustacean shellfish or any crustacean-derived "
            "ingredient, such that a person with a crustacean shellfish allergy "
            "would react to eating it."
        ),
        "true": (
            "Any crustacean is present, including shrimp, prawns, crab, lobster, "
            "crawfish, crayfish, langoustine, and krill, or ingredients made from "
            "them such as shrimp paste, crab stock, lobster bisque, or surimi / "
            "imitation crab."
        ),
        "false": (
            "No crustacean is present. Molluscs alone - clams, mussels, oysters, "
            "scallops, squid, octopus - are not crustaceans and are not one of the "
            "nine major US allergens, so they count as no here. Finned fish alone "
            "also counts as no."
        ),
    },
    {
        "id": "tree_nuts",
        "label": "Tree Nuts",
        "instructions": (
            "This recipe contains tree nuts or any tree-nut-derived ingredient, "
            "such that a person with a tree nut allergy would react to eating it."
        ),
        "true": (
            "Any tree nut is present, including almond, walnut, pecan, cashew, "
            "pistachio, hazelnut or filbert, macadamia, Brazil nut, pine nut, and "
            "chestnut, or products made from them: nut butters, nut flours or meal, "
            "marzipan, praline, nutella, frangipane, almond extract, nut milks, and "
            "pesto made with pine nuts or cashews."
        ),
        "false": (
            "No tree nut is present. Peanuts are legumes and count as no here. "
            "Nutmeg, water chestnut, coconut, and shea are not tree nuts for this "
            "purpose, and a word merely containing the letters 'nut', such as "
            "doughnut, does not count."
        ),
    },
    {
        "id": "peanuts",
        "label": "Peanuts",
        "instructions": (
            "This recipe contains peanuts or any peanut-derived ingredient, such "
            "that a person with a peanut allergy would react to eating it."
        ),
        "true": (
            "Peanuts are present in any form, including peanut butter, peanut "
            "flour, peanut oil, groundnuts, monkey nuts, beer nuts, satay sauce, and "
            "many Thai, Szechuan, and West African sauces that conventionally use "
            "peanut even when not itemized."
        ),
        "false": (
            "No peanut is present. Tree nuts alone count as no, and so do "
            "deliberate peanut-free substitutes such as sunflower seed butter."
        ),
    },
    {
        "id": "wheat",
        "label": "Wheat",
        "instructions": (
            "This recipe contains wheat or any wheat-derived ingredient, such that "
            "a person with a wheat allergy would react to eating it."
        ),
        "true": (
            "Wheat is present in any form, including all-purpose, bread, cake, "
            "pastry or whole wheat flour, semolina, durum, farina, spelt, farro, "
            "einkorn, kamut, bulgur, couscous, seitan, vital wheat gluten, panko or "
            "other breadcrumbs, most pasta, soy sauce brewed with wheat, and the "
            "flour in a roux or a pastry crust."
        ),
        "false": (
            "No wheat is present. Certified gluten-free flours and blends, almond "
            "or coconut or rice flour, cornstarch, oats, buckwheat, quinoa, and "
            "tamari labeled wheat-free all count as no."
        ),
    },
    {
        "id": "soy",
        "label": "Soybeans",
        "instructions": (
            "This recipe contains soybeans or any soy-derived ingredient, such that "
            "a person with a soy allergy would react to eating it."
        ),
        "true": (
            "Soy is present in any form, including soy sauce, shoyu, tamari, miso, "
            "tofu, tempeh, edamame, natto, soy milk, soy flour, textured vegetable "
            "protein, and soybean oil or soy lecithin when listed."
        ),
        "false": (
            "No soy is present. Coconut aminos, chickpea miso, and other "
            "soy-free substitutes count as no."
        ),
    },
    {
        "id": "sesame",
        "label": "Sesame",
        "instructions": (
            "This recipe contains sesame or any sesame-derived ingredient, such "
            "that a person with a sesame allergy would react to eating it."
        ),
        "true": (
            "Sesame is present in any form, including sesame seeds, sesame oil, "
            "toasted sesame oil, tahini, halva, gomashio, za'atar, and the seeds on "
            "a burger bun or bagel. Also yes when a named component conventionally "
            "contains sesame, such as hummus or baba ganoush."
        ),
        "false": (
            "No sesame is present. Other seeds - sunflower, poppy, flax, chia, "
            "pumpkin - are not sesame and count as no."
        ),
    },
)

ALLERGEN_IDS = tuple(a["id"] for a in ALLERGENS)


def build_questions() -> dict[str, Noul]:
    """One Noul per allergen, sent as a single batched System One request."""
    return {
        a["id"]: Noul(
            instructions=a["instructions"],
            criteria={"true": a["true"], "false": a["false"]},
        )
        for a in ALLERGENS
    }


# ---------------------------------------------------------------------------
# Meat and poultry.
#
# These are NOT FDA major allergens. They are dietary restrictions, and they
# are asked in their own separate request so the nine allergen questions above
# stay byte-identical and their calibration is untouched.
# ---------------------------------------------------------------------------

MEATS = (
    {
        "id": "beef",
        "label": "Beef",
        "instructions": (
            "This recipe contains beef, veal, or an ingredient derived from cattle, "
            "such that someone avoiding beef would not eat it."
        ),
        "true": (
            "Beef or veal is present in any form, including ground beef, steak, "
            "brisket, chuck, short rib, oxtail, corned beef, pastrami, bresaola, "
            "beef broth or stock, beef bouillon, demi-glace, suet, and tallow. "
            "Also yes when a named dish conventionally uses beef, such as bolognese, "
            "beef bourguignon, or a classic burger patty."
        ),
        "false": (
            "No cattle-derived ingredient is present. Answer no for a recipe with "
            "no meat in it at all. Dairy comes from cattle but is NOT beef: butter, "
            "ghee, cream, milk, and cheese all count as no here. Eggs, seafood, "
            "vegetable shortening, plant-based beef substitutes, mushroom or "
            "vegetable broth, and other meats alone all count as no."
        ),
    },
    {
        "id": "chicken",
        "label": "Chicken",
        "instructions": (
            "This recipe contains chicken or other poultry, or an ingredient derived "
            "from poultry, such that someone avoiding chicken would not eat it."
        ),
        "true": (
            "Chicken or other poultry is present in any form, including breast, "
            "thigh, wings, whole bird, ground chicken, turkey, duck, chicken broth "
            "or stock, bouillon, schmaltz, and chicken fat. Also yes when a named "
            "dish conventionally uses poultry, such as chicken piccata or coq au vin."
        ),
        "false": (
            "No poultry is present. Answer no for a recipe with no meat in it at "
            "all. Eggs are NOT chicken and count as no on their own, however many "
            "are used. Dairy, seafood, plant-based chicken substitutes, and "
            "vegetable broth all count as no."
        ),
    },
    {
        "id": "pork",
        "label": "Pork",
        "instructions": (
            "This recipe contains pork or an ingredient derived from pigs, such that "
            "someone avoiding pork would not eat it."
        ),
        "true": (
            "Pork is present in any form, including bacon, ham, prosciutto, "
            "pancetta, guanciale, lardo, chorizo, salami, most Italian sausage, "
            "pork shoulder or belly, ribs, lard, and pork stock. Also yes when a "
            "named dish conventionally uses pork, such as carbonara or amatriciana."
        ),
        "false": (
            "No pig-derived ingredient is present. Answer no for a recipe with no "
            "meat in it at all. Turkey bacon, beef sausage, dairy, eggs, and "
            "plant-based substitutes all count as no."
        ),
    },
)

MEAT_IDS = tuple(m["id"] for m in MEATS)


def build_meat_questions() -> dict[str, Noul]:
    """Sent as a separate request from the allergen questions, never merged."""
    return {
        m["id"]: Noul(
            instructions=m["instructions"],
            criteria={"true": m["true"], "false": m["false"]},
        )
        for m in MEATS
    }
