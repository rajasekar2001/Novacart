"""Dynamic structured FAQ extraction and grounded retrieval."""

import io
import ipaddress
import json
import logging
import re
import socket
import time
from collections import Counter
from difflib import SequenceMatcher
from fractions import Fraction
from urllib.parse import urldefrag, urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from django.conf import settings
from docx import Document
from PyPDF2 import PdfReader

from .models import FAQ


logger = logging.getLogger(__name__)


# Generic conversational words only.
# No industry, category, company or product names.
STOP_WORDS = {
    "the", "a", "an", "is", "are", "was", "were",
    "to", "of", "and", "or", "in", "on", "for",
    "with", "what", "how", "do", "does", "did",
    "i", "you", "your", "our", "my", "we",
    "please", "give", "show", "tell", "find",
    "search", "list", "all", "available",
    "availability", "details", "detail",
    "information", "about", "from",
    "price", "pricing", "cost", "rate", "amount",
    "product", "products", "item", "items",
    "service", "services", "category", "categories",
    "model", "models",
}


NOISE_TEXT = {
    "select location",
    "my account",
    "wishlist",
    "reviews and ratings",
    "sign out",
    "sort",
    "view all",
    "add",
    "home",
    "menu",
    "search",
    "login",
    "register",
    "cart",
    "checkout",
    "add to cart",
    "buy now",
    "quick view",
}


LIST_WORDS = {
    "list",
    "show",
    "available",
    "availability",
    "all",
}


PRICE_PHRASES = {
    "price",
    "pricing",
    "cost",
    "rate",
    "amount",
    "how much",
}


MONEY_RE = re.compile(
    r"(?:₹|Rs\.?|INR|\$|USD|€|EUR|£|GBP)"
    r"\s*([0-9][0-9,]*(?:\.\d{1,2})?)",
    re.IGNORECASE,
)


QUANTITY_RE = re.compile(
    r"\b("
    r"(?:\d+\s*/\s*\d+|\d+(?:\.\d+)?)"
    r")\s*"
    r"(kg|g|gm|gms|gram|grams|"
    r"l|ltr|litre|litres|liter|liters|ml|"
    r"pc|pcs|piece|pieces|pack|packs)"
    r"\b"
)


CONTACT_RE = re.compile(
    r"(?:\+?\d[\d\s().-]{7,}\d)"
    r"|(?:[\w.+-]+@[\w.-]+\.[A-Za-z]{2,})"
)


DISCOUNT_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s*%\s*(?:off)?\b",
    re.IGNORECASE,
)


def clean(value):
    """Normalize whitespace while preserving multilingual text."""

    return re.sub(
        r"\s+",
        " ",
        str(value or ""),
    ).strip(" \t\r\n-|:")


def unique(values):
    """Remove duplicates while preserving order."""

    result = []
    seen = set()

    for value in values:
        normalized = clean(value)
        key = normalized.casefold()

        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)

    return result


def normalize_word(word):
    """Small generic normalization for matching plural forms."""

    value = clean(word).casefold()

    if len(value) > 4 and value.endswith("ies"):
        return value[:-3] + "y"

    if len(value) > 4 and value.endswith("es"):
        return value[:-2]

    if len(value) > 3 and value.endswith("s"):
        return value[:-1]

    return value


def tokenize(value, remove_noise=False):
    """Tokenize multilingual text."""

    words = re.findall(
        r"[^\W_]+|\d+(?:\.\d+)?",
        clean(value).casefold(),
        re.UNICODE,
    )

    tokens = {
        normalize_word(word)
        for word in words
        if len(clean(word)) > 1
    }

    if remove_noise:
        tokens -= {
            normalize_word(word)
            for word in STOP_WORDS
        }

    return tokens


def keywords_for(*values, limit=15):
    """Create keywords from any language or industry."""

    words = []

    for value in values:
        words.extend(
            re.findall(
                r"[^\W_]+|\d+(?:\.\d+)?",
                clean(value).casefold(),
                re.UNICODE,
            )
        )

    counter = Counter(
        word
        for word in words
        if (
            len(word) > 1
            and normalize_word(word) not in STOP_WORDS
        )
    )

    return [
        word
        for word, _ in counter.most_common(limit)
    ]


def split_aliases(value):
    """Split multilingual names and alternative labels."""

    return unique(
        re.split(
            r"\s*(?:/|\||•|—)\s*",
            clean(value),
        )
    )


def similarity_score(query, candidate):
    """
    Compare user text with a stored product, category,
    service, model or other entity name.
    """

    query_value = clean(query).casefold()
    candidate_value = clean(candidate).casefold()

    if not query_value or not candidate_value:
        return 0.0

    query_terms = tokenize(
        query_value,
        remove_noise=True,
    )

    best_score = 0.0

    for alias in split_aliases(candidate_value):
        alias_terms = tokenize(
            alias,
            remove_noise=True,
        )

        if not alias_terms:
            alias_terms = tokenize(alias)

        if not alias_terms:
            continue

        if clean(alias).casefold() in query_value:
            best_score = max(
                best_score,
                1.0,
            )

        overlap = len(
            query_terms & alias_terms
        )

        if overlap:
            token_score = (
                overlap
                / max(len(alias_terms), 1)
            )

            best_score = max(
                best_score,
                token_score,
            )

        if query_terms:
            fuzzy_score = max(
                SequenceMatcher(
                    None,
                    query_term,
                    alias_term,
                ).ratio()
                for query_term in query_terms
                for alias_term in alias_terms
            )

            if fuzzy_score >= 0.84:
                best_score = max(
                    best_score,
                    fuzzy_score * 0.85,
                )

    return best_score


def normalize_faq(row, default_url=""):
    """Normalize one structured FAQ record."""

    if not isinstance(row, dict):
        return None

    question = clean(
        row.get("question")
    )

    answer = clean(
        row.get("answer")
    )

    if len(question) < 5 or len(answer) < 2:
        return None

    metadata = row.get(
        "metadata",
        {},
    )

    if not isinstance(metadata, dict):
        metadata = {}

    keywords = row.get(
        "keywords",
        [],
    )

    if not isinstance(keywords, list):
        keywords = []

    source_url = clean(
        row.get("source_url")
        or default_url
    )

    faq_type = clean(
        row.get("faq_type")
        or "general"
    )

    return {
        "question": question[:500],
        "answer": answer[:5000],
        "keywords": unique(
            [str(item) for item in keywords]
            + keywords_for(question, answer)
        )[:20],
        "faq_type": faq_type[:40],
        "metadata": metadata,
        "source_url": source_url,
    }


def deduplicate_faqs(rows):
    """Deduplicate records using question and entity data."""

    result = []
    seen = set()

    for row in rows:
        default_url = ""

        if isinstance(row, dict):
            default_url = row.get(
                "source_url",
                "",
            )

        normalized = normalize_faq(
            row,
            default_url,
        )

        if not normalized:
            continue

        metadata = normalized.get(
            "metadata",
            {},
        )

        key = (
            normalized["question"].casefold(),
            clean(metadata.get("name")).casefold(),
            clean(metadata.get("quantity")).casefold(),
            str(metadata.get("price", "")),
        )

        if key in seen:
            continue

        seen.add(key)
        result.append(normalized)

    return result


def extract_document(upload):
    """Extract text from supported documents."""

    data = upload.read()
    filename = upload.name.lower()

    if filename.endswith(".pdf"):
        reader = PdfReader(
            io.BytesIO(data)
        )

        return "\n".join(
            page.extract_text() or ""
            for page in reader.pages
        )

    if filename.endswith(".docx"):
        document = Document(
            io.BytesIO(data)
        )

        return "\n".join(
            paragraph.text
            for paragraph in document.paragraphs
        )

    if filename.endswith(
        (".txt", ".md", ".csv")
    ):
        return data.decode(
            "utf-8",
            errors="ignore",
        )

    raise ValueError(
        "Supported files are PDF, DOCX, TXT, MD and CSV."
    )


def is_noise(value):
    """Identify common user-interface noise."""

    text = clean(value).casefold()

    return (
        not text
        or text in NOISE_TEXT
        or len(text) < 2
    )


def visible_lines(soup):
    """Extract readable content from rendered HTML."""

    selectors = (
        "h1,h2,h3,h4,h5,h6,"
        "p,li,dt,dd,tr,"
        "article,section,"
        "[class*='product'],"
        "[class*='item'],"
        "[class*='card'],"
        "[class*='price'],"
        "[class*='title'],"
        "[class*='name']"
    )

    lines = []

    for node in soup.select(selectors):
        text = clean(
            node.get_text(
                " ",
                strip=True,
            )
        )

        if (
            not is_noise(text)
            and 2 <= len(text) <= 1500
        ):
            lines.append(text)

    return unique(lines)


def smallest_priced_lines(soup):
    """
    Extract the smallest useful HTML elements containing
    prices. This reduces parent/child duplication.
    """

    candidates = []

    for node in soup.find_all(
        ["div", "article", "li", "tr", "p", "span"]
    ):
        text = clean(
            node.get_text(
                " ",
                strip=True,
            )
        )

        if not MONEY_RE.search(text):
            continue

        if len(text) < 3 or len(text) > 500:
            continue

        child_with_price = False

        for child in node.find_all(
            ["div", "article", "li", "tr", "p"],
            recursive=False,
        ):
            child_text = clean(
                child.get_text(
                    " ",
                    strip=True,
                )
            )

            if MONEY_RE.search(child_text):
                child_with_price = True
                break

        if not child_with_price:
            candidates.append(text)

    return unique(candidates)


def normalize_start_url(start_url):
    """Add an HTTP scheme when it is absent."""

    start_url = clean(start_url)

    if not re.match(
        r"^https?://",
        start_url,
        re.IGNORECASE,
    ):
        start_url = "https://" + start_url

    return start_url


def validate_public_url(url):
    """Reject non-HTTP and private-network crawl targets to prevent SSRF."""
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Enter a valid HTTP or HTTPS website URL.")
    if getattr(settings, "CRAWL_ALLOW_PRIVATE_HOSTS", False):
        return url
    hostname = parsed.hostname.casefold()
    if hostname == "localhost" or hostname.endswith(".local"):
        raise ValueError("Private or local network websites cannot be crawled.")
    try:
        addresses = socket.getaddrinfo(hostname, parsed.port or 443, type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise ValueError("The website hostname could not be resolved.") from exc
    for address in addresses:
        ip = ipaddress.ip_address(address[4][0])
        if not ip.is_global:
            raise ValueError("Private or local network websites cannot be crawled.")
    return url


def create_chrome_driver():
    """Create a headless Selenium Chrome driver."""

    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from webdriver_manager.chrome import ChromeDriverManager

    options = Options()

    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-extensions")
    options.add_argument("--window-size=1920,1080")

    options.add_argument(
        "--user-agent=Mozilla/5.0 "
        "(Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/151.0.0.0 Safari/537.36"
    )

    service = Service(
        ChromeDriverManager().install()
    )

    driver = webdriver.Chrome(
        service=service,
        options=options,
    )

    driver.set_page_load_timeout(
        getattr(
            settings,
            "CRAWL_PAGE_TIMEOUT",
            45,
        )
    )

    return driver


def scroll_dynamic_page(driver):
    """Load lazy and JavaScript-rendered page content."""

    max_rounds = getattr(
        settings,
        "CRAWL_SCROLL_ROUNDS",
        10,
    )

    wait_seconds = getattr(
        settings,
        "CRAWL_SCROLL_WAIT",
        1.2,
    )

    previous_height = 0
    stable_rounds = 0

    for _ in range(max_rounds):
        current_height = driver.execute_script(
            "return document.body.scrollHeight"
        )

        driver.execute_script(
            "window.scrollTo(0, "
            "document.body.scrollHeight);"
        )

        time.sleep(wait_seconds)

        new_height = driver.execute_script(
            "return document.body.scrollHeight"
        )

        if (
            new_height == current_height
            or new_height == previous_height
        ):
            stable_rounds += 1

        else:
            stable_rounds = 0

        if stable_rounds >= 2:
            break

        previous_height = new_height


def should_visit_url(url, root_domain):
    """Check whether a discovered URL is crawlable."""

    parsed = urlparse(url)

    if parsed.scheme not in {
        "http",
        "https",
    }:
        return False

    if (
        parsed.netloc.casefold()
        != root_domain.casefold()
    ):
        return False

    if re.search(
        r"\.(?:jpg|jpeg|png|gif|webp|svg|"
        r"pdf|zip|rar|mp4|mp3|css|js|xml)"
        r"(?:\?|$)",
        parsed.path,
        re.IGNORECASE,
    ):
        return False

    if re.search(
        r"/(?:login|logout|account|wishlist|"
        r"cart|checkout)(?:/|$)",
        parsed.path,
        re.IGNORECASE,
    ):
        return False

    return True


def crawl_with_requests(url):
    """Fallback for environments without Selenium."""

    headers = {
        "User-Agent": (
            "Mozilla/5.0 "
            "(compatible; KnowledgeCrawler/3.0)"
        )
    }

    response = requests.get(
        url,
        headers=headers,
        timeout=20,
    )

    response.raise_for_status()

    validate_public_url(response.url)

    return response.text


def crawl(start_url, max_pages=None):
    """
    Universal same-domain crawler.

    Selenium is used when possible so dynamically rendered
    product and service pages can be extracted.
    """

    start_url = normalize_start_url(
        start_url
    )

    validate_public_url(start_url)

    max_pages = (
        max_pages
        or settings.MAX_CRAWL_PAGES
    )

    root_domain = urlparse(
        start_url
    ).netloc

    queue = [start_url]
    seen = set()
    pages = []
    driver = None

    try:
        try:
            driver = create_chrome_driver()

        except Exception as exc:
            logger.warning(
                "Selenium unavailable; using requests: %s",
                exc,
            )

        while queue and len(pages) < max_pages:
            current_url = urldefrag(
                queue.pop(0)
            )[0].rstrip("/")

            if not current_url:
                current_url = start_url

            if current_url in seen:
                continue

            seen.add(current_url)

            try:
                validate_public_url(current_url)
                if driver:
                    driver.get(current_url)

                    time.sleep(
                        getattr(
                            settings,
                            "CRAWL_INITIAL_WAIT",
                            2,
                        )
                    )

                    scroll_dynamic_page(driver)

                    html = driver.page_source

                else:
                    html = crawl_with_requests(
                        current_url
                    )

                soup = BeautifulSoup(
                    html,
                    "html.parser",
                )

                title = (
                    clean(soup.title.string)
                    if soup.title and soup.title.string
                    else current_url
                )

                product_lines = (
                    smallest_priced_lines(soup)
                )

                for tag in soup.select(
                    "script,style,noscript,svg,"
                    "iframe,footer,nav"
                ):
                    tag.decompose()

                lines = visible_lines(soup)

                lines = unique(
                    product_lines + lines
                )

                body = "\n".join(lines)

                if body:
                    pages.append({
                        "url": current_url,
                        "title": title,
                        "text": body[:50000],
                        "lines": lines[:1200],
                        "product_lines": (
                            product_lines[:500]
                        ),
                    })

                for anchor in soup.select(
                    "a[href]"
                ):
                    next_url = urljoin(
                        current_url,
                        anchor.get("href", ""),
                    )

                    next_url = urldefrag(
                        next_url
                    )[0].rstrip("/")

                    if (
                        next_url
                        and next_url not in seen
                        and next_url not in queue
                        and should_visit_url(
                            next_url,
                            root_domain,
                        )
                    ):
                        queue.append(next_url)

            except Exception as exc:
                logger.warning(
                    "Could not crawl %s: %s",
                    current_url,
                    exc,
                )

    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass

    return pages


def infer_page_type(title, url, text):
    """
    Infer a broad page type.

    These are generic web-document types and do not
    contain industry-specific names.
    """

    value = (
        f"{title} {url} {text[:1500]}"
        .casefold()
    )

    tests = [
        (
            "contact",
            (
                "contact",
                "address",
                "phone",
                "email",
            ),
        ),
        (
            "faq",
            (
                "frequently asked",
                " faq",
                "questions",
            ),
        ),
        (
            "policy",
            (
                "policy",
                "warranty",
                "return",
                "refund",
                "shipping",
                "delivery",
            ),
        ),
        (
            "category",
            (
                "/category/",
                "/categories/",
                "/collection/",
            ),
        ),
        (
            "entity",
            (
                "/product/",
                "/products/",
                "/service/",
                "/services/",
                "/project/",
                "/projects/",
            ),
        ),
        (
            "about",
            (
                "about",
                "who we are",
                "our company",
                "our team",
            ),
        ),
    ]

    for page_type, phrases in tests:
        if any(
            phrase in value
            for phrase in phrases
        ):
            return page_type

    return "general"


def get_page_subject(page):
    """
    Discover the page subject/category dynamically from
    H1/title/URL rather than predefined category names.
    """

    title = clean(
        page.get("title", "")
    )

    subject = clean(
        title.split(" - ")[0]
    )

    if subject:
        return subject

    path = urlparse(
        page.get("url", "")
    ).path

    final_path = path.rstrip("/").split("/")[-1]

    final_path = re.sub(
        r"[-_]+",
        " ",
        final_path,
    )

    final_path = re.sub(
        r"\b\d+\b",
        "",
        final_path,
    )

    return clean(final_path)


def extract_categories(page):
    """Discover category labels from the page."""

    candidates = []
    subject = get_page_subject(page)
    path = urlparse(
        page.get("url", "")
    ).path

    if re.search(
        r"/(?:category|categories|collection|collections)/",
        path,
        re.IGNORECASE,
    ):
        if subject:
            candidates.append(subject)

    for line in page.get("lines", []):
        if (
            "/" in line
            and len(line) <= 100
            and not MONEY_RE.search(line)
            and not CONTACT_RE.search(line)
        ):
            parts = [
                clean(part)
                for part in line.split("/")
            ]

            if (
                1 <= len(parts) <= 4
                and all(
                    1 < len(part) < 60
                    for part in parts
                )
            ):
                candidates.append(
                    " / ".join(parts)
                )

    return unique(candidates)[:100]


def currency_from_line(line):
    """Detect currency without assuming one country."""

    currency_patterns = [
        ("₹", "INR"),
        ("INR", "INR"),
        ("Rs", "INR"),
        ("$", "USD"),
        ("USD", "USD"),
        ("€", "EUR"),
        ("EUR", "EUR"),
        ("£", "GBP"),
        ("GBP", "GBP"),
    ]

    for symbol, code in currency_patterns:
        if symbol.casefold() in line.casefold():
            return code

    return ""


def parse_product_line(line):
    """
    Extract a structured purchasable entity.

    The name may represent a product, model, plan,
    course, service package or another priced entity.
    """

    text = clean(line)

    money_matches = list(
        MONEY_RE.finditer(text)
    )

    if not money_matches:
        return None

    money_match = money_matches[0]

    prefix = clean(
        text[:money_match.start()]
    )

    # Remove discount labels before extracting the name.
    prefix = DISCOUNT_RE.sub(
        " ",
        prefix,
    )

    prefix = re.sub(
        r"\b(?:add to cart|add|buy now|quick view|"
        r"view all|save)\b.*$",
        "",
        prefix,
        flags=re.IGNORECASE,
    )

    prefix = clean(prefix)

    if len(prefix) < 2 or len(prefix) > 250:
        return None

    # Reject strings made only from discounts/numbers.
    if not re.search(
        r"[^\W\d_]",
        prefix,
        re.UNICODE,
    ):
        return None

    quantity_match = QUANTITY_RE.search(
        prefix
    )

    if quantity_match:
        # Uppercase 5G-like model text must not become grams.
        raw_unit = quantity_match.group(2)

        if raw_unit == "G":
            quantity = ""
            name = prefix

        else:
            quantity = clean(
                quantity_match.group(0)
            )

            name = clean(
                prefix[:quantity_match.start()]
                + " "
                + prefix[quantity_match.end():]
            )

    else:
        quantity = ""
        name = prefix

    name = clean(
        DISCOUNT_RE.sub(
            " ",
            name,
        )
    )

    if not name or name.casefold() in NOISE_TEXT:
        return None

    price_text = (
        money_match
        .group(1)
        .replace(",", "")
    )

    try:
        price = float(price_text)

        if price.is_integer():
            price = int(price)

    except ValueError:
        return None

    return {
        "name": name,
        "quantity": quantity,
        "price": price,
        "currency": currency_from_line(text),
    }


def deterministic_page_faqs(page):
    """Create structured records without an LLM."""

    title = clean(
        page.get("title", "")
    )

    url = clean(
        page.get("url", "")
    )

    text = clean(
        page.get("text", "")
    )

    lines = page.get(
        "lines",
        [],
    )

    product_lines = page.get(
        "product_lines",
        [],
    )

    page_type = infer_page_type(
        title,
        url,
        text,
    )

    subject = get_page_subject(page)
    categories = extract_categories(page)

    primary_category = (
        categories[0]
        if categories
        else (
            subject
            if page_type == "category"
            else ""
        )
    )

    rows = []

    if categories:
        rows.append({
            "question": (
                f"What categories are available on {title}?"
            ),
            "answer": ", ".join(categories),
            "keywords": categories,
            "faq_type": "category_list",
            "metadata": {
                "categories": categories,
                "page_subject": subject,
            },
            "source_url": url,
        })

    entities = []
    entity_keys = set()

    for line in unique(
        product_lines + lines
    ):
        entity = parse_product_line(line)

        if not entity:
            continue

        entity_key = (
            entity["name"].casefold(),
            entity["quantity"].casefold(),
            str(entity["price"]),
        )

        if entity_key in entity_keys:
            continue

        entity_keys.add(entity_key)
        entities.append(entity)

    for entity in entities[:200]:
        quantity_text = ""

        if entity["quantity"]:
            quantity_text = (
                f" {entity['quantity']}"
            )

        metadata = {
            **entity,
            "category": primary_category,
            "page_subject": subject,
            "page_type": page_type,
        }

        rows.append({
            "question": (
                f"What is the price of "
                f"{entity['name']}{quantity_text}?"
            ),
            "answer": (
                f"{entity['name']}{quantity_text} "
                f"is listed at "
                f"{entity['currency']} "
                f"{entity['price']}."
            ).replace("  ", " "),
            "keywords": keywords_for(
                entity["name"],
                entity["quantity"],
                primary_category,
                str(entity["price"]),
            ),
            "faq_type": "entity_price",
            "metadata": metadata,
            "source_url": url,
        })

    contacts = unique(
        CONTACT_RE.findall(text)
    )

    if contacts:
        rows.append({
            "question": (
                f"How can I contact {subject or title}?"
            ),
            "answer": (
                "Contact details: "
                + ", ".join(contacts[:10])
                + "."
            ),
            "keywords": keywords_for(
                "contact",
                *contacts,
            ),
            "faq_type": "contact",
            "metadata": {
                "contacts": contacts[:10],
                "page_subject": subject,
            },
            "source_url": url,
        })

    # Genuine question/answer pairs.
    for index, line in enumerate(lines[:-1]):
        if (
            line.endswith("?")
            and 5 < len(line) <= 300
        ):
            next_line = clean(
                lines[index + 1]
            )

            if (
                next_line
                and not next_line.endswith("?")
                and next_line != line
            ):
                rows.append({
                    "question": line,
                    "answer": next_line,
                    "keywords": keywords_for(
                        line,
                        next_line,
                    ),
                    "faq_type": "faq",
                    "metadata": {
                        "page_subject": subject,
                        "category": primary_category,
                    },
                    "source_url": url,
                })

    if not rows:
        meaningful_lines = [
            line
            for line in lines
            if (
                len(line) >= 25
                and not is_noise(line)
            )
        ][:10]

        if meaningful_lines:
            rows.append({
                "question": (
                    f"What information is provided "
                    f"about {subject or title}?"
                ),
                "answer": " ".join(
                    meaningful_lines
                )[:4000],
                "keywords": keywords_for(
                    subject,
                    *meaningful_lines,
                ),
                "faq_type": page_type,
                "metadata": {
                    "page_subject": subject,
                    "category": primary_category,
                },
                "source_url": url,
            })

    return deduplicate_faqs(rows)


def parse_json_response(content):
    """Parse a Groq JSON response."""

    content = clean(content)

    if content.startswith("```"):
        content = re.sub(
            r"^```(?:json)?\s*|\s*```$",
            "",
            content,
            flags=re.IGNORECASE,
        )

    parsed = json.loads(content)

    if isinstance(parsed, dict):
        rows = parsed.get(
            "faqs",
            [],
        )
    else:
        rows = parsed

    if not isinstance(rows, list):
        raise ValueError(
            "Groq response does not contain an FAQ list."
        )

    return rows


def llm_page_faqs(page):
    """Generate additional structured records using Groq."""

    if not settings.GROQ_API_KEY:
        return []

    from groq import Groq

    source_url = page.get(
        "url",
        "",
    )

    schema = {
        "faqs": [
            {
                "question": "Natural user question",
                "answer": "Verified answer",
                "keywords": ["keyword"],
                "faq_type": "entity|entity_price|category|service|contact|policy|faq|general",
                "metadata": {
                    "name": "",
                    "category": "",
                    "quantity": "",
                    "price": None,
                    "currency": "",
                    "attributes": {},
                },
                "source_url": source_url,
            }
        ]
    }

    prompt = f"""
Convert the supplied page into structured FAQ JSON.

Return exactly one JSON object containing a "faqs" array.

Schema:
{json.dumps(schema, ensure_ascii=False)}

Rules:

1. The website may belong to any industry.
2. Discover terminology from the supplied page.
3. Do not assume any predefined products or categories.
4. Extract named entities, categories, variants, prices,
   quantities, specifications, services, projects,
   policies, contacts, team roles and genuine FAQs.
5. Store structured values in metadata.
6. Every price must belong to the same named entity.
7. Never transfer a price or specification between entities.
8. Preserve multilingual names.
9. Remove navigation, account, cart and sorting text.
10. Do not treat discounts as product names or prices.
11. Never invent missing information.
12. Never create numbered "part N" questions.
13. Produce at most 20 high-value records.

PAGE TITLE:
{page.get("title", "")}

SOURCE URL:
{source_url}

PAGE CONTENT:
{page.get("text", "")[:7000]}
""".strip()

    try:
        client = Groq(
            api_key=settings.GROQ_API_KEY
        )

        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": prompt,
                }
            ],
            temperature=0,
            max_tokens=1800,
            response_format={
                "type": "json_object",
            },
        )

        rows = parse_json_response(
            response.choices[0].message.content
        )

        return [
            normalized
            for normalized in (
                normalize_faq(
                    row,
                    source_url,
                )
                for row in rows
            )
            if normalized
        ]

    except Exception as exc:
        logger.warning(
            "Groq FAQ extraction failed for %s: %s",
            source_url,
            exc,
        )

        return []


def generate_website_faqs(pages):
    """Generate structured FAQs for all crawled pages."""

    rows = []

    for page in pages:
        rows.extend(
            deterministic_page_faqs(page)
        )

        rows.extend(
            llm_page_faqs(page)
        )

    return deduplicate_faqs(rows)


def text_to_page(
    text,
    title="Information",
    source_url="",
):
    """Convert text or document content to page data."""

    lines = unique([
        clean(line)
        for line in re.split(
            r"\n+",
            text,
        )
        if not is_noise(line)
    ])

    return {
        "title": title,
        "url": source_url,
        "text": "\n".join(lines),
        "lines": lines,
        "product_lines": [
            line
            for line in lines
            if MONEY_RE.search(line)
        ],
    }


def generate_faqs(
    text,
    title,
    source_url="",
):
    """Generate structured FAQs for text/documents."""

    page = text_to_page(
        text,
        title,
        source_url,
    )

    return deduplicate_faqs(
        deterministic_page_faqs(page)
        + llm_page_faqs(page)
    )


def get_record_name(faq):
    """Return the dynamically extracted entity name."""

    metadata = faq.metadata or {}

    return clean(
        metadata.get("name")
        or metadata.get("entity_name")
        or metadata.get("title")
        or ""
    )


def get_record_category(faq):
    """Return the dynamically extracted category."""

    metadata = faq.metadata or {}

    value = (
        metadata.get("category")
        or metadata.get("group")
        or metadata.get("section")
        or ""
    )

    if isinstance(value, list):
        return " / ".join(
            clean(item)
            for item in value
        )

    return clean(value)


def build_catalog():
    """
    Build an entity/category index entirely from DB data.

    No company, product or industry names are hardcoded.
    """

    records = list(
        FAQ.objects
        .select_related("source")
        .all()
    )

    names = {}
    categories = {}

    for faq in records:
        name = get_record_name(faq)
        category = get_record_category(faq)

        if name:
            names.setdefault(
                name.casefold(),
                name,
            )

        if category:
            categories.setdefault(
                category.casefold(),
                category,
            )

        metadata = faq.metadata or {}

        values = metadata.get(
            "categories",
            [],
        )

        if isinstance(values, list):
            for value in values:
                value = clean(value)

                if value:
                    categories.setdefault(
                        value.casefold(),
                        value,
                    )

    return {
        "records": records,
        "names": list(names.values()),
        "categories": list(
            categories.values()
        ),
    }


def best_match(
    question,
    candidates,
    minimum_score=0.58,
):
    """Find the best stored entity/category for a query."""

    best_candidate = None
    best_score = 0.0

    for candidate in candidates:
        score = similarity_score(
            question,
            candidate,
        )

        if score > best_score:
            best_score = score
            best_candidate = candidate

    if best_score < minimum_score:
        return None

    return best_candidate


def parse_number(value):
    """Parse decimal and fractional quantity values."""

    value = clean(value).replace(
        " ",
        "",
    )

    try:
        if "/" in value:
            return float(
                Fraction(value)
            )

        return float(value)

    except (
        ValueError,
        ZeroDivisionError,
    ):
        return None


def parse_quantity(value):
    """
    Convert quantities to comparable base units.

    Uppercase model suffixes such as 5G are not treated
    as gram quantities.
    """

    match = QUANTITY_RE.search(
        clean(value)
    )

    if not match:
        return None

    raw_unit = match.group(2)

    if raw_unit == "G":
        return None

    amount = parse_number(
        match.group(1)
    )

    if amount is None:
        return None

    unit = raw_unit.casefold()

    conversions = {
        "kg": ("weight", amount * 1000, "g"),
        "g": ("weight", amount, "g"),
        "gm": ("weight", amount, "g"),
        "gms": ("weight", amount, "g"),
        "gram": ("weight", amount, "g"),
        "grams": ("weight", amount, "g"),

        "l": ("volume", amount * 1000, "ml"),
        "ltr": ("volume", amount * 1000, "ml"),
        "litre": ("volume", amount * 1000, "ml"),
        "litres": ("volume", amount * 1000, "ml"),
        "liter": ("volume", amount * 1000, "ml"),
        "liters": ("volume", amount * 1000, "ml"),
        "ml": ("volume", amount, "ml"),

        "pc": ("count", amount, "piece"),
        "pcs": ("count", amount, "piece"),
        "piece": ("count", amount, "piece"),
        "pieces": ("count", amount, "piece"),

        "pack": ("pack", amount, "pack"),
        "packs": ("pack", amount, "pack"),
    }

    quantity_type, base_value, base_unit = (
        conversions[unit]
    )

    return {
        "text": clean(match.group(0)),
        "type": quantity_type,
        "value": base_value,
        "unit": base_unit,
    }


def quantities_match(first, second):
    """Compare compatible normalized quantities."""

    if not first or not second:
        return False

    if first["type"] != second["type"]:
        return False

    return abs(
        first["value"]
        - second["value"]
    ) <= 0.001


def is_list_query(question):
    """Detect a generic list request."""

    tokens = tokenize(question)

    return bool(
        tokens
        & {
            normalize_word(word)
            for word in LIST_WORDS
        }
    )


def is_price_query(question):
    """Detect price or quantity intent."""

    value = clean(question).casefold()

    return (
        any(
            phrase in value
            for phrase in PRICE_PHRASES
        )
        or parse_quantity(question) is not None
    )


def resolve_query(question):
    """Resolve query against entities stored in the DB."""

    catalog = build_catalog()

    entity = best_match(
        question,
        catalog["names"],
        minimum_score=0.58,
    )

    category = best_match(
        question,
        catalog["categories"],
        minimum_score=0.58,
    )

    return {
        "catalog": catalog,
        "entity": entity,
        "category": category,
        "quantity": parse_quantity(
            question
        ),
        "list_intent": is_list_query(
            question
        ),
        "price_intent": is_price_query(
            question
        ),
    }


def retrieve_structured(question, limit=100):
    """Strict structured entity/category retrieval."""

    plan = resolve_query(question)
    results = []

    for faq in plan["catalog"]["records"]:
        name = get_record_name(faq)
        category = get_record_category(faq)

        if plan["entity"]:
            score = similarity_score(
                plan["entity"],
                name,
            )

            if score < 0.75:
                continue

        elif plan["category"]:
            score = similarity_score(
                plan["category"],
                category,
            )

            if score < 0.70:
                continue

        else:
            continue

        if plan["price_intent"] and not name:
            continue

        if plan["quantity"]:
            stored = parse_quantity(
                str(
                    (faq.metadata or {}).get(
                        "quantity",
                        "",
                    )
                )
            )

            if not quantities_match(
                plan["quantity"],
                stored,
            ):
                continue

        rank = 0.0

        if plan["entity"]:
            rank += (
                similarity_score(
                    plan["entity"],
                    name,
                )
                * 10
            )

        if plan["category"]:
            rank += (
                similarity_score(
                    plan["category"],
                    category,
                )
                * 5
            )

        if plan["quantity"]:
            rank += 5

        results.append(
            (rank, faq)
        )

    results.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return (
        [
            faq
            for _, faq in results[:limit]
        ],
        plan,
    )


def retrieve_general(question, limit=8):
    """Retrieve policies, contacts and general FAQs."""

    query_terms = tokenize(
        question,
        remove_noise=True,
    )

    if not query_terms:
        query_terms = tokenize(question)

    ranked = []

    for faq in FAQ.objects.select_related(
        "source"
    ).all():
        searchable = " ".join([
            faq.question,
            faq.answer,
            " ".join(faq.keywords or []),
            json.dumps(
                faq.metadata or {},
                ensure_ascii=False,
            ),
        ])

        record_terms = tokenize(
            searchable,
            remove_noise=True,
        )

        overlap = len(
            query_terms & record_terms
        )

        if not overlap:
            continue

        score = overlap / max(
            len(query_terms),
            1,
        )

        score += (
            SequenceMatcher(
                None,
                clean(question).casefold(),
                clean(faq.question).casefold(),
            ).ratio()
            * 0.30
        )

        ranked.append(
            (score, faq)
        )

    ranked.sort(
        key=lambda item: item[0],
        reverse=True,
    )

    return [
        faq
        for score, faq in ranked[:limit]
        if score >= 0.20
    ]


def retrieve(question, limit=8):
    """Retrieve structured records before general FAQs."""

    structured, plan = (
        retrieve_structured(
            question,
            limit=limit,
        )
    )

    if structured:
        return structured

    # Never answer an entity-specific price query
    # using another entity's price.
    if (
        plan["price_intent"]
        and (
            plan["entity"]
            or plan["quantity"]
        )
    ):
        return []

    return retrieve_general(
        question,
        limit=limit,
    )


def compact_context(
    faqs,
    max_chars=7500,
):
    """Build bounded evidence to prevent HTTP 413."""

    sections = []
    used = 0

    for faq in faqs:
        metadata = json.dumps(
            faq.metadata or {},
            ensure_ascii=False,
        )

        block = (
            f"Question: {faq.question}\n"
            f"Answer: {faq.answer[:1200]}\n"
            f"Type: {faq.faq_type}\n"
            f"Metadata: {metadata[:800]}\n"
            f"Source: "
            f"{faq.source_url or faq.source.title}"
        )

        if used + len(block) > max_chars:
            break

        sections.append(block)
        used += len(block)

    return "\n\n".join(sections)


def format_structured_list(faqs):
    """Format a category/entity list from structured rows."""

    output = []
    seen = set()

    for faq in faqs:
        metadata = faq.metadata or {}

        name = get_record_name(faq)

        if not name:
            continue

        key = name.casefold()

        if key in seen:
            continue

        seen.add(key)

        line = f"• {name}"

        quantity = clean(
            metadata.get("quantity")
        )

        price = metadata.get(
            "price"
        )

        currency = clean(
            metadata.get("currency")
        )

        if quantity:
            line += f" — {quantity}"

        if price not in (None, ""):
            line += (
                f" — {currency} {price}"
            ).rstrip()

        output.append(line)

    return output


def answer_from_live_commerce(question, user=None):
    """Answer volatile catalog/order questions from authoritative tables."""
    from django.db.models import Q
    from store.models import Category, Order, Product, ProductVariant

    value = clean(question).casefold()
    order_match = re.search(r"\border\s*#?\s*(\d+)\b", value)
    if order_match and any(word in value for word in ("status", "track", "where", "delivery")):
        if not user or not user.is_authenticated:
            return (
                "Please sign in to check an order. I can only show orders that belong to your account.",
                [],
            )
        order = Order.objects.filter(id=order_match.group(1), user=user).first()
        if not order:
            return ("I could not find that order in your account.", [])
        answer_text = (
            f"Order #{order.id} is {order.get_status_display()}. "
            f"Payment status: {order.get_payment_status_display()}."
        )
        try:
            shipment = order.shipment
        except Exception:
            shipment = None
        if shipment and shipment.tracking_number:
            answer_text += f" Tracking number: {shipment.tracking_number}."
        return answer_text, [f"/orders/{order.public_id}/"]

    products = Product.objects.filter(
        active=True, catalog_status="published", category__active=True
    ).select_related("category").prefetch_related("variants")
    categories = list(Category.objects.filter(active=True))
    category = best_match(question, [item.name for item in categories], minimum_score=0.72)
    product_names = list(products.values_list("name", flat=True))
    product_name = best_match(question, product_names, minimum_score=0.72)
    variants = ProductVariant.objects.filter(
        active=True, product__active=True, product__catalog_status="published",
        product__category__active=True,
    ).select_related("product")
    variant_names = list(variants.values_list("name", flat=True))
    variant_name = best_match(question, variant_names, minimum_score=0.78)
    wants_list = is_list_query(question)
    wants_price = is_price_query(question)
    wants_stock = any(term in value for term in ("stock", "available", "availability", "in store"))

    if product_name or variant_name:
        if variant_name:
            variant = variants.filter(name=variant_name).first()
            if variant:
                text = (
                    f"{variant.product.name} - {variant.name} costs INR "
                    f"{variant.effective_price} and has {variant.stock} unit(s) in stock."
                )
                return text, [f"/product/{variant.product.slug}/"]
        product = products.filter(name=product_name).first()
        if product and (wants_price or wants_stock):
            active_variants = list(product.variants.filter(active=True))
            if active_variants:
                lines = [
                    f"- {variant.name}: INR {variant.effective_price}, {variant.stock} in stock"
                    for variant in active_variants
                ]
                return f"{product.name} variants:\n" + "\n".join(lines), [f"/product/{product.slug}/"]
            return (
                f"{product.name} costs INR {product.price} and has {product.stock} unit(s) in stock.",
                [f"/product/{product.slug}/"],
            )

    explicit_catalog_words = any(term in value for term in ("product", "products", "catalog", "shop", "items"))
    if wants_list and (category or explicit_catalog_words):
        selected = products.filter(category__name=category) if category else products
        selected = list(selected[:30])
        if not selected:
            return None
        lines = [f"- {item.name}: INR {item.price} ({item.available_stock} in stock)" for item in selected]
        sources = [f"/product/{item.slug}/" for item in selected[:10]]
        heading = f"Available {category} products:" if category else "Available products:"
        return heading + "\n" + "\n".join(lines), sources

    budget_match = re.search(
        r"(?:under|below|less than|up to)\s*(?:inr|rs\.?|₹)?\s*([0-9][0-9,]*)",
        value,
    )
    if budget_match:
        budget = budget_match.group(1).replace(",", "")
        selected = products.filter(price__lte=budget)
        if category:
            selected = selected.filter(category__name=category)
        query_words = tokenize(question, remove_noise=True)
        if query_words:
            query_filter = Q()
            for word in query_words:
                query_filter |= Q(name__icontains=word) | Q(description__icontains=word) | Q(brand__icontains=word)
            selected = selected.filter(query_filter).distinct()
        selected = list(selected.order_by("price")[:12])
        if selected:
            lines = [f"- {item.name}: INR {item.price}" for item in selected]
            return "Matching products:\n" + "\n".join(lines), [f"/product/{item.slug}/" for item in selected]
    # Treat a bare product/brand/category name as a catalog lookup.
    # Keep policy, delivery and other informational questions in the FAQ flow.
    catalog_terms = {"product", "products", "category", "categories", "brand", "brands", "shop", "catalog", "item", "items", "buy", "purchase", "stock"}
    tokens = set(re.findall(r"[\w]+", value))
    question_words = {"what", "which", "do", "does", "is", "are", "have", "show", "list", "find", "any", "available", "sell", "price", "cost", "of", "the", "a", "an", "you", "your", "in", "for", "me", "please"}
    catalog_query = (
        bool(tokens & catalog_terms)
        or (bool(tokens) and len(tokens) <= 3 and not tokens & {"hello", "hi", "hey", "thanks", "thank", "delivery", "shipping", "return", "refund", "policy", "payment", "contact", "help", "order", "track"})
        or (bool(tokens & {"price", "cost", "available", "sell"}) and bool(tokens - question_words))
    )
    if catalog_query:
        # Search exact names, brands, and categories first; don't substitute
        # a similarly named but different product.
        search_terms = [t for t in tokens if t not in question_words and t not in catalog_terms and len(t) > 1]
        matching = products.none()
        if search_terms:
            criteria = Q()
            for term in search_terms:
                criteria |= (Q(name__icontains=term) | Q(brand__icontains=term) | Q(category__name__icontains=term))
            matching = products.filter(criteria).distinct()
        if category and not search_terms:
            matching = products.filter(category__name=category)
        selected = list(matching[:8])
        if selected:
            lines = [f"- {p.name}: INR {p.price} ({p.available_stock} in stock)" for p in selected]
            return "Matching NovaCart products:\n" + "\n".join(lines), [f"/product/{p.slug}/" for p in selected]

        alternatives = list(products.order_by("name")[:5])
        available_categories = categories[:8]
        lines = [f"Sorry, I couldn't find '{clean(question)}' in our current catalog."]
        sources = []
        if alternatives:
            lines.append("Here are products you can explore:")
            for p in alternatives:
                lines.append(f"- {p.name}: INR {p.price} ({p.available_stock} in stock)")
                sources.append(f"/product/{p.slug}/")
        if available_categories:
            lines.append("Available categories: " + ", ".join(c.name for c in available_categories))
            sources.extend(f"/category/{c.slug}/" for c in available_categories)
        if not alternatives and not available_categories:
            lines.append("No products or categories are currently available.")
        return "\n".join(lines), sources
    return None


def answer(question, history=None, user=None):
    """Answer using strict structured retrieval."""

    commerce_answer = answer_from_live_commerce(question, user=user)
    if commerce_answer is not None:
        return commerce_answer

    structured_faqs, plan = (
        retrieve_structured(
            question,
            limit=100,
        )
    )

    if (
        plan["list_intent"]
        and plan["category"]
    ):
        lines = format_structured_list(
            structured_faqs
        )

        if not lines:
            return (
                "I found the requested category, but "
                "no individual items were extracted "
                "for that category.",
                [],
            )

        sources = list(dict.fromkeys(
            faq.source_url
            or faq.source.title
            for faq in structured_faqs
        ))

        return (
            "Available items:\n"
            + "\n".join(lines),
            sources,
        )

    if plan["price_intent"]:
        if not plan["entity"]:
            return (
                "Please specify the exact item, model, "
                "plan or service whose price you need.",
                [],
            )

        if not structured_faqs:
            quantity_text = ""

            if plan["quantity"]:
                quantity_text = (
                    f" for {plan['quantity']['text']}"
                )

            return (
                "I could not find a verified price for "
                f"{plan['entity']}{quantity_text} in "
                "the uploaded knowledge base.",
                [],
            )

        price_records = [
            faq
            for faq in structured_faqs
            if (
                faq.metadata or {}
            ).get("price") not in (
                None,
                "",
            )
        ]

        if not price_records:
            return (
                "I found the requested item, but no "
                "verified price is stored for it.",
                [],
            )

        lines = format_structured_list(
            price_records
        )

        sources = list(dict.fromkeys(
            faq.source_url
            or faq.source.title
            for faq in price_records
        ))

        return (
            "\n".join(lines),
            sources,
        )

    if plan["entity"] and structured_faqs:
        faqs = structured_faqs[:8]

    else:
        faqs = retrieve_general(
            question,
            limit=8,
        )

    if not faqs:
        return (
            "I could not find that information in "
            "the uploaded knowledge base.",
            [],
        )

    sources = list(dict.fromkeys(
        faq.source_url
        or faq.source.title
        for faq in faqs
    ))

    if not settings.GROQ_API_KEY:
        return (
            "\n".join(
                f"• {faq.answer}"
                for faq in faqs[:5]
            ),
            sources,
        )

    from groq import Groq

    client = Groq(
        api_key=settings.GROQ_API_KEY
    )

    context = compact_context(
        faqs,
        getattr(
            settings,
            "RAG_MAX_EVIDENCE_CHARS",
            7500,
        ),
    )

    system_prompt = f"""
You are a grounded conversational assistant.

Answer only from the supplied CONTEXT.

The website may belong to any industry. Use the terminology
and entities found in the context.

Rules:

1. Never substitute one entity for another.
2. Never transfer a price, quantity or specification.
3. Preserve exact names, variants, quantities and prices.
4. Combine records only when they describe the same request.
5. If information is missing, say it is unavailable.
6. Never invent facts.
7. Do not expose internal reasoning.
8. Answer naturally in the user's language.

CONTEXT:

{context}
""".strip()

    safe_history = [
        message
        for message in (history or [])[-6:]
        if message.get("role")
        in {"user", "assistant"}
    ]

    messages = [
        {
            "role": "system",
            "content": system_prompt,
        },
        *safe_history,
        {
            "role": "user",
            "content": question,
        },
    ]

    try:
        response = client.chat.completions.create(
            model=settings.GROQ_MODEL,
            messages=messages,
            temperature=0,
            max_tokens=900,
        )

        result = (
            response
            .choices[0]
            .message
            .content
        )

    except Exception as exc:
        logger.warning(
            "Groq response failed: %s",
            exc,
        )

        compact = compact_context(
            faqs[:3],
            2800,
        )

        try:
            response = client.chat.completions.create(
                model=settings.GROQ_MODEL,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Answer only from the "
                            "following evidence:\n"
                            + compact
                        ),
                    },
                    {
                        "role": "user",
                        "content": question,
                    },
                ],
                temperature=0,
                max_tokens=600,
            )

            result = (
                response
                .choices[0]
                .message
                .content
            )

        except Exception:
            result = "\n".join(
                f"• {faq.answer}"
                for faq in faqs[:5]
            )

    return result, sources
