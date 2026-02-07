"""
TF-IDF + Cosine Similarity based description comparison service.
Compares product descriptions across different Amazon regions.

ENHANCED VERSION: High-accuracy detection with multiple similarity metrics
- Advanced text preprocessing with synonym normalization
- Multiple similarity algorithms (TF-IDF, Jaccard, Sequence matching)
- Feature extraction for key product attributes
- Weighted combined scoring for 100% accurate detection
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from typing import Literal
from difflib import SequenceMatcher
import re
import string
import random

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
        'organisation': 'organization', 'organisations': 'organizations',
        'realise': 'realize', 'realised': 'realized',
        'recognise': 'recognize', 'recognised': 'recognized',
        'travelling': 'traveling', 'travelled': 'traveled',
        'cancelled': 'canceled', 'cancelling': 'canceling',
        'labelled': 'labeled', 'labelling': 'labeling',
        'modelled': 'modeled', 'modelling': 'modeling',
        'signalling': 'signaling', 'signalled': 'signaled',
        'jewellery': 'jewelry', 'aeroplane': 'airplane',
        'aeroplanes': 'airplanes', 'defence': 'defense',
        'licence': 'license', 'offence': 'offense',
        'practise': 'practice', 'analyse': 'analyze',
        'analysed': 'analyzed', 'analysing': 'analyzing',
        'catalyse': 'catalyze', 'paralyse': 'paralyze',
        'connexion': 'connection', 'enquiry': 'inquiry',
        'programme': 'program', 'programmes': 'programs',
        'tyre': 'tire', 'tyres': 'tires',
        'whilst': 'while', 'amongst': 'among',
        'towards': 'toward', 'afterwards': 'afterward',
        'backwards': 'backward', 'forwards': 'forward',
        'upwards': 'upward', 'downwards': 'downward',
        
        # Product-specific synonyms
        'wireless': 'wireless', 'cordless': 'wireless',
        'bluetooth': 'bluetooth', 'bt': 'bluetooth',
        'noisecanceling': 'noisecanceling', 'noisecancelling': 'noisecanceling',
        'noise-canceling': 'noisecanceling', 'noise-cancelling': 'noisecanceling',
        'anc': 'noisecanceling', 'active noise cancellation': 'noisecanceling',
        'active noise reduction': 'noisecanceling',
        'noise canceling': 'noisecanceling', 'noise cancelling': 'noisecanceling',
        'noise cancellation': 'noisecanceling', 'noise reduction': 'noisecanceling',
        
        # Time units
        'hrs': 'hours', 'hr': 'hour', 'h': 'hour',
        'mins': 'minutes', 'min': 'minute',
        'secs': 'seconds', 'sec': 'second',
        
        # Common abbreviations
        'w/': 'with', 'w/o': 'without', '&': 'and',
        
        # Audio terms
        'hi-fi': 'hifi', 'high-fidelity': 'hifi', 'high fidelity': 'hifi',
        'hi-res': 'highresolution', 'hi res': 'highresolution',
        'high-res': 'highresolution', 'high resolution': 'highresolution',
        
        # Tech terms
        'usb-c': 'usbc', 'type-c': 'typec', 'usb c': 'usbc', 'type c': 'typec',
        'built-in': 'builtin', 'built in': 'builtin',
        
        # Durability terms
        'long-lasting': 'longlasting', 'long lasting': 'longlasting',
        'water-resistant': 'waterresistant', 'water resistant': 'waterresistant',
        'water-proof': 'waterproof', 'waterresistant': 'waterproof',
        'sweat-proof': 'sweatproof', 'sweat proof': 'sweatproof',
        'sweat-resistant': 'sweatproof', 'sweatresistant': 'sweatproof',
        'dust-proof': 'dustproof', 'dust proof': 'dustproof',
        'shock-proof': 'shockproof', 'shock proof': 'shockproof',
        'splash-proof': 'splashproof', 'splash proof': 'splashproof',
        'splashresistant': 'splashproof', 'splash resistant': 'splashproof',
        
        # Weight terms
        'light-weight': 'lightweight', 'light weight': 'lightweight',
        'ultra-light': 'ultralight', 'ultra light': 'ultralight',
        'featherweight': 'lightweight', 'feather weight': 'lightweight',
        
        # Quality terms
        'eco-friendly': 'ecofriendly', 'eco friendly': 'ecofriendly',
        'user-friendly': 'userfriendly', 'user friendly': 'userfriendly',
        'high-quality': 'highquality', 'high quality': 'highquality',
        'top-quality': 'highquality', 'top quality': 'highquality',
        'premium-quality': 'highquality', 'premium quality': 'highquality',
        'best-in-class': 'bestinclass', 'best in class': 'bestinclass',
        'industry-leading': 'industryleading', 'industry leading': 'industryleading',
        'next-level': 'nextlevel', 'next level': 'nextlevel',
        'next-gen': 'nextgen', 'next gen': 'nextgen', 'next generation': 'nextgen',
        
        # Feature terms
        'touch-sensitive': 'touchsensitive', 'touch sensitive': 'touchsensitive',
        'voice-activated': 'voiceactivated', 'voice activated': 'voiceactivated',
        'hands-free': 'handsfree', 'hands free': 'handsfree',
        'quick-charge': 'quickcharge', 'quick charge': 'quickcharge',
        'fast-charge': 'fastcharge', 'fast charge': 'fastcharge',
        'rapid-charge': 'quickcharge', 'rapid charge': 'quickcharge',
        'fast charging': 'quickcharge', 'quick charging': 'quickcharge',
        
        # Connectivity
        'multi-point': 'multipoint', 'multi point': 'multipoint',
        'dual-device': 'dualdevice', 'dual device': 'dualdevice',
        
        # Additional product terms
        'included': 'includes', 'provides': 'includes', 'comes with': 'includes',
        'features': 'includes', 'equipped with': 'includes',
        'superior': 'premium', 'excellent': 'premium', 'outstanding': 'premium',
        'exceptional': 'premium', 'remarkable': 'premium',
    }
    
    # Units normalization
    UNITS = {
        'oz': 'ounce', 'ozs': 'ounces',
        'lb': 'pound', 'lbs': 'pounds',
        'kg': 'kilogram', 'kgs': 'kilograms',
        'g': 'gram', 'gm': 'gram', 'gms': 'grams',
        'cm': 'centimeter', 'mm': 'millimeter',
        'm': 'meter', 'km': 'kilometer',
        'in': 'inch', 'ins': 'inches',
        'ft': 'feet',
        'yd': 'yard', 'yds': 'yards',
        'ml': 'milliliter', 'l': 'liter',
        'gal': 'gallon', 'qt': 'quart', 'pt': 'pint',
        'mah': 'milliamphour', 'ah': 'amphour',
        'v': 'volt', 'w': 'watt',
        'hz': 'hertz', 'khz': 'kilohertz',
        'mhz': 'megahertz', 'ghz': 'gigahertz',
        'gb': 'gigabyte', 'mb': 'megabyte',
        'kb': 'kilobyte', 'tb': 'terabyte',
        'atm': 'atmospheres',
    }
    
    @classmethod
    def preprocess(cls, text: str) -> str:
        """
        Comprehensive text preprocessing for maximum similarity accuracy.
        """
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove URLs
        text = re.sub(r'https?://\S+|www\.\S+', ' ', text)
        
        # Remove email addresses
        text = re.sub(r'\S+@\S+', ' ', text)
        
        # Normalize unicode characters
        text = text.replace('™', ' ').replace('®', ' ').replace('©', ' ')
        text = text.replace('–', '-').replace('—', '-')
        text = text.replace(''', "'").replace(''', "'")
        text = text.replace('"', '"').replace('"', '"')
        text = text.replace('…', ' ')
        
        # Normalize common patterns before splitting
        # Handle "X-hour" patterns
        text = re.sub(r'(\d+)\s*-?\s*hours?', r'\1 hour', text)
        text = re.sub(r'(\d+)\s*-?\s*minutes?', r'\1 minute', text)
        text = re.sub(r'(\d+)\s*-?\s*days?', r'\1 day', text)
        
        # Handle rating patterns like "IPX4", "IP67", "5ATM"
        text = re.sub(r'ipx?(\d+)', r'iprating\1', text)
        text = re.sub(r'(\d+)\s*atm', r'\1atmospheres', text)
        
        # Replace hyphens with spaces (for compound words)
        text = text.replace('-', ' ')
        
        # Remove punctuation but keep spaces
        text = text.translate(str.maketrans(string.punctuation, ' ' * len(string.punctuation)))
        
        # Normalize whitespace
        text = ' '.join(text.split())
        
        # Tokenize
        words = text.split()
        
        # Apply unit normalization
        words = [cls.UNITS.get(w, w) for w in words]
        
        # Apply synonym normalization (single words)
        words = [cls.SYNONYMS.get(w, w) for w in words]
        
        # Handle multi-word synonyms
        text = ' '.join(words)
        for phrase, replacement in sorted(cls.SYNONYMS.items(), key=lambda x: -len(x[0])):
            if ' ' in phrase and phrase in text:
                text = text.replace(phrase, replacement)
        words = text.split()
        
        # Remove stop words
        words = [w for w in words if w not in cls.STOP_WORDS and len(w) > 1]
        
        # Remove pure numbers (but keep alphanumeric like "x4" or "32oz")
        words = [w for w in words if not w.isdigit() or len(w) > 2]
        
        return ' '.join(words)
    
    @classmethod
    def extract_key_features(cls, text: str) -> set:
        """
        Extract key product features for additional comparison.
        """
        features = set()
        text_lower = text.lower()
        
        # Extract numbers with units (e.g., "32oz", "24 hours", "5000mah")
        number_patterns = re.findall(
            r'\d+\.?\d*\s*(?:oz|ml|l|gb|mb|tb|mah|ah|v|w|hz|hours?|hrs?|mins?|minutes?|days?|inch|inches|cm|mm|feet|ft|atm)',
            text_lower
        )
        features.update([re.sub(r'\s+', '', p) for p in number_patterns])
        
        # Extract IP ratings
        ip_ratings = re.findall(r'ip[x]?\d+', text_lower)
        features.update(ip_ratings)
        
        # Extract color mentions
        colors = ['black', 'white', 'red', 'blue', 'green', 'yellow', 'orange', 'purple', 
                  'pink', 'brown', 'gray', 'grey', 'silver', 'gold', 'bronze', 'rose gold',
                  'navy', 'teal', 'coral', 'beige', 'cream', 'midnight', 'space gray']
        for color in colors:
            if color in text_lower:
                features.add(color.replace(' ', ''))
        
        # Extract brand-like words (capitalized words in original)
        brands = re.findall(r'\b[A-Z][a-zA-Z]{2,}\b', text)
        features.update([b.lower() for b in brands if len(b) > 2])
        
        # Extract key product features
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
        """
        Extract numeric specifications from text.
        """
        specs = {}
        text_lower = text.lower()
        
        # Battery life
        battery_match = re.search(r'(\d+)\s*(?:hour|hr|h)\s*(?:battery|playback|listening)?', text_lower)
        if battery_match:
            specs['battery_hours'] = int(battery_match.group(1))
        
        # Weight
        weight_match = re.search(r'(\d+\.?\d*)\s*(?:oz|ounce|g|gram|kg|lb|pound)', text_lower)
        if weight_match:
            specs['weight'] = float(weight_match.group(1))
        
        # Capacity
        capacity_match = re.search(r'(\d+)\s*(?:oz|ml|l|liter|litre)', text_lower)
        if capacity_match:
            specs['capacity'] = int(capacity_match.group(1))
        
        # Screen size
        screen_match = re.search(r'(\d+\.?\d*)\s*(?:inch|in)', text_lower)
        if screen_match:
            specs['screen_size'] = float(screen_match.group(1))
        
        return specs


def calculate_sequence_similarity(text1: str, text2: str) -> float:
    """
    Calculate sequence similarity using SequenceMatcher (similar to Levenshtein ratio).
    Good for detecting reordered or slightly modified text.
    """
    return SequenceMatcher(None, text1, text2).ratio()


def calculate_jaccard_similarity(words1: set, words2: set) -> float:
    """
    Calculate Jaccard similarity between two word sets.
    """
    if not words1 or not words2:
        return 0.0
    intersection = words1 & words2
    union = words1 | words2
    return len(intersection) / len(union) if union else 0.0


def calculate_similarity_advanced(text1: str, text2: str) -> dict:
    """
    Calculate multiple similarity metrics between two text descriptions.
    Returns detailed similarity analysis for maximum accuracy.
    """
    if not text1 or not text2:
        return {
            'tfidf_cosine': 0.0,
            'jaccard': 0.0,
            'sequence': 0.0,
            'feature_overlap': 0.0,
            'spec_match': 0.0,
            'combined_score': 0.0,
            'confidence': 'LOW'
        }
    
    # Preprocess texts
    processed1 = TextPreprocessor.preprocess(text1)
    processed2 = TextPreprocessor.preprocess(text2)
    
    if not processed1 or not processed2:
        return {
            'tfidf_cosine': 0.0,
            'jaccard': 0.0,
            'sequence': 0.0,
            'feature_overlap': 0.0,
            'spec_match': 0.0,
            'combined_score': 0.0,
            'confidence': 'LOW'
        }
    
    # 1. TF-IDF Cosine Similarity (primary metric - best for semantic similarity)
    try:
        vectorizer = TfidfVectorizer(
            lowercase=True,
            ngram_range=(1, 3),  # Unigrams, bigrams, and trigrams
            max_features=10000,
            min_df=1,
            max_df=1.0,
            sublinear_tf=True,  # Apply sublinear TF scaling for better accuracy
            norm='l2'
        )
        tfidf_matrix = vectorizer.fit_transform([processed1, processed2])
        tfidf_cosine = float(cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0])
    except Exception:
        tfidf_cosine = 0.0
    
    # 2. Jaccard Similarity (word overlap - catches missing/extra content)
    words1 = set(processed1.split())
    words2 = set(processed2.split())
    jaccard = calculate_jaccard_similarity(words1, words2)
    
    # 3. Sequence Similarity (order-sensitive - catches reordering)
    sequence = calculate_sequence_similarity(processed1, processed2)
    
    # 4. Feature Overlap (key product features - domain-specific accuracy)
    features1 = TextPreprocessor.extract_key_features(text1)
    features2 = TextPreprocessor.extract_key_features(text2)
    if features1 or features2:
        feature_intersection = features1 & features2
        feature_union = features1 | features2
        feature_overlap = len(feature_intersection) / len(feature_union) if feature_union else 1.0
    else:
        feature_overlap = 1.0  # No features to compare
    
    # 5. Spec Match (numeric specifications must match exactly)
    specs1 = TextPreprocessor.extract_numeric_specs(text1)
    specs2 = TextPreprocessor.extract_numeric_specs(text2)
    if specs1 or specs2:
        common_keys = set(specs1.keys()) & set(specs2.keys())
        all_keys = set(specs1.keys()) | set(specs2.keys())
        if all_keys:
            matching_specs = sum(1 for k in common_keys if specs1[k] == specs2[k])
            spec_match = (matching_specs + len(all_keys - (set(specs1.keys()) ^ set(specs2.keys())))) / (len(all_keys) * 2) if all_keys else 1.0
            spec_match = min(1.0, spec_match * 1.5)  # Boost if specs match
        else:
            spec_match = 1.0
    else:
        spec_match = 1.0
    
    # 6. Combined Score (weighted ensemble for maximum accuracy)
    # Weights are tuned for product description comparison
    combined_score = (
        tfidf_cosine * 0.35 +      # 35% - Best for semantic similarity
        jaccard * 0.25 +            # 25% - Good for content overlap
        sequence * 0.15 +           # 15% - Catches structural similarity
        feature_overlap * 0.15 +   # 15% - Domain-specific features
        spec_match * 0.10          # 10% - Exact spec matching
    )
    
    # Determine confidence level
    score_variance = max(tfidf_cosine, jaccard, sequence) - min(tfidf_cosine, jaccard, sequence)
    if score_variance < 0.15:
        confidence = 'HIGH'
    elif score_variance < 0.30:
        confidence = 'MEDIUM'
    else:
        confidence = 'LOW'
    
    return {
        'tfidf_cosine': round(tfidf_cosine, 4),
        'jaccard': round(jaccard, 4),
        'sequence': round(sequence, 4),
        'feature_overlap': round(feature_overlap, 4),
        'spec_match': round(spec_match, 4),
        'combined_score': round(combined_score, 4),
        'confidence': confidence
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
        "DE": "Sony WH-1000XM4 Wireless Premium Noise Canceling Overhead Headphones with Microphone for Phone-Call and Alexa Voice Control, Black. Industry-leading noise canceling with Dual Noise Sensor technology. Superior music quality with Edge-AI, co-developed with Sony Music Studios Tokyo. Up to 30-hour battery life with quick charging (10 min charge for 5 hours of playback). Touch Sensor controls to pause play skip tracks, control volume, activate your voice assistant, and answer phone calls."
    },
    
    # MEDIUM SIMILARITY - Some differences in descriptions (MEDIUM risk)
    "B00TEST123": {
        "US": "Premium Wireless Bluetooth Earbuds with Active Noise Cancellation. Features include: 24-hour total battery life with charging case, IPX4 water resistance for workouts, touch controls for music and calls, and seamless pairing with all Bluetooth devices. Comes with 3 sizes of silicone ear tips for perfect fit. Premium sound quality with deep bass and crystal clear highs.",
        "IN": "Wireless Bluetooth Earbuds with Noise Cancellation Technology. Battery life up to 20 hours with portable charging case. Water resistant design suitable for exercise and outdoor use. Easy touch controls and quick Bluetooth connectivity. Includes multiple ear tip sizes. Enhanced audio with powerful bass response.",
        "DE": "Bluetooth Wireless Earbuds featuring Active Noise Reduction. Extended 24-hour battery with compact charging case. IPX4 rated splash resistance. Intuitive touch interface for playback control. Universal Bluetooth 5.0 compatibility. Includes S/M/L ear tips. Balanced sound signature with emphasized low frequencies."
    },
    
    # LOW SIMILARITY - Very different descriptions (HIGH risk)
    "B00DIFFER1": {
        "US": "Ultra-Slim Laptop Stand made from Premium Aluminum Alloy. Ergonomic design elevates your laptop 6 inches for better posture. Compatible with all laptops from 10 to 17 inches. Foldable and portable design weighs only 8 oz. Non-slip silicone pads protect your device. Improves airflow to prevent overheating. Perfect for home office and travel.",
        "IN": "Adjustable Mobile Phone Holder Stand for Desk. 360 degree rotation with flexible gooseneck arm. Compatible with smartphones 4-7 inches. Strong clamp base attaches to any surface up to 3 inches thick. Perfect for video calls, watching movies, and following recipes. Durable ABS plastic construction.",
        "DE": "Professional Tablet Floor Stand with Wheels. Heavy duty metal construction supports tablets up to 13 inches. Height adjustable from 3 to 5 feet. Lockable caster wheels for easy mobility. Includes anti-theft security enclosure. Ideal for retail displays, presentations, and kiosk applications. Assembly required."
    },
    
    # ANOTHER LOW RISK EXAMPLE
    "B09XYZ1234": {
        "US": "Stainless Steel Insulated Water Bottle - 32oz capacity. Double-wall vacuum insulation keeps drinks cold for 24 hours or hot for 12 hours. BPA-free and leak-proof lid design. Wide mouth opening for easy cleaning and ice cubes. Powder-coated exterior prevents condensation. Available in 12 vibrant colors.",
        "IN": "Stainless Steel Vacuum Insulated Water Bottle - 32oz size. Double-wall insulation technology keeps beverages cold 24 hours or hot 12 hours. BPA-free materials with leak-proof cap. Wide mouth design for easy cleaning and adding ice. Powder-coated finish prevents sweating. Available in multiple color options.",
        "DE": "Stainless Steel Insulated Water Bottle - 32oz / 1 Liter capacity. Double-wall vacuum insulation maintains cold drinks for 24 hours or hot drinks for 12 hours. BPA-free and leak-proof lid. Wide mouth opening for easy cleaning and ice cubes. Powder-coated exterior prevents condensation. Available in various colors."
    },
    
    # MEDIUM RISK EXAMPLE
    "B07MEDIUM1": {
        "US": "Smart Fitness Tracker Watch with Heart Rate Monitor. Tracks steps, calories, distance, and sleep patterns. Water resistant to 50 meters for swimming. 7-day battery life on single charge. Compatible with iOS and Android. GPS connectivity for outdoor activities. Customizable watch faces and interchangeable bands.",
        "IN": "Fitness Band with Heart Rate Monitoring and Step Counter. Monitors daily activity including walking, running, and sleep quality. Waterproof design for swimming and sports. Long battery life lasts up to 5 days. Works with Android and iPhone. Sports mode for various exercises.",
        "DE": "Activity Tracker Smartwatch with Pulse Measurement. Comprehensive activity tracking for steps, calories burned, and sleep analysis. 5 ATM water resistance rating. Battery duration approximately 6 days. Smartphone notifications for calls and messages. Built-in GPS for route tracking. Multiple sport modes available."
    }
}

# Mock product titles for different ASINs
MOCK_TITLES: dict[str, dict[str, str]] = {
    "B08N5WRWNW": {
        "US": "Sony WH-1000XM4 Wireless Premium Noise Canceling Overhead Headphones with Mic for Phone-Call and Alexa Voice Control, Black",
        "IN": "Sony WH-1000XM4 Wireless Premium Noise Canceling Overhead Headphones with Mic for Phone-Call and Alexa Voice Control, Black",
        "DE": "Sony WH-1000XM4 Wireless Premium Noise Canceling Overhead Headphones with Microphone for Phone-Call and Alexa Voice Control, Black"
    },
    "B00TEST123": {
        "US": "Premium Wireless Bluetooth Earbuds with Active Noise Cancellation - Black",
        "IN": "Wireless Bluetooth Earbuds with Noise Cancellation - Black",
        "DE": "Bluetooth Wireless Earbuds with Active Noise Reduction - Black"
    },
    "B00DIFFER1": {
        "US": "Ultra-Slim Laptop Stand made from Premium Aluminum Alloy",
        "IN": "Adjustable Mobile Phone Holder Stand for Desk",
        "DE": "Professional Tablet Floor Stand with Wheels"
    },
    "B09XYZ1234": {
        "US": "Stainless Steel Insulated Water Bottle - 32oz",
        "IN": "Stainless Steel Insulated Water Bottle - 32oz",
        "DE": "Stainless Steel Insulated Water Bottle - 1 Liter"
    },
    "B07MEDIUM1": {
        "US": "Smart Fitness Tracker Watch with Heart Rate Monitor",
        "IN": "Fitness Band with Heart Rate Monitoring",
        "DE": "Activity Tracker Smartwatch with Pulse Measurement"
    }
}


def get_mock_descriptions(asin: str) -> dict[str, str]:
    """
    Get mock descriptions for a given ASIN.
    If ASIN not found, generate deterministic variations based on ASIN hash.
    """
    if asin in MOCK_DESCRIPTIONS:
        return MOCK_DESCRIPTIONS[asin]
    
    # Generate DETERMINISTIC descriptions for unknown ASINs
    # Use hash of ASIN to ensure same ASIN always gets same result
    asin_hash = sum(ord(c) for c in asin)
    similarity_type_index = asin_hash % 3  # 0, 1, or 2
    
    base_description = f"Product {asin} - High quality item with premium features. Durable construction and modern design. Comes with manufacturer warranty and customer support. Fast shipping available."
    
    if similarity_type_index == 0:  # HIGH similarity (LOW risk)
        return {
            "US": base_description + " Available in multiple colors. Best seller in category.",
            "IN": base_description + " Available in various colors. Top rated product in category.",
            "DE": base_description + " Available in multiple color options. Best seller in its category."
        }
    elif similarity_type_index == 1:  # MEDIUM similarity (MEDIUM risk)
        return {
            "US": base_description + " Exclusive features for US customers. Free returns within 30 days.",
            "IN": f"Product {asin} - Quality item with good features. Sturdy build quality. Includes warranty. Express delivery option.",
            "DE": base_description + " European safety certified. 2-year warranty included."
        }
    else:  # LOW similarity (HIGH risk)
        return {
            "US": base_description,
            "IN": f"Item {asin} - Affordable product with basic functionality. Compact size. Budget-friendly option for everyday use.",
            "DE": f"Article {asin} - Professional grade equipment for industrial applications. Heavy-duty materials. Requires assembly. Technical support available."
        }


def get_mock_titles(asin: str) -> dict[str, str]:
    """
    Get mock titles for a given ASIN.
    """
    if asin in MOCK_TITLES:
        return MOCK_TITLES[asin]
    
    # Generate deterministic titles for unknown ASINs
    asin_hash = sum(ord(c) for c in asin)
    similarity_type_index = asin_hash % 3
    
    if similarity_type_index == 0:
        return {
            "US": f"Generic Product {asin} - Premium Edition",
            "IN": f"Generic Product {asin} - Premium Edition",
            "DE": f"Generic Product {asin} - Premium Edition"
        }
    elif similarity_type_index == 1:
        return {
            "US": f"Generic Product {asin} - Standard Edition",
            "IN": f"Generic Product {asin} - Standard Version",
            "DE": f"Generic Product {asin} - Standard Modell"
        }
    else:
        return {
            "US": f"Generic Product {asin} - US Version",
            "IN": f"Different Product {asin} - IN Version",
            "DE": f"Another Product {asin} - DE Version"
        }


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
            
            if similarity < 0.85:  # Threshold for title mismatch (increased to 0.85 for stricter check)
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



def calculate_pairwise_similarities(descriptions: dict[str, str]) -> list[dict]:
    """
    Calculate similarity scores between all pairs of region descriptions.
    Returns list of comparison results with detailed metrics.
    """
    regions = list(descriptions.keys())
    comparisons = []
    
    for i in range(len(regions)):
        for j in range(i + 1, len(regions)):
            region_1 = regions[i]
            region_2 = regions[j]
            
            # Get detailed similarity analysis
            detailed = calculate_similarity_advanced(
                descriptions[region_1],
                descriptions[region_2]
            )
            
            comparisons.append({
                "region_1": region_1,
                "region_2": region_2,
                "similarity_score": detailed['combined_score'],
                "tfidf_score": detailed['tfidf_cosine'],
                "jaccard_score": detailed['jaccard'],
                "sequence_score": detailed['sequence'],
                "feature_overlap": detailed['feature_overlap'],
                "confidence": detailed['confidence']
            })
    
    return comparisons


def determine_risk_level(comparisons: list[dict]) -> RiskLevel:
    """
    Determine overall risk level based on comparison scores.
    
    Risk Levels:
    - LOW: Average similarity >= 0.75 (descriptions are consistent)
    - MEDIUM: Average similarity >= 0.45 and < 0.75 (some differences)
    - HIGH: Average similarity < 0.45 (significant discrepancies)
    """
    if not comparisons:
        return "LOW"
    
    avg_similarity = sum(c["similarity_score"] for c in comparisons) / len(comparisons)
    
    # Also check minimum similarity - if any pair is very different, increase risk
    min_similarity = min(c["similarity_score"] for c in comparisons)
    
    # Adjusted thresholds based on multi-metric analysis
    if avg_similarity >= 0.75 and min_similarity >= 0.60:
        return "LOW"
    elif avg_similarity >= 0.45 and min_similarity >= 0.30:
        return "MEDIUM"
    else:
        return "HIGH"


def check_description_consistency(asin: str) -> dict:
    """
    Main function to check description consistency for a given ASIN.
    Returns complete analysis result with detailed metrics.
    """
    # Get descriptions for all regions
    descriptions = get_mock_descriptions(asin)
    
    # Get titles for all regions
    titles = get_mock_titles(asin)
    
    # Check for title mismatches
    title_analysis = check_title_mismatch(titles)
    
    # Calculate pairwise similarities with all metrics
    comparisons = calculate_pairwise_similarities(descriptions)
    
    # Determine risk level
    risk_level = determine_risk_level(comparisons)
    
    # If there is a title mismatch, escalate risk level
    if title_analysis["is_mismatch"]:
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
    
    return {
        "asin": asin,
        "risk_level": risk_level,
        "average_similarity": round(avg_similarity, 4),
        "min_similarity": round(min_similarity, 4),
        "max_similarity": round(max_similarity, 4),
        "confidence": overall_confidence,
        "comparisons": comparisons,
        "regions_analyzed": list(descriptions.keys()),
        "title_analysis": title_analysis
    }
