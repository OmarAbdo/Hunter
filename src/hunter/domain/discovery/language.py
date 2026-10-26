"""The language a job ad is written in, told by its most common words ("und", "wir", "the",
"our"). A campaign can ask for the languages it can work in. It's a count, not a model: a title
alone says too little, and an ad half in one language and half in another says nothing."""

import re

FEWEST_WORDS = 8  # common words needed before the count says anything
LEAD = 2  # the winner needs at least twice the words of the next language
WORDS = re.compile(r"[a-zäöüßàâçéèêëîïôûùüÿñ]+")


def word_set(words: str) -> frozenset[str]:
    return frozenset(words.split())


# Words common in job ads that, among these languages, belong to one only.
COMMON_WORDS = {
    "de": word_set(
        "und der die das wir du sie ist mit für ein eine einen unser unsere unseren bei auf "
        "nicht oder sowie von zu im den dem des als bist hast"
    ),
    "en": word_set(
        "the and we you our with for are is a an of to in your this that will be on as or who have"
    ),
    "nl": word_set("het een wij jij je bent bij onze ons voor van en met zijn niet of"),
    "fr": word_set("le la les et nous vous une des du pour avec est sur au aux notre nos votre"),
    "es": word_set("el la los las y nosotros una para con es en del nuestro nuestra tu su"),
}


def language_of(text: str) -> str | None:
    """The ISO 639-1 code of the language most of the text is in, or None when it can't tell."""
    words = WORDS.findall(text.lower())
    counts = sorted(
        ((sum(word in common for word in words), code) for code, common in COMMON_WORDS.items()),
        reverse=True,
    )
    (most, language), (next_most, _) = counts[0], counts[1]
    return language if most >= FEWEST_WORDS and most >= LEAD * next_most else None
