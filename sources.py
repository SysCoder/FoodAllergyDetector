"""Ingredient attribution - which ingredient triggered a detection.

Jev cannot generate text, so the source cannot simply be asked for. Instead a
short list of candidate ingredients is built from the recipe and each flagged
item gets a `Choice` over that list, which Jev *can* answer.

Candidates come from two places, in order of preference:

  1. The ingredient vocabulary in `ingredients.py`, matched against the recipe.
     Clean ingredient names concentrate the answer far better than raw recipe
     lines do, which otherwise leave an ambiguous case flapping between a line
     and "implied" between runs.
  2. Line-based segmentation, used when the vocabulary finds too little. This
     is what keeps an ingredient that is missing from the vocabulary from
     losing its attribution entirely.

This all runs as a separate follow-up request. The allergen questions and the
state they are sent with are untouched, so detection accuracy is unaffected by
anything in this module.
"""

from __future__ import annotations

import re

from typesafe_sdk import Choice

from ingredients import find

# Jev supports a cardinality up to 255; stay well under it.
MAX_SEGMENTS = 120
MIN_SEGMENT_CHARS = 3

# Fall back to line splitting only when the vocabulary finds nothing at all.
# Even a single match beats a line: on a prose recipe ("spaghetti carbonara")
# the lone "spaghetti" match correctly attributes wheat and lets everything
# else resolve to "implied", where line mode offered the whole sentence as a
# source for egg and pork.
MIN_VOCAB_MATCHES = 1

# Chosen when no candidate is responsible - an allergen implied by a dish name
# ("carbonara", "hummus") rather than itemised. Without this escape hatch Jev is
# forced to blame an unrelated ingredient.
IMPLIED = "__implied__"
IMPLIED_TEXT = (
    "Last resort. Choose this ONLY when not one of the options above is or "
    "contains the item, and it is present only because a named dish, a prepared "
    "component, or a cooking method implies it. If any option above contains the "
    "item, choose that option instead of this one."
)

# An option needs this share of the probability mass to be shown as a source,
# and at most MAX_SOURCES are listed. This is what lets a recipe with two real
# dairy ingredients name both instead of arbitrarily picking one.
MIN_SOURCE_SHARE = 0.15
MAX_SOURCES = 3


def segment(recipe: str) -> dict[str, str]:
    """Split a recipe into candidate lines, the fallback when vocabulary is thin.

    Commas and semicolons both split, with no minimum line length: measured
    against the earlier length-gated version this was equal or better on every
    case, and surplus fragments are simply never chosen by Jev.
    """
    out: dict[str, str] = {}
    seen: set[str] = set()
    for raw_line in recipe.splitlines():
        line = raw_line.strip(" \t-*•")
        if len(line) < MIN_SEGMENT_CHARS:
            continue
        parts = re.split(r"[;,]", line) if re.search(r"[;,]", line) else [line]
        for part in parts:
            text = part.strip()
            key = text.lower()
            if len(text) < MIN_SEGMENT_CHARS or key in seen:
                continue
            seen.add(key)
            out[f"s{len(out)}"] = text
            if len(out) >= MAX_SEGMENTS:
                return out
    return out


def candidates(recipe: str) -> tuple[dict[str, str], str]:
    """Build the option set for attribution. Returns (options, which_source)."""
    matches = find(recipe)
    if len(matches) >= MIN_VOCAB_MATCHES:
        # Vocabulary only. Mixing in raw lines would split the mass between
        # "ricotta" and "15 oz ricotta", which is the failure this replaced.
        return {f"i{n}": text for n, text in enumerate(matches)}, "vocabulary"
    return segment(recipe), "lines"


def build_source_questions(items: list[dict], options: dict[str, str]) -> dict[str, Choice]:
    """One Choice per flagged item, all sent in a single batched request.

    Phrasing matters here. Asking which option is "the main reason X is
    present" invites causal reasoning - on a lasagna it blamed the ricotta for
    egg, since a ricotta filling is bound with egg. Asking which option
    *contains* X fixes that.
    """
    criteria = {**options, IMPLIED: IMPLIED_TEXT}

    def question(label: str) -> Choice:
        return Choice(
            instructions=(
                f"Which one of these ingredients contains {label}, or is made "
                f"from {label}? Pick the option that most directly contains "
                f"{label} itself - the one a person avoiding {label} would have "
                f"to remove. Prefer a real ingredient over the last option "
                f"whenever any of them contains it at all."
            ),
            criteria=criteria,
        )

    return {item["id"]: question(item["label"].lower()) for item in items}


def _tidy(text: str) -> str:
    clean = re.sub(r"\s+", " ", text).strip()
    return clean[:57].rstrip() + "…" if len(clean) > 60 else clean


def resolve(answer, options: dict[str, str]) -> dict | None:
    """Turn a ChoiceAnswer into displayable source text, naming every real
    contributor that holds a meaningful share rather than only the winner."""
    probabilities = answer.probabilities or {}

    if answer.choice == IMPLIED:
        return {
            "texts": [],
            "implied": True,
            "confidence": round(probabilities.get(IMPLIED, answer.confidence), 3),
        }

    ranked = sorted(
        ((key, p) for key, p in probabilities.items() if key != IMPLIED and key in options),
        key=lambda kv: -kv[1],
    )
    picked: list[tuple[str, float]] = []
    for key, probability in ranked:
        if probability < MIN_SOURCE_SHARE:
            break
        # "Beef Lasagna" in the title and "ground beef" in the ingredients are
        # the same source; drop the one contained in the other.
        text = options[key].lower()
        if any(text in options[chosen].lower() for chosen, _ in picked):
            continue
        picked.append((key, probability))
        if len(picked) >= MAX_SOURCES:
            break
    if not picked:
        # Fall back to whatever was chosen, even if the mass was diffuse.
        if answer.choice not in options:
            return None
        picked = [(answer.choice, probabilities.get(answer.choice, answer.confidence))]

    return {
        "texts": [_tidy(options[key]) for key, _ in picked],
        "implied": False,
        "confidence": round(picked[0][1], 3),
    }
