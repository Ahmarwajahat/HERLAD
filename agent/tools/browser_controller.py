import subprocess
import time
import pyautogui
import os

def open_firefox(url: str = "") -> str:
    """Open Firefox browser, optionally go to URL"""
    try:
        if url:
            subprocess.Popen(['firefox', url])
        else:
            subprocess.Popen(['firefox'])
        time.sleep(3)
        return f"Firefox opened{' at ' + url if url else ''}"
    except Exception as e:
        return f"Error: {str(e)}"

def firefox_goto(url: str) -> str:
    """Navigate Firefox to a URL using keyboard"""
    try:
        time.sleep(1)
        pyautogui.hotkey('ctrl', 'l')  # focus address bar
        time.sleep(0.5)
        pyautogui.hotkey('ctrl', 'a')
        pyautogui.typewrite(url, interval=0.05)
        pyautogui.press('enter')
        time.sleep(3)
        return f"Navigated to {url}"
    except Exception as e:
        return f"Error: {str(e)}"

def firefox_search(query: str) -> str:
    """Search something in Firefox"""
    search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
    return open_firefox(search_url)

def take_screenshot(filename: str = "screenshot.png") -> str:
    """Take screenshot to see current screen"""
    try:
        filepath = f"/mnt/AhmarData/openwork_project/logs/{filename}"
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        screenshot = pyautogui.screenshot()
        screenshot.save(filepath)
        return f"Screenshot saved: {filepath}"
    except Exception as e:
        return f"Error: {str(e)}"

def click_on_screen(x: int, y: int) -> str:
    """Click at screen coordinates"""
    try:
        pyautogui.click(x, y)
        time.sleep(0.5)
        return f"Clicked at ({x}, {y})"
    except Exception as e:
        return f"Error: {str(e)}"

def type_text(text: str) -> str:
    """Type text on keyboard"""
    try:
        pyautogui.typewrite(text, interval=0.05)
        return f"Typed: {text}"
    except Exception as e:
        return f"Error: {str(e)}"

def press_key(key: str) -> str:
    """Press a keyboard key"""
    try:
        pyautogui.press(key)
        return f"Pressed: {key}"
    except Exception as e:
        return f"Error: {str(e)}"

def upload_file_dialog(filepath: str) -> str:
    """Handle file upload dialog — type filepath and press Enter"""
    try:
        time.sleep(1)
        pyautogui.typewrite(filepath, interval=0.05)
        time.sleep(0.5)
        pyautogui.press('enter')
        time.sleep(2)
        return f"File upload submitted: {filepath}"
    except Exception as e:
        return f"Error: {str(e)}"
