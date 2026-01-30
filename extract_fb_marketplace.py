from selenium.webdriver.common.by import By
from time import sleep
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import json
import re
import os
from geopy.geocoders import Nominatim
from geopy.distance import geodesic

def calculate_distance(location):
    """
    Calculate distance from location to Upper Darby, PA
    """
    try:
        geolocator = Nominatim(user_agent="marketplace_extractor")
        sleep(1)
        target = geolocator.geocode("Upper Darby, PA")
        if target:
            target_coords = (target.latitude, target.longitude)
            sleep(1)
            loc = geolocator.geocode(location)
            if loc:
                return round(geodesic((loc.latitude, loc.longitude), target_coords).miles, 2)
    except:
        pass
    return None

def extract_all_listings(driver):
    """
    Extracts all visible listings from the current page.
    """
    listings = []
    
    # Find all marketplace listing links
    links = driver.find_elements(By.XPATH, "//a[contains(@href, '/marketplace/item/')]")
    
    print(f"Found {len(links)} listing links on page")
    
    for idx, link in enumerate(links):
        try:
            # Scroll into view
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", link)
            sleep(0.3)
            
            url = link.get_attribute("href")
            if not url or "/marketplace/item/" not in url:
                continue
                
            # Get the text content
            name = link.text.strip()
            if not name:
                name = link.get_attribute("aria-label") or ""
            
            # Find the container
            container = driver.execute_script(
                "return arguments[0].closest('div[role=\"article\"]') || arguments[0].closest('div[data-testid*=\"marketplace\"]') || arguments[0].parentElement;", 
                link
            )
            
            # Extract price
            price = 0
            try:
                price_elems = container.find_elements(By.XPATH, ".//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '$') or contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'free')]")
                price_text = ""
                for p in price_elems:
                    pt = p.text.strip().upper()
                    if '$' in pt or 'FREE' in pt:
                        price_text = pt
                        break
                if 'FREE' in price_text:
                    price = 0
                else:
                    price_match = re.search(r'(\d+(?:,\d{3})*(?:\.\d{2})?)', price_text)
                    price = int(price_match.group(1).replace(',', '')) if price_match else 0
            except:
                pass
            
            # Extract location from name
            location = name.split('\n')[-1].strip()
            
            listings.append({
                "name": name,
                "price": price,
                "location": location,
                "url": url,
                "miles": None  # Will be calculated later in batch
            })
            
            print(f"[{idx+1}/{len(links)}] Extracted: {name[:40]}... | Price: {price}")
            
        except Exception as e:
            print(f"Error extracting listing {idx+1}: {str(e)}")
            continue
    
    return listings

def save_listing(data_file, listing):
    """
    Appends listing to JSON file, skips duplicates by URL.
    """
    data = {"listings": []}
    if os.path.exists(data_file):
        try:
            with open(data_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except:
            data = {"listings": []}
    if any(item["url"] == listing["url"] for item in data["listings"]):
        return
    data["listings"].append(listing)
    with open(data_file, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
def load_miles_cache(cache_file):
    if os.path.exists(cache_file):
        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_miles_cache(cache_file, cache):
    with open(cache_file, 'w', encoding='utf-8') as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)

def main(driver):
    """
    Main extraction: scrapes all visible listings at once.
    """
    data_file = "fb_marketplace.json"
    print("FB Marketplace Extractor")
    input("Navigate to listings page, press Enter to start extraction...")
    
    calc_miles_input = input("Calculate miles distances? (y/n): ").strip().lower()
    calc_miles = calc_miles_input in ['y', 'yes']
    
    print("\n=== Extracting all listings ===")
    listings = extract_all_listings(driver)
    
    if not listings:
        print("No listings found!")
        return
    
    cache_file = "miles_cache.json"
    cache = load_miles_cache(cache_file)
    
    print(f"\n=== Processing miles for {len(listings)} listings ===")
    for idx, listing in enumerate(listings):
        if listing['location']:
            loc = listing['location']
            if loc in cache:
                listing['miles'] = cache[loc]
                print(f"[{idx+1}/{len(listings)}] Cache hit: '{loc}' -> {listing['miles']} mi")
            elif calc_miles:
                print(f"[{idx+1}/{len(listings)}] Calc new: '{loc}'")
                miles = calculate_distance(loc)
                listing['miles'] = miles
                if miles is not None:
                    cache[loc] = miles
                    save_miles_cache(cache_file, cache)
            else:
                listing['miles'] = None
                print(f"[{idx+1}/{len(listings)}] Skip uncached '{loc}'")
        else:
            listing['miles'] = None
    
    print(f"\n=== Saving {len(listings)} listings ===")
    saved_count = 0
    for listing in listings:
        save_listing(data_file, listing)
        saved_count += 1
        print(f"Saved: {listing['name'][:40]}... | ${listing['price']} | {listing['location'][:25]}... | {listing.get('miles', 'N/A')} mi")
    
    print(f"\nTotal: {saved_count} listings saved to {data_file}")
