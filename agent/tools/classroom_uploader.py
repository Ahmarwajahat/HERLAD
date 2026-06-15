# agent/tools/classroom_uploader.py
import os
import time
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from agent.tools.notifier import whatsapp_notify_me


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def select_google_account(driver, account_name: str = "default") -> bool:
    """Auto-click the requested Google account if on the chooser page"""
    try:
        curr_url = driver.current_url.lower()
        if "choose" in curr_url or "chooser" in curr_url or len(driver.find_elements(By.XPATH, "//div[@role='link'][contains(@data-email, '@')]")) > 0:
            accounts = driver.find_elements(By.XPATH, "//div[@role='link'][contains(@data-email, '@')]")
            if not accounts:
                accounts = driver.find_elements(By.XPATH, "//*[contains(@data-email, '@')]")
            
            if accounts:
                target_account = None
                if "@" in account_name:
                    for acc in accounts:
                        email = acc.get_attribute("data-email") or ""
                        if account_name.lower() in email.lower():
                            target_account = acc
                            break
                
                # Default fallback: click the first account in the chooser list
                if not target_account:
                    target_account = accounts[0]
                
                email_selected = target_account.get_attribute("data-email")
                print(f"[Classroom]: Auto-selecting Google account: {email_selected}")
                target_account.click()
                time.sleep(3)
                return True
    except Exception as e:
        print(f"[Classroom]: Error auto-selecting account: {e}")
    return False

def upload_to_classroom(filepath: str, class_name: str, assignment_name: str, account_name: str = "default") -> str:
    """Automate Google Classroom file upload using Selenium Firefox"""
    if not os.path.exists(filepath):
        # Check if file is in Desktop
        alt_path = os.path.join("/mnt/AhmarData", os.path.basename(filepath))
        if os.path.exists(alt_path):
            filepath = alt_path
        else:
            return f"Error: File '{filepath}' not found."
            
    abs_filepath = os.path.abspath(filepath)
    
    # Setup profile folder for the requested account to keep cookies/session saved
    safe_account = "".join([c for c in account_name if c.isalnum() or c in ('-', '_')]).strip()
    if not safe_account:
        safe_account = "default"
        
    profile_dir = os.path.join(PROJECT_ROOT, "agent", "profiles", safe_account)
    os.makedirs(profile_dir, exist_ok=True)
    
    driver = None
    try:
        options = Options()
        options.add_argument("-profile")
        options.add_argument(profile_dir)
        options.add_argument("--start-maximized")
        
        driver = webdriver.Firefox(options=options)
        print(f"[Classroom]: Navigating to Google Classroom using profile '{safe_account}'...")
        driver.get("https://classroom.google.com")
        time.sleep(5)
        
        # Check if we are redirected to Google Classroom landing/marketing page
        if "edu.google.com" in driver.current_url or len(driver.find_elements(By.XPATH, "//a[contains(text(), 'Sign in to Classroom') or contains(text(), 'Sign in') or contains(@href, 'classroom.google.com')]")) > 0:
            print("[Classroom]: Landing page detected. Clicking sign in button...")
            clicked = False
            for xpath in [
                "//a[contains(text(), 'Sign in to Classroom')]",
                "//a[contains(text(), 'Sign in')]",
                "//a[contains(@href, 'classroom.google.com')]"
            ]:
                try:
                    btns = driver.find_elements(By.XPATH, xpath)
                    for btn in btns:
                        if btn.is_displayed():
                            btn.click()
                            time.sleep(5)
                            clicked = True
                            break
                    if clicked:
                        break
                except:
                    pass

        # Try to auto-select account if chooser page is present
        select_google_account(driver, account_name)
        
        # Check if we need to log in
        current_url = driver.current_url
        if "accounts.google.com" in current_url or "signin" in current_url or "edu.google.com" in current_url or len(driver.find_elements(By.ID, "identifierId")) > 0:
            print("[Classroom]: Login required! Notifying owner on WhatsApp...")
            whatsapp_notify_me(f"🔑 HERALD: I need to upload your lab to Google Classroom, but I am not logged in for the account '{safe_account}'. I have opened the login page on your browser. Please log in, and I will resume once you do.")
            
            # Poll until user logs in (up to 5 minutes)
            logged_in = False
            for attempt in range(150): # 150 * 2 = 300s (5 minutes)
                time.sleep(2)
                
                # If still stuck on marketing page, try clicking Sign in again
                if "edu.google.com" in driver.current_url:
                    try:
                        btn = driver.find_element(By.XPATH, "//a[contains(text(), 'Sign in to Classroom')]")
                        btn.click()
                        time.sleep(3)
                    except:
                        pass
                        
                select_google_account(driver, account_name)
                try:
                    curr_url = driver.current_url
                    # If we are on the main classroom home page, we are logged in
                    if "classroom.google.com" in curr_url and "accounts.google.com" not in curr_url and "edu.google.com" not in curr_url and ("/h" in curr_url or "/u/" in curr_url):
                        print("[Classroom]: Login detected! Proceeding...")
                        logged_in = True
                        break
                except:
                    pass
            if not logged_in:
                return "Error: Login timeout exceeded. Please run the command again and log in promptly."
                
        # On Classroom Home
        print("[Classroom]: Looking for class...")
        try:
            # Wait up to 15 seconds for any class links to appear
            WebDriverWait(driver, 15).until(
                lambda d: len(d.find_elements(By.XPATH, "//a[contains(@href, '/c/')]")) > 0
            )
        except Exception as e:
            print(f"[Classroom]: Wait for class links timed out/failed: {e}")
        time.sleep(2)
        
        # Try to find the class link
        # Find all link tags containing class URLs and match by name
        class_link = None
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            try:
                text = link.text.lower()
                href = link.get_attribute("href") or ""
                if "/c/" in href and class_name.lower() in text:
                    class_link = link
                    break
            except:
                continue
                
        if not class_link:
            # Fallback: exact text or title matching
            try:
                class_link = driver.find_element(By.XPATH, f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{class_name.lower()}')]")
            except:
                pass
                
        if not class_link:
            # Gather list of classes to show user
            available = []
            for link in links:
                try:
                    href = link.get_attribute("href") or ""
                    if "/c/" in href and link.text.strip():
                        available.append(link.text.strip())
                except:
                    pass
            available_str = ", ".join(list(set(available)))
            return f"Error: Could not find class '{class_name}'. Available classes: {available_str}"
            
        print(f"[Classroom]: Clicking class '{class_name}'...")
        class_link.click()
        
        # Navigate to Classwork
        print("[Classroom]: Navigating to Classwork...")
        try:
            classwork_tab = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/w/') or contains(text(), 'Classwork') or contains(text(), 'classwork') or contains(translate(text(), 'CLASSWORK', 'classwork'), 'classwork')]"))
            )
            classwork_tab.click()
            time.sleep(4)
        except Exception as e:
            print(f"[Classroom]: Classwork tab navigation issue: {e}. Trying direct search...")
            
        # Look for assignment link
        assignment_link = None
        try:
            # Wait up to 15 seconds for assignment links to load
            WebDriverWait(driver, 15).until(
                lambda d: len(d.find_elements(By.XPATH, "//a[contains(@href, '/a/')]")) > 0
            )
        except Exception as e:
            print(f"[Classroom]: Wait for assignment links timed out/failed: {e}")
        time.sleep(2)
        
        links = driver.find_elements(By.TAG_NAME, "a")
        for link in links:
            try:
                text = link.text.lower()
                href = link.get_attribute("href") or ""
                if "/a/" in href and assignment_name.lower() in text:
                    assignment_link = link
                    break
            except:
                continue
                
        if not assignment_link:
            # Try to find element with text and click it
            try:
                assignment_link = driver.find_element(By.XPATH, f"//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), '{assignment_name.lower()}')]")
            except:
                pass
                
        if not assignment_link:
            return f"Error: Could not find assignment '{assignment_name}' inside class '{class_name}'."
            
        print(f"[Classroom]: Clicking assignment '{assignment_name}'...")
        assignment_link.click()
        time.sleep(3)
        
        # Click "View assignment" if it expanded or go to it directly
        curr_url = driver.current_url
        if "/details" not in curr_url and "/a/" in curr_url:
            # Try to find a link containing details
            try:
                details_link = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, "//a[contains(@href, '/details')]"))
                )
                details_link.click()
                time.sleep(4)
            except:
                pass
                
        print("[Classroom]: On assignment page. Looking for 'Add or create' button...")
        # Search for Add or Create button
        add_btn = None
        try:
            # Wait up to 15 seconds for Add/Create or Turn in button to be visible/clickable
            WebDriverWait(driver, 15).until(
                lambda d: len(d.find_elements(By.XPATH, "//*[contains(text(), 'Add') or contains(text(), 'Create') or contains(text(), 'Add or create') or contains(text(), 'shaamil')]")) > 0
            )
        except Exception as e:
            print(f"[Classroom]: Wait for Add or Create button timed out: {e}")
            
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            try:
                text = btn.text.lower()
                if "add" in text or "create" in text or "shaamil" in text:
                    add_btn = btn
                    break
            except:
                continue
                
        if not add_btn:
            # Try xpath
            try:
                add_btn = driver.find_element(By.XPATH, "//*[contains(text(), 'Add') or contains(text(), 'Create') or contains(text(), 'Add or create')]")
            except:
                return "Error: Could not find 'Add or create' button on the assignment page. Maybe it is already submitted?"
                
        add_btn.click()
        time.sleep(2)
        
        # Click 'File' option in dropdown
        print("[Classroom]: Selecting 'File' upload...")
        file_option = None
        # Look for element with text "File" or paperclip icon
        menu_items = driver.find_elements(By.XPATH, "//*[contains(text(), 'File') or contains(text(), 'file')]")
        for item in menu_items:
            try:
                if item.text.strip().lower() == "file":
                    file_option = item
                    break
            except:
                continue
                
        if not file_option:
            # Just find any clickable item with class name or list item
            try:
                file_option = driver.find_element(By.XPATH, "//div[role='menuitem']//*[contains(text(), 'File')]")
            except:
                pass
                
        if file_option:
            file_option.click()
        else:
            # Fallback: try pressing keyboard down keys or clicking coordinate
            import pyautogui
            pyautogui.press('down')
            time.sleep(0.2)
            pyautogui.press('down')
            time.sleep(0.2)
            pyautogui.press('enter')
            
        time.sleep(5)
        
        # The file upload dialog runs in a Google Drive Picker iframe.
        # Let's switch to the iframe.
        print("[Classroom]: Switching to upload picker iframe...")
        iframes = driver.find_elements(By.TAG_NAME, "iframe")
        picker_iframe = None
        for iframe in iframes:
            try:
                title = iframe.get_attribute("title") or ""
                src = iframe.get_attribute("src") or ""
                if "picker" in title.lower() or "picker" in src.lower() or "upload" in title.lower():
                    picker_iframe = iframe
                    break
            except:
                continue
                
        if picker_iframe:
            driver.switch_to.frame(picker_iframe)
            time.sleep(2)
            
        # In the iframe, find <input type="file">
        print(f"[Classroom]: Uploading file: {abs_filepath}")
        file_input = WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//input[@type='file']"))
        )
        file_input.send_keys(abs_filepath)
        time.sleep(8) # Wait for file to upload
        
        # Switch back to default content
        driver.switch_to.default_content()
        time.sleep(3)
        
        # Click "Turn in" / "Hand in" button
        print("[Classroom]: Submitting assignment...")
        turn_in_btn = None
        buttons = driver.find_elements(By.TAG_NAME, "button")
        for btn in buttons:
            try:
                text = btn.text.lower()
                if "turn in" in text or "hand in" in text or "submit" in text or "jama" in text:
                    turn_in_btn = btn
                    break
            except:
                continue
                
        if turn_in_btn:
            turn_in_btn.click()
            time.sleep(2)
            
            # Click confirm "Turn in" in the confirmation modal
            confirm_btn = None
            # Find the confirmation button on modal (usually another turn in button)
            confirm_buttons = driver.find_elements(By.XPATH, "//div[role='dialog']//button")
            for btn in confirm_buttons:
                try:
                    text = btn.text.lower()
                    if "turn in" in text or "hand in" in text or "submit" in text or "confirm" in text:
                        confirm_btn = btn
                        break
                except:
                    continue
            if not confirm_btn:
                # Fallback: look for any button with text "Turn in" that is active
                for btn in driver.find_elements(By.TAG_NAME, "button"):
                    if btn.text.lower() == "turn in" or btn.text.lower() == "hand in":
                        confirm_btn = btn
                        
            if confirm_btn:
                confirm_btn.click()
                time.sleep(5)
                print("[Classroom]: Submitted successfully!")
            else:
                print("[Classroom]: Could not find confirmation button. File uploaded but confirmation might need manual intervention.")
        else:
            return "Error: File uploaded but could not locate 'Turn in' button."
            
        # Capture screenshot of confirmation
        screenshot_dir = "/mnt/AhmarData/screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)
        screenshot_path = os.path.join(screenshot_dir, "classroom_submitted.png")
        driver.save_screenshot(screenshot_path)
        
        return f"Successfully uploaded '{os.path.basename(filepath)}' to class '{class_name}' for assignment '{assignment_name}' and turned it in! Screenshot saved to /mnt/AhmarData/screenshots/classroom_submitted.png."
        
    except Exception as e:
        return f"Classroom automation failed: {str(e)}"
    finally:
        if driver:
            driver.quit()
