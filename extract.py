from selenium.webdriver.common.by import By
from time import sleep
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
import requests
import io
from PIL import Image
import base64
from selenium.webdriver.support.ui import WebDriverWait as wait
import json
import re
from flask import Flask, request, jsonify
import threading
from flask_cors import CORS
import os


def extract_title(driver):
    """
    Extracts the product title from the page.
    Assumes the page is loaded and the title element is present.
    """
    title_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "h1.page-title"))
    )
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", title_element)
    sleep(0.5)
    title = title_element.text.strip()
    print(f"Extracted title: {title}")
    return title


def extract_reference(driver):
    """
    Extracts the Kimland product reference from the page.
    Assumes the page is loaded and the reference element is present.
    """
    ref_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.product-code"))
    )
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", ref_element)
    sleep(0.5)
    ref_text = ref_element.text.strip()
    ref = ref_text.replace("Référence :", "").replace("Référence:", "").strip()
    print(f"Extracted reference: {ref}")
    return ref


def extract_brand(driver):
    """
    Extracts the brand name from the brand logo image.
    Assumes the page is loaded and the brand image is present.
    """
    brand_element = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "//img[@title and contains(@src, 'upload/logo/')]"))
    )
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", brand_element)
    sleep(0.5)
    brand = brand_element.get_attribute("title").strip()
    print(f"Extracted brand: {brand}")
    return brand


def extract_sizes(driver):
    """
    Extracts all available sizes with their inventory quantities.
    Assumes the page is loaded and the size select element is present.
    """
    size_select = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "select[name='pointure']"))
    )
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", size_select)
    sleep(0.5)
    
    options = size_select.find_elements(By.TAG_NAME, "option")
    sizes = []
    
    for option in options:
        option_text = option.text.strip()
        parts = option_text.split(" - ")
        if len(parts) >= 2:
            size = parts[0].strip()
            inventory_text = parts[1].strip()
            inventory = re.sub(r'[^\d]', '', inventory_text)
            if inventory:
                sizes.append({
                    "size": size,
                    "inventory_quantity": int(inventory)
                })
    
    print(f"Extracted {len(sizes)} sizes")
    return sizes


def extract_price(driver):
    """
    Extracts the selling price (Prix de vente) numbers only, without currency.
    Assumes the page is loaded and the price element is present.
    """
    try:
        price_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//strong[@style='color:green']"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", price_element)
        sleep(0.5)
        
        price_text = price_element.text.strip()
        price = re.sub(r'[^\d]', '', price_text)
        print(f"Extracted selling price (Prix de vente): {price}")
        return price
    except Exception as e:
        print(f"Error extracting selling price, trying regular price: {str(e)}")
        price_element = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "span.price"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", price_element)
        sleep(0.5)
        
        price_text = price_element.text.strip()
        price = re.sub(r'[^\d]', '', price_text)
        print(f"Extracted regular price: {price}")
        return price


def extract_images(driver):
    """
    Extracts all product image URLs from the thumbnail carousel.
    Assumes the page is loaded and the carousel is present.
    """
    thumbnails = WebDriverWait(driver, 10).until(
        lambda d: d.find_elements(By.CSS_SELECTOR, "#thumbnails a[data-image]")
    )
    
    images = []
    for thumbnail in thumbnails:
        image_url = thumbnail.get_attribute("data-image")
        if image_url:
            full_url = driver.execute_script("return arguments[0];", image_url)
            if full_url.startswith("upload/"):
                full_url = f"https://kimland.dz/{full_url}"
            images.append(full_url)
    
    print(f"Extracted {len(images)} images")
    return images


def extract_category_subcategory(driver):
    """
    Extracts category and subcategory from the breadcrumb navigation.
    Assumes the page is loaded and breadcrumb is present.
    """
    try:
        breadcrumb = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ol.breadcrumb"))
        )
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", breadcrumb)
        sleep(0.5)
        
        breadcrumb_items = breadcrumb.find_elements(By.TAG_NAME, "li")
        
        category = ""
        subcategory = ""
        
        if len(breadcrumb_items) >= 3:
            category = breadcrumb_items[-2].text.strip()
        
        if len(breadcrumb_items) >= 4:
            subcategory = breadcrumb_items[-1].text.strip()
        
        print(f"Category: {category}, Subcategory: {subcategory}")
        return category, subcategory
    except Exception as e:
        print(f"Error extracting breadcrumb: {str(e)}")
        return "", ""


def prompt_user_option():
    """
    Prompts the user to select one of three extraction options.
    Returns: 1, 2, or 3 based on user selection.
    """
    print("\n" + "="*50)
    print("PRODUCT EXTRACTION OPTIONS")
    print("="*50)
    print("1. Normal extraction (current page - single product)")
    print("2. Extract product list URLs first, then process them")
    print("3. Process existing URL list (skip URL collection)")
    print("="*50)
    
    while True:
        choice = input("Select option (1/2/3): ").strip()
        if choice in ['1', '2', '3']:
            return int(choice)
        else:
            print("Invalid option. Please enter 1, 2, or 3.")


def extract_product_urls_from_list(driver):
    """
    Extracts all product URLs from a product list page.
    Skips products with 'Exclusive' in their name.
    Assumes the page is loaded and product items are present.
    Returns: List of product URLs.
    """
    print("Extracting product URLs from list page...")
    sleep(2)
    
    product_items = WebDriverWait(driver, 10).until(
        lambda d: d.find_elements(By.CSS_SELECTOR, "div.product-item")
    )
    
    urls = []
    skipped_count = 0
    
    for item in product_items:
        try:
            link = item.find_element(By.CSS_SELECTOR, "a.product-item-img")
            href = link.get_attribute("href")
            
            if not href or "product/" not in href:
                continue
            
            product_name_element = item.find_element(By.CSS_SELECTOR, "strong.product-item-name a")
            product_name = product_name_element.text.strip()
            
            if "exclusive" in product_name.lower():
                print(f"Skipping exclusive product: {product_name}")
                skipped_count += 1
                continue
            
            urls.append(href)
        except Exception as e:
            print(f"Error processing product item: {str(e)}")
            continue
    
    print(f"Extracted {len(urls)} product URLs from the list page (skipped {skipped_count} exclusive products)")
    return urls


def load_url_tracking_json(filename):
    """
    Loads the URL tracking JSON file.
    Creates a new structure if file doesn't exist.
    Returns: Dictionary with 'urls' list.
    """
    if not os.path.exists(filename):
        print(f"{filename} not found, creating new structure")
        return {"urls": []}
    
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if "urls" not in data or not isinstance(data["urls"], list):
                data = {"urls": []}
            print(f"Loaded {len(data['urls'])} URL(s) from {filename}")
            return data
    except Exception as e:
        print(f"Error loading {filename}: {str(e)}")
        return {"urls": []}


def save_url_tracking_json(filename, data):
    """
    Saves the URL tracking data to JSON file.
    """
    try:
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"URL tracking data saved to {filename}")
    except Exception as e:
        print(f"Error saving to {filename}: {str(e)}")


def add_urls_to_tracking(filename, urls):
    """
    Adds URLs to the tracking JSON file with visited=False status.
    Skips URLs that already exist in the file.
    """
    data = load_url_tracking_json(filename)
    
    existing_urls = [item["url"] for item in data["urls"]]
    added_count = 0
    
    for url in urls:
        if url not in existing_urls:
            data["urls"].append({
                "url": url,
                "visited": False
            })
            added_count += 1
    
    save_url_tracking_json(filename, data)
    print(f"Added {added_count} new URL(s) to tracking file (skipped {len(urls) - added_count} duplicates)")


def mark_url_as_visited(filename, url):
    """
    Marks a specific URL as visited in the tracking JSON.
    """
    data = load_url_tracking_json(filename)
    
    for item in data["urls"]:
        if item["url"] == url:
            item["visited"] = True
            break
    
    save_url_tracking_json(filename, data)


def process_url_list(driver, url_tracking_file, data_output_file):
    """
    Processes each unvisited URL from the tracking file.
    Extracts product data and marks URLs as visited.
    """
    data = load_url_tracking_json(url_tracking_file)
    
    unvisited_urls = [item for item in data["urls"] if not item["visited"]]
    
    if len(unvisited_urls) == 0:
        print("No unvisited URLs found in the tracking file.")
        return
    
    print(f"\nFound {len(unvisited_urls)} unvisited URL(s) to process")
    
    for index, item in enumerate(unvisited_urls):
        url = item["url"]
        print("\n" + "="*70)
        print(f"Processing URL {index + 1}/{len(unvisited_urls)}")
        print(f"URL: {url}")
        print("="*70 + "\n")
        
        while True:
            try:
                driver.get(url)
                sleep(3)
                
                product_data = extract_single_product(driver, data_output_file)
                
                if product_data is not None:
                    mark_url_as_visited(url_tracking_file, url)
                    print(f"Successfully processed and marked as visited: {url}")
                else:
                    print(f"Product extraction returned None (likely unavailable or error)")
                    mark_url_as_visited(url_tracking_file, url)
                
                break
            except Exception as e:
                print(f"Error processing URL: {str(e)}")
                retry = input("Press Enter to retry this URL or 's' to skip: ").strip().lower()
                if retry == 's':
                    mark_url_as_visited(url_tracking_file, url)
                    print(f"Skipped URL: {url}")
                    break
        
        sleep(2)
    
    print("\n" + "="*70)
    print("FINISHED PROCESSING ALL UNVISITED URLs")
    print("="*70)


def extract_single_product(driver, data_output_file):
    """
    Extracts product data from the current page and saves to JSON.
    This is the original extraction logic from main().
    Returns: Product data dictionary or None if extraction fails.
    """
    print("Starting product data extraction...")
    sleep(2)
    vip_message = "Ce produit est dédié au Pack DIAMOND VIP"
    if vip_message in driver.page_source:
        print(f">>> Skipping: Diamond VIP restricted product detected.")
        return None
    
    product_data = {}
    
    try:
        product_data["ref_kimland_side"] = extract_reference(driver)
    except Exception as e:
        print(f"Error extracting reference: {str(e)}")
        product_data["ref_kimland_side"] = ""
    
    product_data["ref_shopify_side"] = ""
    
    try:
        product_data["title"] = extract_title(driver)
    except Exception as e:
        print(f"Error extracting title: {str(e)}")
        product_data["title"] = ""
    
    try:
        product_data["brand"] = extract_brand(driver)
    except Exception as e:
        print(f"Error extracting brand: {str(e)}")
        product_data["brand"] = ""
    
    try:
        product_data["sizes"] = extract_sizes(driver)
    except Exception as e:
        print(f"Error extracting sizes: {str(e)}")
        product_data["sizes"] = []
    
    try:
        product_data["price"] = extract_price(driver)
    except Exception as e:
        print(f"Error extracting price: {str(e)}")
        product_data["price"] = ""
    
    try:
        product_data["images"] = extract_images(driver)
    except Exception as e:
        print(f"Error extracting images: {str(e)}")
        product_data["images"] = []
    
    try:
        category, subcategory = extract_category_subcategory(driver)
        product_data["category"] = category
        product_data["subcategory"] = ""
        product_data["description"] = ""
        product_data["tags"] = subcategory
    except Exception as e:
        print(f"Error extracting category/subcategory: {str(e)}")
        product_data["category"] = ""
        product_data["subcategory"] = ""
        product_data["description"] = ""
        product_data["tags"] = ""
    
    print("\n" + "="*50)
    print("EXTRACTED PRODUCT DATA:")
    print("="*50)
    print(json.dumps(product_data, ensure_ascii=False, indent=2))
    print("="*50 + "\n")
    
    if not product_data.get("title") and not product_data.get("ref_kimland_side") and not product_data.get("brand"):
        print("ERROR: Product data is empty or incomplete. Not saving to file.")
        print("Please ensure the browser session is active and the page is fully loaded.")
        return None
    
    if not product_data.get("sizes") or len(product_data.get("sizes", [])) == 0:
        print("ERROR: This product is not available (no sizes found).")
        print("Skipping save to file.")
        return None
    
    data_structure = {"products": []}
    
    try:
        with open(data_output_file, 'r', encoding='utf-8') as f:
            data_structure = json.load(f)
            if "products" not in data_structure or not isinstance(data_structure["products"], list):
                data_structure = {"products": []}
        print(f"Loaded {len(data_structure['products'])} existing product(s) from {data_output_file}")
    except FileNotFoundError:
        print(f"{data_output_file} not found, creating new file")
    except Exception as e:
        print(f"Error loading {data_output_file}: {str(e)}")
        data_structure = {"products": []}
    
    ref_to_check = product_data.get("ref_kimland_side", "")
    for existing_product in data_structure["products"]:
        if existing_product.get("ref_kimland_side") == ref_to_check and ref_to_check:
            print(f"WARNING: Product with reference '{ref_to_check}' already exists in the file.")
            print("Skipping save to avoid duplicate.")
            return product_data
    
    data_structure["products"].append(product_data)
    
    with open(data_output_file, 'w', encoding='utf-8') as f:
        json.dump(data_structure, f, ensure_ascii=False, indent=2)
    
    print(f"Data saved to {data_output_file} (Total products: {len(data_structure['products'])})")
    
    return product_data


def main(driver):
    """
    Main function with three extraction options:
    1. Normal extraction (single product from current page)
    2. Extract product list URLs, then process them
    3. Process existing URL list
    """
    data_output_file = "/Users/mehdi/projects/kimland/assets/api/data.json"
    url_tracking_file = "/Users/mehdi/projects/kimland/assets/browser_flow/product_urls.json"
    
    option = prompt_user_option()
    
    if option == 1:
        print("\n--- OPTION 1: Normal Extraction (Current Page) ---\n")
        extract_single_product(driver, data_output_file)
    
    elif option == 2:
        print("\n--- OPTION 2: Extract Product List URLs ---\n")
        
        urls = extract_product_urls_from_list(driver)
        
        if len(urls) == 0:
            print("No product URLs found on this page.")
            return
        
        add_urls_to_tracking(url_tracking_file, urls)
        
        proceed = input("\nProceed with visiting and extracting each URL? (y/n): ").strip().lower()
        
        if proceed == 'y':
            process_url_list(driver, url_tracking_file, data_output_file)
        else:
            print("URL extraction completed. URLs saved to tracking file.")
            print("Run Option 3 later to process the URLs.")
    
    elif option == 3:
        print("\n--- OPTION 3: Process Existing URL List ---\n")
        
        if not os.path.exists(url_tracking_file):
            print(f"ERROR: URL tracking file not found: {url_tracking_file}")
            print("Please run Option 2 first to collect URLs.")
            return
        
        process_url_list(driver, url_tracking_file, data_output_file) 
