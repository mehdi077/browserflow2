# AI Agent Guide: `run.py -bot` (HTTP control mode)

This document describes **exactly** how an automated agent should operate this repository using **bot mode** (`python3 run.py -bot`).

Bot mode exists so an agent can:
- start **one** persistent Chrome/Selenium session,
- modify task modules on disk,
- execute/re-execute those updated modules **without restarting** Chrome,
- avoid interactive terminal menus (`input()`), by using a **local HTTP API**.

---

## 0) Working assumptions

### Repository root

The repository root is the directory that contains:

- `run.py`
- `proxy.py`
- `save_dom.py`
- `page_dom.txt`
- `chrome/`
- `examples/`

All relative paths in this guide assume the current working directory is the repo root.

### Single-driver rule

Selenium operations are **not thread-safe**.

In bot mode, the HTTP server **serializes** all Selenium commands and executes them against a **single** `driver` instance.
Your agent must assume:
- Only one command runs at a time.
- Each HTTP request blocks until the Selenium command finishes (or times out).

### “Bot-safe module” rule

In bot mode, do **not** call modules that use `input()` prompts.

If a module’s `main()` prompts the user, it will **block the daemon** and your agent will not be able to proceed (until the user provides stdin, which bot mode intentionally avoids).

Write new modules for bot mode to be **non-interactive** and parameterized via the JSON payload (details below).

---

## 1) Start the daemon

### Command

Start bot mode with the `-bot` flag:

```bash
python3 run.py -bot
```

Optional network configuration:

```bash
python3 run.py -bot --host 127.0.0.1 --port 8765
```

### Binding

The HTTP API binds to `--host` (default `127.0.0.1`) and `--port` (default `8765`).

**Security note:** this API is intentionally **unauthenticated** and must only be bound to `127.0.0.1` unless you add authentication.

### Process behavior

When the daemon starts:
1. It may terminate existing `chrome` / `chromedriver` processes (`kill_relevant_processes()`).
2. It starts Chrome via `undetected_chromedriver` with a persistent profile directory under `./chrome_profiles/`.
3. It starts an HTTP server and prints the endpoints.

The daemon keeps running until you call `/shutdown` or terminate the process.

---

## 2) Chrome binary resolution

On startup, `run.py` resolves the Chrome executable in this order:

1. **System Chrome auto-detection** (preferred): lets `undetected_chromedriver` locate a system-installed Chrome
   - If auto-detection fails due to a Chrome/ChromeDriver major-version mismatch, `run.py` retries using the major parsed from the error.
2. **Repo Chrome**: searches under `./chrome/` for a "Chrome for Testing" executable
3. **Saved path**: reads `./.chrome_executable_path` if present
4. **Prompt**: if none exist, it prompts on stdin and saves the chosen path

In bot mode, **stdin prompting is not desirable**.

Therefore, an agent should ensure one of these is true **before** starting the daemon:
- `./chrome/` contains a valid Chrome executable, OR
- `./.chrome_executable_path` exists and points to an executable

---

## 3) Health check (required)

After starting the daemon, the agent must confirm the API is alive before sending commands.

### Endpoint

`GET /health`

### Example

```bash
curl -s http://127.0.0.1:8765/health
```

### Response schema

```json
{
  "ok": true,
  "mode": "bot",
  "host": "127.0.0.1",
  "port": 8765,
  "base_dir": "/abs/path/to/repo",
  "page_dom_path": "/abs/path/to/repo/page_dom.txt",
  "state": {
    "current_url": "...",
    "title": "..."
  }
}
```

If `ok` is not `true`, treat the daemon as unusable.

---

## 4) Navigate the active tab

### Endpoint

`POST /navigate`

### Request schema

```json
{
  "url": "https://example.com",
  "wait_seconds": 2
}
```

- `url` (required): if it does not start with `http`, the daemon will prefix `https://`.
- `wait_seconds` (optional): numeric; the daemon will `sleep()` after navigation.

### Example

```bash
curl -s \
  -X POST http://127.0.0.1:8765/navigate \
  -H 'Content-Type: application/json' \
  -d '{"url":"https://kimland.dz/app/client/","wait_seconds":2}'
```

### Response schema

```json
{
  "ok": true,
  "result": {
    "current_url": "...",
    "title": "..."
  }
}
```

---

## 5) Save the DOM snapshot to `page_dom.txt`

### Purpose

This repository’s development loop commonly depends on:
1) visiting a page in the live Chrome session, then
2) saving its DOM into `page_dom.txt`, then
3) using that DOM to author a Selenium automation module.

### Endpoint

`POST /save_dom`

### Request schema

```json
{
  "filename": "page_dom.txt"
}
```

- `filename` is optional; defaults to `page_dom.txt`.
- The path is treated as **relative to the repo root** unless you pass an absolute path.

### Example

```bash
curl -s \
  -X POST http://127.0.0.1:8765/save_dom \
  -H 'Content-Type: application/json' \
  -d '{"filename":"page_dom.txt"}'
```

### Response schema

```json
{
  "ok": true,
  "result": null,
  "page_dom_path": "/abs/path/to/repo/page_dom.txt"
}
```

Notes:
- `save_dom.py` overwrites the file each run.
- The daemon does not return the DOM contents; the agent should read `page_dom.txt` from disk.

---

## 6) Execute a task module (hot-reload)

### Endpoint

`POST /run_module`

### What it does

1. Imports the Python module by name (`importlib.import_module(module)`)
2. Reloads it (`importlib.reload(module)`)
3. Calls `module.main(driver)` or `module.main(driver, payload)` depending on the function signature

This enables the agent to edit a module on disk and re-run it without restarting `run.py`.

### Request schema

```json
{
  "module": "my_task",
  "timeout_seconds": 600,

  "any_other_key": "is passed to main(driver, payload)"
}
```

- `module` (required): Python import name (file `my_task.py` ⇒ module name `my_task`).
- `timeout_seconds` (optional): request timeout for this execution.
- Any other keys are passed through as `payload`.

### Response schema

Success:

```json
{ "ok": true, "result": null }
```

Failure:

```json
{
  "ok": false,
  "error": "...",
  "traceback": "..."
}
```

### Example: run a repo module

```bash
curl -s \
  -X POST http://127.0.0.1:8765/run_module \
  -H 'Content-Type: application/json' \
  -d '{"module":"examples.extract_fb_marketplace","timeout_seconds":900}'
```

### Example: run your own module with parameters

Create `my_task.py` with a bot-safe `main(driver, payload)`:

```python
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


def main(driver, payload=None):
    """Bot-safe entry point: no input()."""
    payload = payload or {}
    css = payload.get("css")
    if not css:
        raise Exception("Missing payload.css")
    el = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CSS_SELECTOR, css)))
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", el)
    return {"text": el.text}
```

Then run it:

```bash
curl -s \
  -X POST http://127.0.0.1:8765/run_module \
  -H 'Content-Type: application/json' \
  -d '{"module":"my_task","css":"h1"}'
```

---

## 7) Recommended agent workflow (end-to-end)

This is the intended loop for an agent that needs to create new automations.

1. **Start daemon**
   - Ensure Chrome exists under `./chrome/` (preferred).
   - Start `python3 run.py -bot`.
   - Wait for `/health` to return `ok: true`.

2. **Navigate to the target page**
   - `POST /navigate` with the desired URL.

3. **Save DOM**
   - `POST /save_dom` to overwrite `page_dom.txt`.

4. **Read DOM from disk**
   - Read `page_dom.txt` and analyze selectors/text to plan automation.

5. **Write a new bot-safe module**
   - Follow: `docs_info/selenium_action_generation_guide_LLM_rules.mdc`
   - Implement `main(driver, payload=None)` (preferred in bot mode).
   - Avoid `input()`.

6. **Execute + iterate (hot reload)**
   - `POST /run_module` for your module.
   - If it fails, edit the module and rerun `/run_module`.

7. **Shutdown**
   - `POST /shutdown` when done.

---

## 8) Shutdown (required)

### Endpoint

`POST /shutdown`

### Example

```bash
curl -s -X POST http://127.0.0.1:8765/shutdown -H 'Content-Type: application/json' -d '{}'
```

Behavior:
- The HTTP server stops.
- The daemon loop exits.
- `driver.quit()` is called.

---

## 9) Endpoint summary

| Method | Path | Purpose |
|---|---|---|
| GET | `/health` | readiness check + base paths |
| GET | `/state` | current URL + title |
| POST | `/navigate` | navigate active tab |
| POST | `/save_dom` | overwrite `page_dom.txt` (or custom filename) |
| POST | `/run_module` | reload + run `module.main(...)` |
| POST | `/shutdown` | stop the daemon |
