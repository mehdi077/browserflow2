from selenium.webdriver.common.by import By
from time import sleep
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains


def prompt_youtube_url():
    """
    Prompts the user to paste a YouTube video URL.
    Returns the non-empty URL string.
    """
    while True:
        youtube_url = input("Paste YouTube video URL: ").strip()
        if youtube_url:
            return youtube_url
        print("URL cannot be empty. Please try again.")


def navigate_to_notegpt(driver):
    """
    Ensures the browser is on the NoteGPT YouTube transcript generator page.
    Navigates to the page if not already there.
    """
    target_url = "https://notegpt.io/youtube-transcript-generator"
    if not str(driver.current_url).startswith(target_url):
        driver.get(target_url)
        sleep(2)
    WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.TAG_NAME, "body"))
    )


def enter_youtube_url(driver, youtube_url):
    """
    Finds the YouTube URL input field, scrolls to it, clears it, and enters the provided URL.
    Assumes the NoteGPT page is loaded.
    """
    input_field = WebDriverWait(driver, 20).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='text']"))
    )
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", input_field)
    sleep(0.5)
    input_field.clear()
    input_field.send_keys(youtube_url)
    print("YouTube URL entered.")


def click_generate_button(driver):
    """
    Clicks the generate button to start transcript creation.
    Assumes the URL field has been populated.
    """
    buttons = WebDriverWait(driver, 20).until(
        lambda d: d.find_elements(By.XPATH, "//button[contains(., 'Generate') or contains(., 'generate')]")
    )
    if len(buttons) < 1:
        raise Exception("Generate button not found on the page.")
    generate_button = buttons[0]
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", generate_button)
    sleep(0.5)
    generate_button.click()
    print("Clicked generate button.")
    sleep(2)


def wait_for_transcript(driver):
    """
    Waits until the generated transcript content appears on the page.
    """
    WebDriverWait(driver, 20).until(
        lambda d: len(d.find_elements(By.XPATH, "//div[starts-with(@id,'youTube_transcript_item_')]") ) > 0
    )
    print("Transcript appears to be ready.")


def collect_transcript_text(driver):
    """
    Collects all transcript segments (timestamp + text) into a single string.
    """
    items = WebDriverWait(driver, 20).until(
        lambda d: d.find_elements(By.XPATH, "//div[starts-with(@id,'youTube_transcript_item_')]")
    )
    if len(items) == 0:
        raise Exception("No transcript items found.")

    transcript_lines = []
    for item in items:
        try:
            timestamp_el = item.find_element(By.CSS_SELECTOR, ".text-primary")
            text_el = item.find_element(By.CSS_SELECTOR, "div.relative div.overflow-hidden")
            ts = timestamp_el.text.strip()
            txt = text_el.text.strip()
            transcript_lines.append(f"{ts} {txt}")
        except Exception:
            continue

    if len(transcript_lines) == 0:
        raise Exception("Transcript text could not be collected.")

    full_transcript = "\n".join(transcript_lines)
    print(f"Collected transcript with {len(transcript_lines)} segments.")
    return full_transcript


def copy_transcript_to_clipboard(driver, transcript_text):
    """
    Copies the transcript text to clipboard via JS; falls back silently if denied.
    """
    try:
        driver.execute_script(
            """
            const text = arguments[0];
            if (navigator.clipboard && navigator.clipboard.writeText) {
                return navigator.clipboard.writeText(text).then(() => true).catch(() => false);
            }
            const ta = document.createElement('textarea');
            ta.value = text;
            document.body.appendChild(ta);
            ta.select();
            try { document.execCommand('copy'); } catch(e) {}
            document.body.removeChild(ta);
            return true;
            """,
            transcript_text,
        )
        print("Transcript copied to clipboard (best effort).")
    except Exception as e:
        print(f"Clipboard copy may have failed: {str(e)}")


def go_to_gemini(driver):
    """
    Navigates to Gemini app after copying transcript.
    """
    target_url = "https://gemini.google.com/app"
    driver.get(target_url)
    print("Navigated to Gemini.")
    sleep(2)


def paste_into_gemini_chat(driver, transcript_text):
    """
    Pastes the transcript into Gemini chat input and appends three newlines.
    """
    field = WebDriverWait(driver, 30).until(
        lambda d: next(
            (el for el in d.find_elements(By.CSS_SELECTOR, "textarea, div[contenteditable='true'][role='textbox']") if el.is_displayed()),
            None,
        )
    )
    if field is None:
        raise Exception("Gemini input field not found.")

    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", field)
    sleep(0.5)

    try:
        ActionChains(driver).move_to_element(field).click().key_down(Keys.CONTROL).send_keys("a").key_up(Keys.CONTROL).send_keys(Keys.BACKSPACE).perform()
    except Exception:
        try:
            field.clear()
        except Exception:
            pass

    try:
        field.send_keys(transcript_text + "\n\n\n")
    except Exception:
        driver.execute_script("arguments[0].textContent = arguments[1];", field, transcript_text + "\n\n\n")
    print("Transcript pasted into Gemini chat.")


def main(driver):
    """
    Main loop for knowledge workflow: prompt URL, open NoteGPT, paste it, and click generate.
    """
    while True:
        youtube_url = prompt_youtube_url()
        try:
            navigate_to_notegpt(driver)
            enter_youtube_url(driver, youtube_url)
            click_generate_button(driver)
            wait_for_transcript(driver)
            # transcript_text = collect_transcript_text(driver)
            # copy_transcript_to_clipboard(driver, transcript_text)
            # go_to_gemini(driver)
            # paste_into_gemini_chat(driver, transcript_text)
        except Exception as e:
            print(f"Error: {str(e)}")
            retry = input("Press Enter to retry or 'q' to quit: ").strip().lower()
            if retry == 'q':
                break
            continue
        break
