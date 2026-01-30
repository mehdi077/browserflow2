import undetected_chromedriver as uc
import os
import psutil
import importlib
import pathlib

import proxy



def kill_relevant_processes():
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            process_info = proc.info
            if process_info['name'] in ['chrome', 'chromedriver']:
                os.kill(process_info['pid'], 9)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
kill_relevant_processes()


def _discover_chrome_in_repo(chrome_dir: str):
    p = pathlib.Path(chrome_dir)
    if not p.exists() or not p.is_dir():
        return None

    # Prefer "Chrome for Testing" shipped in this repo.
    for candidate in p.rglob("Google Chrome for Testing"):
        try:
            if not candidate.is_file():
                continue
            parts = [part.lower() for part in candidate.parts]
            if "contents" not in parts or "macos" not in parts:
                continue
            if os.access(str(candidate), os.X_OK):
                return str(candidate)
        except OSError:
            continue
    return None


def _normalize_user_chrome_path(user_path: str):
    p = os.path.expanduser(user_path.strip().strip('"').strip("'"))
    p = os.path.abspath(p)

    # Allow passing the .app bundle path on macOS.
    if p.endswith(".app") and os.path.isdir(p):
        maybe = os.path.join(p, "Contents", "MacOS")
        if os.path.isdir(maybe):
            # Common executable names.
            for name in (
                "Google Chrome for Testing",
                "Google Chrome",
                "Chromium",
            ):
                exe = os.path.join(maybe, name)
                if os.path.exists(exe):
                    p = exe
                    break

    return p


def _resolve_chrome_executable(base_dir: str) -> str:
    chrome_dir = os.path.join(base_dir, "chrome")
    saved_path_file = os.path.join(base_dir, ".chrome_executable_path")

    repo_chrome = _discover_chrome_in_repo(chrome_dir)
    if repo_chrome:
        return repo_chrome

    if os.path.exists(saved_path_file):
        try:
            with open(saved_path_file, "r", encoding="utf-8") as f:
                saved = f.read().strip()
            saved = _normalize_user_chrome_path(saved)
            if saved and os.path.exists(saved) and os.access(saved, os.X_OK):
                return saved
        except OSError:
            pass

    while True:
        user_path = input(
            "Chrome not found in ./chrome. Please enter the full path to the Chrome executable (or .app), then press Enter:\n> "
        )
        chrome_path = _normalize_user_chrome_path(user_path)

        if not chrome_path:
            print("Path cannot be empty.")
            continue
        if not os.path.exists(chrome_path):
            print(f"Path does not exist: {chrome_path}")
            continue
        if not os.access(chrome_path, os.X_OK):
            print(f"Path is not executable: {chrome_path}")
            continue

        try:
            with open(saved_path_file, "w", encoding="utf-8") as f:
                f.write(chrome_path)
        except OSError as e:
            print(f"Warning: could not save Chrome path ({saved_path_file}): {e}")
        return chrome_path


# ---------------------------------------------
def start_browser():
    options = uc.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    
    # Set Chrome binary location (must be a string; Selenium will error if it is None)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    chrome_path = _resolve_chrome_executable(base_dir)
    options.binary_location = str(chrome_path)

    # Define the path for the profile
    user_data_dir = os.path.join(base_dir, "chrome_profiles")

    # -------------------------- profiles here ---------------------------------
    profile_dir = "profile_name_1" 
    # profile_dir = "profile_name_2" 
    # profile_dir = "profile_name_3" 
    # profile_dir = "profile_name_4" 
    # profile_dir = "profile_name_5" 
    # profile_dir = "profile_name_6" 
    # --------------------------------------------------------------------------

    options.add_argument(f"--user-data-dir={user_data_dir}")
    options.add_argument(f'--profile-directory={profile_dir}')

    # Create the user data directory if it doesn't exist
    if not os.path.exists(user_data_dir):
        os.makedirs(user_data_dir)
    driver = uc.Chrome(options=options, version_main=142)
    return driver


def control_browser(driver):
    while True:
        print("\nChoose an option:")
        print("1. Enter a website URL")
        print("2. Open proxy menu")

        choice = input("Enter your choice (1 or 2): ").strip().lower()

        if choice in ("exit", "q", "quit"):
            break
        elif choice == '1':
            custom_url = input("Enter the website URL: ").strip()
            if not custom_url:
                print("URL cannot be empty.")
                continue
            if not custom_url.startswith('http'):
                custom_url = 'https://' + custom_url
            driver.get(custom_url)
            print(driver.title)
        elif choice == '2':
            try:
                importlib.reload(proxy)
                proxy.main(driver)
            except Exception as e:
                print(f"Error running proxy menu: {e}")
                continue
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    driver = start_browser()
    try:
        control_browser(driver)
    finally:
        driver.quit()

