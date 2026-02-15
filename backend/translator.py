"""
Multi-language translation module for cross-region description comparison.
Uses deep-translator (Google Translate) — free, no API key required.
Includes lightweight local language detection via Unicode ranges & word frequency.
"""

import hashlib
import logging
import re
import time
from typing import Optional

logger = logging.getLogger("mrcc.translator")

# ── Region → primary language mapping ────────────────────────────────
REGION_LANGUAGES: dict[str, str] = {
    "US": "en",
    "IN": "en",    # English (India) – some Hindi possible
    "DE": "de",
    "UK": "en",
    "JP": "ja",
    "FR": "fr",
    "CA": "en",    # English/French bilingual
    "AU": "en",
    "ES": "es",
}

LANGUAGE_NAMES: dict[str, str] = {
    "en": "English",
    "de": "German",
    "ja": "Japanese",
    "fr": "French",
    "es": "Spanish",
    "hi": "Hindi",
    "pt": "Portuguese",
    "it": "Italian",
    "zh": "Chinese",
    "ko": "Korean",
    "ar": "Arabic",
    "nl": "Dutch",
}

# deep-translator uses full language names for some engines; map codes
_DT_LANG_CODE: dict[str, str] = {
    "en": "en", "de": "de", "ja": "ja", "fr": "fr", "es": "es",
    "hi": "hi", "pt": "pt", "it": "it", "zh-CN": "zh-CN", "ko": "ko",
    "ar": "ar", "nl": "nl", "zh": "zh-CN",
}

# ── In-memory translation cache ─────────────────────────────────────
_translation_cache: dict[str, dict] = {}
_CACHE_TTL = 3600  # 1 hour


def _cache_key(text: str, target_lang: str) -> str:
    h = hashlib.md5(f"{text}:{target_lang}".encode()).hexdigest()
    return h


def _get_cached(text: str, target_lang: str) -> Optional[dict]:
    key = _cache_key(text, target_lang)
    entry = _translation_cache.get(key)
    if entry and (time.time() - entry["ts"]) < _CACHE_TTL:
        return entry["data"]
    return None


def _set_cache(text: str, target_lang: str, data: dict):
    key = _cache_key(text, target_lang)
    _translation_cache[key] = {"data": data, "ts": time.time()}


# ── Language detection (lightweight, no external deps) ───────────────

_KOREAN_RE = re.compile(r'[\uAC00-\uD7AF\u1100-\u11FF]')
_ARABIC_RE = re.compile(r'[\u0600-\u06FF]')
_HINDI_RE = re.compile(r'[\u0900-\u097F]')
_CHINESE_RE = re.compile(r'[\u4E00-\u9FFF]')

_GERMAN_MARKERS = {
    'und', 'die', 'der', 'das', 'ist', 'für', 'mit', 'ein', 'eine', 'auf',
    'den', 'dem', 'des', 'von', 'zu', 'sich', 'nicht', 'auch', 'aus',
    'kann', 'oder', 'werden', 'wird', 'sind', 'hab', 'haben',
    'über', 'nach', 'bei', 'durch', 'wie', 'noch', 'nur', 'sehr',
    'stunden', 'akku', 'kabellos', 'geräuschunterdrückung', 'kopfhörer',
    'lautsprecher', 'wasserdicht', 'tragbar', 'batterie', 'ladung',
    'qualität', 'leicht', 'einstellbar', 'farben', 'edelstahl',
}

_FRENCH_MARKERS = {
    'le', 'la', 'les', 'de', 'du', 'des', 'un', 'une', 'et', 'en',
    'est', 'que', 'qui', 'dans', 'pour', 'pas', 'sur', 'ce', 'avec',
    'sont', 'son', 'mais', 'plus', 'par', 'tout', 'fait', 'comme',
    'heures', 'batterie', 'sans', 'fil', 'casque', 'réduction',
    'bruit', 'qualité', 'autonomie', 'étanche', 'portable',
    'commande', 'tactile', 'compatible', 'léger', 'acier', 'inoxydable',
}

_SPANISH_MARKERS = {
    'el', 'la', 'los', 'las', 'de', 'del', 'en', 'y', 'un', 'una',
    'es', 'que', 'por', 'con', 'para', 'no', 'son', 'su', 'al',
    'lo', 'se', 'como', 'más', 'pero', 'todo', 'esta', 'fue',
    'horas', 'batería', 'inalámbrico', 'auriculares', 'cancelación',
    'ruido', 'calidad', 'resistente', 'agua', 'portátil', 'carga',
    'táctil', 'compatible', 'acero', 'inoxidable', 'aislado',
}


def detect_language(text: str, region: str = "") -> str:
    """
    Detect the language of a text string.
    Uses Unicode ranges for CJK/Arabic/Hindi, then word frequency for European languages.
    Falls back to region language if detection is uncertain.
    """
    if not text or len(text.strip()) < 10:
        return REGION_LANGUAGES.get(region, "en")

    # Check for Japanese (hiragana/katakana unique to Japanese)
    hiragana_katakana = len(re.findall(r'[\u3040-\u309F\u30A0-\u30FF]', text))
    if hiragana_katakana > 3:
        return "ja"

    # Check for Korean
    if len(_KOREAN_RE.findall(text)) > 5:
        return "ko"

    # Check for Hindi/Devanagari
    if len(_HINDI_RE.findall(text)) > 5:
        return "hi"

    # Check for Arabic
    if len(_ARABIC_RE.findall(text)) > 5:
        return "ar"

    # Check for Chinese (CJK without Japanese kana)
    cjk = len(_CHINESE_RE.findall(text))
    if cjk > 5 and hiragana_katakana == 0:
        return "zh"

    # European language detection via word frequency
    words = set(re.findall(r'\b[a-zA-Zäöüßàâéèêëïîôùûçñáéíóúü]+\b', text.lower()))

    de_score = len(words & _GERMAN_MARKERS)
    fr_score = len(words & _FRENCH_MARKERS)
    es_score = len(words & _SPANISH_MARKERS)

    max_score = max(de_score, fr_score, es_score)
    if max_score >= 3:
        if de_score == max_score and de_score > fr_score and de_score > es_score:
            return "de"
        if fr_score == max_score and fr_score > de_score and fr_score > es_score:
            return "fr"
        if es_score == max_score and es_score > de_score and es_score > fr_score:
            return "es"

    # German-specific characters (umlauts are strong signals)
    if re.search(r'[äöüß]', text.lower()):
        return "de"

    # French-specific accented chars
    if re.search(r'[àâéèêëïîôùûç]', text.lower()) and not re.search(r'[ñ]', text.lower()):
        return "fr"

    # Spanish ñ or inverted punctuation
    if re.search(r'[ñ¿¡]', text.lower()):
        return "es"

    return REGION_LANGUAGES.get(region, "en")


# ── Free translation (deep-translator — Google Translate, no key) ────

def _translate_text(text: str, source_lang: str, target_lang: str = "en") -> Optional[str]:
    """
    Translate text using deep-translator's GoogleTranslator (free, no API key).
    Handles long text by chunking (Google Translate has a ~5000 char limit).
    """
    # Check cache first
    cached = _get_cached(text, target_lang)
    if cached:
        return cached.get("translated_text")

    try:
        from deep_translator import GoogleTranslator

        src = _DT_LANG_CODE.get(source_lang, source_lang)
        tgt = _DT_LANG_CODE.get(target_lang, target_lang)

        # Google Translate has a ~5000 char limit per request
        MAX_CHUNK = 4500
        if len(text) <= MAX_CHUNK:
            translated = GoogleTranslator(source=src, target=tgt).translate(text)
        else:
            # Split on sentence boundaries
            sentences = re.split(r'(?<=[.!?。])\s+', text)
            chunks: list[str] = []
            current = ""
            for s in sentences:
                if len(current) + len(s) + 1 > MAX_CHUNK:
                    if current:
                        chunks.append(current)
                    current = s
                else:
                    current = f"{current} {s}".strip() if current else s
            if current:
                chunks.append(current)

            translator = GoogleTranslator(source=src, target=tgt)
            translated_parts = [translator.translate(chunk) for chunk in chunks]
            translated = " ".join(p for p in translated_parts if p)

        if translated:
            _set_cache(text, target_lang, {"translated_text": translated})
            return translated

    except ImportError:
        logger.error("deep-translator not installed. Run: pip install deep-translator")
    except Exception as e:
        logger.warning(f"Translation failed for {source_lang}->{target_lang}: {e}")

    return None


# ── Batch translation for all regions ────────────────────────────────

async def translate_descriptions(
    descriptions: dict[str, str],
    target_lang: str = "en",
) -> dict[str, dict]:
    """
    Translate all non-target-language descriptions to the target language.

    Returns a dict of region -> {
        "original": <original text>,
        "translated": <translated text or original if already target language>,
        "source_language": <detected language code>,
        "source_language_name": <human-readable language name>,
        "was_translated": <bool>,
    }
    """
    import asyncio

    results: dict[str, dict] = {}

    for region, text in descriptions.items():
        lang = detect_language(text, region)
        lang_name = LANGUAGE_NAMES.get(lang, lang)

        if lang == target_lang:
            results[region] = {
                "original": text,
                "translated": text,
                "source_language": lang,
                "source_language_name": lang_name,
                "was_translated": False,
            }
        else:
            # Run sync translator in thread pool to avoid blocking the event loop
            translated = await asyncio.to_thread(_translate_text, text, lang, target_lang)
            results[region] = {
                "original": text,
                "translated": translated if translated else text,
                "source_language": lang,
                "source_language_name": lang_name,
                "was_translated": translated is not None,
            }

    return results


def get_language_info(region: str) -> dict:
    """Get language information for a region."""
    lang = REGION_LANGUAGES.get(region, "en")
    return {
        "code": lang,
        "name": LANGUAGE_NAMES.get(lang, lang),
    }
