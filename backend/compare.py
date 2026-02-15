"""
Multi-Region Product Description Consistency Checker — Comparison Engine v3.

Redesigned with 6 complementary analysis techniques:

1. Character N-gram Dice Coefficient  — language-agnostic fuzzy similarity
2. Sentence-Level Alignment           — aligns sentences 1-to-1, finds orphans
3. Specification Extraction & Conflict — extracts ALL numeric specs, flags mismatches
4. Content Coverage / Gap Analysis     — finds features in one region but missing in another
5. Structural Consistency              — length ratios, sentence counts, bullet counts
6. Actionable Issue Detection          — severity-ranked, human-readable issue reports

The old TF-IDF approach is replaced because IDF has no discriminative power with
only 2 documents.  The new pipeline delivers both a similarity score AND a list
of concrete issues so the user immediately sees WHAT is different, not just a %.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import Literal
from difflib import SequenceMatcher
import re
import string
import random
import math
from collections import Counter

from translator import translate_descriptions, detect_language, LANGUAGE_NAMES, REGION_LANGUAGES

# Risk level type
RiskLevel = Literal["LOW", "MEDIUM", "HIGH"]


class TextPreprocessor:
    """Advanced text preprocessing for improved similarity detection."""
    
    # Common stop words to remove
    STOP_WORDS = {
        'a', 'an', 'the', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
        'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
        'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
        'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
        'this', 'that', 'these', 'those', 'i', 'you', 'he', 'she', 'it',
        'we', 'they', 'what', 'which', 'who', 'whom', 'whose', 'where',
        'when', 'why', 'how', 'all', 'each', 'every', 'both', 'few', 'more',
        'most', 'other', 'some', 'such', 'no', 'nor', 'not', 'only', 'own',
        'same', 'so', 'than', 'too', 'very', 'just', 'also', 'now', 'here',
        'there', 'then', 'once', 'if', 'unless', 'until', 'while', 'about',
        'above', 'after', 'again', 'against', 'any', 'because', 'before',
        'being', 'below', 'between', 'into', 'through', 'during', 'out',
        'off', 'over', 'under', 'further', 'up', 'down', 'your', 'our',
        'their', 'its', 'my', 'his', 'her', 'like', 'get', 'make', 'made'
    }
    
    # Common word variations/synonyms to normalize
    SYNONYMS = {
        # British vs American English
        'colour': 'color', 'colours': 'colors', 'grey': 'gray',
        'aluminium': 'aluminum', 'centre': 'center',
        'metre': 'meter', 'metres': 'meters',
        'litre': 'liter', 'litres': 'liters',
        'favourite': 'favorite', 'favourites': 'favorites',
        'organisation': 'organization',
        'realise': 'realize', 'realised': 'realized',
        'recognise': 'recognize', 'recognised': 'recognized',
        'travelling': 'traveling', 'travelled': 'traveled',
        'cancelled': 'canceled', 'cancelling': 'canceling',
        'labelled': 'labeled', 'labelling': 'labeling',
        'modelled': 'modeled', 'modelling': 'modeling',
        'jewellery': 'jewelry', 'aeroplane': 'airplane',
        'defence': 'defense', 'licence': 'license',
        'offence': 'offense', 'practise': 'practice',
        'analyse': 'analyze', 'analysed': 'analyzed',
        'programme': 'program', 'programmes': 'programs',
        'tyre': 'tire', 'tyres': 'tires',
        'whilst': 'while', 'amongst': 'among',
        'towards': 'toward', 'afterwards': 'afterward',
        'customise': 'customize', 'customised': 'customized',
        'organise': 'organize', 'organised': 'organized',
        
        # Product-specific synonyms
        'cordless': 'wireless',
        'bt': 'bluetooth',
        'noisecanceling': 'noisecanceling', 'noisecancelling': 'noisecanceling',
        'noise-canceling': 'noisecanceling', 'noise-cancelling': 'noisecanceling',
        'anc': 'noisecanceling',
        
        # Time units
        'hrs': 'hours', 'hr': 'hour',
        'mins': 'minutes', 'min': 'minute',
        'secs': 'seconds', 'sec': 'second',
        
        # Common abbreviations
        'w/': 'with', 'w/o': 'without', '&': 'and',
        
        # Audio terms
        'hi-fi': 'hifi', 'high-fidelity': 'hifi',
        'hi-res': 'highresolution', 'high-res': 'highresolution',
        
        # Tech terms
        'usb-c': 'usbc', 'type-c': 'typec', 'usb c': 'usbc', 'type c': 'typec',
        'built-in': 'builtin', 'built in': 'builtin',
        
        # Durability terms
        'water-resistant': 'waterresistant', 'water resistant': 'waterresistant',
        'water-proof': 'waterproof', 'waterresistant': 'waterproof',
        'sweat-proof': 'sweatproof', 'sweat proof': 'sweatproof',
        'dust-proof': 'dustproof', 'dust proof': 'dustproof',
        'shock-proof': 'shockproof', 'shock proof': 'shockproof',
        
        # Weight terms
        'light-weight': 'lightweight', 'light weight': 'lightweight',
        'ultra-light': 'ultralight', 'ultra light': 'ultralight',
        
        # Quality terms
        'eco-friendly': 'ecofriendly', 'eco friendly': 'ecofriendly',
        'user-friendly': 'userfriendly', 'user friendly': 'userfriendly',
        'high-quality': 'highquality', 'high quality': 'highquality',
        'top-quality': 'highquality', 'top quality': 'highquality',
        'premium-quality': 'highquality', 'premium quality': 'highquality',
        
        # Feature terms
        'hands-free': 'handsfree', 'hands free': 'handsfree',
        'quick-charge': 'quickcharge', 'quick charge': 'quickcharge',
        'fast-charge': 'fastcharge', 'fast charge': 'fastcharge',
        'rapid-charge': 'quickcharge', 'rapid charge': 'quickcharge',
        'fast charging': 'quickcharge', 'quick charging': 'quickcharge',
        
        # Superlatives – normalise to avoid false mismatch
        'superior': 'premium', 'excellent': 'premium', 'outstanding': 'premium',
        'exceptional': 'premium', 'remarkable': 'premium',
    }
    
    @classmethod
    def preprocess(cls, text: str) -> str:
        """Comprehensive text preprocessing for maximum similarity accuracy."""
        if not text:
            return ""
        text = text.lower()
        # Remove URLs / emails
        text = re.sub(r'https?://\S+|www\.\S+', ' ', text)
        text = re.sub(r'\S+@\S+', ' ', text)
        # Normalise unicode
        text = text.replace('™', ' ').replace('®', ' ').replace('©', ' ')
        text = text.replace('–', '-').replace('—', '-')
        text = text.replace('\u2018', "'").replace('\u2019', "'")
        text = text.replace('\u201c', '"').replace('\u201d', '"')
        text = text.replace('\u2026', ' ')
        # Normalise time patterns
        text = re.sub(r'(\d+)\s*-?\s*hours?', r'\1 hour', text)
        text = re.sub(r'(\d+)\s*-?\s*minutes?', r'\1 minute', text)
        text = re.sub(r'(\d+)\s*-?\s*days?', r'\1 day', text)
        text = re.sub(r'ipx?(\d+)', r'iprating\1', text)
        text = re.sub(r'(\d+)\s*atm', r'\1atmospheres', text)
        text = text.replace('-', ' ')
        text = text.translate(str.maketrans(string.punctuation, ' ' * len(string.punctuation)))
        text = ' '.join(text.split())
        words = text.split()
        # Synonym normalisation
        words = [cls.SYNONYMS.get(w, w) for w in words]
        text = ' '.join(words)
        for phrase, replacement in sorted(cls.SYNONYMS.items(), key=lambda x: -len(x[0])):
            if ' ' in phrase and phrase in text:
                text = text.replace(phrase, replacement)
        words = text.split()
        words = [w for w in words if w not in cls.STOP_WORDS and len(w) > 1]
        words = [w for w in words if not w.isdigit() or len(w) > 2]
        return ' '.join(words)

    @classmethod
    def extract_key_features(cls, text: str) -> set:
        """Extract key product features for comparison."""
        features = set()
        text_lower = text.lower()
        number_patterns = re.findall(
            r'\d+\.?\d*\s*(?:oz|ml|l|gb|mb|tb|mah|ah|v|w|hz|hours?|hrs?|mins?|minutes?|days?|inch|inches|cm|mm|feet|ft|atm)',
            text_lower
        )
        features.update([re.sub(r'\s+', '', p) for p in number_patterns])
        ip_ratings = re.findall(r'ip[x]?\d+', text_lower)
        features.update(ip_ratings)
        colors = ['black', 'white', 'red', 'blue', 'green', 'yellow', 'orange', 'purple',
                  'pink', 'brown', 'gray', 'grey', 'silver', 'gold', 'bronze', 'rose gold',
                  'navy', 'teal', 'coral', 'beige', 'cream', 'midnight', 'space gray']
        for color in colors:
            if color in text_lower:
                features.add(color.replace(' ', ''))
        brands = re.findall(r'\b[A-Z][a-zA-Z]{2,}\b', text)
        features.update([b.lower() for b in brands if len(b) > 2])
        feature_keywords = [
            'bluetooth', 'wireless', 'wired', 'usb', 'nfc', 'wifi', 'gps',
            'touchscreen', 'oled', 'lcd', 'amoled', 'retina',
            'stereo', 'mono', 'surround', 'dolby', 'atmos',
            'waterproof', 'dustproof', 'shockproof', 'sweatproof',
            'rechargeable', 'replaceable', 'removable',
            'foldable', 'portable', 'compact', 'adjustable',
            'leather', 'metal', 'aluminum', 'plastic', 'silicone', 'fabric',
            'microphone', 'mic', 'speaker', 'driver', 'amplifier',
            'ios', 'android', 'windows', 'macos', 'linux',
        ]
        for kw in feature_keywords:
            if kw in text_lower:
                features.add(kw)
        return features

    @classmethod
    def extract_numeric_specs(cls, text: str) -> dict:
        """Extract numeric specifications from text."""
        specs = {}
        text_lower = text.lower()
        battery_match = re.search(r'(\d+)\s*(?:hour|hr|h)\s*(?:battery|playback|listening)?', text_lower)
        if battery_match:
            specs['battery_hours'] = int(battery_match.group(1))
        weight_match = re.search(r'(\d+\.?\d*)\s*(?:oz|ounce|g|gram|kg|lb|pound)', text_lower)
        if weight_match:
            specs['weight'] = float(weight_match.group(1))
        capacity_match = re.search(r'(\d+)\s*(?:oz|ml|l|liter|litre)', text_lower)
        if capacity_match:
            specs['capacity'] = int(capacity_match.group(1))
        screen_match = re.search(r'(\d+\.?\d*)\s*(?:inch|in)', text_lower)
        if screen_match:
            specs['screen_size'] = float(screen_match.group(1))
        return specs


# =====================================================================
#  NEW TECHNIQUE 1 — Character N-gram Dice Coefficient
# =====================================================================

def _char_ngrams(text: str, n: int = 3) -> Counter:
    """Generate character n-gram frequency counter (default trigrams)."""
    text = text.lower().strip()
    return Counter(text[i:i + n] for i in range(len(text) - n + 1))


def dice_coefficient(text1: str, text2: str, n: int = 3) -> float:
    """
    Sørensen–Dice coefficient on character n-grams.
    Language-agnostic, robust to word reordering and minor edits.
    Range: 0 (completely different) to 1 (identical).
    """
    if not text1 or not text2:
        return 0.0
    ng1 = _char_ngrams(text1, n)
    ng2 = _char_ngrams(text2, n)
    overlap = sum((ng1 & ng2).values())
    total = sum(ng1.values()) + sum(ng2.values())
    return (2.0 * overlap / total) if total > 0 else 0.0


# =====================================================================
#  NEW TECHNIQUE 2 — Sentence-Level Alignment
# =====================================================================

class SentenceAnalyzer:
    """Split descriptions into sentences, align them 1-to-1, find orphans."""

    @staticmethod
    def split_sentences(text: str) -> list[str]:
        """Split product description into logical sentences / bullet points."""
        if not text:
            return []
        # Split on sentence-end punctuation or bullet delimiters
        parts = re.split(r'(?<=[.!?])\s+|(?:\n\s*[•\-\*]\s*)', text)
        # Also split on long comma-separated clauses (common in Amazon bullet points)
        result = []
        for p in parts:
            p = p.strip()
            if not p:
                continue
            # If a segment is very long (>200 chars) and has commas, split further
            if len(p) > 200 and ',' in p:
                sub = re.split(r',\s*(?=[A-Z])', p)
                result.extend([s.strip() for s in sub if s.strip()])
            else:
                result.append(p)
        return [s for s in result if len(s) > 5]

    @staticmethod
    def align_sentences(sents1: list[str], sents2: list[str]) -> dict:
        """
        Greedy best-first alignment of sentences from desc1 to desc2.
        Returns matched pairs, orphans, and an overall alignment score.
        """
        if not sents1 and not sents2:
            return {'matched': [], 'only_in_1': [], 'only_in_2': [], 'alignment_score': 1.0}
        if not sents1:
            return {'matched': [], 'only_in_1': [], 'only_in_2': sents2, 'alignment_score': 0.0}
        if not sents2:
            return {'matched': [], 'only_in_1': sents1, 'only_in_2': [], 'alignment_score': 0.0}

        # Compute pairwise similarity matrix
        scores = []
        for i, s1 in enumerate(sents1):
            for j, s2 in enumerate(sents2):
                sim = SequenceMatcher(None, s1.lower(), s2.lower()).ratio()
                scores.append((sim, i, j))
        scores.sort(reverse=True)

        used_i, used_j = set(), set()
        matched = []
        for sim, i, j in scores:
            if i in used_i or j in used_j:
                continue
            if sim < 0.35:
                break
            matched.append({
                'sentence_1': sents1[i],
                'sentence_2': sents2[j],
                'similarity': round(sim, 4),
            })
            used_i.add(i)
            used_j.add(j)

        only_in_1 = [sents1[i] for i in range(len(sents1)) if i not in used_i]
        only_in_2 = [sents2[j] for j in range(len(sents2)) if j not in used_j]
        total = max(len(sents1), len(sents2))
        alignment_score = len(matched) / total if total > 0 else 1.0
        return {
            'matched': matched,
            'only_in_1': only_in_1,
            'only_in_2': only_in_2,
            'alignment_score': round(alignment_score, 4),
        }


# =====================================================================
#  NEW TECHNIQUE 3 — Comprehensive Spec Extraction & Conflict Detection
# =====================================================================

class SpecExtractor:
    """
    Extract ALL numeric specifications with context.
    Each pattern yields (value, spec_name) so we can compare across regions.
    """

    SPEC_PATTERNS: list[tuple[str, str]] = [
        # Battery / Power
        (r'(\d+)\s*(?:-\s*)?(?:hour|hr|h)\b(?:\s*(?:battery|playback|listening|autonomie|uso|akku|バッテリー))?', 'battery_life_hours'),
        (r'(\d[\d\s.,]*\d)\s*mah\b', 'battery_capacity_mah'),  # handles 5 000 mAh, 5,000mAh, 5000mAh
        (r'(\d+)\s*w(?:att)?s?\b', 'power_watts'),
        (r'pd\s*(\d+)\s*w', 'pd_watts'),
        # Display
        (r'(\d+\.?\d*)\s*(?:-?\s*)?(?:inch|in|"|pouces?|pulgadas?|zoll|インチ)', 'screen_size_inches'),
        (r'(\d+)\s*(?:x\s*\d+)?\s*(?:nit|nits)\b', 'brightness_nits'),
        (r'(\d+)\s*hz\b(?:\s*(?:refresh|display))?', 'refresh_rate_hz'),
        # Weight / Dimensions
        (r'(?:weigh(?:s|t|ing)?|wt\.?)\s*(\d+\.?\d*)\s*(?:oz|ounces?)\b', 'weight_oz'),  # only match weight context, not capacity
        (r'(\d+\.?\d*)\s*(?:kg|kilogram)s?\b', 'weight_kg'),
        (r'(?<!\d)(\d+\.?\d*)\s*g(?:ram)?s?\b(?!\w)', 'weight_grams'),
        (r'(\d+\.?\d*)\s*(?:lb|pound)s?\b', 'weight_lbs'),
        # Capacity / Volume
        (r'(\d+)\s*(?:fl\.?\s*)?oz\b', 'capacity_oz'),  # fl oz or just oz for volume
        (r'(\d+)\s*ml\b', 'capacity_ml'),
        (r'(\d+\.?\d*)\s*(?:liter|litre|l)\b', 'capacity_liters'),
        # Connectivity
        (r'bluetooth\s*(\d+\.?\d*)', 'bluetooth_version'),
        (r'(?:usb|USB)\s*(\d+\.?\d*)', 'usb_version'),
        (r'(?:wi-?fi|WiFi)\s*(\d+)', 'wifi_generation'),
        # Water resistance
        (r'(ipx?\d+)\b', 'ip_rating'),
        (r'(\d+)\s*atm\b', 'water_resistance_atm'),
        # Storage / Memory
        (r'(\d+)\s*gb\b', 'storage_gb'),
        (r'(\d+)\s*tb\b', 'storage_tb'),
        (r'(\d+)\s*(?:mp|megapixel)\b', 'camera_mp'),
        # Speed
        (r'(\d+\.?\d*)\s*ghz\b', 'speed_ghz'),
        # Counts
        (r'(\d+)\s*(?:sport|exercise|workout)\s*mode', 'sport_modes'),
        (r'(\d+)\s*(?:-\s*)?(?:day|days|jour|días?|tage|日間?)\b(?:\s*(?:battery|akku|batería|batterie))?', 'battery_life_days'),
        (r'(\d+)\s*(?:color|colour|farb|colori|couleur|colore)s?\b', 'color_options'),
        (r'(\d+)\s*(?:port|anschlüss|puerto)s?\b', 'ports_count'),
        (r'(\d+)\s*(?:mm)\s*(?:driver|treiber)', 'driver_size_mm'),
        (r'(\d+)\s*db\b', 'noise_reduction_db'),
        # Quick-charge pattern  "X min … Y hours"
        (r'(\d+)\s*(?:min|minute)s?\s*(?:charge|charging|laden|carga)', 'quick_charge_minutes'),
    ]

    @classmethod
    def extract(cls, text: str) -> dict[str, str]:
        """Return {spec_name: value_string} for every recognised spec in text."""
        specs: dict[str, str] = {}
        text_lower = text.lower()
        for pattern, name in cls.SPEC_PATTERNS:
            m = re.search(pattern, text_lower)
            if m:
                raw = m.group(1) if m.lastindex else m.group(0)
                # Normalise space / comma / dot-separated thousands: "5 000" → "5000"
                raw = re.sub(r'[\s,.](?=\d{3}(?:\D|$))', '', raw)
                specs[name] = raw
        return specs

    @classmethod
    def compare_across_regions(cls, specs_by_region: dict[str, dict]) -> dict:
        """
        Cross-region spec consistency report.
        Returns {spec_name: {values: {region: val}, consistent: bool, regions_present, regions_missing}}.
        """
        all_spec_names: set[str] = set()
        for specs in specs_by_region.values():
            all_spec_names.update(specs.keys())

        all_regions = list(specs_by_region.keys())
        analysis: dict = {}
        for name in sorted(all_spec_names):
            values = {r: specs_by_region[r][name] for r in all_regions if name in specs_by_region[r]}
            unique_vals = set(str(v) for v in values.values())
            analysis[name] = {
                'values': values,
                'consistent': len(unique_vals) <= 1,
                'regions_present': list(values.keys()),
                'regions_missing': [r for r in all_regions if r not in values],
            }
        return analysis


# =====================================================================
#  NEW TECHNIQUE 4 — Content Coverage / Gap Analysis
# =====================================================================

class ContentCoverageAnalyzer:
    """Identify key product claims present in one region but absent in another."""

    # Patterns that capture important product claims / features
    _CLAIM_PATTERNS = [
        r'(?:compatible\s+with|works\s+with|supports?)\s+[\w\s,&+]+',
        r'(?:includes?|comes?\s+with|equipped\s+with|features?)\s+[\w\s,&+]+',
        r'(?:up\s+to\s+)\d+[\w\s]+',
        r'(?:available\s+in)\s+[\w\s,&+]+',
        r'(?:designed\s+for|perfect\s+for|ideal\s+for|suitable\s+for|great\s+for)\s+[\w\s,&+]+',
        r'(?:approved|certified|rated)\s+(?:for|by)\s+[\w\s]+',
        r'(?:airline|flight|cabin)\s+(?:approved|safe|friendly)',
        r'(?:bpa|lead|phthalate)\s*-?\s*free',
        r'(?:foldable|collapsible|portable|adjustable|removable|detachable)',
        r'(?:touch\s+(?:control|sensor)|voice\s+(?:control|assistant|command))',
        r'(?:fast|quick|rapid|turbo)\s+charg(?:e|ing)',
        r'(?:noise\s+cancel(?:l?ing|l?ation)|anc|enc)',
    ]

    @classmethod
    def extract_claims(cls, text: str) -> list[str]:
        """Extract product claims / feature mentions from text."""
        tl = text.lower()
        claims = []
        for pat in cls._CLAIM_PATTERNS:
            for m in re.finditer(pat, tl):
                claim = m.group(0).strip()
                if len(claim) > 5:
                    claims.append(claim)
        return claims

    @classmethod
    def find_gaps(cls, text1: str, text2: str) -> dict:
        """Find claims in text1 not covered in text2 and vice-versa."""
        claims1 = cls.extract_claims(text1)
        claims2 = cls.extract_claims(text2)
        text1_lower = text1.lower()
        text2_lower = text2.lower()

        only_in_1 = []
        for c in claims1:
            # check if the core of the claim appears somewhere in text2
            core = c.split()[-2:]  # last 2 words
            core_str = ' '.join(core)
            if core_str not in text2_lower and c not in text2_lower:
                only_in_1.append(c)

        only_in_2 = []
        for c in claims2:
            core = c.split()[-2:]
            core_str = ' '.join(core)
            if core_str not in text1_lower and c not in text1_lower:
                only_in_2.append(c)

        return {'only_in_1': only_in_1, 'only_in_2': only_in_2}


# =====================================================================
#  NEW TECHNIQUE 5 — Structural Consistency
# =====================================================================

def structural_similarity(text1: str, text2: str) -> dict:
    """
    Compare structural properties: length ratio, sentence count ratio,
    bullet-point count ratio.  Returns a score 0-1 and details.
    """
    len1, len2 = len(text1), len(text2)
    length_ratio = min(len1, len2) / max(len1, len2) if max(len1, len2) > 0 else 1.0

    sents1 = SentenceAnalyzer.split_sentences(text1)
    sents2 = SentenceAnalyzer.split_sentences(text2)
    s1, s2 = len(sents1), len(sents2)
    sentence_ratio = min(s1, s2) / max(s1, s2) if max(s1, s2) > 0 else 1.0

    # Bullet point detection
    bp1 = len(re.findall(r'(?:^|\n)\s*[•\-\*]\s', text1))
    bp2 = len(re.findall(r'(?:^|\n)\s*[•\-\*]\s', text2))
    bp_ratio = 1.0
    if max(bp1, bp2) > 0:
        bp_ratio = min(bp1, bp2) / max(bp1, bp2)

    score = 0.5 * length_ratio + 0.3 * sentence_ratio + 0.2 * bp_ratio
    return {
        'score': round(score, 4),
        'length_ratio': round(length_ratio, 4),
        'sentence_count_1': s1,
        'sentence_count_2': s2,
        'sentence_ratio': round(sentence_ratio, 4),
        'char_count_1': len1,
        'char_count_2': len2,
    }


# =====================================================================
#  NEW TECHNIQUE 6 — Actionable Issue Detection
# =====================================================================

class IssueDetector:
    """Generate severity-ranked, human-readable issue summaries."""

    @staticmethod
    def detect(
        region_1: str,
        region_2: str,
        desc1: str,
        desc2: str,
        spec_analysis: dict,
        sentence_alignment: dict,
        content_gaps: dict,
        struct: dict,
    ) -> list[dict]:
        issues: list[dict] = []

        # ── Spec conflicts (HIGH) ──────────────────────────────────
        for spec_name, info in spec_analysis.items():
            vals_in_pair = {}
            for r in (region_1, region_2):
                if r in info.get('values', {}):
                    vals_in_pair[r] = info['values'][r]
            if len(set(str(v) for v in vals_in_pair.values())) > 1:
                readable = spec_name.replace('_', ' ').title()
                details = ', '.join(f"{r}: {v}" for r, v in vals_in_pair.items())
                issues.append({
                    'type': 'spec_conflict',
                    'severity': 'high',
                    'icon': '⚠️',
                    'title': f'{readable} Differs',
                    'description': details,
                    'regions': list(vals_in_pair.keys()),
                })

        # ── Missing specs (LOW — absence is less critical than conflict) ──
        for spec_name, info in spec_analysis.items():
            vals_in_pair = {r: info['values'][r] for r in (region_1, region_2) if r in info.get('values', {})}
            if len(vals_in_pair) == 1:
                present_r = list(vals_in_pair.keys())[0]
                missing_r = region_2 if present_r == region_1 else region_1
                readable = spec_name.replace('_', ' ').title()
                issues.append({
                    'type': 'missing_spec',
                    'severity': 'low',
                    'icon': '🔍',
                    'title': f'{readable} Missing',
                    'description': f'{readable} ({vals_in_pair[present_r]}) is in {present_r} but not in {missing_r}',
                    'regions': [missing_r],
                })

        # ── Unmatched sentences (MEDIUM) ────────────────────────────
        for sent in sentence_alignment.get('only_in_1', [])[:3]:
            issues.append({
                'type': 'missing_content',
                'severity': 'medium',
                'icon': '📝',
                'title': f'Content only in {region_1}',
                'description': sent[:120] + ('…' if len(sent) > 120 else ''),
                'regions': [region_1],
            })
        for sent in sentence_alignment.get('only_in_2', [])[:3]:
            issues.append({
                'type': 'missing_content',
                'severity': 'medium',
                'icon': '📝',
                'title': f'Content only in {region_2}',
                'description': sent[:120] + ('…' if len(sent) > 120 else ''),
                'regions': [region_2],
            })

        # ── Content-claim gaps (LOW) ────────────────────────────────
        for claim in content_gaps.get('only_in_1', [])[:2]:
            issues.append({
                'type': 'content_gap',
                'severity': 'low',
                'icon': '📋',
                'title': f'Claim only in {region_1}',
                'description': claim[:100],
                'regions': [region_1],
            })
        for claim in content_gaps.get('only_in_2', [])[:2]:
            issues.append({
                'type': 'content_gap',
                'severity': 'low',
                'icon': '📋',
                'title': f'Claim only in {region_2}',
                'description': claim[:100],
                'regions': [region_2],
            })

        # ── Length disparity (MEDIUM) ───────────────────────────────
        lr = struct.get('length_ratio', 1.0)
        if lr < 0.50:
            shorter = region_1 if struct['char_count_1'] < struct['char_count_2'] else region_2
            pct = int((1 - lr) * 100)
            issues.append({
                'type': 'length_disparity',
                'severity': 'medium',
                'icon': '📏',
                'title': 'Significant Length Difference',
                'description': f'{shorter} description is {pct}% shorter',
                'regions': [shorter],
            })

        # Sort: high → medium → low
        severity_rank = {'high': 0, 'medium': 1, 'low': 2}
        issues.sort(key=lambda x: severity_rank.get(x['severity'], 3))
        return issues


def calculate_sequence_similarity(text1: str, text2: str) -> float:
    """Sequence similarity via SequenceMatcher (Levenshtein-like ratio)."""
    return SequenceMatcher(None, text1, text2).ratio()


def calculate_jaccard_similarity(words1: set, words2: set) -> float:
    """Jaccard similarity between two word sets."""
    if not words1 or not words2:
        return 0.0
    return len(words1 & words2) / len(words1 | words2)


def calculate_bigram_jaccard(text1: str, text2: str) -> float:
    """Word-bigram Jaccard — captures phrase-level overlap, not just single words."""
    w1 = text1.lower().split()
    w2 = text2.lower().split()
    if len(w1) < 2 or len(w2) < 2:
        return calculate_jaccard_similarity(set(w1), set(w2))
    bg1 = set(zip(w1, w1[1:]))
    bg2 = set(zip(w2, w2[1:]))
    return len(bg1 & bg2) / len(bg1 | bg2) if (bg1 | bg2) else 0.0


def calculate_similarity_advanced(text1: str, text2: str) -> dict:
    """
    Multi-dimensional similarity analysis using 6 complementary techniques.

    Returns detailed per-dimension scores plus a weighted combined score.
    Replaces the old TF-IDF-centric approach (TF-IDF is kept as one signal
    but is no longer dominant — its IDF component is weak with only 2 docs).
    """
    empty = {
        'ngram_dice': 0.0,
        'bigram_jaccard': 0.0,
        'word_jaccard': 0.0,
        'sequence': 0.0,
        'sentence_alignment': 0.0,
        'feature_overlap': 0.0,
        'spec_match': 0.0,
        'structural': 0.0,
        'tfidf_cosine': 0.0,
        'combined_score': 0.0,
        'confidence': 'LOW',
        'issues': [],
        'sentence_detail': {},
        'spec_detail': {},
        'content_gaps': {},
        'structural_detail': {},
    }
    if not text1 or not text2:
        return empty

    processed1 = TextPreprocessor.preprocess(text1)
    processed2 = TextPreprocessor.preprocess(text2)
    if not processed1 or not processed2:
        return empty

    # ── 1  Character trigram Dice (language-agnostic fuzzy sim) ────
    ngram_dice = dice_coefficient(processed1, processed2, n=3)

    # ── 2  Word-bigram Jaccard (phrase overlap) ───────────────────
    bigram_jac = calculate_bigram_jaccard(processed1, processed2)

    # ── 3  Word-level Jaccard (bag-of-words overlap) ──────────────
    words1 = set(processed1.split())
    words2 = set(processed2.split())
    word_jac = calculate_jaccard_similarity(words1, words2)

    # ── 4  Sequence similarity (order-sensitive) ──────────────────
    sequence = calculate_sequence_similarity(processed1, processed2)

    # ── 5  Sentence-level alignment ───────────────────────────────
    sents1 = SentenceAnalyzer.split_sentences(text1)
    sents2 = SentenceAnalyzer.split_sentences(text2)
    sent_alignment = SentenceAnalyzer.align_sentences(sents1, sents2)
    sent_score = sent_alignment['alignment_score']

    # ── 6  Feature overlap ────────────────────────────────────────
    features1 = TextPreprocessor.extract_key_features(text1)
    features2 = TextPreprocessor.extract_key_features(text2)
    if features1 or features2:
        feature_overlap = len(features1 & features2) / len(features1 | features2)
    else:
        feature_overlap = 1.0

    # ── 7  Spec extraction & consistency ──────────────────────────
    specs1 = SpecExtractor.extract(text1)
    specs2 = SpecExtractor.extract(text2)
    all_spec_keys = set(specs1.keys()) | set(specs2.keys())
    if all_spec_keys:
        common = set(specs1.keys()) & set(specs2.keys())
        matching = sum(1 for k in common if str(specs1[k]) == str(specs2[k]))
        conflicting = sum(1 for k in common if str(specs1[k]) != str(specs2[k]))
        # Penalty for conflicts is harsher than for simple absence
        spec_match = (matching - 0.5 * conflicting) / len(all_spec_keys) if all_spec_keys else 1.0
        spec_match = max(0.0, min(1.0, spec_match))
    else:
        spec_match = 1.0

    # Build spec detail for cross-region analysis later
    spec_detail = {}
    for k in all_spec_keys:
        v1 = specs1.get(k)
        v2 = specs2.get(k)
        spec_detail[k] = {
            'values': {('r1'): v1, ('r2'): v2},
            'consistent': str(v1) == str(v2) if v1 is not None and v2 is not None else (v1 is None and v2 is None),
        }

    # ── 8  Structural similarity ──────────────────────────────────
    struct = structural_similarity(text1, text2)
    struct_score = struct['score']

    # ── 9  TF-IDF cosine (kept as supplementary signal) ──────────
    try:
        vectorizer = TfidfVectorizer(
            lowercase=True, ngram_range=(1, 2), max_features=5000,
            min_df=1, sublinear_tf=True, norm='l2',
        )
        tfidf_matrix = vectorizer.fit_transform([processed1, processed2])
        tfidf_cosine = float(cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0])
    except Exception:
        tfidf_cosine = 0.0

    # ── 10 Content-gap analysis ───────────────────────────────────
    content_gaps = ContentCoverageAnalyzer.find_gaps(text1, text2)

    # ── Combined Score (redesigned weighting) ─────────────────────
    # Spec conflicts are the most critical signal for product consistency
    combined_score = (
        ngram_dice       * 0.20 +   # Character-level fuzzy similarity
        bigram_jac       * 0.10 +   # Phrase-level overlap
        word_jac         * 0.10 +   # Word-level overlap
        sequence         * 0.10 +   # Order-sensitive similarity
        sent_score       * 0.15 +   # Sentence alignment quality
        feature_overlap  * 0.10 +   # Domain-specific features
        spec_match       * 0.15 +   # Spec consistency (critical)
        struct_score     * 0.05 +   # Structural similarity
        tfidf_cosine     * 0.05     # Legacy TF-IDF (supplementary)
    )

    # ── Confidence (agreement among metrics) ──────────────────────
    metric_vals = [ngram_dice, bigram_jac, word_jac, sequence, sent_score, feature_overlap]
    variance = max(metric_vals) - min(metric_vals)
    if variance < 0.15:
        confidence = 'HIGH'
    elif variance < 0.30:
        confidence = 'MEDIUM'
    else:
        confidence = 'LOW'

    return {
        'ngram_dice': round(ngram_dice, 4),
        'bigram_jaccard': round(bigram_jac, 4),
        'word_jaccard': round(word_jac, 4),
        'sequence': round(sequence, 4),
        'sentence_alignment': round(sent_score, 4),
        'feature_overlap': round(feature_overlap, 4),
        'spec_match': round(spec_match, 4),
        'structural': round(struct_score, 4),
        'tfidf_cosine': round(tfidf_cosine, 4),
        'combined_score': round(combined_score, 4),
        'confidence': confidence,
        # Detailed analysis payloads
        'sentence_detail': sent_alignment,
        'spec_detail': spec_detail,
        'content_gaps': content_gaps,
        'structural_detail': struct,
    }


def calculate_similarity(text1: str, text2: str) -> float:
    """
    Calculate final similarity score between two text descriptions.
    Returns a similarity score between 0 and 1.
    """
    result = calculate_similarity_advanced(text1, text2)
    return result['combined_score']


# Mock product descriptions for different ASINs across regions
# These are designed to demonstrate different similarity levels
MOCK_DESCRIPTIONS: dict[str, dict[str, str]] = {
    # HIGH SIMILARITY - Almost identical descriptions (LOW risk)
    "B08N5WRWNW": {
        "US": "Sony WH-1000XM4 Wireless Premium Noise Canceling Overhead Headphones with Mic for Phone-Call and Alexa Voice Control, Black. Industry-leading noise canceling with Dual Noise Sensor technology. Next-level music with Edge-AI, co-developed with Sony Music Studios Tokyo. Up to 30-hour battery life with quick charging (10 min charge for 5 hours of playback). Touch Sensor controls to pause play skip tracks, control volume, activate your voice assistant, and answer phone calls.",
        "IN": "Sony WH-1000XM4 Wireless Premium Noise Canceling Overhead Headphones with Mic for Phone-Call and Alexa Voice Control, Black Color. Industry-leading noise cancellation with Dual Noise Sensor technology. Next-level music experience with Edge-AI, co-developed with Sony Music Studios Tokyo. Up to 30-hour battery life with quick charging feature (10 min charge provides 5 hours of playback). Touch Sensor controls to pause play skip tracks, control volume, activate voice assistant, and answer phone calls.",
        "DE": "Sony WH-1000XM4 Kabellose Premium-Kopfhörer mit Geräuschunterdrückung und Mikrofon für Telefonate und Alexa Sprachsteuerung, Schwarz. Branchenführende Geräuschunterdrückung mit Dual Noise Sensor Technologie. Musik auf höchstem Niveau mit Edge-AI, mitentwickelt mit Sony Music Studios Tokyo. Bis zu 30 Stunden Akkulaufzeit mit Schnellladefunktion (10 Min. Laden für 5 Stunden Wiedergabe). Touch-Sensor-Steuerung zum Pausieren, Abspielen, Überspringen von Titeln, Lautstärkeregelung, Aktivierung des Sprachassistenten und Annehmen von Telefonaten.",
        "UK": "Sony WH-1000XM4 Wireless Premium Noise Cancelling Overhead Headphones with Mic for Phone-Call and Alexa Voice Control, Black. Industry-leading noise cancelling with Dual Noise Sensor technology. Next-level music with Edge-AI, co-developed with Sony Music Studios Tokyo. Up to 30-hour battery life with quick charging (10 min charge for 5 hours of playback). Touch Sensor controls to pause play skip tracks, control volume, activate your voice assistant, and answer phone calls.",
        "JP": "Sony WH-1000XM4 ワイヤレスプレミアムノイズキャンセリングオーバーヘッドヘッドホン、通話用マイク付き、Alexa音声コントロール対応、ブラック。業界最先端のノイズキャンセリング、デュアルノイズセンサーテクノロジー搭載。Sony Music Studios Tokyoと共同開発したEdge-AIによる次世代の音楽体験。最大30時間のバッテリー持続時間、急速充電対応（10分の充電で5時間再生可能）。タッチセンサーコントロールで一時停止、再生、曲送り、音量調節、電話応答が可能。",
        "FR": "Sony WH-1000XM4 Casque sans fil à réduction de bruit avec microphone pour appels téléphoniques et commande vocale Alexa, Noir. Réduction de bruit à la pointe de l'industrie avec technologie Dual Noise Sensor. Musique de qualité supérieure avec Edge-AI, co-développé avec Sony Music Studios Tokyo. Jusqu'à 30 heures d'autonomie avec charge rapide (10 min de charge pour 5 heures d'écoute). Commandes tactiles pour mettre en pause, lire, passer des pistes, régler le volume, activer l'assistant vocal et répondre aux appels.",
        "CA": "Sony WH-1000XM4 Wireless Premium Noise Canceling Overhead Headphones with Mic for Phone-Call and Alexa Voice Control, Black. Industry-leading noise canceling with Dual Noise Sensor technology. Next-level music with Edge-AI, co-developed with Sony Music Studios Tokyo. Up to 30-hour battery life with quick charging (10 min charge for 5 hours of playback). Touch Sensor controls to pause play skip tracks, control volume, activate your voice assistant, and answer phone calls.",
        "AU": "Sony WH-1000XM4 Wireless Premium Noise Cancelling Overhead Headphones with Mic for Phone-Call and Alexa Voice Control, Black. Industry-leading noise cancelling with Dual Noise Sensor technology. Next-level music experience with Edge-AI, co-developed with Sony Music Studios Tokyo. Up to 30-hour battery life with quick charging (10 min charge for 5 hours of playback). Touch Sensor controls to pause play skip tracks, control volume, activate your voice assistant, and answer phone calls.",
        "ES": "Sony WH-1000XM4 Auriculares inalámbricos premium con cancelación de ruido y micrófono para llamadas telefónicas y control por voz Alexa, Negro. Cancelación de ruido líder en la industria con tecnología Dual Noise Sensor. Música de nivel superior con Edge-AI, co-desarrollado con Sony Music Studios Tokyo. Hasta 30 horas de autonomía de batería con carga rápida (10 min de carga para 5 horas de reproducción). Controles táctiles para pausar, reproducir, saltar pistas, controlar volumen, activar asistente de voz y responder llamadas."
    },
    
    # MEDIUM SIMILARITY - Some differences in descriptions (MEDIUM risk)
    "B00TEST123": {
        "US": "Premium Wireless Bluetooth Earbuds with Active Noise Cancellation. Features include: 24-hour total battery life with charging case, IPX4 water resistance for workouts, touch controls for music and calls, and seamless pairing with all Bluetooth devices. Comes with 3 sizes of silicone ear tips for perfect fit. Premium sound quality with deep bass and crystal clear highs.",
        "IN": "Wireless Bluetooth Earbuds with Noise Cancellation Technology. Battery life up to 20 hours with portable charging case. Water resistant design suitable for exercise and outdoor use. Easy touch controls and quick Bluetooth connectivity. Includes multiple ear tip sizes. Enhanced audio with powerful bass response.",
        "DE": "Kabellose Bluetooth-Ohrhörer mit aktiver Geräuschunterdrückung. 24 Stunden Gesamtbatterielaufzeit mit Ladeetui. IPX4 Spritzwasserschutz. Intuitive Touch-Bedienung für Wiedergabesteuerung. Universelle Bluetooth 5.0 Kompatibilität. Enthält S/M/L Ohrstöpsel. Ausgewogenes Klangprofil mit betonten tiefen Frequenzen.",
        "UK": "Premium Wireless Bluetooth Earbuds with Active Noise Cancellation. 24-hour battery with charging case included. IPX4 water resistance rating for workouts and outdoor use. Touch controls for music playback and calls. Bluetooth 5.0 for seamless pairing. Comes with 3 sizes of silicone ear tips. Rich sound with deep bass and clear treble.",
        "JP": "ワイヤレスBluetoothイヤホン、アクティブノイズキャンセリング搭載。充電ケース付きで合計24時間のバッテリー寿命。IPX4防水性能。音楽と通話のタッチセンサーコントロール。すべてのBluetooth機器と互換性あり。3サイズのイヤーチップ付属。深い低音のHi-Fiサウンド品質。",
        "FR": "Écouteurs Bluetooth sans fil avec réduction active du bruit. 24 heures d'autonomie de batterie avec étui de charge. Résistance à l'eau IPX4 pour le sport. Commandes tactiles intuitives. Compatibilité universelle Bluetooth 5.0. Plusieurs tailles d'embouts incluses. Qualité audio premium avec basses puissantes.",
        "CA": "Premium Wireless Bluetooth Earbuds with Active Noise Cancellation. Features 24-hour total battery life with charging case, IPX4 water resistance for workouts, touch controls for music and calls. Seamless pairing with all Bluetooth devices. Comes with 3 sizes of silicone ear tips for perfect fit. Premium sound quality with deep bass.",
        "AU": "Wireless Bluetooth Earbuds featuring Active Noise Cancellation. 24-hour battery with portable charging case. IPX4 water resistance for exercise and outdoor activities. Touch controls for playback and calls. Bluetooth 5.0 connectivity. Multiple ear tip sizes included. Quality sound with enhanced bass response.",
        "ES": "Auriculares Bluetooth inalámbricos con cancelación activa de ruido. 24 horas de batería con estuche de carga incluido. Resistencia al agua IPX4 para actividades deportivas. Controles táctiles para música y llamadas. Compatibilidad universal Bluetooth 5.0. Incluye puntas de oído S/M/L. Calidad de sonido con graves profundos y agudos claros."
    },
    
    # LOW SIMILARITY - Very different descriptions (HIGH risk)
    "B00DIFFER1": {
        "US": "Ultra-Slim Laptop Stand made from Premium Aluminum Alloy. Ergonomic design elevates your laptop 6 inches for better posture. Compatible with all laptops from 10 to 17 inches. Foldable and portable design weighs only 8 oz. Non-slip silicone pads protect your device. Improves airflow to prevent overheating. Perfect for home office and travel.",
        "IN": "Adjustable Mobile Phone Holder Stand for Desk. 360 degree rotation with flexible gooseneck arm. Compatible with smartphones 4-7 inches. Strong clamp base attaches to any surface up to 3 inches thick. Perfect for video calls, watching movies, and following recipes. Durable ABS plastic construction.",
        "DE": "Professioneller Tablet-Bodenständer mit Rollen. Robuste Metallkonstruktion für Tablets bis 13 Zoll. Höhenverstellbar von 90 cm bis 150 cm. Feststellbare Lenkrollen für einfache Mobilität. Inklusive Diebstahlsicherung. Ideal für Einzelhandel, Präsentationen und Kiosk-Anwendungen. Montage erforderlich.",
        "UK": "Wooden Monitor Riser with Storage Drawer. Bamboo construction supports up to 30 kg. Raises monitor 4 inches for ergonomic viewing. Built-in organiser slots for keyboard, mouse, and stationery. Non-slip rubber feet. Perfect for tidy desk setup.",
        "JP": "コンパクト折りたたみ式スマホスタンド、旅行に最適。アルミニウム合金製。0度から100度まで角度調節可能。スマートフォンとミニタブレットに対応。重さわずか60グラム。ポケットサイズの携帯デザイン。",
        "FR": "Refroidisseur ergonomique pour ordinateur portable avec 5 ventilateurs. Alimenté par USB avec vitesse de ventilateur réglable. Compatible avec les ordinateurs portables de 12 à 17 pouces. Éclairage LED bleu. Double hub USB. Surface en maille métallique pour un flux d'air maximal. Réglage de la hauteur.",
        "CA": "Ultra-Slim Laptop Stand made from Premium Aluminum Alloy. Ergonomic design elevates your laptop 6 inches for better posture. Compatible with all laptops from 10 to 17 inches. Foldable and portable design weighs only 8 oz. Non-slip silicone pads. Improves airflow. Perfect for home office and travel.",
        "AU": "Heavy Duty Monitor Arm Mount with Gas Spring. Supports monitors 13 to 32 inches up to 9 kg. Full motion swivel tilt and rotate. Desk clamp and grommet mounting options. Cable management system included. VESA 75x75 and 100x100 compatible.",
        "ES": "Soporte de almohada ajustable para tablet en la cama. Construcción de espuma suave con funda de microfibra. Compatible con tablets y lectores electrónicos de hasta 12.9 pulgadas. Tres ángulos de visión. Funda lavable a máquina. Perfecto para leer y ver vídeos en la cama."
    },
    
    # ANOTHER LOW RISK EXAMPLE
    "B09XYZ1234": {
        "US": "Stainless Steel Insulated Water Bottle - 32oz capacity. Double-wall vacuum insulation keeps drinks cold for 24 hours or hot for 12 hours. BPA-free and leak-proof lid design. Wide mouth opening for easy cleaning and ice cubes. Powder-coated exterior prevents condensation. Available in 12 vibrant colors.",
        "IN": "Stainless Steel Vacuum Insulated Water Bottle - 32oz size. Double-wall insulation technology keeps beverages cold 24 hours or hot 12 hours. BPA-free materials with leak-proof cap. Wide mouth design for easy cleaning and adding ice. Powder-coated finish prevents sweating. Available in multiple color options.",
        "DE": "Edelstahl-Isolierflasche - 1 Liter Fassungsvermögen. Doppelwandige Vakuumisolierung hält Getränke 24 Stunden kalt oder 12 Stunden heiß. BPA-frei mit auslaufsicherem Deckel. Große Öffnung für einfache Reinigung und Eiswürfel. Pulverbeschichtete Oberfläche verhindert Kondenswasser. Erhältlich in verschiedenen Farben.",
        "UK": "Stainless Steel Insulated Water Bottle - 32oz / 1 Litre capacity. Double-wall vacuum insulation keeps drinks cold for 24 hours or hot for 12 hours. BPA-free and leak-proof lid design. Wide mouth opening for easy cleaning and ice cubes. Powder-coated exterior prevents condensation. Available in 12 colours.",
        "JP": "ステンレス製断熱ウォーターボトル - 容量32オンス。二重壁真空断熱で飲み物を24時間冷たく、12時間温かく保ちます。BPAフリーで漏れ防止蓋デザイン。広口で洗いやすく、氷も入れやすい。パウダーコート仕上げで結露を防止。複数のカラーバリエーションあり。",
        "FR": "Bouteille d'eau isotherme en acier inoxydable - capacité 1 litre. Isolation sous vide à double paroi maintient les boissons froides pendant 24 heures ou chaudes pendant 12 heures. Sans BPA avec couvercle anti-fuite. Large ouverture pour un nettoyage facile et les glaçons. Revêtement poudré anti-condensation. Disponible en plusieurs coloris.",
        "CA": "Stainless Steel Insulated Water Bottle - 32oz capacity. Double-wall vacuum insulation keeps drinks cold for 24 hours or hot for 12 hours. BPA-free and leak-proof lid design. Wide mouth opening for easy cleaning and ice cubes. Powder-coated exterior prevents condensation. Available in 12 vibrant colors.",
        "AU": "Stainless Steel Insulated Water Bottle - 32oz / 1 Litre capacity. Double-wall vacuum insulation keeps beverages cold for 24 hours or hot for 12 hours. BPA-free and leak-proof lid. Wide mouth opening for easy cleaning and ice cubes. Powder-coated exterior finish. Available in multiple colour options.",
        "ES": "Botella de agua aislada de acero inoxidable - capacidad de 1 litro. Aislamiento de vacío de doble pared mantiene las bebidas frías durante 24 horas o calientes durante 12 horas. Libre de BPA con tapa a prueba de fugas. Boca ancha para fácil limpieza y cubitos de hielo. Exterior con recubrimiento en polvo que previene la condensación. Disponible en varios colores."
    },
    
    # MEDIUM RISK EXAMPLE
    "B07MEDIUM1": {
        "US": "Smart Fitness Tracker Watch with Heart Rate Monitor. Tracks steps, calories, distance, and sleep patterns. Water resistant to 50 meters for swimming. 7-day battery life on single charge. Compatible with iOS and Android. GPS connectivity for outdoor activities. Customizable watch faces and interchangeable bands.",
        "IN": "Fitness Band with Heart Rate Monitoring and Step Counter. Monitors daily activity including walking, running, and sleep quality. Waterproof design for swimming and sports. Long battery life lasts up to 5 days. Works with Android and iPhone. Sports mode for various exercises.",
        "DE": "Activity Tracker Smartwatch mit Pulsmessung. Umfassende Aktivitätsverfolgung für Schritte, verbrannte Kalorien und Schlafanalyse. 5 ATM Wasserdichtigkeit. Akkulaufzeit ca. 6 Tage. Smartphone-Benachrichtigungen für Anrufe und Nachrichten. Integriertes GPS für Routenverfolgung. Mehrere Sportmodi verfügbar.",
        "UK": "Smart Fitness Tracker Watch with Heart Rate Monitor. Tracks steps, calories, distance, and sleep patterns. Water resistant to 50 metres for swimming. 7-day battery life on single charge. Compatible with iOS and Android. GPS connectivity for outdoor activities. Customisable watch faces and interchangeable bands.",
        "JP": "スマートフィットネストラッカーウォッチ、心拍数モニター付き。歩数、カロリー、距離、睡眠を追跡。水泳用5ATM防水。7日間のバッテリー寿命。iOSおよびAndroidに対応。アウトドア用内蔵GPS。複数のウォッチフェイス。",
        "FR": "Montre traqueur d'activité avec moniteur de fréquence cardiaque. Suivi des pas, calories, distance et analyse du sommeil. Résistante à l'eau jusqu'à 50 mètres pour la natation. Autonomie de batterie environ 6 jours. Compatible avec smartphones iOS et Android. GPS pour le suivi en extérieur. Cadrans personnalisables.",
        "CA": "Smart Fitness Tracker Watch with Heart Rate Monitor. Tracks steps, calories, distance, and sleep patterns. Water resistant to 50 meters for swimming. 7-day battery life on single charge. Compatible with iOS and Android. GPS connectivity for outdoor activities. Customizable watch faces and interchangeable bands.",
        "AU": "Smart Fitness Tracker Watch with Heart Rate Monitor. Tracks steps, calories, distance, and sleep patterns. Water resistant to 50 metres for swimming. 7-day battery life. Compatible with iOS and Android. GPS for outdoor activities. Customisable watch faces and interchangeable bands.",
        "ES": "Reloj inteligente rastreador de actividad con monitor de frecuencia cardíaca. Seguimiento de pasos, calorías, distancia y análisis del sueño. Resistente al agua 5 ATM para natación. Duración de la batería hasta 6 días. Compatible con iOS y Android. GPS para actividades al aire libre. Múltiples modos deportivos y esferas personalizables."
    }
}

# Mock product titles for different ASINs
MOCK_TITLES: dict[str, dict[str, str]] = {
    "B08N5WRWNW": {
        "US": "Sony WH-1000XM4 Wireless Premium Noise Canceling Overhead Headphones with Mic for Phone-Call and Alexa Voice Control, Black",
        "IN": "Sony WH-1000XM4 Wireless Premium Noise Canceling Overhead Headphones with Mic for Phone-Call and Alexa Voice Control, Black",
        "DE": "Sony WH-1000XM4 Kabellose Premium-Kopfhörer mit Geräuschunterdrückung und Mikrofon, Schwarz",
        "UK": "Sony WH-1000XM4 Wireless Premium Noise Cancelling Overhead Headphones with Mic for Phone-Call and Alexa Voice Control, Black",
        "JP": "Sony WH-1000XM4 ワイヤレスプレミアムノイズキャンセリングヘッドホン ブラック",
        "FR": "Sony WH-1000XM4 Casque sans fil à réduction de bruit, Noir",
        "CA": "Sony WH-1000XM4 Wireless Premium Noise Canceling Overhead Headphones with Mic for Phone-Call and Alexa Voice Control, Black",
        "AU": "Sony WH-1000XM4 Wireless Premium Noise Cancelling Overhead Headphones with Mic for Phone-Call and Alexa Voice Control, Black",
        "ES": "Sony WH-1000XM4 Auriculares inalámbricos premium con cancelación de ruido, Negro"
    },
    "B00TEST123": {
        "US": "Premium Wireless Bluetooth Earbuds with Active Noise Cancellation - Black",
        "IN": "Wireless Bluetooth Earbuds with Noise Cancellation - Black",
        "DE": "Kabellose Bluetooth-Ohrhörer mit Aktiver Geräuschunterdrückung - Schwarz",
        "UK": "Premium Wireless Bluetooth Earbuds with Active Noise Cancellation - Black",
        "JP": "ワイヤレスBluetoothイヤホン アクティブノイズキャンセリング - ブラック",
        "FR": "Écouteurs Bluetooth sans fil avec réduction active du bruit - Noir",
        "CA": "Premium Wireless Bluetooth Earbuds with Active Noise Cancellation - Black",
        "AU": "Wireless Bluetooth Earbuds with Active Noise Cancellation - Black",
        "ES": "Auriculares Bluetooth inalámbricos con cancelación activa de ruido - Negro"
    },
    "B00DIFFER1": {
        "US": "Ultra-Slim Laptop Stand made from Premium Aluminum Alloy",
        "IN": "Adjustable Mobile Phone Holder Stand for Desk",
        "DE": "Professioneller Tablet-Bodenständer mit Rollen",
        "UK": "Wooden Monitor Riser with Storage Drawer",
        "JP": "コンパクト折りたたみ式スマホスタンド",
        "FR": "Refroidisseur ergonomique pour ordinateur portable avec 5 ventilateurs",
        "CA": "Ultra-Slim Laptop Stand - Premium Aluminum",
        "AU": "Heavy Duty Monitor Arm Mount with Gas Spring",
        "ES": "Soporte de almohada ajustable para tablet en la cama"
    },
    "B09XYZ1234": {
        "US": "Stainless Steel Insulated Water Bottle - 32oz",
        "IN": "Stainless Steel Insulated Water Bottle - 32oz",
        "DE": "Edelstahl-Isolierflasche - 1 Liter",
        "UK": "Stainless Steel Insulated Water Bottle - 1 Litre",
        "JP": "ステンレス製断熱ウォーターボトル - 32オンス",
        "FR": "Bouteille d'eau isotherme en acier inoxydable - 1 Litre",
        "CA": "Stainless Steel Insulated Water Bottle - 32oz",
        "AU": "Stainless Steel Insulated Water Bottle - 1 Litre",
        "ES": "Botella de agua aislada de acero inoxidable - 1 Litro"
    },
    "B07MEDIUM1": {
        "US": "Smart Fitness Tracker Watch with Heart Rate Monitor",
        "IN": "Fitness Band with Heart Rate Monitoring",
        "DE": "Activity Tracker Smartwatch mit Pulsmessung",
        "UK": "Smart Fitness Tracker Watch with Heart Rate Monitor",
        "JP": "スマートフィットネストラッカーウォッチ 心拍数モニター付き",
        "FR": "Montre traqueur d'activité avec moniteur de fréquence cardiaque",
        "CA": "Smart Fitness Tracker Watch with Heart Rate Monitor",
        "AU": "Smart Fitness Tracker Watch with Heart Rate Monitor",
        "ES": "Reloj inteligente rastreador de actividad con monitor cardíaco"
    }
}


def get_mock_descriptions(asin: str) -> dict[str, str]:
    """
    Get mock descriptions for a given ASIN.
    If ASIN not found, generate deterministic variations based on ASIN hash.
    Produces realistically different descriptions per region to simulate
    how real Amazon listings differ across marketplaces.
    """
    if asin in MOCK_DESCRIPTIONS:
        return MOCK_DESCRIPTIONS[asin]
    
    # Generate DETERMINISTIC descriptions for unknown ASINs
    # Use hash of ASIN to ensure same ASIN always gets same result
    asin_hash = sum(ord(c) for c in asin)
    similarity_type_index = asin_hash % 3  # 0, 1, or 2
    
    # Product category variations based on ASIN hash
    categories = [
        {"name": "Wireless Headphones", "features": {
            "US": "Advanced 40mm dynamic drivers deliver deep bass and crystal-clear highs. Active Noise Cancellation blocks ambient noise up to 30dB. Bluetooth 5.2 with multipoint connection for seamless switching. 30-hour battery life with quick charge — 10 minutes for 5 hours playback. Built-in microphone with AI noise reduction for clear calls. Foldable design with premium carrying case included. Touch controls on ear cup for playback and volume. Compatible with iOS and Android. Available in Midnight Black, Arctic White, and Navy Blue.",
            "IN": "Premium 40mm drivers produce rich bass and clear treble audio. Active Noise Cancelling technology reduces surrounding noise. Wireless Bluetooth 5.2 connectivity with dual device pairing. Long-lasting 30 hour battery with fast charging support — 10 min charge gives 5 hours use. Built-in mic with noise cancellation for calls. Foldable headband with carry pouch. Touch gesture controls on earcup. Works with all smartphones. Colour options: Black, White.",
            "DE": "Hochwertige 40-mm-Treiber liefern tiefen Bass und klare Höhen. Aktive Geräuschunterdrückung reduziert Umgebungsgeräusche um bis zu 30 dB. Bluetooth 5.2 mit Multipoint-Verbindung. 30 Stunden Akkulaufzeit mit Schnellladefunktion — 10 Minuten Laden für 5 Stunden Wiedergabe. Integriertes Mikrofon mit KI-Störgeräuschreduzierung. Faltbares Design mit Premium-Tragetasche. Touch-Steuerung am Ohrpolster. Kompatibel mit iOS und Android. Erhältlich in Schwarz, Weiß und Blau.",
            "UK": "Advanced 40mm dynamic drivers deliver deep bass and crystal-clear highs. Active Noise Cancellation blocks ambient noise up to 30dB. Bluetooth 5.2 with multipoint connection for seamless switching. 30-hour battery life with quick charge — 10 minutes for 5 hours playback. Built-in microphone with AI noise reduction for clear calls. Foldable design with premium carrying case included. Touch controls on ear cup. Compatible with iOS and Android. Available in Midnight Black, Arctic White, and Navy Blue.",
            "JP": "40mm大口径ドライバーが深みのある低音とクリアな高音を実現。アクティブノイズキャンセリングで最大30dBの騒音を低減。Bluetooth 5.2マルチポイント対応。30時間バッテリー、10分充電で5時間再生。AIノイズリダクション搭載マイク。折りたたみ式デザイン、キャリングケース付属。タッチコントロール対応。iOS/Android対応。ブラック、ホワイト、ネイビーの3色展開。",
            "FR": "Transducteurs dynamiques 40mm pour basses profondes et aigus cristallins. Réduction active du bruit jusqu'à 30dB. Bluetooth 5.2 avec connexion multipoint. Autonomie 30 heures avec charge rapide — 10 minutes pour 5 heures d'écoute. Microphone intégré avec réduction de bruit IA. Design pliable avec étui de transport premium. Commandes tactiles. Compatible iOS et Android. Disponible en noir, blanc et bleu marine.",
            "CA": "Advanced 40mm dynamic drivers deliver deep bass and crystal-clear highs. Active Noise Cancellation blocks ambient noise up to 30dB. Bluetooth 5.2 with multipoint connection. 30-hour battery life with quick charge — 10 minutes for 5 hours playback. Built-in microphone with AI noise reduction for clear calls. Foldable design with carrying case included. Touch controls on ear cup. Compatible with iOS and Android. Available in Midnight Black, Arctic White, and Navy Blue.",
            "AU": "Premium 40mm dynamic drivers for rich bass and crisp highs. Active Noise Cancellation blocks ambient noise up to 30dB. Bluetooth 5.2 with multipoint connectivity. 30-hour battery with quick charge — 10 mins for 5 hours. Built-in mic with AI noise reduction. Foldable design with carry case. Touch controls. Compatible with iOS and Android. Colours: Midnight Black, Arctic White, Navy Blue.",
            "ES": "Controladores dinámicos de 40mm para graves profundos y agudos cristalinos. Cancelación activa de ruido hasta 30dB. Bluetooth 5.2 con conexión multipunto. 30 horas de batería con carga rápida — 10 minutos para 5 horas. Micrófono integrado con reducción de ruido IA. Diseño plegable con estuche. Controles táctiles. Compatible con iOS y Android. Disponible en negro, blanco y azul marino."
        }},
        {"name": "Smart Watch", "features": {
            "US": "1.4-inch AMOLED display with Always-On mode and 1000 nits peak brightness. Heart rate monitoring, SpO2 tracking, and stress management. GPS + GLONASS for accurate outdoor tracking. 14-day battery life with typical usage. 5ATM water resistance — suitable for swimming. 120+ sport modes including running, cycling, and yoga. Sleep tracking with REM analysis. Notifications for calls, texts, and apps. Customizable watch faces. Works with iOS 12+ and Android 8+. Stainless steel case with silicone band.",
            "IN": "1.4 inch AMOLED full touch display with Always-On feature, 1000 nits brightness. Continuous heart rate monitor with SpO2 and stress tracking. Built-in GPS for outdoor activities. Up to 14 days battery life on single charge. 5ATM water resistant for swimming and showering. 120 sports modes covering running, walking, cycling. Advanced sleep monitoring. Smart notifications for calls and messages. Multiple watch face options. Supports Android 8+ and iOS 12+. Metal body with silicone strap.",
            "DE": "1,4-Zoll-AMOLED-Display mit Always-On-Modus und 1000 Nits Spitzenhelligkeit. Herzfrequenzüberwachung, SpO2-Messung und Stressmanagement. GPS + GLONASS für präzises Outdoor-Tracking. 14 Tage Akkulaufzeit bei normaler Nutzung. 5ATM wasserdicht – zum Schwimmen geeignet. Über 120 Sportmodi. Schlafüberwachung mit REM-Analyse. Benachrichtigungen für Anrufe und Nachrichten. Anpassbare Zifferblätter. Kompatibel mit iOS 12+ und Android 8+.",
            "UK": "1.4-inch AMOLED display with Always-On mode and 1000 nits peak brightness. Heart rate monitoring, SpO2 tracking, and stress management tools. GPS + GLONASS for precise outdoor tracking. 14-day battery life with typical usage. 5ATM water resistance for swimming. 120+ sport modes. Sleep tracking with REM analysis. Call and app notifications. Customisable watch faces. Compatible with iOS 12+ and Android 8+. Stainless steel case with silicone band.",
            "JP": "1.4インチAMOLEDディスプレイ、常時表示対応、最大1000nits。心拍数モニタリング、SpO2、ストレス管理。GPS+GLONASS搭載。14日間バッテリー。5ATM防水。120以上のスポーツモード。睡眠トラッキング（REM分析付き）。通知機能。カスタマイズ可能な文字盤。iOS 12+/Android 8+対応。",
            "FR": "Écran AMOLED 1,4 pouces avec mode Always-On et luminosité 1000 nits. Suivi de la fréquence cardiaque, SpO2 et gestion du stress. GPS + GLONASS pour un suivi précis en extérieur. Autonomie 14 jours. Étanchéité 5ATM pour la natation. Plus de 120 modes sportifs. Suivi du sommeil avec analyse REM. Notifications appels et messages. Cadrans personnalisables. Compatible iOS 12+ et Android 8+.",
            "CA": "1.4-inch AMOLED display with Always-On mode and 1000 nits brightness. Heart rate, SpO2, and stress monitoring. GPS + GLONASS for outdoor tracking. 14-day battery life. 5ATM water resistance for swimming. 120+ sport modes. Sleep tracking with REM analysis. Notifications for calls and apps. Customizable watch faces. Works with iOS 12+ and Android 8+. Stainless steel case.",
            "AU": "1.4-inch AMOLED display with Always-On and 1000 nits brightness. Heart rate monitoring, SpO2, and stress management. GPS + GLONASS. 14-day battery. 5ATM water resistant — swim-ready. 120+ sport modes. Sleep tracking with REM. Call and app notifications. Customisable watch faces. iOS 12+ and Android 8+ compatible. Stainless steel with silicone band.",
            "ES": "Pantalla AMOLED de 1,4 pulgadas con modo Always-On y brillo de 1000 nits. Monitorización de frecuencia cardíaca, SpO2 y gestión del estrés. GPS + GLONASS para seguimiento preciso. 14 días de batería. Resistencia al agua 5ATM. Más de 120 modos deportivos. Seguimiento del sueño con análisis REM. Notificaciones de llamadas y apps. Esferas personalizables. Compatible iOS 12+ y Android 8+."
        }},
        {"name": "Portable Charger", "features": {
            "US": "20000mAh high-capacity portable power bank with USB-C PD 65W fast charging. Charges a MacBook Air to 50% in 30 minutes. Dual USB-C ports and one USB-A port for charging 3 devices simultaneously. LED digital display shows exact battery percentage. Slim aluminum body weighs only 12.5oz. Includes USB-C to USB-C cable. Airline approved — safe for carry-on luggage. Compatible with iPhone 15, Samsung Galaxy, iPad, Nintendo Switch, and more.",
            "IN": "20000mAh power bank with 65W USB-C Power Delivery charging. Fast charges laptops and smartphones. Two USB-C + one USB-A port for 3 devices at once. Digital LED display for battery level. Lightweight aluminium alloy body at 350g. USB-C cable included in box. Flight-safe design approved for cabin baggage. Universal compatibility with all USB devices including iPhone, Samsung, Xiaomi, OnePlus.",
            "DE": "20000mAh Powerbank mit USB-C PD 65W Schnellladefunktion. Lädt ein MacBook Air in 30 Minuten auf 50%. Zwei USB-C-Anschlüsse und ein USB-A-Anschluss für 3 Geräte gleichzeitig. LED-Display zeigt den genauen Akkustand. Schlankes Aluminiumgehäuse mit nur 350g. USB-C-Kabel im Lieferumfang. Flugzeug-zugelassen als Handgepäck. Kompatibel mit iPhone, Samsung Galaxy, iPad und mehr.",
            "UK": "20000mAh high-capacity portable power bank with USB-C PD 65W fast charging. Charges a MacBook Air to 50% in 30 minutes. Dual USB-C and one USB-A port for 3 devices simultaneously. LED display shows battery percentage. Slim aluminium body weighs only 350g. USB-C cable included. Airline approved for carry-on. Compatible with iPhone 15, Samsung Galaxy, iPad, Nintendo Switch.",
            "JP": "20000mAhモバイルバッテリー、USB-C PD 65W急速充電対応。MacBook Airを30分で50%充電。USB-C×2 + USB-A×1で3台同時充電。LEDデジタル表示。軽量アルミボディ（約350g）。USB-Cケーブル付属。機内持ち込み可能。iPhone、Galaxy、iPad対応。",
            "FR": "Batterie externe 20000mAh avec charge rapide USB-C PD 65W. Charge un MacBook Air à 50% en 30 minutes. Double USB-C + USB-A pour 3 appareils simultanément. Affichage LED du niveau de batterie. Corps fin en aluminium de 350g. Câble USB-C inclus. Approuvé pour avion en cabine. Compatible iPhone 15, Samsung Galaxy, iPad.",
            "CA": "20000mAh high-capacity portable power bank with USB-C PD 65W fast charging. Charges MacBook Air to 50% in 30 minutes. Dual USB-C + USB-A for 3 devices. LED display for battery level. Slim aluminum body at 12.5oz. USB-C cable included. Airline approved for carry-on. Compatible with iPhone, Samsung, iPad, Switch.",
            "AU": "20000mAh power bank with USB-C PD 65W fast charging. Charges MacBook Air to 50% in 30 min. Dual USB-C + USB-A — charge 3 devices at once. LED display shows exact battery percentage. Lightweight aluminium body, 350g. USB-C cable included. Airline approved. Works with iPhone 15, Samsung Galaxy, iPad, Nintendo Switch and more.",
            "ES": "Batería externa 20000mAh con carga rápida USB-C PD 65W. Carga un MacBook Air al 50% en 30 minutos. Doble USB-C + USB-A para 3 dispositivos simultáneamente. Pantalla LED con porcentaje de batería. Cuerpo delgado de aluminio, 350g. Cable USB-C incluido. Aprobado para avión. Compatible con iPhone 15, Samsung Galaxy, iPad."
        }}
    ]
    
    category = categories[asin_hash % len(categories)]
    
    if similarity_type_index == 0:  # LOW risk - mostly same content, minor locale tweaks
        base = category["features"]["US"]
        return {
            "US": base,
            "IN": base.replace("colors", "colours").replace("12.5oz", "350g"),
            "DE": base.replace("colors", "Farben").replace("inches", "Zoll"),
            "UK": base.replace("colors", "colours").replace("aluminum", "aluminium"),
            "JP": base,
            "FR": base.replace("colors", "couleurs").replace("aluminum", "aluminium"),
            "CA": base,
            "AU": base.replace("colors", "colours").replace("aluminum", "aluminium").replace("customize", "customise"),
            "ES": base.replace("colors", "colores").replace("aluminum", "aluminio"),
        }
    elif similarity_type_index == 1:  # MEDIUM risk - regionally adapted
        return category["features"]
    else:  # HIGH risk - significantly different per region
        features = category["features"]
        # Shuffle some region descriptions to create bigger mismatches
        return {
            "US": features["US"],
            "IN": features["IN"],
            "DE": features["DE"],
            "UK": features["UK"],
            "JP": features["JP"],
            "FR": features["FR"],
            "CA": features["CA"],
            "AU": features["AU"],
            "ES": features["ES"],
        }


def get_mock_titles(asin: str) -> dict[str, str]:
    """
    Get mock titles for a given ASIN.
    Generate realistic region-specific titles for unknown ASINs.
    """
    if asin in MOCK_TITLES:
        return MOCK_TITLES[asin]
    
    # Generate deterministic titles for unknown ASINs
    asin_hash = sum(ord(c) for c in asin)
    similarity_type_index = asin_hash % 3
    
    categories = [
        {
            "US": "Premium Wireless Over-Ear Headphones with Active Noise Cancellation, 30H Battery, Bluetooth 5.2",
            "IN": "Wireless Bluetooth Headphones with ANC, 30 Hour Battery, Over-Ear Design",
            "DE": "Kabellose Over-Ear-Kopfhörer mit aktiver Geräuschunterdrückung, 30 Std. Akku, Bluetooth 5.2",
            "UK": "Premium Wireless Over-Ear Headphones with Active Noise Cancellation, 30H Battery, Bluetooth 5.2",
            "JP": "ワイヤレスノイズキャンセリングヘッドホン Bluetooth 5.2 30時間再生",
            "FR": "Casque sans fil à réduction de bruit active, 30H d'autonomie, Bluetooth 5.2",
            "CA": "Premium Wireless Over-Ear Headphones with Active Noise Cancellation, 30H Battery",
            "AU": "Wireless Over-Ear Headphones with ANC, 30H Battery, Bluetooth 5.2",
            "ES": "Auriculares inalámbricos con cancelación activa de ruido, 30H batería, Bluetooth 5.2"
        },
        {
            "US": "Smart Fitness Watch 1.4\" AMOLED, GPS, Heart Rate & SpO2, 14-Day Battery, 5ATM Waterproof",
            "IN": "Smartwatch with AMOLED Display, GPS, Heart Rate Monitor, 14 Day Battery, Water Resistant",
            "DE": "Smartwatch 1,4\" AMOLED, GPS, Herzfrequenz & SpO2, 14 Tage Akku, 5ATM Wasserdicht",
            "UK": "Smart Fitness Watch 1.4\" AMOLED, GPS, Heart Rate & SpO2, 14-Day Battery, 5ATM",
            "JP": "スマートウォッチ 1.4インチAMOLED GPS 心拍数SpO2 14日間バッテリー 5ATM防水",
            "FR": "Montre connectée AMOLED 1,4\", GPS, Fréquence cardiaque, 14 jours d'autonomie, 5ATM",
            "CA": "Smart Fitness Watch 1.4\" AMOLED, GPS, Heart Rate & SpO2, 14-Day Battery",
            "AU": "Smart Fitness Watch AMOLED, GPS, Heart Rate, SpO2, 14-Day Battery, 5ATM",
            "ES": "Reloj inteligente AMOLED 1,4\", GPS, Frecuencia cardíaca, 14 días batería, 5ATM"
        },
        {
            "US": "20000mAh Portable Charger USB-C PD 65W Fast Charging Power Bank, 3-Port, Airline Approved",
            "IN": "20000mAh Power Bank with 65W USB-C Fast Charging, Triple Port, Laptop Compatible",
            "DE": "20000mAh Powerbank USB-C PD 65W Schnelllade-Akku, 3 Anschlüsse, Flugzeug-zugelassen",
            "UK": "20000mAh Portable Charger USB-C PD 65W Fast Charging, 3-Port, Airline Approved",
            "JP": "モバイルバッテリー 20000mAh USB-C PD 65W 急速充電 3ポート 機内持込可",
            "FR": "Batterie externe 20000mAh USB-C PD 65W, 3 ports, approuvée avion",
            "CA": "20000mAh Portable Charger USB-C PD 65W Fast Charging, 3-Port, Airline Approved",
            "AU": "20000mAh Power Bank USB-C PD 65W Fast Charge, 3-Port, Airline Safe",
            "ES": "Batería externa 20000mAh USB-C PD 65W carga rápida, 3 puertos, aprobada avión"
        }
    ]
    
    return categories[asin_hash % len(categories)]


def tokenize_title(text: str) -> list[str]:
    """
    Tokenize title into words and punctuation for better diffing.
    """
    return re.findall(r'\w+|[^\w\s]', text, re.UNICODE)


def calculate_title_similarity(t1: str, t2: str) -> float:
    """
    Calculate a robust similarity score for titles.
    Combines Jaccard (word overlap) and Sequence (character order) similarity.
    """
    # Normalize
    t1_norm = t1.lower()
    t2_norm = t2.lower()
    
    # 1. Jaccard Similarity (Word Overlap)
    # Use simple split for Jaccard to avoid punctuation noise
    words1 = set(t1_norm.split())
    words2 = set(t2_norm.split())
    intersection = len(words1.intersection(words2))
    union = len(words1.union(words2))
    jaccard = intersection / union if union > 0 else 0.0
    
    # 2. Sequence Similarity (Character Order / Levenshtein-like)
    sequence = SequenceMatcher(None, t1_norm, t2_norm).ratio()
    
    # Weighted Average: 40% Jaccard, 60% Sequence
    # Sequence is usually better for titles as order matters ("Case for iPhone" vs "iPhone for Case")
    return (jaccard * 0.4) + (sequence * 0.6)


def generate_title_diff(title1: str, title2: str) -> list[dict]:
    """
    Generate a detailed token-level diff between two titles.
    """
    # Use advanced tokenization to separate punctuation
    a = tokenize_title(title1)
    b = tokenize_title(title2)
    
    matcher = SequenceMatcher(None, a, b)
    diff = []
    
    for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
        if opcode == 'equal':
            diff.append({"type": "equal", "text": "".join([" " + t if t.isalnum() else t for t in a[a0:a1]]).strip()})
        elif opcode == 'insert':
            diff.append({"type": "insert", "text": "".join([" " + t if t.isalnum() else t for t in b[b0:b1]]).strip()})
        elif opcode == 'delete':
            diff.append({"type": "delete", "text": "".join([" " + t if t.isalnum() else t for t in a[a0:a1]]).strip()})
        elif opcode == 'replace':
            diff.append({"type": "delete", "text": "".join([" " + t if t.isalnum() else t for t in a[a0:a1]]).strip()})
            diff.append({"type": "insert", "text": "".join([" " + t if t.isalnum() else t for t in b[b0:b1]]).strip()})
            
    return diff


def generate_description_diff(desc1: str, desc2: str) -> list[dict]:
    """
    Generate a word-level diff between two descriptions.
    Uses word-level comparison for accurate highlighting of differences.
    Falls back to character-level for very short texts.
    """
    if not desc1 or not desc2:
        return [{"type": "equal", "text": desc1 or desc2 or ""}]
    
    # For very short texts (< 5 words), use character-level diff
    if len(desc1.split()) < 5 and len(desc2.split()) < 5:
        matcher = SequenceMatcher(None, desc1, desc2)
        diff = []
        for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
            if opcode == 'equal':
                diff.append({"type": "equal", "text": desc1[a0:a1]})
            elif opcode == 'insert':
                diff.append({"type": "insert", "text": desc2[b0:b1]})
            elif opcode == 'delete':
                diff.append({"type": "delete", "text": desc1[a0:a1]})
            elif opcode == 'replace':
                diff.append({"type": "delete", "text": desc1[a0:a1]})
                diff.append({"type": "insert", "text": desc2[b0:b1]})
        return diff
    
    # Word-level diff for normal text
    a = desc1.split()
    b = desc2.split()

    matcher = SequenceMatcher(None, a, b)
    diff = []

    for opcode, a0, a1, b0, b1 in matcher.get_opcodes():
        if opcode == 'equal':
            diff.append({"type": "equal", "text": " ".join(a[a0:a1])})
        elif opcode == 'insert':
            diff.append({"type": "insert", "text": " ".join(b[b0:b1])})
        elif opcode == 'delete':
            diff.append({"type": "delete", "text": " ".join(a[a0:a1])})
        elif opcode == 'replace':
            diff.append({"type": "delete", "text": " ".join(a[a0:a1])})
            diff.append({"type": "insert", "text": " ".join(b[b0:b1])})

    return diff


# Amazon region domain mapping
REGION_DOMAINS: dict[str, str] = {
    "US": "www.amazon.com",
    "IN": "www.amazon.in",
    "DE": "www.amazon.de",
    "UK": "www.amazon.co.uk",
    "JP": "www.amazon.co.jp",
    "FR": "www.amazon.fr",
    "CA": "www.amazon.ca",
    "AU": "www.amazon.com.au",
    "ES": "www.amazon.es"
}


def get_region_url(region: str, asin: str) -> str:
    """Get the Amazon product URL for a given region and ASIN."""
    domain = REGION_DOMAINS.get(region, "www.amazon.com")
    return f"https://{domain}/dp/{asin}"


def check_title_mismatch(titles: dict[str, str]) -> dict:
    """
    Check for title mismatches across regions.
    """
    regions = list(titles.keys())
    mismatches = []
    is_mismatch = False
    
    for i in range(len(regions)):
        for j in range(i + 1, len(regions)):
            r1, r2 = regions[i], regions[j]
            t1, t2 = titles[r1], titles[r2]
            
            # Calculate robust similarity
            similarity = calculate_title_similarity(t1, t2)
            
            if similarity < 0.70:  # Threshold for title mismatch (calibrated for translated titles)
                is_mismatch = True
                # Generate diff
                diff = generate_title_diff(t1, t2)
                
                mismatches.append({
                    "region_1": r1,
                    "region_2": r2,
                    "title_1": t1,
                    "title_2": t2,
                    "similarity": round(similarity, 4),
                    "diff": diff
                })
                
    return {
        "is_mismatch": is_mismatch,
        "titles": titles,
        "mismatches": mismatches
    }



def calculate_pairwise_similarities(descriptions: dict[str, str], asin: str) -> tuple[list[dict], dict, list[dict]]:
    """
    Calculate similarity scores between all pairs of region descriptions.
    Returns (comparisons, global_spec_analysis, global_issues).

    NEW: Runs the full 6-technique pipeline per pair and aggregates issues.
    """
    regions = list(descriptions.keys())
    comparisons = []

    # ── Global spec extraction (across ALL regions at once) ───────
    specs_by_region = {r: SpecExtractor.extract(descriptions[r]) for r in regions}
    global_spec_analysis = SpecExtractor.compare_across_regions(specs_by_region)

    all_issues: list[dict] = []

    for i in range(len(regions)):
        for j in range(i + 1, len(regions)):
            region_1 = regions[i]
            region_2 = regions[j]
            desc_1 = descriptions[region_1]
            desc_2 = descriptions[region_2]

            # Full multi-dimensional analysis
            detailed = calculate_similarity_advanced(desc_1, desc_2)

            # Generate description diff (word-level)
            desc_diff = generate_description_diff(desc_1, desc_2)

            # Detect issues for this pair
            pair_issues = IssueDetector.detect(
                region_1, region_2, desc_1, desc_2,
                global_spec_analysis,
                detailed['sentence_detail'],
                detailed['content_gaps'],
                detailed['structural_detail'],
            )
            all_issues.extend(pair_issues)

            comparisons.append({
                "region_1": region_1,
                "region_2": region_2,
                "similarity_score": detailed['combined_score'],
                # New per-dimension scores
                "ngram_dice": detailed['ngram_dice'],
                "bigram_jaccard": detailed['bigram_jaccard'],
                "word_jaccard": detailed['word_jaccard'],
                "sequence_score": detailed['sequence'],
                "sentence_alignment": detailed['sentence_alignment'],
                "feature_overlap": detailed['feature_overlap'],
                "spec_match": detailed['spec_match'],
                "structural_score": detailed['structural'],
                "tfidf_score": detailed['tfidf_cosine'],
                # Keep legacy field names for backward compat
                "jaccard_score": detailed['word_jaccard'],
                "confidence": detailed['confidence'],
                "description_1": desc_1,
                "description_2": desc_2,
                "description_diff": desc_diff,
                "url_1": get_region_url(region_1, asin),
                "url_2": get_region_url(region_2, asin),
                # Per-pair issues
                "issues": pair_issues,
                # Full sentence alignment for structured diff view
                "sentence_detail": detailed['sentence_detail'],
                # Content gaps
                "content_gaps": detailed['content_gaps'],
            })

    # De-duplicate global issues (same spec conflict may appear from multiple pairs)
    seen = set()
    unique_issues = []
    for iss in all_issues:
        key = (iss['type'], iss['title'], iss['description'])
        if key not in seen:
            seen.add(key)
            unique_issues.append(iss)
    unique_issues.sort(key=lambda x: {'high': 0, 'medium': 1, 'low': 2}.get(x['severity'], 3))

    # Cap issues per severity to keep the output manageable
    MAX_HIGH = 20
    MAX_MEDIUM = 15
    MAX_LOW = 10
    capped: list[dict] = []
    counts = {'high': 0, 'medium': 0, 'low': 0}
    caps = {'high': MAX_HIGH, 'medium': MAX_MEDIUM, 'low': MAX_LOW}
    for iss in unique_issues:
        sev = iss['severity']
        if counts[sev] < caps.get(sev, 10):
            capped.append(iss)
            counts[sev] += 1

    return comparisons, global_spec_analysis, capped


def determine_risk_level(comparisons: list[dict]) -> RiskLevel:
    """
    Determine overall risk level based on comparison scores.
    
    Risk Levels:
    - LOW: Average similarity >= 0.55 and min >= 0.30
    - MEDIUM: Average similarity >= 0.30 and min >= 0.10
    - HIGH: Below MEDIUM thresholds or >=5 spec conflicts
    
    Thresholds are calibrated for translated content where word-level
    metrics naturally score lower than monolingual comparisons.
    """
    if not comparisons:
        return "LOW"
    
    avg_similarity = sum(c["similarity_score"] for c in comparisons) / len(comparisons)
    min_similarity = min(c["similarity_score"] for c in comparisons)
    
    # Count high-severity issues across all pairs
    total_high_issues = sum(len([i for i in c.get("issues", []) if i.get("severity") == "high"]) for c in comparisons)
    
    # If there are many actual spec conflicts, that's a strong signal
    if total_high_issues >= 5:
        return "HIGH"
    
    if avg_similarity >= 0.55 and min_similarity >= 0.30:
        return "LOW"
    elif avg_similarity >= 0.30 and min_similarity >= 0.10:
        return "MEDIUM"
    else:
        return "HIGH"


async def generate_descriptions_from_page(page_description: str, page_region: str) -> dict[str, str]:
    """
    Generate per-region descriptions based on actual scraped content from the
    current Amazon page.  The current region gets the real text; English-speaking
    regions get locale-tweaked copies; non-English regions get Google-Translated
    versions so the translation pipeline is exercised realistically.
    """
    import asyncio
    base = page_description
    descriptions: dict[str, str] = {}

    # Current region always gets the exact scraped text
    descriptions[page_region] = base

    # English-speaking regions: small locale tweaks
    en_tweaks = {
        "US": lambda d: d,
        "IN": lambda d: d.replace("$", "₹").replace("12.5oz", "350g"),
        "UK": lambda d: (d.replace("color", "colour").replace("Color", "Colour")
                          .replace("aluminum", "aluminium").replace("Aluminum", "Aluminium")
                          .replace("customize", "customise")),
        "CA": lambda d: d,
        "AU": lambda d: (d.replace("color", "colour").replace("Color", "Colour")
                          .replace("aluminum", "aluminium").replace("Aluminum", "Aluminium")
                          .replace("customize", "customise").replace("organize", "organise")),
    }

    for region, tweak in en_tweaks.items():
        if region not in descriptions:
            descriptions[region] = tweak(base)

    # Non-English regions: translate the base description
    from translator import _translate_text, _DT_LANG_CODE
    target_langs = {"DE": "de", "JP": "ja", "FR": "fr", "ES": "es"}

    async def _translate_for_region(region: str, lang: str):
        try:
            translated = await asyncio.to_thread(_translate_text, base, "en", lang)
            return region, translated if translated else base
        except Exception:
            return region, base

    tasks = [
        _translate_for_region(r, l)
        for r, l in target_langs.items()
        if r not in descriptions
    ]
    if tasks:
        results = await asyncio.gather(*tasks)
        for region, text in results:
            descriptions[region] = text

    return descriptions


async def generate_titles_from_page(page_title: str, page_region: str) -> dict[str, str]:
    """
    Generate per-region titles based on the actual scraped title.
    Similar logic to generate_descriptions_from_page but for short titles.
    """
    import asyncio
    titles: dict[str, str] = {}
    titles[page_region] = page_title

    # English regions get the same title
    for r in ["US", "IN", "UK", "CA", "AU"]:
        if r not in titles:
            titles[r] = page_title

    # Non-English regions get translated titles
    from translator import _translate_text
    target_langs = {"DE": "de", "JP": "ja", "FR": "fr", "ES": "es"}

    async def _translate_title(region: str, lang: str):
        try:
            translated = await asyncio.to_thread(_translate_text, page_title, "en", lang)
            return region, translated if translated else page_title
        except Exception:
            return region, page_title

    tasks = [
        _translate_title(r, l)
        for r, l in target_langs.items()
        if r not in titles
    ]
    if tasks:
        results = await asyncio.gather(*tasks)
        for region, text in results:
            titles[region] = text

    return titles


async def check_description_consistency(
    asin: str,
    page_title: str | None = None,
    page_description: str | None = None,
    page_region: str | None = None,
) -> dict:
    """
    Main function to check description consistency for a given ASIN.
    Returns complete analysis result with detailed metrics.
    Translates non-English descriptions to English before comparison.

    If page_title / page_description / page_region are provided and the ASIN
    is not one of the hardcoded mock ASINs, the actual scraped content is used
    as the base for generating realistic per-region mock data.
    """
    # Get descriptions for all regions
    use_page_data = (
        page_description
        and page_region
        and len(page_description) >= 30
        and asin not in MOCK_DESCRIPTIONS
    )
    if use_page_data:
        descriptions = await generate_descriptions_from_page(page_description, page_region)
    else:
        descriptions = get_mock_descriptions(asin)

    # Get titles for all regions
    use_page_title = (
        page_title
        and page_region
        and len(page_title) >= 5
        and asin not in MOCK_TITLES
    )
    if use_page_title:
        titles = await generate_titles_from_page(page_title, page_region)
    else:
        titles = get_mock_titles(asin)
    
    # ── Translate descriptions to English for fair comparison ─────
    translation_results = await translate_descriptions(descriptions, target_lang="en")
    
    # Build translated descriptions dict for comparison
    translated_descriptions = {
        region: info["translated"]
        for region, info in translation_results.items()
    }
    
    # Build language info per region
    language_info = {}
    for region, info in translation_results.items():
        language_info[region] = {
            "detected_language": info["source_language"],
            "language_name": info["source_language_name"],
            "was_translated": info["was_translated"],
            "original_text": info["original"],
            "translated_text": info["translated"],
        }
    
    # ── Translate titles to English for fair comparison ───────────
    title_translation_results = await translate_descriptions(titles, target_lang="en")
    translated_titles = {
        region: info["translated"]
        for region, info in title_translation_results.items()
    }
    
    # Check for title mismatches using translated titles
    title_analysis = check_title_mismatch(translated_titles)
    # Also include original titles in the analysis
    title_analysis["original_titles"] = titles
    title_analysis["translated_titles"] = translated_titles
    title_language_info = {}
    for region, info in title_translation_results.items():
        title_language_info[region] = {
            "detected_language": info["source_language"],
            "language_name": info["source_language_name"],
            "was_translated": info["was_translated"],
        }
    title_analysis["language_info"] = title_language_info
    
    # Calculate pairwise similarities using TRANSLATED descriptions
    comparisons, global_spec_analysis, global_issues = calculate_pairwise_similarities(translated_descriptions, asin)
    
    # Enrich comparisons with original text + language info
    for comp in comparisons:
        r1 = comp["region_1"]
        r2 = comp["region_2"]
        comp["original_description_1"] = descriptions[r1]
        comp["original_description_2"] = descriptions[r2]
        comp["language_1"] = language_info[r1]["detected_language"]
        comp["language_2"] = language_info[r2]["detected_language"]
        comp["language_name_1"] = language_info[r1]["language_name"]
        comp["language_name_2"] = language_info[r2]["language_name"]
        comp["was_translated_1"] = language_info[r1]["was_translated"]
        comp["was_translated_2"] = language_info[r2]["was_translated"]
    
    # Determine risk level
    risk_level = determine_risk_level(comparisons)

    # Escalate risk if there are high-severity issues
    high_issues = [i for i in global_issues if i['severity'] == 'high']
    if high_issues and risk_level == "LOW":
        risk_level = "MEDIUM"
    
    # If there is a title mismatch AND high-severity issues, escalate
    # (title mismatch alone doesn't escalate — translated titles naturally differ)
    if title_analysis["is_mismatch"] and high_issues:
        if risk_level == "LOW":
            risk_level = "MEDIUM"
        elif risk_level == "MEDIUM":
            risk_level = "HIGH"
    
    # Calculate statistics
    similarity_scores = [c["similarity_score"] for c in comparisons]
    avg_similarity = sum(similarity_scores) / len(similarity_scores) if similarity_scores else 1.0
    min_similarity = min(similarity_scores) if similarity_scores else 1.0
    max_similarity = max(similarity_scores) if similarity_scores else 1.0
    
    # Determine overall confidence
    confidences = [c["confidence"] for c in comparisons]
    if all(c == "HIGH" for c in confidences):
        overall_confidence = "HIGH"
    elif any(c == "LOW" for c in confidences):
        overall_confidence = "LOW"
    else:
        overall_confidence = "MEDIUM"
    
    # Build region URLs map
    region_urls = {region: get_region_url(region, asin) for region in descriptions.keys()}
    
    return {
        "asin": asin,
        "risk_level": risk_level,
        "average_similarity": round(avg_similarity, 4),
        "min_similarity": round(min_similarity, 4),
        "max_similarity": round(max_similarity, 4),
        "confidence": overall_confidence,
        "comparisons": comparisons,
        "regions_analyzed": list(descriptions.keys()),
        "region_urls": region_urls,
        "descriptions": descriptions,
        "translated_descriptions": translated_descriptions,
        "language_info": language_info,
        "title_analysis": title_analysis,
        # ── NEW v3 fields ──────────────────────────────────────────
        "issues": global_issues,
        "spec_analysis": global_spec_analysis,
        "issue_counts": {
            "high": len([i for i in global_issues if i['severity'] == 'high']),
            "medium": len([i for i in global_issues if i['severity'] == 'medium']),
            "low": len([i for i in global_issues if i['severity'] == 'low']),
            "total": len(global_issues),
        },
    }
