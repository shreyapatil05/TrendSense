import requests
import sys
import os
import json
import time
import re
import random
import feedparser

from datetime import datetime, timedelta
from urllib.parse import quote
from collections import Counter

from pytrends.request import TrendReq


# ============================================================
# PROJECT PATH
# ============================================================

sys.path.append(
    os.path.dirname(
        os.path.dirname(
            os.path.abspath(__file__)
        )
    )
)

from config import (
    YOUTUBE_API_KEY,
    NEWS_API_KEY,
    FASHION_KEYWORDS,
    BEAUTY_KEYWORDS,
    FASHION_SEED_TOPICS,
    BEAUTY_SEED_TOPICS,
    ALL_KEYWORDS,
    DATA_DIR,
    VELOCITY_THRESHOLD
)


# ============================================================
# SETTINGS
# ============================================================

REQUEST_TIMEOUT = 20

RANDOM_SEED = 42
random.seed(RANDOM_SEED)


# ============================================================
# GOOGLE TRENDS SETTINGS
# ============================================================

# Keep Google Trends conservative.
#
# IMPORTANT:
# pytrends is an unofficial interface to Google Trends and
# related_queries() is especially prone to 429/quota errors.
#
# Therefore:
#   - velocity collection is enabled
#   - related/rising queries are optional
#   - related_queries() is DISABLED by default
# ============================================================

GOOGLE_BATCH_SIZE = 5

GOOGLE_INITIAL_DELAY = 5

GOOGLE_SUCCESS_MIN_DELAY = 20
GOOGLE_SUCCESS_MAX_DELAY = 30

GOOGLE_MAX_RETRIES = 2

GOOGLE_RETRY_BASE_DELAY = 30

GOOGLE_MAX_CONSECUTIVE_FAILURES = 2

GOOGLE_COOLDOWN_AFTER_FAILURE = 60

GOOGLE_ENABLE_RISING_QUERIES = False

GOOGLE_RISING_MAX_KEYWORDS = 5

GOOGLE_AUTOCOMPLETE_ENABLED = True
GOOGLE_AUTOCOMPLETE_MAX_SEEDS = 20
GOOGLE_AUTOCOMPLETE_DELAY_MIN = 1.0
GOOGLE_AUTOCOMPLETE_DELAY_MAX = 2.0


# ============================================================
# YOUTUBE SETTINGS
# ============================================================

YOUTUBE_MAX_RESULTS = 15

YOUTUBE_DELAY_MIN = 1
YOUTUBE_DELAY_MAX = 2


# ============================================================
# WIKIPEDIA SETTINGS
# ============================================================

WIKIPEDIA_DELAY_MIN = 1.5
WIKIPEDIA_DELAY_MAX = 3.0

WIKIPEDIA_MAX_PAGES_PER_RUN = 25

WIKIPEDIA_DAYS_BACK = 30

WIKIPEDIA_REQUEST_RETRIES = 1

WIKIPEDIA_PROJECT = "en.wikipedia"

WIKIPEDIA_ACCESS = "all-access"

WIKIPEDIA_AGENT = "user"


# ============================================================
# RSS SETTINGS
# ============================================================

RSS_DELAY_MIN = 1
RSS_DELAY_MAX = 2

RSS_MAX_ARTICLES_PER_QUERY = 15


# ============================================================
# CACHE
# ============================================================

CACHE_DIR = os.path.join(
    DATA_DIR,
    "cache"
)

GOOGLE_CACHE_FILE = os.path.join(
    CACHE_DIR,
    "google_trends_cache.json"
)

WIKIPEDIA_CACHE_FILE = os.path.join(
    CACHE_DIR,
    "wikipedia_pageviews_cache.json"
)


def ensure_directories():

    os.makedirs(
        DATA_DIR,
        exist_ok=True
    )

    os.makedirs(
        CACHE_DIR,
        exist_ok=True
    )


def load_json_cache(filepath):

    ensure_directories()

    if not os.path.exists(filepath):

        return {}

    try:

        with open(
            filepath,
            "r",
            encoding="utf-8"
        ) as f:

            return json.load(f)

    except Exception as e:

        print(
            f"  [Cache] Could not load "
            f"{filepath}: {e}"
        )

        return {}


def save_json_cache(
    filepath,
    cache
):

    ensure_directories()

    try:

        with open(
            filepath,
            "w",
            encoding="utf-8"
        ) as f:

            json.dump(
                cache,
                f,
                indent=2,
                ensure_ascii=False
            )

    except Exception as e:

        print(
            f"  [Cache] Could not save "
            f"{filepath}: {e}"
        )


def load_google_cache():

    return load_json_cache(
        GOOGLE_CACHE_FILE
    )


def save_google_cache(cache):

    save_json_cache(
        GOOGLE_CACHE_FILE,
        cache
    )


def load_wikipedia_cache():

    return load_json_cache(
        WIKIPEDIA_CACHE_FILE
    )


def save_wikipedia_cache(cache):

    save_json_cache(
        WIKIPEDIA_CACHE_FILE,
        cache
    )


# ============================================================
# NOISE FILTER
# ============================================================

NOISE_PATTERNS = [

    r'\w+shorts\w*',
    r'\w+feed\w*',
    r'\w+reels\w*',
    r'\w+viral\w*',
    r'[a-z]+makeup[a-z]+',
    r'[a-z]+fashion[a-z]+',
    r'\w+india[a-z]+',
    r'\w+trending\w*',
    r'\w+trendingshorts\w*'
]


def is_noise(phrase):

    if not phrase:

        return True

    phrase = str(
        phrase
    ).strip().lower()

    for pattern in NOISE_PATTERNS:

        if re.search(
            pattern,
            phrase
        ):

            return True

    words = phrase.split()

    if any(
        len(word) > 20
        for word in words
    ):

        return True

    return False


# ============================================================
# TEXT NORMALIZATION
# ============================================================

def normalize_text(text):

    if not text:

        return ""

    text = str(
        text
    ).lower()

    text = re.sub(
        r'[#@]',
        ' ',
        text
    )

    text = re.sub(
        r'[^a-z0-9\s\-]',
        ' ',
        text
    )

    text = re.sub(
        r'\s+',
        ' ',
        text
    )

    return text.strip()


KEYWORD_ALIASES = {
    "co-ord set": ["co ord set", "coordinated set", "matching set", "two piece set"],
    "ethnic fusion": ["fusion wear", "traditional fusion", "traditional silhouettes", "indo western"],
    "kurta set": ["kurta", "kurti", "traditional wear", "ethnic wear", "traditional indian silhouettes", "indian silhouettes"],
    "mirror work": ["shisha embroidery", "mirror embroidery"],
    "bandhani dress": ["bandhani", "bandhej", "tie dye ethnic wear"],
    "phulkari dupatta": ["phulkari", "punjabi embroidery"],
    "saree draping": ["saree", "sari", "saree styling", "sari styling"],
    "lehenga skirt": ["lehenga", "bridal skirt"],
    "sharara set": ["sharara", "gharara"],
    "palazzo set": ["palazzo", "wide leg ethnic pants"],
    "Y2K fashion": ["y2k", "2000s fashion", "2000s style"],
    "clean girl aesthetic": ["clean girl", "clean girl makeup", "clean beauty"],
    "old money style": ["old money", "quiet luxury", "stealth wealth"],
    "ballet core": ["balletcore", "ballet core"],
    "glass skin": ["dewy complexion", "radiant skin"],
    "glazed donut skin": ["glazed skin", "dewy skin"],
    "skin flooding": ["hydration layering", "hydrated skin"],
    "slugging skincare": ["slugging", "occlusive skincare"],
    "dewy skin": ["dewy complexion", "luminous skin", "glowing skin"],
    "barrier repair": ["skin barrier", "barrier cream"],
    "bollywood glam": ["bollywood makeup", "glam makeup"],
    "lip liner": ["lip contour", "overlined lips"],
    "skin tint": ["tinted foundation", "sheer foundation"],
}

# Broader editorial language is used only for NewsAPI/RSS matching. These
# terms identify a related topic, but are not treated as exact trend names in
# YouTube, Trends, Autocomplete, or Wikipedia signals.
NEWS_RELATED_TERMS = {
    "co-ord set": ["co ord", "coordinated outfit", "matching outfit"],
    "ethnic fusion": ["ethnic wear", "fusion wear", "traditional silhouettes"],
    "kurta set": ["traditional wear", "ethnic wear", "kurta", "kurti", "indian silhouettes"],
    "mirror work": ["shisha embroidery", "embroidered ethnic wear"],
    "bandhani dress": ["bandhani", "bandhej", "tie dye ethnic wear"],
    "phulkari dupatta": ["phulkari", "punjabi embroidery"],
    "saree draping": ["saree", "sari", "draping saree", "saree styling"],
    "lehenga skirt": ["lehenga", "bridal wear", "bridal skirt"],
    "sharara set": ["sharara", "gharara", "festive ethnic wear"],
    "palazzo set": ["palazzo", "wide leg ethnic pants"],
    "Y2K fashion": ["y2k", "2000s fashion", "early 2000s style"],
    "quiet luxury": ["quiet luxury", "understated luxury", "minimal luxury"],
    "old money style": ["old money", "stealth wealth", "classic luxury"],
    "clean girl aesthetic": ["clean girl", "minimal beauty", "natural beauty"],
    "glass skin": ["glass skin", "dewy complexion", "radiant skin", "glowing skin"],
    "glazed donut skin": ["glazed skin", "dewy skin", "hydrated skin"],
    "skin flooding": ["hydration layering", "hydrated skin", "skin hydration"],
    "slugging skincare": ["slugging", "occlusive skincare", "skin barrier"],
    "dewy skin": ["dewy complexion", "luminous skin", "glowing skin"],
    "barrier repair": ["skin barrier", "barrier cream", "barrier repair"],
    "clean girl makeup": ["clean girl", "natural makeup", "minimal makeup"],
    "no makeup makeup": ["no makeup look", "natural makeup", "minimal makeup"],
    "lip liner overline": ["overlined lips", "lip contour", "lip liner"],
    "bollywood glam": ["bollywood makeup", "glam makeup", "celebrity makeup"],
    "skin tint": ["skin tint", "sheer foundation", "tinted foundation"],
    "tinted moisturizer": ["tinted moisturizer", "sheer coverage", "lightweight foundation"],
}


def find_matching_keywords(
    text,
    keywords,
    include_news_related=False
):

    normalized = normalize_text(
        text
    )

    matched = []

    for keyword in keywords:

        variants = [keyword] + KEYWORD_ALIASES.get(keyword, [])
        if include_news_related:
            variants += NEWS_RELATED_TERMS.get(keyword, [])
        matched_variant = False
        for variant in variants:
            variant_normalized = normalize_text(variant)
            if not variant_normalized:
                continue
            pattern = r'(?<!\w)' + re.escape(variant_normalized) + r'(?!\w)'
            if re.search(pattern, normalized):
                matched.append(keyword)
                matched_variant = True
                break

        if not matched_variant:
            keyword_tokens = set(normalize_text(keyword).split())
            text_tokens = set(normalized.split())
            if (
                len(keyword_tokens) > 1
                and len(keyword_tokens & text_tokens) / len(keyword_tokens) >= 0.75
            ):
                matched.append(keyword)

    return matched


# ============================================================
# GENERAL FASHION / BEAUTY RELEVANCE
# ============================================================

FASHION_RELEVANCE_TERMS = [

    "fashion",
    "outfit",
    "outfits",
    "style",
    "streetwear",
    "clothing",
    "dress",
    "dresses",
    "saree",
    "lehenga",
    "kurta",
    "ethnic wear",
    "western wear",
    "denim",
    "jeans",
    "skirt",
    "blazer",
    "jacket",
    "fashion trends"
]


BEAUTY_RELEVANCE_TERMS = [

    "beauty",
    "makeup",
    "skincare",
    "skin care",
    "skin",
    "cosmetic",
    "cosmetics",
    "lipstick",
    "lip",
    "blush",
    "mascara",
    "eyeliner",
    "serum",
    "moisturizer",
    "sunscreen",
    "hair",
    "hairstyle",
    "beauty trend",
    "beauty trends"
]


def detect_domain(text):

    normalized = normalize_text(
        text
    )

    fashion_matches = []

    beauty_matches = []

    for term in FASHION_RELEVANCE_TERMS:

        if re.search(
            r'(?<!\w)'
            + re.escape(term)
            + r'(?!\w)',
            normalized
        ):

            fashion_matches.append(
                term
            )

    for term in BEAUTY_RELEVANCE_TERMS:

        if re.search(
            r'(?<!\w)'
            + re.escape(term)
            + r'(?!\w)',
            normalized
        ):

            beauty_matches.append(
                term
            )

    if (
        fashion_matches
        and beauty_matches
    ):

        domain = "fashion_beauty"

    elif fashion_matches:

        domain = "fashion"

    elif beauty_matches:

        domain = "beauty"

    else:

        domain = "unknown"

    return {

        "domain":
            domain,

        "fashion_terms":
            fashion_matches,

        "beauty_terms":
            beauty_matches
    }


# ============================================================
# SAFE HTTP GET
# ============================================================

def safe_request_get(
    url,
    retries=1,
    retry_on_429=False,
    **kwargs
):

    kwargs.setdefault(
        "timeout",
        REQUEST_TIMEOUT
    )

    for attempt in range(
        retries + 1
    ):

        try:

            response = requests.get(
                url,
                **kwargs
            )

            # ----------------------------------------------
            # Success
            # ----------------------------------------------

            if response.status_code == 200:

                return response

            # ----------------------------------------------
            # 404
            # ----------------------------------------------

            if response.status_code == 404:

                return response

            # ----------------------------------------------
            # Rate limit
            # ----------------------------------------------

            if response.status_code == 429:

                if not retry_on_429:

                    return response

                if attempt >= retries:

                    return response

                wait = (
                    5 +
                    random.uniform(
                        2,
                        5
                    )
                )

                print(
                    f"  [HTTP] 429. "
                    f"Retrying in "
                    f"{wait:.1f}s..."
                )

                time.sleep(
                    wait
                )

                continue

            # ----------------------------------------------
            # Other HTTP errors
            # ----------------------------------------------

            print(
                f"  [HTTP] Status "
                f"{response.status_code}"
            )

            return response

        except requests.exceptions.Timeout:

            if attempt >= retries:

                print(
                    "  [HTTP] Timeout."
                )

                return None

            wait = 2

            print(
                f"  [HTTP] Timeout. "
                f"Retrying in "
                f"{wait}s..."
            )

            time.sleep(
                wait
            )

        except requests.exceptions.ConnectionError as e:

            # Do not repeatedly hammer a host when DNS/
            # connection resolution is unavailable.

            if attempt >= retries:

                print(
                    f"  [HTTP] Connection "
                    f"failed: {e}"
                )

                return None

            wait = 2

            print(
                f"  [HTTP] Connection "
                f"error. Retrying in "
                f"{wait}s..."
            )

            time.sleep(
                wait
            )

        except requests.exceptions.RequestException as e:

            print(
                f"  [HTTP] Request error: "
                f"{e}"
            )

            return None

    return None


# ============================================================
# RANDOMIZED DELAY
# ============================================================

def randomized_delay(
    min_seconds=2,
    max_seconds=5
):

    time.sleep(
        random.uniform(
            min_seconds,
            max_seconds
        )
    )


# ============================================================
# WIKIPEDIA PAGE LIST
# ============================================================

WIKIPEDIA_PAGES = {

    "fashion_aesthetics": [

        "Quiet luxury",
        "Cottagecore",
        "Dark academia",
        "Y2K fashion",
        "Mob wife aesthetic",
        "Old money aesthetic",
        "Balletcore",
        "Gorpcore",
        "Coastal grandmother",
        "Normcore",
        "Dopamine dressing",
        "Barbiecore",
        "Clean girl aesthetic"
    ],

    "indian_fashion": [

        "Kurta",
        "Lehenga",
        "Salwar kameez",
        "Saree",
        "Indo-western clothing",
        "Churidar",
        "Anarkali suit",
        "Bandhani",
        "Phulkari",
        "Ajrakh",
        "Fashion in India"
    ],

    "beauty_trends": [

        "Glass skin",
        "Skinimalism",
        "K-beauty",
        "Slugging (skincare)",
        "Double cleansing",
        "Skin care",
        "Korean beauty",
        "Contouring",
        "Lip liner",
        "Eyebrow shaping"
    ],

    "general_fashion": [

        "Fast fashion",
        "Sustainable fashion",
        "Streetwear",
        "Athleisure",
        "Capsule wardrobe",
        "Vintage clothing"
    ]
}


# ============================================================
# WIKIPEDIA PAGE VIEWS
# ============================================================

def fetch_wikipedia_pageviews(
    days_back=WIKIPEDIA_DAYS_BACK
):

    results = []

    headers = {

        "User-Agent":
            "TrendForecaster/1.0 "
            "(academic-capstone-project)"
    }

    end = datetime.now()

    start = (
        end -
        timedelta(
            days=days_back
        )
    )

    start_str = start.strftime(
        "%Y%m%d"
    )

    end_str = end.strftime(
        "%Y%m%d"
    )

    cache = load_wikipedia_cache()

    all_pages = []

    for category, pages in (
        WIKIPEDIA_PAGES.items()
    ):

        for page in pages:

            all_pages.append(
                (
                    page,
                    category
                )
            )

    # --------------------------------------------------------
    # Limit requests so Wikimedia does not get hammered.
    # --------------------------------------------------------

    if len(all_pages) > WIKIPEDIA_MAX_PAGES_PER_RUN:

        selected_pages = (
            all_pages[
                :WIKIPEDIA_MAX_PAGES_PER_RUN
            ]
        )

        print(
            f"  [Wikipedia] Limiting "
            f"run to "
            f"{WIKIPEDIA_MAX_PAGES_PER_RUN} "
            f"pages."
        )

    else:

        selected_pages = all_pages

    print(
        f"  [Wikipedia] Checking "
        f"{len(selected_pages)} pages..."
    )

    consecutive_429 = 0

    for page_title, category in selected_pages:

        cache_key = (
            f"{start_str}|"
            f"{end_str}|"
            f"{page_title}"
        )

        # ----------------------------------------------------
        # Cache
        # ----------------------------------------------------

        if cache_key in cache:

            result = cache[cache_key]

            result = dict(result)
            result["data_status"] = "cached"
            result["cache_age_hours"] = None

            results.append(
                result
            )

            print(
                f"  [Wikipedia] "
                f"{page_title:<32} "
                f"using cached data"
            )

            continue

        # ----------------------------------------------------
        # URL encode title correctly.
        # ----------------------------------------------------

        page_encoded = quote(
            page_title.replace(
                " ",
                "_"
            ),
            safe=""
        )

        url = (

            "https://wikimedia.org/"
            "api/rest_v1/metrics/"
            "pageviews/per-article/"
            f"{WIKIPEDIA_PROJECT}/"
            f"{WIKIPEDIA_ACCESS}/"
            f"{WIKIPEDIA_AGENT}/"
            f"{page_encoded}/daily/"
            f"{start_str}/{end_str}"
        )

        response = safe_request_get(
            url,
            retries=WIKIPEDIA_REQUEST_RETRIES,
            retry_on_429=False,
            headers=headers
        )

        if response is None:

            continue

        # ----------------------------------------------------
        # Rate limited
        # ----------------------------------------------------

        if response.status_code == 429:

            consecutive_429 += 1

            print(
                f"  [Wikipedia] "
                f"HTTP 429 for "
                f"'{page_title}'"
            )

            # If Wikimedia starts rate limiting,
            # stop the remaining page requests.
            if consecutive_429 >= 2:

                print(
                    "  [Wikipedia] "
                    "Rate limiting detected. "
                    "Stopping page-view requests "
                    "for this run."
                )

                break

            continue

        consecutive_429 = 0

        # ----------------------------------------------------
        # Missing page
        # ----------------------------------------------------

        if response.status_code == 404:

            print(
                f"  [Wikipedia] "
                f"'{page_title}' "
                f"— page not found"
            )

            results.append({
                "source": "wikipedia_pageviews",
                "page": page_title,
                "category": category,
                "data_status": "unavailable",
                "data_quality": "page_not_found",
                "reason": "page_not_found",
                "rising": None,
                "matched_keywords": find_matching_keywords(page_title, ALL_KEYWORDS),
                "fetched_at": datetime.now().isoformat(),
            })

            randomized_delay(
                WIKIPEDIA_DELAY_MIN,
                WIKIPEDIA_DELAY_MAX
            )

            continue

        # ----------------------------------------------------
        # Other errors
        # ----------------------------------------------------

        if response.status_code != 200:

            print(
                f"  [Wikipedia] HTTP "
                f"{response.status_code} "
                f"for '{page_title}'"
            )

            continue

        try:

            data = response.json()

        except Exception as e:

            print(
                f"  [Wikipedia] Invalid "
                f"JSON for "
                f"'{page_title}': {e}"
            )

            continue

        items = data.get(
            "items",
            []
        )

        if not items:

            print(
                f"  [Wikipedia] "
                f"No page-view data for "
                f"'{page_title}'"
            )

            continue

        views_list = [

            int(
                item.get(
                    "views",
                    0
                )
                or 0
            )

            for item in items
        ]

        if not views_list:

            continue

        recent = (

            views_list[-7:]

            if len(views_list) >= 7

            else views_list
        )

        older = (

            views_list[:-7]

            if len(views_list) > 7

            else []
        )

        recent_avg = (

            sum(recent) /
            len(recent)

            if recent

            else 0
        )

        older_avg = (

            sum(older) /
            len(older)

            if older

            else recent_avg
        )

        velocity = (
            recent_avg -
            older_avg
        )

        if older_avg > 0:

            normalized_velocity = (
                velocity /
                older_avg
            )

        else:

            normalized_velocity = 0

        rising = (

            velocity > 50

            or

            normalized_velocity > 0.25
        )

        matched = (
            find_matching_keywords(
                page_title,
                ALL_KEYWORDS
            )
        )

        result = {

            "source":
                "wikipedia_pageviews",

            "page":
                page_title,

            "category":
                category,

            "total_views":
                sum(views_list),

            "recent_avg_daily":
                round(
                    recent_avg,
                    2
                ),

            "older_avg_daily":
                round(
                    older_avg,
                    2
                ),

            "velocity":
                round(
                    velocity,
                    2
                ),

            "normalized_velocity":
                round(
                    normalized_velocity,
                    4
                ),

            "peak_views":
                max(
                    views_list
                ),

            "rising":
                bool(rising),

            "matched_keywords":
                matched,

            "fetched_at":
                datetime.now().isoformat()
        }

        results.append(
            result
        )

        cache[
            cache_key
        ] = result

        status = (

            "RISING"

            if rising

            else "stable"
        )

        print(

            f"  [Wikipedia] "
            f"{page_title:<32} "
            f"avg: "
            f"{round(recent_avg):>6}/day "
            f"velocity: "
            f"{velocity:>8.1f} "
            f"[{status}]"
        )

        save_wikipedia_cache(
            cache
        )

        randomized_delay(
            WIKIPEDIA_DELAY_MIN,
            WIKIPEDIA_DELAY_MAX
        )

    rising = [

        r
        for r in results
        if r.get("rising")
    ]

    print(

        f"  [Wikipedia] "
        f"{len(results)} pages tracked | "
        f"{len(rising)} rising"
    )

    return results


# ============================================================
# WIKIPEDIA TOP TRENDING
# ============================================================

def fetch_wikipedia_top_trending():

    results = []

    headers = {

        "User-Agent":
            "TrendForecaster/1.0 "
            "(academic-capstone-project)"
    }

    fashion_beauty_words = [

        "fashion",
        "style",
        "beauty",
        "makeup",
        "skin",
        "hair",
        "dress",
        "outfit",
        "aesthetic",
        "trend",
        "clothing",
        "kurta",
        "saree",
        "lehenga",
        "ethnic",
        "western",
        "cosmetic",
        "skincare",
        "lipstick",
        "blush",
        "cottagecore",
        "luxury",
        "vintage",
        "streetwear",
        "athleisure"
    ]

    # --------------------------------------------------------
    # IMPORTANT:
    #
    # Correct endpoint:
    #
    # /top/en.wikipedia/all-access/YYYY/MM/DD
    #
    # NOT:
    #
    # /top/en.wikipedia/all-access/YYYY/MM/DD
    #
    # with the date as one YYYY/MM/DD string.
    #
    # We construct the segments explicitly.
    # --------------------------------------------------------

    target_date = (
        datetime.now() -
        timedelta(days=1)
    )

    year = target_date.strftime(
        "%Y"
    )

    month = target_date.strftime(
        "%m"
    )

    day = target_date.strftime(
        "%d"
    )

    url = (

        "https://wikimedia.org/"
        "api/rest_v1/metrics/"
        "pageviews/top/"
        f"{WIKIPEDIA_PROJECT}/"
        f"{WIKIPEDIA_ACCESS}/"
        f"{year}/"
        f"{month}/"
        f"{day}"
    )

    try:

        response = safe_request_get(
            url,
            retries=1,
            retry_on_429=False,
            headers=headers
        )

        if response is None:

            return results

        if response.status_code == 429:

            print(
                "  [Wikipedia Top] "
                "HTTP 429 — skipped "
                "to protect the API."
            )

            return results

        if response.status_code != 200:

            print(
                f"  [Wikipedia Top] "
                f"HTTP "
                f"{response.status_code}"
            )

            return results

        data = response.json()

        items = data.get(
            "items",
            []
        )

        if not items:

            print(
                "  [Wikipedia Top] "
                "No data returned."
            )

            return results

        articles = items[0].get(
            "articles",
            []
        )

        print(

            f"  [Wikipedia Top] "
            f"Scanning top "
            f"{len(articles)} "
            f"trending pages..."
        )

        excluded_prefixes = [

            "Special:",
            "Wikipedia:",
            "Portal:",
            "Main Page",
            "File:",
            "Help:",
            "Talk:"
        ]

        for article in articles[:1000]:

            title = (

                article
                .get(
                    "article",
                    ""
                )
                .replace(
                    "_",
                    " "
                )
            )

            views = int(
                article.get(
                    "views",
                    0
                )
                or 0
            )

            rank = int(
                article.get(
                    "rank",
                    0
                )
                or 0
            )

            if any(
                title.startswith(prefix)
                for prefix in excluded_prefixes
            ):

                continue

            title_lower = title.lower()

            if any(
                word in title_lower
                for word in fashion_beauty_words
            ):

                matched = (
                    find_matching_keywords(
                        title,
                        ALL_KEYWORDS
                    )
                )

                domain = detect_domain(
                    title
                )

                results.append({

                    "source":
                        "wikipedia_top_trending",

                    "page":
                        title,

                    "views_today":
                        views,

                    "global_rank":
                        rank,

                    "matched_keywords":
                        matched,

                    "domain":
                        domain["domain"],

                    "fetched_at":
                        datetime.now().isoformat()
                })

        print(

            f"  [Wikipedia Top] "
            f"{len(results)} "
            f"fashion/beauty pages found"
        )

    except Exception as e:

        print(
            f"  [Wikipedia Top] "
            f"Error: {e}"
        )

    return results


# ============================================================
# YOUTUBE SHORTS
# ============================================================

def fetch_youtube_shorts(
    seed_topics,
    max_results=YOUTUBE_MAX_RESULTS,
    selected_keywords=None,
    published_after=None,
    published_before=None,
    region="IN",
    content_modes=None,
):

    results = []
    seen_video_ids = set()

    if not YOUTUBE_API_KEY:

        print(
            "  [YouTube] "
            "YOUTUBE_API_KEY not configured"
        )

        return results

    modes = content_modes or ["shorts"]

    for topic in seed_topics:
      for content_mode in modes:

        url = (
            "https://www.googleapis.com/"
            "youtube/v3/search"
        )

        params = {

            "part":
                "snippet",

            "q": topic + (" #shorts" if content_mode == "shorts" else ""),

            "type":
                "video",

            "order":
                "viewCount",

            "maxResults":
                max_results,

            "regionCode":
                region,

            "relevanceLanguage":
                "en",

            "key":
                YOUTUBE_API_KEY
        }

        if published_after:
            params["publishedAfter"] = published_after
        if published_before:
            params["publishedBefore"] = published_before

        try:

            response = safe_request_get(
                url,
                retries=1,
                retry_on_429=False,
                params=params
            )

            if response is None:

                continue

            if response.status_code != 200:

                print(

                    f"  [YouTube] "
                    f"HTTP "
                    f"{response.status_code}"
                )

                continue

            data = response.json()

            topic_count = 0

            for item in data.get(
                "items",
                []
            ):

                snippet = item.get(
                    "snippet",
                    {}
                )

                title = snippet.get(
                    "title",
                    ""
                )

                video_id = item.get("id", {}).get("videoId", "")

                if not video_id or video_id in seen_video_ids:
                    continue

                seen_video_ids.add(video_id)

                description = snippet.get(
                    "description",
                    ""
                )

                if is_noise(title):

                    continue

                combined = (
                    title +
                    " " +
                    description
                )

                matched = (
                    find_matching_keywords(
                        combined,
                        selected_keywords if selected_keywords is not None else ALL_KEYWORDS
                    )
                )

                domain = detect_domain(
                    combined
                )

                results.append({

                    "source": "youtube_shorts" if content_mode == "shorts" else "youtube_videos",

                    "seed_topic":
                        topic,

                    "title":
                        title,

                    "channel":
                        snippet.get(
                            "channelTitle",
                            ""
                        ),

                    "published_at":
                        snippet.get(
                            "publishedAt",
                            ""
                        ),

                    "video_id":
                        video_id,

                    "description":
                        description[:300],

                    "views": None,

                    "likes": None,

                    "comments": None,

                    "age_days": None,

                    "views_per_day": None,

                    "like_rate": None,

                    "comment_rate": None,

                    "matched_keywords":
                        matched,

                    "domain":
                        domain["domain"],

                    "fashion_terms":
                        domain["fashion_terms"],

                    "beauty_terms":
                        domain["beauty_terms"],

                    "fetched_at":
                        datetime.now().isoformat()
                })

                topic_count += 1

            print(

                f"  [YouTube] "
                f"'{topic}' ({content_mode}) -> "
                f"{topic_count} usable videos"
            )

            randomized_delay(
                YOUTUBE_DELAY_MIN,
                YOUTUBE_DELAY_MAX
            )

        except Exception as e:

            print(

                f"  [YouTube] "
                f"Error for '{topic}': {e}"
            )

    # Search results contain no engagement statistics. Enrich unique videos in
    # batches so old viral clips do not count the same as recent fast-growing
    # clips. Failure is non-fatal because collection is still useful without
    # optional statistics quota.
    for start in range(0, len(results), 50):
        batch = results[start:start + 50]
        try:
            response = safe_request_get(
                "https://www.googleapis.com/youtube/v3/videos",
                retries=1,
                retry_on_429=False,
                params={
                    "part": "statistics",
                    "id": ",".join(item["video_id"] for item in batch),
                    "key": YOUTUBE_API_KEY
                }
            )
            if response is None or response.status_code != 200:
                continue
            stats_by_id = {
                item.get("id"): item.get("statistics", {})
                for item in response.json().get("items", [])
            }
            for item in batch:
                stats = stats_by_id.get(item["video_id"], {})
                views = int(stats.get("viewCount", 0) or 0)
                likes = int(stats.get("likeCount", 0) or 0)
                comments = int(stats.get("commentCount", 0) or 0)
                try:
                    published = datetime.fromisoformat(item["published_at"].replace("Z", "+00:00"))
                    age_days = max((datetime.now(published.tzinfo) - published).total_seconds() / 86400, 1 / 24)
                except (ValueError, TypeError, AttributeError):
                    age_days = None
                item.update({
                    "views": views,
                    "likes": likes,
                    "comments": comments,
                    "age_days": round(age_days, 3) if age_days is not None else None,
                    "views_per_day": round(views / age_days, 2) if age_days else None,
                    "like_rate": round(likes / views, 6) if views else None,
                    "comment_rate": round(comments / views, 6) if views else None,
                })
        except Exception as e:
            print(f"  [YouTube] Statistics unavailable: {e}")

    return results


# ============================================================
# GOOGLE TRENDS CLIENT
# ============================================================

def create_google_trends_client():

    return TrendReq(

        hl="en-IN",

        tz=330,

        timeout=(
            10,
            30
        ),

        retries=0,

        backoff_factor=0
    )


def is_rate_limit_error(error):

    error_text = str(
        error
    ).lower()

    indicators = [

        "429",
        "too many requests",
        "rate limit",
        "ratelimit",
        "response code 429",
        "response code: 429",
        "quota exceeded"
    ]

    return any(

        indicator in error_text

        for indicator in indicators
    )


# ============================================================
# GOOGLE TRENDS VELOCITY
# ============================================================

def fetch_google_trends_velocity(
    keywords,
    geo="IN"
):

    results = []

    if not keywords:

        return results

    cache = load_google_cache()

    today = datetime.now().strftime(
        "%Y-%m-%d"
    )

    chunks = [

        keywords[i:i + GOOGLE_BATCH_SIZE]

        for i in range(
            0,
            len(keywords),
            GOOGLE_BATCH_SIZE
        )
    ]

    print(

        "\n  [Google Trends] "
        f"{len(keywords)} keywords "
        f"divided into "
        f"{len(chunks)} batches"
    )

    cached_count = 0

    fresh_keywords = []

    for keyword in keywords:

        cache_key = (
            f"{today}|"
            f"{geo}|"
            f"{keyword}"
        )

        if cache_key in cache:
            cached_signal = dict(cache[cache_key])
            cached_at = cached_signal.get("fetched_at")
            try:
                cache_age_hours = max(
                    0.0,
                    (datetime.now() - datetime.fromisoformat(cached_at)).total_seconds() / 3600,
                )
            except (TypeError, ValueError):
                cache_age_hours = None
            cached_signal["data_status"] = "cached"
            cached_signal["cache_age_hours"] = round(cache_age_hours, 2) if cache_age_hours is not None else None
            cached_signal["rising"] = float(cached_signal.get("velocity", 0) or 0) >= VELOCITY_THRESHOLD
            results.append(cached_signal)

            cached_count += 1

        else:

            fresh_keywords.append(
                keyword
            )

    print(

        f"  [Google Trends] "
        f"{cached_count} cached | "
        f"{len(fresh_keywords)} "
        f"require fresh data"
    )

    if not fresh_keywords:

        print(
            "  [Google Trends] "
            "All data loaded from cache."
        )

        return results

    fresh_chunks = [

        fresh_keywords[i:i + GOOGLE_BATCH_SIZE]

        for i in range(
            0,
            len(fresh_keywords),
            GOOGLE_BATCH_SIZE
        )
    ]

    print(

        "  [Google Trends] "
        f"Initial delay: "
        f"{GOOGLE_INITIAL_DELAY}s"
    )

    time.sleep(
        GOOGLE_INITIAL_DELAY
    )

    pytrends = (
        create_google_trends_client()
    )

    consecutive_failures = 0

    for index, chunk in enumerate(
        fresh_chunks,
        start=1
    ):

        print(

            f"\n  [Google Trends] "
            f"Batch {index}/"
            f"{len(fresh_chunks)}: "
            f"{chunk}"
        )

        success = False

        for attempt in range(
            1,
            GOOGLE_MAX_RETRIES + 1
        ):

            try:

                pytrends.build_payload(

                    chunk,

                    timeframe="now 7-d",

                    geo=geo
                )

                interest_df = (
                    pytrends
                    .interest_over_time()
                )

                if interest_df.empty:

                    print(

                        "  [Google Trends] "
                        "No data returned. "
                        "Skipping this batch."
                    )

                    success = True

                    break

                batch_results = []

                for keyword in chunk:

                    if (
                        keyword
                        not in
                        interest_df.columns
                    ):

                        continue

                    series = (

                        interest_df[
                            keyword
                        ]
                        .fillna(0)
                    )

                    recent_avg = (

                        series
                        .tail(3)
                        .mean()
                    )

                    recent_count = min(3, len(series))
                    previous_series = series.iloc[-(recent_count * 2):-recent_count]
                    previous_avg = (
                        previous_series.mean()
                        if len(previous_series) >= 1
                        else None
                    )

                    overall_avg = (

                        series
                        .mean()
                    )

                    velocity = (

                        recent_avg -
                        overall_avg
                    )

                    previous_velocity = (
                        previous_avg - series.iloc[:-recent_count].mean()
                        if previous_avg is not None and len(series.iloc[:-recent_count]) > 0
                        else None
                    )
                    acceleration = (
                        velocity - previous_velocity
                        if previous_velocity is not None
                        else None
                    )

                    peak_value = (
                        series.max()
                    )

                    if overall_avg > 0:

                        normalized_velocity = (

                            velocity /
                            overall_avg
                        )

                    else:

                        normalized_velocity = 0

                    rising = velocity >= VELOCITY_THRESHOLD

                    signal = {

                        "source":
                            "google_trends",

                        "keyword":
                            keyword,

                        "recent_avg":
                            round(
                                float(
                                    recent_avg
                                ),
                                2
                            ),

                        "overall_avg":
                            round(
                                float(
                                    overall_avg
                                ),
                                2
                            ),

                        "velocity":
                            round(
                                float(
                                    velocity
                                ),
                                2
                            ),

                        "historical_avg":
                            round(float(overall_avg), 2),

                        "previous_avg":
                            round(float(previous_avg), 2)
                            if previous_avg is not None else None,

                        "acceleration":
                            round(float(acceleration), 2)
                            if acceleration is not None else None,

                        "observations":
                            int(len(series)),

                        "data_quality":
                            "valid_with_history"
                            if acceleration is not None
                            else "valid_velocity_only",

                        "data_status": "fresh",

                        "cache_age_hours": 0,

                        "normalized_velocity":
                            round(
                                float(
                                    normalized_velocity
                                ),
                                4
                            ),

                        "peak_value":
                            round(
                                float(
                                    peak_value
                                ),
                                2
                            ),

                        "rising":
                            bool(rising),

                        "geo":
                            geo,

                        "timeframe":
                            "now 7-d",

                        "fetched_at":
                            datetime.now().isoformat()
                    }

                    batch_results.append(
                        signal
                    )

                # Save only successfully obtained
                # signals.

                for signal in batch_results:

                    results.append(
                        signal
                    )

                    cache_key = (
                        f"{today}|"
                        f"{geo}|"
                        f"{signal['keyword']}"
                    )

                    cache[
                        cache_key
                    ] = signal

                save_google_cache(
                    cache
                )

                success = True

                consecutive_failures = 0

                print(

                    f"  [Google Trends] "
                    f"Batch {index} "
                    f"successful"
                )

                randomized_delay(
                    GOOGLE_SUCCESS_MIN_DELAY,
                    GOOGLE_SUCCESS_MAX_DELAY
                )

                break

            except Exception as e:

                if is_rate_limit_error(e):

                    consecutive_failures += 1

                    wait_time = (

                        GOOGLE_RETRY_BASE_DELAY *
                        (2 ** (attempt - 1))
                    )

                    wait_time += random.uniform(
                        3,
                        8
                    )

                    print(

                        "  [Google Trends] "
                        "Rate limit / quota "
                        "error detected."
                    )

                    print(

                        f"  Waiting "
                        f"{wait_time:.1f}s "
                        f"before retry "
                        f"{attempt}/"
                        f"{GOOGLE_MAX_RETRIES}"
                    )

                    time.sleep(
                        wait_time
                    )

                else:

                    print(

                        f"  [Google Trends] "
                        f"Error: {e}"
                    )

                    break

        if not success:

            print(

                f"  [Google Trends] "
                f"Batch failed: "
                f"{chunk}"
            )

            if (
                consecutive_failures
                >=
                GOOGLE_MAX_CONSECUTIVE_FAILURES
            ):

                print(

                    "\n  [Google Trends] "
                    "Persistent rate limiting "
                    "detected."
                )

                print(

                    f"  Cooling down for "
                    f"{GOOGLE_COOLDOWN_AFTER_FAILURE}s."
                )

                time.sleep(
                    GOOGLE_COOLDOWN_AFTER_FAILURE
                )

                print(

                    "  [Google Trends] "
                    "Stopping further "
                    "requests."
                )

                break

    print(

        f"\n  [Google Trends] "
        f"Collected "
        f"{len(results)} "
        f"keyword signals"
    )

    return results


# ============================================================
# GOOGLE AUTOCOMPLETE
# ============================================================

def fetch_google_autocomplete(seed_topics, keywords):
    if not GOOGLE_AUTOCOMPLETE_ENABLED:
        print("  [Google Autocomplete] Disabled.")
        return []

    results = []
    for seed in seed_topics[:GOOGLE_AUTOCOMPLETE_MAX_SEEDS]:
        try:
            response = safe_request_get(
                "https://suggestqueries.google.com/complete/search",
                retries=1,
                retry_on_429=False,
                params={
                    "client": "firefox",
                    "q": seed,
                    "hl": "en-IN",
                    "gl": "in",
                },
            )
            if response is None or response.status_code != 200:
                continue

            data = response.json()
            suggestions = data[1] if isinstance(data, list) and len(data) > 1 else []
            for suggestion in suggestions:
                suggestion = str(suggestion).strip()
                if not suggestion:
                    continue
                matched = find_matching_keywords(suggestion, keywords)
                domain = detect_domain(suggestion)
                for keyword in matched:
                    results.append({
                        "source": "google_autocomplete",
                        "keyword": keyword,
                        "seed_query": seed,
                        "suggestion": suggestion,
                        "matched_keywords": [keyword],
                        "data_status": "available",
                        "data_quality": "query_suggestions_only",
                        "volume_available": False,
                        "domain": domain["domain"],
                        "fetched_at": datetime.now().isoformat(),
                    })
            randomized_delay(
                GOOGLE_AUTOCOMPLETE_DELAY_MIN,
                GOOGLE_AUTOCOMPLETE_DELAY_MAX,
            )
        except Exception as e:
            print(f"  [Google Autocomplete] Error for '{seed}': {e}")

    print(f"  [Google Autocomplete] Collected {len(results)} signals")
    return results


# ============================================================
# GOOGLE RISING QUERIES
#
# DISABLED BY DEFAULT
#
# Reason:
# pytrends related_queries() is unreliable and commonly
# returns 429/quota errors.
#
# The function is retained so the architecture can support
# it later without breaking anything.
# ============================================================

def fetch_google_trends_rising_queries(
    keywords,
    geo="IN"
):

    if not GOOGLE_ENABLE_RISING_QUERIES:

        print(

            "\n  [Google Rising] "
            "Disabled for this run."
        )

        print(

            "  [Google Rising] "
            "Google Trends velocity "
            "data will be used instead."
        )

        return []

    results = []

    if not keywords:

        return results

    keywords = keywords[
        :GOOGLE_RISING_MAX_KEYWORDS
    ]

    print(

        "\n  [Google Rising] "
        f"Checking top "
        f"{len(keywords)} keywords"
    )

    pytrends = (
        create_google_trends_client()
    )

    try:

        time.sleep(
            20
        )

        for keyword in keywords:

            try:

                pytrends.build_payload(

                    [keyword],

                    timeframe="today 1-m",

                    geo=geo
                )

                related = (
                    pytrends
                    .related_queries()
                )

                if (
                    keyword
                    not in related
                ):

                    continue

                data = related[
                    keyword
                ]

                if data is None:

                    continue

                rising_df = data.get(
                    "rising"
                )

                if rising_df is None:

                    continue

                for _, row in (
                    rising_df.iterrows()
                ):

                    query = str(
                        row.get(
                            "query",
                            ""
                        )
                    ).strip()

                    if not query:

                        continue

                    if is_noise(query):

                        continue

                    results.append({

                        "source":
                            "google_trends_rising",

                        "parent_keyword":
                            keyword,

                        "rising_query":
                            query,

                        "value":
                            row.get(
                                "value",
                                0
                            ),

                        "geo":
                            geo,

                        "timeframe":
                            "today 1-m",

                        "fetched_at":
                            datetime.now().isoformat()
                    })

                randomized_delay(
                    20,
                    30
                )

            except Exception as e:

                print(

                    f"  [Google Rising] "
                    f"Failed for "
                    f"'{keyword}': "
                    f"{e}"
                )

                if is_rate_limit_error(e):

                    print(

                        "  [Google Rising] "
                        "Rate limit detected. "
                        "Stopping rising-query "
                        "collection."
                    )

                    break

    except Exception as e:

        print(

            f"  [Google Rising] "
            f"Error: {e}"
        )

    print(

        f"\n  [Google Rising] "
        f"Collected "
        f"{len(results)} "
        f"rising queries"
    )

    return results


# ============================================================
# NEWS API
# ============================================================

def fetch_news_articles(
    keywords
):

    if not NEWS_API_KEY:

        print(

            "  [NewsAPI] "
            "Skipping — "
            "NEWS_API_KEY not set"
        )

        return []

    results = []

    queries = [
        ("Indian fashion trends", "fashion"),
        ("Indian ethnic wear saree lehenga kurta", "fashion"),
        ("Indian fashion outfit style trends", "fashion"),
        ("India beauty makeup skincare trends", "beauty"),
        ("India skincare glass skin makeup", "beauty"),
        ("clean girl makeup India beauty", "beauty"),
        ("Bollywood fashion beauty outfit", "fashion_beauty"),
        ("Gen Z India fashion beauty", "fashion_beauty"),
    ]

    for query, query_domain in queries:

        try:

            url = (
                "https://newsapi.org/v2/everything"
            )

            params = {

                "q":
                    query,

                "language":
                    "en",

                "sortBy":
                    "publishedAt",

                "pageSize":
                    10,

                "apiKey":
                    NEWS_API_KEY
            }

            response = safe_request_get(
                url,
                retries=1,
                retry_on_429=False,
                params=params
            )

            if response is None:

                continue

            if response.status_code != 200:

                print(

                    f"  [NewsAPI] "
                    f"HTTP "
                    f"{response.status_code}"
                )

                continue

            data = response.json()

            articles = data.get(
                "articles",
                []
            )

            matched_count = 0
            relevant_count = 0

            for article in articles:

                title = str(
                    article.get(
                        "title",
                        ""
                    )
                )

                description = str(
                    article.get(
                        "description",
                        ""
                    )
                )[:300]

                article_content = str(
                    article.get(
                        "content",
                        ""
                    )
                )[:1000]

                content = (
                    title +
                    " " +
                    description +
                    " " +
                    article_content
                )

                matched = (
                    find_matching_keywords(
                        content,
                        keywords,
                        include_news_related=True
                    )
                )

                domain = detect_domain(
                    content
                )

                relevant = domain["domain"] != "unknown" or bool(matched)
                matched_count += bool(matched)
                relevant_count += relevant

                results.append({

                    "source":
                        "newsapi",

                    "title":
                        title,

                    "description":
                        description,

                    "content_excerpt":
                        article_content,

                    "url":
                        article.get(
                            "url",
                            ""
                        ),

                    "published_at":
                        article.get(
                            "publishedAt",
                            ""
                        ),

                    "source_name":
                        article
                        .get(
                            "source",
                            {}
                        )
                        .get(
                            "name",
                            ""
                        ),

                    "query": query,

                    "query_domain": query_domain,

                    "relevant": relevant,

                    "matched_keywords":
                        matched,

                    "domain":
                        domain["domain"],

                    "fashion_terms":
                        domain["fashion_terms"],

                    "beauty_terms":
                        domain["beauty_terms"],

                    "fetched_at":
                        datetime.now().isoformat()
                })

            print(

                f"  [NewsAPI] "
                f"'{query}' -> "
                f"{len(articles)} articles | "
                f"{relevant_count} relevant | "
                f"{matched_count} keyword-matched"
            )

            randomized_delay(
                1,
                2
            )

        except Exception as e:

            print(

                f"  [NewsAPI] "
                f"Error for "
                f"'{query}': {e}"
            )

    return results


# ============================================================
# GOOGLE NEWS RSS
#
# More robust than relying on individual publisher feeds.
# ============================================================

def fetch_rss_feeds(
    keywords
):

    queries = [

        (
            "Indian fashion trends",
            "fashion"
        ),

        (
            "Indian beauty makeup skincare",
            "beauty"
        ),

        (
            "Gen Z India fashion beauty",
            "fashion_beauty"
        ),

        (
            "Indian ethnic wear saree lehenga trend",
            "fashion"
        ),

        (
            "India skincare beauty trends",
            "beauty"
        )
    ]

    results = []

    for query, query_domain in queries:

        try:

            rss_url = (

                "https://news.google.com/rss/search?"
                "q="
                +
                quote(
                    query
                )
                +
                "&hl=en-IN"
                "&gl=IN"
                "&ceid=IN:en"
            )

            feed = feedparser.parse(
                rss_url
            )

            if feed.bozo:

                print(

                    f"  [RSS] "
                    f"Warning parsing "
                    f"'{query}'"
                )

            entries = feed.entries[
                :RSS_MAX_ARTICLES_PER_QUERY
            ]

            count = 0

            for entry in entries:

                title = str(
                    entry.get(
                        "title",
                        ""
                    )
                ).strip()

                summary = str(
                    entry.get(
                        "summary",
                        ""
                    )
                )[:500]

                if not title:

                    continue

                content = (
                    title +
                    " " +
                    summary
                )

                matched = (
                    find_matching_keywords(
                        content,
                        keywords,
                        include_news_related=True
                    )
                )

                domain = detect_domain(
                    content
                )

                results.append({

                    "source":
                        "rss_feed",

                    "feed_name":
                        "Google News RSS",

                    "query":
                        query,

                    "query_domain":
                        query_domain,

                    "title":
                        title,

                    "summary":
                        summary,

                    "url":
                        entry.get(
                            "link",
                            ""
                        ),

                    "published_at":
                        entry.get(
                            "published",
                            ""
                        ),

                    "matched_keywords":
                        matched,

                    "domain":
                        domain["domain"],

                    "fashion_terms":
                        domain["fashion_terms"],

                    "beauty_terms":
                        domain["beauty_terms"],

                    "fetched_at":
                        datetime.now().isoformat()
                })

                count += 1

            print(

                f"  [RSS] "
                f"Google News — "
                f"'{query}' -> "
                f"{count} articles"
            )

            randomized_delay(
                RSS_DELAY_MIN,
                RSS_DELAY_MAX
            )

        except Exception as e:

            print(

                f"  [RSS] "
                f"Error for "
                f"'{query}': {e}"
            )

    return results


# ============================================================
# DEDUPLICATION
# ============================================================

def deduplicate_signals(
    signals
):

    unique = []

    seen = set()

    for signal in signals:

        source = signal.get(
            "source",
            ""
        )

        if source == "youtube_shorts":

            video_id = signal.get(
                "video_id",
                ""
            )

            if video_id:

                key = (
                    source,
                    video_id
                )

            else:

                key = (
                    source,
                    signal.get(
                        "title",
                        ""
                    ),
                    signal.get(
                        "channel",
                        ""
                    )
                )

        elif source == "google_trends":

            key = (

                source,

                signal.get(
                    "keyword",
                    ""
                )
            )

        elif source == "google_trends_rising":

            key = (

                source,

                signal.get(
                    "parent_keyword",
                    ""
                ),

                signal.get(
                    "rising_query",
                    ""
                )
            )

        elif source == "google_autocomplete":

            key = (
                source,
                signal.get("keyword", ""),
                signal.get("seed_query", ""),
                signal.get("suggestion", ""),
            )

        elif source == "wikipedia_pageviews":

            key = (

                source,

                signal.get(
                    "page",
                    ""
                )
            )

        elif source == "wikipedia_top_trending":

            key = (

                source,

                signal.get(
                    "page",
                    ""
                )
            )

        else:

            url = signal.get(
                "url",
                ""
            )

            title = signal.get(
                "title",
                ""
            )

            key = (

                source,

                url,

                title
            )

        if key in seen:

            continue

        seen.add(
            key
        )

        unique.append(
            signal
        )

    return unique


def save_scout_health(health):
    ensure_directories()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filepath = os.path.join(DATA_DIR, f"scout_health_{timestamp}.json")
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(health, f, indent=2, ensure_ascii=False)
    print(f"  Scout health saved to: {filepath}")
    return filepath


# ============================================================
# MAIN SCOUT RUNNER
# ============================================================

def run_scout(run_config=None, start=None, end=None, history_path=None):
    if run_config is not None:
        from agents.selected_scout import collect_selected
        return collect_selected(run_config, start, end, history_path)

    print(
        "\n" +
        "=" * 70
    )

    print(
        "  SCOUT AGENT RUNNING"
    )

    print(
        "=" * 70
    )

    ensure_directories()

    all_signals = []

    all_seed_topics = (

        FASHION_SEED_TOPICS +

        BEAUTY_SEED_TOPICS
    )

    # ========================================================
    # 1. YOUTUBE
    # ========================================================

    print(
        "\n[1/8] "
        "Fetching YouTube Shorts..."
    )

    youtube_data = (
        fetch_youtube_shorts(
            all_seed_topics,
            max_results=
                YOUTUBE_MAX_RESULTS
        )
    )

    all_signals.extend(
        youtube_data
    )

    print(

        f"  Total: "
        f"{len(youtube_data)} "
        f"videos collected"
    )

    # ========================================================
    # 2. GOOGLE TRENDS
    # ========================================================

    print(
        "\n[2/8] "
        "Scoring curated keywords "
        "via Google Trends..."
    )

    trends_data = (
        fetch_google_trends_velocity(
            ALL_KEYWORDS,
            geo="IN"
        )
    )

    all_signals.extend(
        trends_data
    )

    rising = [

        s
        for s in trends_data
        if s.get("rising")
    ]

    print(

        f"  Total: "
        f"{len(trends_data)} "
        f"keywords scored"
    )

    print(

        "  Currently RISING in India: "
        f"{[s['keyword'] for s in rising]}"
    )

    # ========================================================
    # 3. GOOGLE AUTOCOMPLETE
    # ========================================================

    print(
        "\n[3/8] "
        "Google Autocomplete..."
    )

    autocomplete_data = fetch_google_autocomplete(
        all_seed_topics,
        ALL_KEYWORDS
    )
    all_signals.extend(autocomplete_data)

    print(
        f"  Total: {len(autocomplete_data)} autocomplete signals"
    )

    # ========================================================
    # 4. GOOGLE RISING QUERIES
    # ========================================================

    rising_data = []

    print(
        "\n[4/8] "
        "Google Trends breakout queries..."
    )

    if GOOGLE_ENABLE_RISING_QUERIES:

        if trends_data:

            top_keywords = [

                s["keyword"]

                for s in sorted(

                    trends_data,

                    key=lambda x:
                        x.get(
                            "velocity",
                            0
                        ),

                    reverse=True
                )[
                    :GOOGLE_RISING_MAX_KEYWORDS
                ]
            ]

            rising_data = (
                fetch_google_trends_rising_queries(
                    top_keywords,
                    geo="IN"
                )
            )

            all_signals.extend(
                rising_data
            )

            print(

                f"  Total: "
                f"{len(rising_data)} "
                f"rising queries found"
            )

        else:

            print(
                "  Google Trends "
                "unavailable."
            )

    else:

        print(
            "  Disabled to prevent "
            "Google Trends related-query "
            "quota/rate-limit failures."
        )

        print(
            "  Velocity-based rising signals "
            "are still collected."
        )

    # ========================================================
    # 4. NEWS
    # ========================================================

    print(
        "\n[5/8] "
        "Fetching news articles..."
    )

    news_data = (
        fetch_news_articles(
            ALL_KEYWORDS
        )
    )

    all_signals.extend(
        news_data
    )

    news_with_matches = [

        n
        for n in news_data
        if n.get(
            "matched_keywords"
        )
    ]

    print(

        f"  Total: "
        f"{len(news_data)} articles | "
        f"{len(news_with_matches)} "
        f"matched curated keywords"
    )

    # ========================================================
    # 5. RSS
    # ========================================================

    print(
        "\n[6/8] "
        "Fetching RSS news signals..."
    )

    rss_data = (
        fetch_rss_feeds(
            ALL_KEYWORDS
        )
    )

    all_signals.extend(
        rss_data
    )

    rss_with_matches = [

        r
        for r in rss_data
        if r.get(
            "matched_keywords"
        )
    ]

    print(

        f"  Total: "
        f"{len(rss_data)} articles | "
        f"{len(rss_with_matches)} "
        f"matched curated keywords"
    )

    # ========================================================
    # 6. WIKIPEDIA PAGE VIEWS
    # ========================================================

    print(
        "\n[7/8] "
        "Checking Wikipedia "
        "page-view velocity..."
    )

    wiki_pageviews = (

        fetch_wikipedia_pageviews(
            days_back=
                WIKIPEDIA_DAYS_BACK
        )
    )

    all_signals.extend(
        wiki_pageviews
    )

    # ========================================================
    # 7. WIKIPEDIA TOP TRENDING
    # ========================================================

    print(
        "\n[8/8] "
        "Fetching Wikipedia "
        "top trending pages..."
    )

    wiki_trending = (
        fetch_wikipedia_top_trending()
    )

    all_signals.extend(
        wiki_trending
    )

    wiki_rising = [

        w
        for w in wiki_pageviews
        if w.get("rising")
    ]

    print(

        "  Wikipedia rising: "
        f"{[w['page'] for w in wiki_rising]}"
    )

    # ========================================================
    # DEDUPLICATION
    # ========================================================

    before = len(
        all_signals
    )

    all_signals = (
        deduplicate_signals(
            all_signals
        )
    )

    after = len(
        all_signals
    )

    google_coverage = (
        len({
            signal.get("keyword")
            for signal in trends_data
            if signal.get("keyword")
        })
        / len(ALL_KEYWORDS)
        if ALL_KEYWORDS
        else 0
    )

    google_trends_available = google_coverage >= 0.80
    google_trends_data_available = google_coverage >= 0.30

    health = {
        "source": "scout_health",
        "google_trends_available": google_trends_available,
        "google_trends_data_available": google_trends_data_available,
        "google_trends_coverage": round(google_coverage, 4),
        "google_trends_expected_keywords": len(ALL_KEYWORDS),
        "google_trends_valid_keywords": len(trends_data),
        "google_trends_cached_keywords": sum(
            signal.get("data_status") == "cached" for signal in trends_data
        ),
        "google_trends_fresh_keywords": sum(
            signal.get("data_status") == "fresh" for signal in trends_data
        ),
        "google_trends_unavailable_keywords": len(ALL_KEYWORDS) - len(trends_data),
        "autocomplete_signals": len(autocomplete_data),
        "source_counts": {
            "youtube_shorts": len(youtube_data),
            "google_trends": len(trends_data),
            "google_autocomplete": len(autocomplete_data),
            "google_trends_rising": len(rising_data) if GOOGLE_ENABLE_RISING_QUERIES else 0,
            "newsapi": len(news_data),
            "rss_feed": len(rss_data),
            "wikipedia_pageviews": len(wiki_pageviews),
            "wikipedia_top_trending": len(wiki_trending),
        },
        "google_trends_role": "primary_search_velocity_signal",
        "wikipedia_role": "supplementary_validation",
        "generated_at": datetime.now().isoformat()
    }
    save_scout_health(health)

    if not google_trends_available:
        print(
            "  Google Trends status: unavailable/partial data; "
            "missing keywords are not evidence of declining interest."
        )

    print(

        f"\n  Deduplication: "
        f"{before} -> {after} signals"
    )

    # ========================================================
    # COMPLETE
    # ========================================================

    print(
        "\n" +
        "=" * 70
    )

    print(

        f"  SCOUT COMPLETE — "
        f"{len(all_signals)} "
        f"unique signals collected"
    )

    print(
        "=" * 70
    )

    return all_signals


# ============================================================
# SUMMARY
# ============================================================

def print_summary(
    signals
):

    print(
        "\n--- SIGNAL SUMMARY ---\n"
    )

    sources = [

        "youtube_shorts",

        "google_trends",

        "google_autocomplete",

        "google_trends_rising",

        "newsapi",

        "rss_feed",

        "wikipedia_pageviews",

        "wikipedia_top_trending"
    ]

    for source in sources:

        items = [

            s
            for s in signals
            if s["source"] == source
        ]

        if source == "google_trends_rising" and not GOOGLE_ENABLE_RISING_QUERIES:
            print(
                f"  {source:<30}: disabled"
            )
            continue

        print(

            f"  {source:<30}: "
            f"{len(items)} signals"
        )

    # ========================================================
    # GOOGLE TRENDS
    # ========================================================

    print(
        "\n  Keywords RISING in India:"
    )

    trends = [

        s
        for s in signals
        if s["source"] ==
        "google_trends"
    ]

    rising = [

        t
        for t in trends
        if t.get("rising")
    ]

    if rising:

        for item in sorted(

            rising,

            key=lambda x:
                x.get(
                    "velocity",
                    0
                ),

            reverse=True
        ):

            print(

                f"    RISING "
                f"{item['keyword']:<30} "
                f"velocity: "
                f"{item['velocity']}"
            )

    else:

        print(
            "    None above threshold"
        )

    # ========================================================
    # ALL VELOCITIES
    # ========================================================

    print(
        "\n  All keyword velocities:"
    )

    for item in sorted(

        trends,

        key=lambda x:
            x.get(
                "velocity",
                0
            ),

        reverse=True
    ):

        status = (

            "RISING"

            if item.get("rising")

            else "stable"
        )

        print(

            f"    [{status:<6}] "
            f"{item['keyword']:<30} "
            f"{item['velocity']:>7.2f}"
        )

    # ========================================================
    # RISING QUERIES
    # ========================================================

    print(
        "\n  Top rising breakout queries:"
    )

    rising_q = sorted(

        [

            s
            for s in signals
            if s["source"] ==
            "google_trends_rising"

        ],

        key=lambda x:
            x.get(
                "value",
                0
            ),

        reverse=True
    )[:8]

    if rising_q:

        for item in rising_q:

            print(

                f"    "
                f"'{item['rising_query']}' "
                f"<- "
                f"'{item['parent_keyword']}' "
                f"(value: "
                f"{item['value']})"
            )

    else:

        print(
            "    Not collected "
            "(Google related queries disabled)"
        )

    # ========================================================
    # NEWS / RSS
    # ========================================================

    print(
        "\n  Curated keyword mentions "
        "in news/RSS:"
    )

    all_matched = []

    for signal in signals:

        if signal["source"] in [

            "newsapi",
            "rss_feed"
        ]:

            all_matched.extend(

                signal.get(
                    "matched_keywords",
                    []
                )
            )

    mention_counts = Counter(
        all_matched
    )

    if mention_counts:

        for kw, count in (
            mention_counts
            .most_common(10)
        ):

            print(

                f"    {kw:<30} "
                f"mentions: {count}"
            )

    else:

        print(
            "    No curated keyword "
            "matches"
        )

    # ========================================================
    # DOMAIN SUMMARY
    # ========================================================

    print(
        "\n  Domain distribution:"
    )

    domains = Counter()

    for signal in signals:

        domain = signal.get(
            "domain"
        )

        if domain:

            domains[domain] += 1

    if domains:

        for domain, count in (
            domains.most_common()
        ):

            print(

                f"    {domain:<20} "
                f"{count} signals"
            )

    else:

        print(
            "    Domain metadata "
            "not available"
        )

    # ========================================================
    # WIKIPEDIA
    # ========================================================

    print(
        "\n  Wikipedia RISING pages:"
    )

    wiki_rising = [

        s
        for s in signals

        if (

            s["source"] ==
            "wikipedia_pageviews"

            and

            s.get("rising")
        )
    ]

    if wiki_rising:

        for item in sorted(

            wiki_rising,

            key=lambda x:
                x.get(
                    "velocity",
                    0
                ),

            reverse=True
        ):

            print(

                f"    "
                f"{item['page']:<32} "
                f"+{item['velocity']:.0f} "
                f"views/day "
                f"({item['recent_avg_daily']:.0f} "
                f"avg/day)"
            )

    else:

        print(
            "    None rising"
        )

    print(
        "\n  Wikipedia top trending "
        "fashion/beauty pages:"
    )

    wiki_top = sorted(

        [

            s
            for s in signals

            if s["source"] ==
            "wikipedia_top_trending"

        ],

        key=lambda x:
            x.get(
                "views_today",
                0
            ),

        reverse=True
    )[:5]

    if wiki_top:

        for item in wiki_top:

            print(

                f"    "
                f"#{item['global_rank']} "
                f"{item['page']:<32} "
                f"{item['views_today']:,} views"
            )

    else:

        print(
            "    None found"
        )


# ============================================================
# SAVE SIGNALS
# ============================================================

def save_signals(
    signals
):

    ensure_directories()

    timestamp = (

        datetime.now()
        .strftime(
            "%Y%m%d_%H%M%S"
        )
    )

    filepath = os.path.join(

        DATA_DIR,

        f"signals_{timestamp}.json"
    )

    with open(

        filepath,

        "w",

        encoding="utf-8"

    ) as f:

        json.dump(

            signals,

            f,

            indent=2,

            ensure_ascii=False
        )

    return filepath


# ============================================================
# ENTRY POINT
# ============================================================

if __name__ == "__main__":

    signals = run_scout()

    print_summary(
        signals
    )

    filepath = save_signals(
        signals
    )

    print(

        f"\n  Signals saved to: "
        f"{filepath}"
    )
