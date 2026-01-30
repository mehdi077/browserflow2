import undetected_chromedriver as uc
import os
import argparse
import json
import psutil
import importlib
import pathlib
import queue
import threading
import traceback
import inspect
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import sys

def kill_relevant_processes():
    for proc in psutil.process_iter(['pid', 'name']):
        try:
            process_info = proc.info
            if process_info['name'] in ['chrome', 'chromedriver']:
                os.kill(process_info['pid'], 9)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass


def _json_response(handler: BaseHTTPRequestHandler, status: int, payload: dict):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(status)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _read_json_body(handler: BaseHTTPRequestHandler):
    length = int(handler.headers.get("Content-Length") or 0)
    raw = handler.rfile.read(length) if length > 0 else b""
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except Exception:
        raise Exception("Invalid JSON body")


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


def _resolve_chrome_executable(base_dir: str, prefer_auto: bool = True):
    chrome_dir = os.path.join(base_dir, "chrome")
    saved_path_file = os.path.join(base_dir, ".chrome_executable_path")

    # Priority 1: Let undetected_chromedriver find system Chrome automatically.
    # Returning None signals "use auto-detection".
    if prefer_auto:
        return None

    repo_chrome = _discover_chrome_in_repo(chrome_dir)
    if repo_chrome:
        print(f"[Chrome] Using repo Chrome: {repo_chrome}")
        return repo_chrome

    if os.path.exists(saved_path_file):
        try:
            with open(saved_path_file, "r", encoding="utf-8") as f:
                saved = f.read().strip()
            saved = _normalize_user_chrome_path(saved)
            if saved and os.path.exists(saved) and os.access(saved, os.X_OK):
                print(f"[Chrome] Using saved Chrome path: {saved}")
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


def _call_module_main(module_name: str, driver, payload: dict):
    mod = importlib.import_module(module_name)
    mod = importlib.reload(mod)

    if not hasattr(mod, "main"):
        raise Exception(f"Module '{module_name}' does not have a main(driver) function")

    main_fn = getattr(mod, "main")
    sig = inspect.signature(main_fn)
    if len(sig.parameters) >= 2:
        return main_fn(driver, payload)
    return main_fn(driver)


def run_bot_api(driver, host: str, port: int, base_dir: str):
    command_q: queue.Queue = queue.Queue()
    stop_event = threading.Event()

    def submit_raw(fn, timeout_s: float = 300.0):
        resp_q: queue.Queue = queue.Queue(maxsize=1)
        command_q.put((fn, resp_q))
        try:
            return resp_q.get(timeout=timeout_s)
        except queue.Empty:
            raise Exception("Timed out waiting for Selenium command to finish")

    def submit(fn, timeout_s: float = 300.0):
        resp = submit_raw(fn, timeout_s=timeout_s)
        if not resp.get("ok"):
            raise Exception(resp.get("error") or "Selenium command failed")
        return resp.get("value")

    def make_handler():
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                # Keep default HTTP logs minimal; important info is returned in JSON.
                return

            def do_GET(self):
                if self.path == "/health":
                    try:
                        state = submit(
                            lambda d: {
                                "current_url": getattr(d, "current_url", ""),
                                "title": getattr(d, "title", ""),
                            },
                            timeout_s=10.0,
                        )
                        _json_response(
                            self,
                            200,
                            {
                                "ok": True,
                                "mode": "bot",
                                "host": host,
                                "port": port,
                                "base_dir": base_dir,
                                "page_dom_path": os.path.join(base_dir, "page_dom.txt"),
                                "state": state,
                            },
                        )
                    except Exception as e:
                        _json_response(self, 500, {"ok": False, "error": str(e)})
                    return

                if self.path == "/state":
                    try:
                        state = submit(
                            lambda d: {
                                "current_url": getattr(d, "current_url", ""),
                                "title": getattr(d, "title", ""),
                            },
                            timeout_s=10.0,
                        )
                        _json_response(self, 200, {"ok": True, "state": state})
                    except Exception as e:
                        _json_response(self, 500, {"ok": False, "error": str(e)})
                    return

                _json_response(self, 404, {"ok": False, "error": "Not found"})

            def do_POST(self):
                try:
                    payload = _read_json_body(self)
                except Exception as e:
                    _json_response(self, 400, {"ok": False, "error": str(e)})
                    return

                if self.path == "/navigate":
                    url = (payload.get("url") or "").strip()
                    wait_seconds = payload.get("wait_seconds")
                    if not url:
                        _json_response(self, 400, {"ok": False, "error": "Missing 'url'"})
                        return
                    if not url.startswith("http"):
                        url = "https://" + url

                    try:
                        result = submit(
                            lambda d: (
                                d.get(url),
                                time.sleep(float(wait_seconds))
                                if wait_seconds is not None
                                else None,
                                {"current_url": d.current_url, "title": d.title},
                            )[-1],
                            timeout_s=300.0,
                        )
                        _json_response(self, 200, {"ok": True, "result": result})
                    except Exception as e:
                        _json_response(self, 500, {"ok": False, "error": str(e)})
                    return

                if self.path == "/save_dom":
                    filename = (payload.get("filename") or "page_dom.txt").strip() or "page_dom.txt"
                    out_path = os.path.join(base_dir, filename)
                    try:
                        resp = submit_raw(
                            lambda d: _call_module_main(
                                "save_dom",
                                d,
                                {"filename": out_path},
                            ),
                            timeout_s=120.0,
                        )
                        if not resp.get("ok"):
                            _json_response(
                                self,
                                500,
                                {
                                    "ok": False,
                                    "error": resp.get("error") or "save_dom failed",
                                    "traceback": resp.get("traceback"),
                                },
                            )
                            return
                        _json_response(
                            self,
                            200,
                            {
                                "ok": True,
                                "result": resp.get("value"),
                                "page_dom_path": out_path,
                            },
                        )
                    except Exception as e:
                        _json_response(self, 500, {"ok": False, "error": str(e)})
                    return

                if self.path == "/run_module":
                    module_name = (payload.get("module") or "").strip()
                    if not module_name:
                        _json_response(self, 400, {"ok": False, "error": "Missing 'module'"})
                        return
                    try:
                        resp = submit_raw(
                            lambda d: _call_module_main(module_name, d, payload),
                            timeout_s=float(payload.get("timeout_seconds") or 600.0),
                        )
                        if not resp.get("ok"):
                            _json_response(
                                self,
                                500,
                                {
                                    "ok": False,
                                    "error": resp.get("error") or "run_module failed",
                                    "traceback": resp.get("traceback"),
                                },
                            )
                            return
                        _json_response(self, 200, {"ok": True, "result": resp.get("value")})
                    except Exception as e:
                        _json_response(self, 500, {"ok": False, "error": str(e)})
                    return

                if self.path == "/shutdown":
                    try:
                        stop_event.set()
                        # Wake the Selenium loop if it's waiting.
                        command_q.put((lambda d: None, queue.Queue(maxsize=1)))
                        _json_response(self, 200, {"ok": True})
                    finally:
                        # ThreadingHTTPServer handles requests in worker threads;
                        # calling shutdown() here is safe.
                        threading.Thread(target=httpd.shutdown, daemon=True).start()
                    return

                _json_response(self, 404, {"ok": False, "error": "Not found"})

        return Handler

    Handler = make_handler()
    httpd = ThreadingHTTPServer((host, port), Handler)

    server_thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    server_thread.start()

    print(f"[bot] API listening on http://{host}:{port}")
    print("[bot] GET  /health")
    print("[bot] POST /navigate   {url, wait_seconds?}")
    print("[bot] POST /save_dom   {filename?}")
    print("[bot] POST /run_module {module, ...payload}")
    print("[bot] POST /shutdown")

    try:
        while not stop_event.is_set():
            fn, resp_q = command_q.get()
            try:
                value = fn(driver)
                resp_q.put({"ok": True, "value": value})
            except Exception as e:
                resp_q.put(
                    {
                        "ok": False,
                        "error": str(e),
                        "traceback": traceback.format_exc(),
                    }
                )
    finally:
        try:
            httpd.shutdown()
        except Exception:
            pass
        try:
            httpd.server_close()
        except Exception:
            pass



# ---------------------------------------------
def start_browser():
    options = uc.ChromeOptions()
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")

    base_dir = os.path.dirname(os.path.abspath(__file__))

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

    # Priority 1: Try system Chrome auto-detection first.
    try:
        print("[Chrome] Trying system Chrome auto-detection...")
        driver = uc.Chrome(options=options)
        print("[Chrome] Successfully using system Chrome")
        return driver
    except Exception as e:
        print(f"[Chrome] Auto-detection failed: {e}")
        print("[Chrome] Falling back to manual detection...")

    # Priority 2/3/4: repo chrome -> saved path -> prompt
    chrome_path = _resolve_chrome_executable(base_dir, prefer_auto=False)
    options.binary_location = str(chrome_path)
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
                import proxy
                importlib.reload(proxy)
                proxy.main(driver)
            except Exception as e:
                print(f"Error running proxy menu: {e}")
                continue
        else:
            print("Invalid choice.")


if __name__ == "__main__":
    argv = sys.argv[1:]
    bot_mode = False
    if "-bot" in argv:
        bot_mode = True
        argv = [a for a in argv if a != "-bot"]

    parser = argparse.ArgumentParser(add_help=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args(argv)

    kill_relevant_processes()

    driver = start_browser()
    try:
        if bot_mode:
            base_dir = os.path.dirname(os.path.abspath(__file__))
            run_bot_api(driver, host=args.host, port=args.port, base_dir=base_dir)
        else:
            control_browser(driver)
    finally:
        driver.quit()

