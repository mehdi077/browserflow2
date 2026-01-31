# browserflow2

`browserflow2` is a small Selenium/`undetected_chromedriver` harness that keeps a single Chrome tab/session open while you run different automation scripts from a terminal menu.

The core workflow is:
1) open any URL in a real Chrome session, 2) save the current page DOM to `page_dom.txt`, 3) write a new automation module based on that DOM, 4) add it to the proxy menu so you can run it without restarting the browser.

## Project entry points

- `run.py` — starts Chrome (with a persistent profile) and gives you a small CLI to either visit a URL or open the proxy menu.
- `proxy.py` — the “menu router” that lets you run different automation modules against the current browser tab.
- `save_dom.py` — saves the current page HTML DOM to `page_dom.txt` (overwrites the file each run).

Example automation modules you can use as references:
- `examples/extract.py`
- `examples/extract_fb_marketplace.py`
- `examples/knowledge.py`

## Requirements

### 1) Python packages

You’ll need Python 3 and the packages used by the scripts you run.

At minimum (to start the browser + menu):

```bash
python3 -m pip install undetected_chromedriver psutil selenium
```

Some example modules import extra dependencies (install as needed):

```bash
python3 -m pip install flask flask_cors requests pillow geopy
```

Notes:
- `examples/extract.py` / `save_dom.py` currently import `flask`, `flask_cors`, `requests`, `PIL` even if you only use parts of them.
- `examples/extract_fb_marketplace.py` uses `geopy`.

### 2) Chrome binary

This project expects a Chrome binary.

Preferred setup: place a **Chrome for Testing** build inside the repo under `./chrome/`.
- Example already in this repo: `chrome/mac-142.0.7444.59/.../Google Chrome for Testing`

If `./chrome/` does not contain a usable Chrome executable, `run.py` will prompt you to paste a Chrome path and will save it to:

- `.chrome_executable_path` (in the project root)

So you won’t be asked again on the next run.

## How to use

### 1) Start the browser

```bash
python3 run.py
```

`run.py` will:
- start Chrome with a persistent profile directory under `./chrome_profiles/`
- then show a menu:
  - **1**: enter a URL (navigate the current tab)
  - **2**: open the proxy menu (run your automation modules)

### 2) Navigate to a target page

Choose **1** and paste a URL (it will auto-prefix `https://` if you omit it).

### 3) Save the page DOM to `page_dom.txt`

Choose **2** to open the proxy menu, then choose:

- **Save DOM** (runs `save_dom.py`)

This overwrites `page_dom.txt` with the current page’s HTML (`driver.page_source`).

### 4) Generate a new automation module

Open `page_dom.txt` and use it to understand the page structure (selectors, button text, forms, etc.).

Then, when writing new automations, follow the rules/style in:

- `docs_info/selenium_action_generation_guide_LLM_rules.mdc`

Create a new Python file (example: `my_new_task.py`) that follows the project pattern:

- implement a `main(driver)` entry point
- use `WebDriverWait` + `expected_conditions` (`EC`) + `sleep(...)`
- scroll elements into view before clicking/typing
- keep helpers modular (small functions)

You can use these as starting references:
- `examples/extract.py` (Kimland product extraction)
- `examples/extract_fb_marketplace.py` (Facebook Marketplace listing extraction)
- `examples/knowledge.py` (NoteGPT transcript flow)

Important: some examples contain machine-specific file paths (e.g. `examples/extract.py` writes to `/Users/mehdi/...`). Adjust outputs/paths for your environment.

### 5) Add your module to the proxy menu

Edit `proxy.py` and follow the same pattern as the existing menu entries:

- import your module at the top
- add a new numbered menu item
- call `importlib.reload(your_module)` then `your_module.main(driver)`

After that, you can:
- keep the browser open
- update your module
- re-run it from the proxy menu (reload happens each time)

## Files and folders

- `chrome/` — Chrome for Testing (preferred) lives here.
- `chrome_profiles/` — persistent Chrome user data dir. Configure the profile name in `run.py` (`profile_dir = ...`).
- `page_dom.txt` — overwritten snapshot of the current page DOM.
- `docs_info/selenium_action_generation_guide_LLM_rules.mdc` — rules/style guide for writing new automations.

## Notes / troubleshooting

- If you see an error like `Binary Location Must be a String`, it means Chrome wasn’t found. Put Chrome under `./chrome/` or let `run.py` prompt you for a path.
- `run.py` contains a `kill_relevant_processes()` helper that kills processes named `chrome` and `chromedriver` before starting; be aware this can close other Chrome instances.
