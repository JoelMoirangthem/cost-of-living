from flask import Flask, render_template, request
import requests
from bs4 import BeautifulSoup
import re
from collections import OrderedDict, defaultdict
import logging

app = Flask(__name__)

# --- configure logging ---
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# -----------------------
# Category definitions
# -----------------------
Restaurants = [
    "Meal, Inexpensive Restaurant",
    "Meal for 2 People, Mid-range Restaurant, Three-course",
    "McMeal at McDonalds (or Equivalent Combo Meal)",
    "Domestic Beer (0.5 liter draught)",
    "Imported Beer (0.33 liter bottle)",
    "Cappuccino (regular)",
    "Coke/Pepsi (0.33 liter bottle)",
    "Water (0.33 liter bottle)",
]

Markets = [
    "Milk (regular), (1 liter)",
    "Loaf of Fresh White Bread (500g)",
    "Rice (white), (1kg)",
    "Eggs (regular) (12)",
    "Local Cheese (1kg)",
    "Chicken Fillets (1kg)",
    "Buffalo Round (1kg) (or Equivalent Back Leg Red Meat)",
    "Apples (1kg)",
    "Banana (1kg)",
    "Oranges (1kg)",
    "Tomato (1kg)",
    "Potato (1kg)",
    "Onion (1kg)",
    "Lettuce (1 head)",
    "Water (1.5 liter bottle)",
    "Bottle of Wine (Mid-Range)",
    "Domestic Beer (0.5 liter bottle)",
    "Imported Beer (0.33 liter bottle)",
    "Cigarettes 20 Pack (Marlboro)",
]

Transportation = [
    "One-way Ticket (Local Transport)",
    "Monthly Pass (Regular Price)",
    "Taxi Start (Normal Tariff)",
    "Taxi 1km (Normal Tariff)",
    "Taxi 1hour Waiting (Normal Tariff)",
    "Gasoline (1 liter)",
    "Volkswagen Golf 1.4 90 KW Trendline (Or Equivalent New Car)",
    "Toyota Corolla Sedan 1.6l 97kW Comfort (Or Equivalent New Car)",
]

Utilities = [
    "Basic (Electricity, Heating, Cooling, Water, Garbage) for 85m2 Apartment",
    "Mobile Phone Monthly Plan with Calls and 10GB+ Data",
    "Internet (60 Mbps or More, Unlimited Data, Cable/ADSL)",
]

Sports_And_Leisure = [
    "Fitness Club, Monthly Fee for 1 Adult",
    "Tennis Court Rent (1 Hour on Weekend)",
    "Cinema, International Release, 1 Seat",
]

Childcare = [
    "Preschool (or Kindergarten), Full Day, Private, Monthly for 1 Child",
    "International Primary School, Yearly for 1 Child",
]

Clothing_And_Shoes = [
    "1 Pair of Jeans (Levis 501 Or Similar)",
    "1 Summer Dress in a Chain Store (Zara, H&M, ...)",
    "1 Pair of Nike Running Shoes (Mid-Range)",
    "1 Pair of Men Leather Business Shoes",
]

Rent_Per_Month = [
    "Apartment (1 bedroom) in City Centre",
    "Apartment (1 bedroom) Outside of Centre",
    "Apartment (3 bedrooms) in City Centre",
    "Apartment (3 bedrooms) Outside of Centre",
]

Buy_Apartment_Price = [
    "Price per Square Meter to Buy Apartment in City Centre",
    "Price per Square Meter to Buy Apartment Outside of Centre",
]

Salaries_And_Financing = [
    "Average Monthly Net Salary (After Tax)",
    "Mortgage Interest Rate in Percentages (%), Yearly, for 20 Years Fixed-Rate",
]

CATEGORY_MAP = OrderedDict([
    ('Markets', Markets),
    ('Restaurants', Restaurants),
    ('Transportation', Transportation),
    ('Utilities', Utilities),
    ('Sports And Leisure', Sports_And_Leisure),
    ('Childcare', Childcare),
    ('Clothing And Shoes', Clothing_And_Shoes),
    ('Rent Per Month', Rent_Per_Month),
    ('Buy Apartment Price', Buy_Apartment_Price),
    ('Salaries And Financing', Salaries_And_Financing),
])


# -----------------------
# Helpers
# -----------------------
def normalize_text(s: str) -> str:
    """Normalize label text: replace NBSP, collapse whitespace, lower-case, strip punctuation at ends."""
    if not s:
        return ''
    s = s.replace('\xa0', ' ')
    s = s.replace('\u200b', '')
    s = re.sub(r'\s+', ' ', s).strip()
    return s.lower()


def build_lookup_map(category_map):
    """
    Build a dict: normalized_label -> (category_name, canonical_label)
    Also store shorter normalized tokens for substring matching fallback.
    """
    lookup = {}
    token_index = defaultdict(list)  # token -> list of keys for approximate matching
    for cat, items in category_map.items():
        for orig in items:
            norm = normalize_text(orig)
            lookup[norm] = (cat, orig)
            # index by significant words (tokens) for fallback matching
            tokens = [t for t in re.findall(r'\w+', norm) if len(t) > 2]
            for t in tokens:
                token_index[t].append(norm)
    return lookup, token_index


def extract_price(price_text: str):
    """
    Extract first currency + numeric group from text.
    Returns a cleaned string (e.g., '₹1234' or '1234.56') or None if not found.
    """
    if not price_text:
        return None
    price_text = price_text.replace('\xa0', ' ').strip()
    # find first occurrence of optional currency symbol and number
    m = re.search(r'([₹$€£])?\s*([\d,]+(?:\.\d+)?)', price_text)
    if not m:
        return None
    currency = m.group(1) or ''
    number = m.group(2).replace(',', '')
    return f"{currency}{number}"


# build lookup once
LOOKUP_MAP, TOKEN_INDEX = build_lookup_map(CATEGORY_MAP)


# -----------------------
# Flask routes
# -----------------------
@app.route('/', methods=['GET', 'POST'])
def index():
    city = "Imphal"
    country = "India"
    if request.method == 'POST':
        city = request.form.get('city', city).strip() or city
        country = request.form.get('country', country).strip() or country

    categories = OrderedDict([(name, OrderedDict()) for name in CATEGORY_MAP.keys()])
    unmatched = []  # list of (label, raw_price) we couldn't match to any category

    city_url = city.replace(" ", "-")
    # custom special-casing (keep original logic if you need)
    if city.lower() == "imphal":
        url = f'https://www.numbeo.com/cost-of-living/in/{city_url}-{country}'
    elif city.lower() == "lucknow":
        url = f'https://www.numbeo.com/cost-of-living/in/{city_url}-Lakhnau'
    else:
        url = f'https://www.numbeo.com/cost-of-living/in/{city_url}'

    logger.info("Fetching URL: %s", url)
    try:
        response = requests.get(url, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
                                timeout=10)
    except requests.RequestException as e:
        logger.exception("Request failed for %s", url)
        return render_template('index.html', data=None, error=f"Failed to fetch data: {e}", city=city, country=country)

    logger.info("Response status code: %s", response.status_code)
    if response.status_code != 200:
        return render_template('index.html', data=None,
                               error=f"Failed to fetch {url} (status {response.status_code})",
                               city=city, country=country)

    soup = BeautifulSoup(response.text, 'html.parser')

    # Try to find the main data table(s). Numbeo tends to use a table with class 'data_wide_table'.
    tables = soup.find_all('table', class_='data_wide_table')
    if not tables:
        # If no tables found, provide debugging snippet in logs
        snippet = response.text[:2000]
        logger.warning("No data_wide_table found. HTML snippet:\n%s", snippet)
        return render_template('index.html', data=None,
                               error="City not found or no data available (page structure may have changed).",
                               city=city, country=country)

    # iterate all rows across all such tables
    for table in tables:
        for row in table.find_all('tr'):
            cols = row.find_all('td')
            if len(cols) < 2:
                continue

            raw_label = cols[0].get_text(separator=' ', strip=True)
            raw_price = cols[1].get_text(separator=' ', strip=True)

            label_norm = normalize_text(raw_label)
            price_clean = extract_price(raw_price)

            if not price_clean:
                logger.debug("Skipping label with no numeric price: '%s' => '%s'", raw_label, raw_price)
                continue

            # 1) exact normalized match
            matched = False
            if label_norm in LOOKUP_MAP:
                cat_name, canonical = LOOKUP_MAP[label_norm]
                categories[cat_name][canonical] = price_clean
                matched = True
                logger.debug("Exact match: '%s' -> %s : %s", raw_label, cat_name, price_clean)
                continue

            # 2) try token-based approximate matching (look up tokens in token index)
            tokens = [t for t in re.findall(r'\w+', label_norm) if len(t) > 2]
            candidate_norms = set()
            for t in tokens:
                for cand in TOKEN_INDEX.get(t, []):
                    candidate_norms.add(cand)

            # check candidate normalized strings for substring overlaps
            for cand_norm in candidate_norms:
                if cand_norm in label_norm or label_norm in cand_norm:
                    cat_name, canonical = LOOKUP_MAP[cand_norm]
                    categories[cat_name][canonical] = price_clean
                    matched = True
                    logger.debug("Token/substring match: '%s' -> %s (matched against '%s') : %s",
                                 raw_label, cat_name, canonical, price_clean)
                    break
            if matched:
                continue

            # 3) last-chance substring check against original items
            for cat_name, items in CATEGORY_MAP.items():
                for it in items:
                    it_norm = normalize_text(it)
                    if it_norm in label_norm or label_norm in it_norm:
                        categories[cat_name][it] = price_clean
                        matched = True
                        logger.debug("Fallback substring match: '%s' -> %s (item: '%s') : %s",
                                     raw_label, cat_name, it, price_clean)
                        break
                if matched:
                    break

            if not matched:
                unmatched.append((raw_label, raw_price))
                logger.debug("Unmatched: '%s' | raw_price: '%s'", raw_label, raw_price)

    # Log a few unmatched labels for debugging
    if unmatched:
        logger.info("Found %d unmatched labels. Examples: %s", len(unmatched), unmatched[:8])

    return render_template('index.html', data=categories, city=city, country=country, unmatched=unmatched)


if __name__ == '__main__':
    app.run(debug=True)
