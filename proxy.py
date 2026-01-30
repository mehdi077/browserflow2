import extract
import save_dom
import extract_fb_marketplace
import knowledge

import importlib


def main(driver):
    while True:
        print("\n--- Menu ---")
        print("1. Save DOM")
        print("2. Extract")
        print("3. FB Marketplace")
        print("4. Knowledge")
        print("5. Exit")
        
        choice = input("Enter selection (1, 2, 3, or 4): ").strip()
        
        if choice == '1':
            importlib.reload(save_dom)
            save_dom.main(driver)
        elif choice == '2':
            importlib.reload(extract)
            extract.main(driver)
        elif choice == '3':
            importlib.reload(extract_fb_marketplace)
            extract_fb_marketplace.main(driver)
        elif choice == '4':
            importlib.reload(knowledge)
            knowledge.main(driver)
        elif choice == '5':
            print("Catch you later!")
            break
        else:
            print("Not a valid choice, try again.")