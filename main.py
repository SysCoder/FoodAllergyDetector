"""FoodAllergyDetector - FastAPI server.

Serves the single-page UI and proxies recipe text to TypeSafe's Jev model so the
API key never reaches the browser.

Three separate requests are made, deliberately not merged into one:

  1. Allergens  - the nine FDA major allergens. These questions and the state
                  they are sent with are byte-identical to the calibrated
                  version, so nothing else here can move their numbers.
  2. Meats      - beef, chicken, pork. Not allergens; dietary restrictions.
                  Issued concurrently with (1) as its own request.
  3. Sources    - a follow-up Choice over the recipe's own lines, asked only
                  for items that were already flagged.

Keeping them apart costs one extra round trip and makes the isolation
structural rather than something that has to be re-measured.
"""

from __future__ import annotations

import asyncio
import logging
import os
import weakref
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field
from typesafe_sdk import AsyncTypeSafeClient, TypeSafeError

from allergens import ALLERGEN_IDS, ALLERGENS, MEAT_IDS, MEATS, build_meat_questions, build_questions
from fallback import detect as keyword_detect
from sources import build_source_questions, candidates, resolve

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# Thresholds were tuned against a set of recipes with known answers rather
# than picked by eye. A high cutoff was found to hide allergens that are only
# implied by a dish rather than itemised, so anything at or above DETECTED is
# called and the band below it is surfaced as "possible" instead of being
# silently cleared.
#
# Scores are not perfectly repeatable, so a value sitting right on a boundary
# can land either side of it between runs. The bands are wide enough that this
# does not move a clear result.
DETECTED_THRESHOLD = 0.50
POSSIBLE_THRESHOLD = 0.15

MAX_RECIPE_CHARS = 12_000

logger = logging.getLogger("foodallergydetector")

app = FastAPI(title="FoodAllergyDetector")

# One client per event loop, not one per process.
#
# The SDK client holds an httpx connection pool, and a pool is bound to the
# loop that created it. Under uvicorn there is exactly one loop forever, so a
# process-wide singleton is indistinguishable from this. Under a serverless
# handler that drives the app with its own loop per invocation, a process-wide
# singleton breaks: the pool ends up attached to a closed loop and raises
# "RuntimeError: Event loop is closed" on the next call.
#
# What makes that failure mode nasty is that a client stranded on a closed loop
# still reports is_closed == False, so nothing detects it and the stale client
# keeps being handed out. Keying on the running loop means a new loop simply
# gets a new client instead of inheriting a broken one.
#
# WeakKeyDictionary so finished loops and their clients are collected rather
# than accumulating for the life of the process.
_clients: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, AsyncTypeSafeClient]" = (
    weakref.WeakKeyDictionary()
)
_allergen_questions = build_questions()
_meat_questions = build_meat_questions()


def get_client() -> AsyncTypeSafeClient:
    """Return the client belonging to the running loop, building it on demand."""
    if not os.environ.get("TYPESAFE_API_KEY"):
        raise TypeSafeError("TYPESAFE_API_KEY is not set")

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        # No running loop: nothing can be pooled against, so hand back a
        # client that is not cached rather than poisoning the cache.
        return AsyncTypeSafeClient(timeout=20.0)

    client = _clients.get(loop)
    if client is None:
        client = AsyncTypeSafeClient(timeout=20.0)
        _clients[loop] = client
    return client


class AnalyzeRequest(BaseModel):
    recipe: str = Field(default="")
    # Evaluation runs measure detection only, so they turn off the groups they
    # are not scoring. Both default to on, which is what the page sends.
    include_meats: bool = Field(default=True)
    include_sources: bool = Field(default=True)


def classify(probability: float) -> str:
    if probability >= DETECTED_THRESHOLD:
        return "detected"
    if probability >= POSSIBLE_THRESHOLD:
        return "possible"
    return "clear"


def collect(definitions, response) -> list[dict]:
    results = []
    for item in definitions:
        probability = response.answers[item["id"]].noul
        results.append(
            {
                "id": item["id"],
                "label": item["label"],
                "probability": round(probability, 3),
                "status": classify(probability),
                "source": None,
            }
        )
    return results


@app.get("/api/allergens")
def list_groups() -> dict:
    """The grid definitions, so the page renders its tiles before any analysis."""
    return {
        "allergens": [{"id": a["id"], "label": a["label"]} for a in ALLERGENS],
        "meats": [{"id": m["id"], "label": m["label"]} for m in MEATS],
        "thresholds": {
            "detected": DETECTED_THRESHOLD,
            "possible": POSSIBLE_THRESHOLD,
        },
    }


@app.post("/api/analyze")
async def analyze(payload: AnalyzeRequest) -> JSONResponse:
    recipe = payload.recipe.strip()

    if not recipe:
        return JSONResponse(
            status_code=400,
            content={"error": "empty", "message": "Paste a recipe first."},
        )
    if len(recipe) > MAX_RECIPE_CHARS:
        return JSONResponse(
            status_code=413,
            content={
                "error": "too_long",
                "message": (
                    f"That recipe is {len(recipe):,} characters. "
                    f"Please trim it to {MAX_RECIPE_CHARS:,} or fewer."
                ),
            },
        )

    client = None
    try:
        client = get_client()
        calls = [client.system_one(state=recipe, questions=_allergen_questions)]
        if payload.include_meats:
            calls.append(client.system_one(state=recipe, questions=_meat_questions))
        responses = await asyncio.gather(*calls)
        allergen_response = responses[0]
        meat_response = responses[1] if payload.include_meats else None
    except TypeSafeError as exc:
        # Degrade to offline keyword matching rather than showing nothing. This
        # is a materially weaker check - on the calibration suite it missed 5
        # real allergens that Jev caught - so the response is labelled as such
        # and the page is required to warn before showing any of it.
        logger.warning("Jev unreachable, falling back to keyword matching: %s", exc)
        return JSONResponse(
            content={
                "allergens": keyword_detect(recipe, ALLERGEN_IDS),
                "meats": keyword_detect(recipe, MEAT_IDS),
                "model": None,
                "input_tokens": None,
                "candidate_source": "keywords",
                "mode": "fallback",
                "warning": (
                    "The allergen model could not be reached, so this is an "
                    "offline keyword match only. It recognises a fixed list of "
                    "ingredients and a handful of well-known dishes. Anything "
                    "outside that list is invisible to it, including most dishes "
                    "named without their ingredients. Treat anything not flagged "
                    "here as unchecked, not as safe."
                ),
            }
        )

    allergens = collect(ALLERGENS, allergen_response)
    meats = collect(MEATS, meat_response) if meat_response is not None else []

    # Attribution runs last and only for things already flagged, so a failure
    # here degrades to "no source shown" and never affects a detection.
    flagged = [r for r in allergens + meats if r["status"] in ("detected", "possible")]
    options, option_kind = candidates(recipe)
    if payload.include_sources and flagged and options:
        try:
            source_response = await client.system_one(
                state=recipe,
                questions=build_source_questions(flagged, options),
            )
            for result in flagged:
                answer = source_response.answers.get(result["id"])
                if answer is not None:
                    result["source"] = resolve(answer, options)
        except TypeSafeError as exc:
            logger.warning("Source attribution failed, continuing without it: %s", exc)

    return JSONResponse(
        content={
            "allergens": allergens,
            "meats": meats,
            "model": allergen_response.model,
            "input_tokens": allergen_response.usage.input_tokens,
            "candidate_source": option_kind,
            "mode": "jev",
            "warning": None,
        }
    )


# Mounted last so the API routes above take precedence.
app.mount("/", StaticFiles(directory=BASE_DIR / "static", html=True), name="static")
