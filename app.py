from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from bs4 import BeautifulSoup
import re
from collections import OrderedDict

app = Flask(__name__)
CORS(app)

# Category definitions
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

@app.route('/info', methods=['GET', 'POST'])
def index():
    city = "Imphal"
    country = "India"

    if request.method == 'POST':
        city = request.form.get('city', 'Imphal')
        country = request.form.get('country', 'India')

    categories = OrderedDict([
        ('Markets', OrderedDict()),
        ('Restaurants', OrderedDict()),
        ('Transportation', OrderedDict()),
        ('Utilities', OrderedDict()),
        ('Sports And Leisure', OrderedDict()),
        ('Childcare', OrderedDict()),
        ('Clothing And Shoes', OrderedDict()),
        ('Rent Per Month', OrderedDict()),
        ('Buy Apartment Price', OrderedDict()),
        ('Salaries And Financing', OrderedDict()),
    ])

    city_url = city.replace(" ", "-")
    if city.lower() == "imphal" or city.lower() == 'haldwani' or city.lower() == 'ahmednagar':
        url = f'https://www.numbeo.com/cost-of-living/in/{city_url}-{country}'
    elif city.lower() == "lucknow":
        url = f'https://www.numbeo.com/cost-of-living/in/{city_url}-Lakhnau'
    elif city.lower() == "allahabad":
        url = 'https://www.numbeo.com/cost-of-living/in/Allahabad-India'

    else:
        url = f'https://www.numbeo.com/cost-of-living/in/{city_url}'

    response = requests.get(url)
    soup = BeautifulSoup(response.text, 'html.parser')

    price_re = re.compile(r'^[\d\.,\s€$£₹]+$')
    table = soup.find('table', class_='data_wide_table')

    if not table:
        
        return jsonify({
        "data" : None,
        "error" : "City not found or no data available.",
        "city" : city,
        "country" : country
        })
    for row in table.find_all('tr'):
        cols = row.find_all('td')
        if len(cols) >= 2:
            label = cols[0].get_text(strip=True)
            raw_price = cols[1].get_text(strip=True)
            if price_re.match(raw_price):
                price = raw_price.replace('\xa0', ' ').strip()
                if price.endswith('₹'):
                    price = '₹' + price[:-1].strip()
                for cat, items in [
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
                ]:
                    if label in items:
                        categories[cat][label] = price

    
    return jsonify({
        "data" : categories,
        "error" : None,
        "city" : city,
        "country" : country
    })

if __name__ == '__main__':
    app.run(debug=True)
