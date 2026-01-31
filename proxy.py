import save_dom
import importlib


def main(driver):
    while True:
        print("\n--- Menu ---")
        print("1. Save DOM")
        print("2. Exit")
        
        choice = input("Enter selection (1 or 2): ").strip()
        
        if choice == '1':
            importlib.reload(save_dom)
            save_dom.main(driver)
        elif choice == '2':
            print("Catch you later!")
            break
        else:
            print("Not a valid choice, try again.")