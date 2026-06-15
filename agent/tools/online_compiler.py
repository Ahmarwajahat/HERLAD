# agent/tools/online_compiler.py
import os
import time
import subprocess
import requests
import pyperclip
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

def run_code_locally_with_screenshot(code: str, language: str = "python") -> str:
    """
    Write code to a temp file, execute it locally via subprocess, capture its
    stdout/stderr output, render that output as a small text image using
    Pillow (so the screenshot contains ONLY the output - no web noise), and
    save it to logs/local_output_<lang>.png.

    Falls back to saving a plain-text output image if Pillow is unavailable.
    Returns a status string containing the output text and screenshot path.
    """
    screenshot_dir = "/mnt/AhmarData/screenshots"
    os.makedirs(screenshot_dir, exist_ok=True)

    lang_ext = {"python": "py", "py": "py", "python3": "py",
                "javascript": "js", "js": "js",
                "cpp": "cpp", "c++": "cpp", "c": "c", "java": "java"}.get(language.lower(), "py")
    lang_cmd = {"py": ["python3"], "js": ["node"], "cpp": ["bash", "-c"],
                "c": ["bash", "-c"], "java": ["bash", "-c"]}.get(lang_ext, ["python3"])

    code_file = os.path.join(PROJECT_ROOT, "tasks", f"local_exec.{lang_ext}")
    os.makedirs(os.path.dirname(code_file), exist_ok=True)
    with open(code_file, "w") as f:
        f.write(code)

    # Detect OpenMP or MPI features in the code
    is_mpi = "mpi.h" in code or "MPI_" in code
    is_openmp = "omp.h" in code or "omp_get" in code or "#pragma omp" in code

    # Build the run command
    if lang_ext == "py":
        cmd = ["python3", code_file]
    elif lang_ext == "js":
        cmd = ["node", code_file]
    elif lang_ext == "cpp":
        exe_file = os.path.join(PROJECT_ROOT, "tasks", "local_exec.out")
        if os.path.exists(exe_file):
            try: os.remove(exe_file)
            except: pass
        compiler = "mpicxx" if is_mpi else "g++"
        flags = "-fopenmp" if is_openmp else ""
        run_prefix = "mpirun -np 4 " if is_mpi else ""
        cmd = ["bash", "-c", f"{compiler} -O3 {flags} '{code_file}' -o '{exe_file}' && {run_prefix}'{exe_file}'"]
    elif lang_ext == "c":
        exe_file = os.path.join(PROJECT_ROOT, "tasks", "local_exec.out")
        if os.path.exists(exe_file):
            try: os.remove(exe_file)
            except: pass
        compiler = "mpicc" if is_mpi else "gcc"
        flags = "-fopenmp" if is_openmp else ""
        run_prefix = "mpirun -np 4 " if is_mpi else ""
        cmd = ["bash", "-c", f"{compiler} -O3 {flags} '{code_file}' -o '{exe_file}' && {run_prefix}'{exe_file}'"]
    else:
        cmd = ["bash", "-c", f"python3 '{code_file}'"]  # generic fallback

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=15)
        stdout = result.stdout.strip()
        stderr = result.stderr.strip()
        output = stdout if stdout else (stderr if stderr else "(no output)")
    except subprocess.TimeoutExpired:
        output = "Error: Code execution timed out (>15s)."
    except Exception as e:
        output = f"Error running code: {e}"

    # ── Render output as a clean image using Pillow ──────────────────────────
    screenshot_path = os.path.join(screenshot_dir, f"local_output_{lang_ext}.png")
    try:
        from PIL import Image, ImageDraw, ImageFont
        # Terminal-style dark background
        BG      = (18, 18, 18)
        FG      = (0, 255, 128)
        PADDING = 20
        FONT_SZ = 14
        try:
            font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf", FONT_SZ)
        except Exception:
            font = ImageFont.load_default()

        lines = output.split('\n')
        # measure
        dummy = Image.new('RGB', (1, 1))
        dd    = ImageDraw.Draw(dummy)
        line_h = FONT_SZ + 4
        max_w  = max((dd.textlength(l, font=font) for l in lines), default=300)
        img_w  = int(max_w) + PADDING * 2
        img_h  = line_h * len(lines) + PADDING * 2
        img_w  = max(img_w, 400)

        img  = Image.new('RGB', (img_w, img_h), color=BG)
        draw = ImageDraw.Draw(img)
        # header bar
        draw.rectangle([0, 0, img_w, 28], fill=(30, 30, 40))
        draw.text((10, 6), f"● Output  —  {language.upper()}", fill=(180, 180, 200), font=font)
        y = 36
        for l in lines:
            draw.text((PADDING, y), l, fill=FG, font=font)
            y += line_h
        img.save(screenshot_path)
    except Exception:
        # Pillow not available – use scrot to grab desktop
        try:
            subprocess.run(["scrot", screenshot_path], timeout=5)
        except Exception:
            pass

    return (
        f"Code executed locally.\n"
        f"Screenshot saved: /mnt/AhmarData/screenshots/local_output_{lang_ext}.png\n"
        f"Output:\n{output}"
    )

def run_code_via_piston(code: str, language: str) -> str:
    """Run code via free Piston API (supports 100+ languages, no key required)"""
    url = "https://emkc.org/api/v2/piston/execute"
    
    # Map common aliases
    lang_map = {
        "py": "python",
        "python": "python",
        "python3": "python",
        "js": "javascript",
        "javascript": "javascript",
        "node": "javascript",
        "cpp": "c++",
        "c++": "c++",
        "c": "c",
        "java": "java",
        "cs": "csharp",
        "csharp": "csharp",
        "go": "go",
        "rust": "rust",
        "php": "php"
    }
    
    lang = lang_map.get(language.lower(), language.lower())
    payload = {
        "language": lang,
        "version": "*",
        "files": [
            {
                "content": code
            }
        ]
    }
    
    try:
        r = requests.post(url, json=payload, timeout=10)
        if r.status_code == 200:
            res = r.json()
            run_info = res.get("run", {})
            stdout = run_info.get("stdout", "")
            stderr = run_info.get("stderr", "")
            code_exit = run_info.get("code", 0)
            
            output = ""
            if stdout:
                output += f"Stdout:\n{stdout}\n"
            if stderr:
                output += f"Stderr:\n{stderr}\n"
            if not stdout and not stderr:
                output = "Code executed successfully with no output."
            return f"Language: {lang}\nExit Code: {code_exit}\n\n{output}"
        else:
            return f"Piston API error (Status {r.status_code}): {r.text}"
    except Exception as e:
        return f"Failed to execute via Piston API: {str(e)}"

def run_code_via_browser(code: str, language: str) -> str:
    """Open Firefox, navigate to an online compiler, paste the code, run it, and take a screenshot."""
    import pyautogui
    lang_map = {
        "python": "python", "py": "python", "python3": "python",
        "c++": "cpp", "cpp": "cpp",
        "c": "c",
        "java": "java",
        "javascript": "javascript", "js": "javascript"
    }
    lang = lang_map.get(language.lower(), "python")
    url = f"https://onecompiler.com/{lang}"
    
    driver = None
    try:
        options = Options()
        # Run headful so the user can see it running
        options.add_argument("--start-maximized")
        driver = webdriver.Firefox(options=options)
        driver.get(url)
        time.sleep(3)
        
        # Remove Google One Tap popups to prevent obscuring screenshots
        try:
            driver.execute_script("""
              document.querySelectorAll('iframe').forEach(iframe => {
                if (iframe.src.includes('google.com') || iframe.id.includes('credential_picker_container')) {
                  iframe.remove();
                }
              });
              let g = document.getElementById('credential_picker_container');
              if (g) g.remove();
            """)
        except Exception:
            pass
        time.sleep(2)
        
        # We will copy the code to clipboard
        pyperclip.copy(code)
        
        # Focus the editor
        try:
            editor = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CLASS_NAME, "ace_text-input"))
            )
            editor.click()
            time.sleep(0.5)
        except:
            pass
            
        # Select all and replace with our code
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.3)
        pyautogui.press('backspace')
        time.sleep(0.3)
        pyautogui.hotkey('ctrl', 'v')
        time.sleep(0.5)
        
        # Click Run Button using explicit wait and text locator
        try:
            run_btn = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(., 'Run')]"))
            )
            run_btn.click()
        except Exception:
            # fallback keyboard shortcut
            pyautogui.hotkey('ctrl', 'enter')
            
        time.sleep(5) # Wait for execution
        
        # Remove any lingering overlays immediately before screenshot capture
        try:
            driver.execute_script("""
              document.querySelectorAll('iframe').forEach(iframe => {
                if (iframe.src.includes('google.com') || iframe.id.includes('credential_picker_container')) {
                  iframe.remove();
                }
              });
              let g = document.getElementById('credential_picker_container');
              if (g) g.remove();
            """)
        except Exception:
            pass
        time.sleep(0.5)

        screenshot_dir = "/mnt/AhmarData/screenshots"
        os.makedirs(screenshot_dir, exist_ok=True)
        screenshot_path = os.path.join(screenshot_dir, f"online_compiler_{lang}.png")
        driver.save_screenshot(screenshot_path)
        
        # Try to extract output text from the output terminal container
        output_text = "See screenshot for details."
        try:
            # Look for whitespace-pre-wrap and cursor-text container
            el = driver.find_element(By.XPATH, "//div[contains(@class, 'whitespace-pre-wrap') and contains(@class, 'cursor-text')]")
            if el and el.text:
                output_text = el.text
        except Exception:
            try:
                elements = driver.find_elements(By.XPATH, "//*[contains(@class, 'output') or contains(@class, 'terminal')]")
                if elements:
                    output_text = "\n".join([el.text for el in elements if el.text])
            except Exception:
                pass
            
        return f"Browser compiler completed. Screenshot saved to /mnt/AhmarData/screenshots/online_compiler_{lang}.png.\nExtracted Output:\n{output_text}"
        
    except Exception as e:
        return f"Error executing code via browser compiler: {str(e)}"
    finally:
        if driver:
            driver.quit()

def execute_code_online(code: str, language: str, method: str = "api") -> str:
    """Main wrapper tool to run code online"""
    if method == "browser":
        return run_code_via_browser(code, language)
    
    result = run_code_via_piston(code, language)
    if "API error" in result or "Failed to execute" in result:
        print("[Compiler]: Piston API failed/whitelisted. Falling back to browser compiler...")
        return run_code_via_browser(code, language)
    return result
