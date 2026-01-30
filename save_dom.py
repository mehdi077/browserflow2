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



def save_page_dom_to_file(driver, filename="page_dom.txt"):
    """
    Extracts the full DOM (HTML source) of the current page and saves it to a text file.
    This includes all HTML elements as they appear in the browser's inspect window.
    """
    try:
        # Get the entire page source (DOM)
        page_source = driver.page_source
        
        # Save to text file
        with open(filename, 'w', encoding='utf-8') as file:
            file.truncate(0)
            file.write(page_source)
        
        print(f"DOM saved successfully to {filename} (overwritten)")
        print(f"Total characters: {len(page_source)}")
        
    except Exception as e:
        print(f"Error extracting DOM: {str(e)}")
        raise Exception(f"Failed to save DOM: {str(e)}")


def save_frais_results_to_file(results, filename="Frais de livraison.txt"):
    """
    Saves the frais results to a text file with proper formatting.
    """
    try:
        with open(filename, 'w', encoding='utf-8') as file:
            file.write("Frais de livraison par Wilaya\n")
            file.write("=" * 40 + "\n\n")
            
            for result in results:
                file.write(f"Wilaya: {result['wilaya']}\n")
                file.write(f"Frais de livraison: {result['frais']}\n")
                file.write("-" * 30 + "\n")
        
        print(f"Results saved successfully to {filename}")
        
    except Exception as e:
        print(f"Error saving results to file: {str(e)}")
        raise Exception(f"Failed to save results: {str(e)}")


def save_frais_to_file(wilaya_name, frais_value, filename="Frais de livraison.txt"):
    """
    Saves a single wilaya and its frais value to the text file.
    """
    try:
        # Check if file exists to determine if we need to add a header
        file_exists = os.path.exists(filename)
        
        with open(filename, 'a', encoding='utf-8') as file:
            # Add header if file is new
            if not file_exists:
                file.write("Frais de livraison par Wilaya\n")
                file.write("=" * 40 + "\n\n")
            
            # Write the current wilaya data
            file.write(f"Wilaya: {wilaya_name}\n")
            file.write(f"Frais de livraison: {frais_value}\n")
            file.write("-" * 30 + "\n")
            file.flush()  # Ensure data is written immediately
        
        print(f"Saved: {wilaya_name} - {frais_value}")
        
    except Exception as e:
        print(f"Error saving to file: {str(e)}")
        raise Exception(f"Failed to save to file: {str(e)}")


def extract_frais_livraison(driver):
    """
    Selects dropdown options in a loop until reaching "Batna", 
    saving each wilaya and its frais value to a text file.
    """
    try:
        # Wait for the Wilaya dropdown to be present
        wilaya_dropdown = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "wilaya"))
        )
        
        # Also wait for frais input field
        frais_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "frais"))
        )
        
        # Scroll to element and ensure it's visible
        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", wilaya_dropdown)
        sleep(0.5)
        
        # Wait for options to be available and get all option elements
        wilaya_dropdown.click()
        sleep(1)
        
        options = WebDriverWait(driver, 5).until(
            EC.presence_of_all_elements_located((By.TAG_NAME, "option"))
        )
        
        print(f"Found {len(options)} options in dropdown")
        
        # Loop through all options, starting from index 1 (skip "Séléctionner")
        for i in range(1, len(options)):
            # Open dropdown again for each iteration
            wilaya_dropdown.click()
            sleep(1)
            
            # Get the current option
            current_option = options[i]
            wilaya_name = current_option.text
            wilaya_value = current_option.get_attribute("value")
            
            print(f"Selecting option {i}: '{wilaya_name}' with value: {wilaya_value}")
            
            # Click on the option directly
            current_option.click()
            sleep(2)  # Wait for the page to update the frais
            
            # Extract the frais value after selection
            frais_value = frais_input.get_attribute("value")
            
            print(f"Successfully selected: {wilaya_name}, Frais: {frais_value}")
            
            # Save to file immediately
            save_frais_to_file(wilaya_name, frais_value)
            
            # Check if we've reached "Batna"
            if wilaya_name == "In Salah":
                print("Reached Batna! Stopping the loop.")
                break
            
            sleep(1)  # Wait before next selection
        
        print("Finished processing dropdown options")
        
    except Exception as e:
        print(f"Error selecting dropdown option: {str(e)}")
        raise Exception(f"Failed to select dropdown option: {str(e)}")


def main(driver, payload=None):
    """
    Main function to perform keyboard actions on the Wilaya dropdown.
    """
    # extract_frais_livraison(driver)
    filename = "page_dom.txt"
    if isinstance(payload, dict) and payload.get("filename"):
        filename = payload.get("filename")
    save_page_dom_to_file(driver, filename=filename)