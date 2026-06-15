# agent/tools/code_runner.py
import os
import subprocess
import time

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(
    os.path.abspath(__file__))))

def write_and_run_code(code: str, filename: str = "output.py") -> str:
    """Save code to file and execute it, return output"""
    try:
        filepath = os.path.join(PROJECT_ROOT, "tasks", filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(code)
            
        return run_existing_file(filepath)
    except Exception as e:
        return f"Error writing/running code: {str(e)}"

def run_existing_file(filepath: str) -> str:
    """Run an existing Python file and return output"""
    if not os.path.exists(filepath):
        if not os.path.dirname(filepath):
            filepath = os.path.join(PROJECT_ROOT, "tasks", filepath)
            
    if not os.path.exists(filepath):
        return f"Error: File '{filepath}' not found."
        
    try:
        result = subprocess.run(
            ["python3", filepath],
            capture_output=True,
            text=True,
            timeout=30
        )
        output = f"Stdout:\n{result.stdout}\nStderr:\n{result.stderr}"
        return output[:2000]
    except subprocess.TimeoutExpired:
        return "Error: Execution timed out (30 seconds limit reached)."
    except Exception as e:
        return f"Error executing file: {str(e)}"

def run_antigravity() -> str:
    """Launch the antigravity easter egg"""
    import subprocess
    subprocess.Popen(['python3', '-c', 'import antigravity'])
    return "Antigravity launched! 🚀"

def run_code_in_nano_and_screenshot(code: str, filename: str = "program.py", language: str = "python") -> str:
    """
    Write code to a file, open it in 'nano' inside a gnome-terminal window, 
    take a screenshot of the nano editor, close it, run the program inside 
    gnome-terminal, and capture a screenshot of its terminal output.
    """
    try:
        filepath = os.path.join(PROJECT_ROOT, "tasks", filename)
        os.makedirs(os.path.dirname(filepath), exist_ok=True)
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(code)
            
        logs_dir = os.path.join(PROJECT_ROOT, "logs")
        os.makedirs(logs_dir, exist_ok=True)
        
        # 1. Open in nano editor in gnome-terminal
        nano_title = f"HERALD_NANO_{int(time.time())}"
        nano_cmd = f"gnome-terminal --title='{nano_title}' --geometry=80x24 -- bash -c 'export DISPLAY=:0.0; nano \"{filepath}\"'"
        subprocess.Popen(nano_cmd, shell=True)
        time.sleep(2.0)
        
        nano_screenshot = os.path.join(logs_dir, f"nano_{os.path.splitext(filename)[0]}.png")
        try:
            win_proc = subprocess.run(["xdotool", "search", "--title", nano_title], capture_output=True, text=True, timeout=5)
            win_id = win_proc.stdout.strip().split('\n')[0]
            if win_id:
                subprocess.run(["xdotool", "windowactivate", win_id])
                time.sleep(0.5)
                subprocess.run(["scrot", "-u", nano_screenshot])
                time.sleep(0.5)
                subprocess.run(["xdotool", "windowkill", win_id])
        except Exception as ex:
            print(f"[Nano Screenshot Fallback]: {ex}")
            subprocess.run(["scrot", nano_screenshot])
            
        # 2. Run the code in gnome-terminal and screenshot output
        run_title = f"HERALD_RUN_{int(time.time())}"
        lang_cmd = "python3" if language.lower() in ["python", "py", "python3"] else ("node" if language.lower() in ["javascript", "js"] else "bash")
        
        run_cmd = f"gnome-terminal --title='{run_title}' --geometry=80x24 -- bash -c 'export DISPLAY=:0.0; echo \"$ {lang_cmd} {filename}\"; {lang_cmd} \"{filepath}\"; echo; echo \"Press Enter to close...\"; read'"
        subprocess.Popen(run_cmd, shell=True)
        time.sleep(2.0)
        
        run_screenshot = os.path.join(logs_dir, f"run_{os.path.splitext(filename)[0]}.png")
        try:
            win_proc = subprocess.run(["xdotool", "search", "--title", run_title], capture_output=True, text=True, timeout=5)
            win_id = win_proc.stdout.strip().split('\n')[0]
            if win_id:
                subprocess.run(["xdotool", "windowactivate", win_id])
                time.sleep(0.5)
                subprocess.run(["scrot", "-u", run_screenshot])
                time.sleep(0.5)
                subprocess.run(["xdotool", "windowkill", win_id])
        except Exception as ex:
            print(f"[Run Screenshot Fallback]: {ex}")
            subprocess.run(["scrot", run_screenshot])

        raw_result = run_existing_file(filepath)
        
        return (
            f"Successfully wrote code to '{filepath}'.\n"
            f"Opened program in 'nano' editor and saved screenshot: logs/nano_{os.path.splitext(filename)[0]}.png\n"
            f"Ran program in terminal and saved screenshot: logs/run_{os.path.splitext(filename)[0]}.png\n"
            f"Program Output:\n{raw_result}"
        )
    except Exception as e:
        return f"Error executing run_code_in_nano_and_screenshot: {str(e)}"

def execute_bash_command(command: str, working_dir: str | None = None) -> str:
    """
    Execute a shell/bash command on the system, capture its output, and return it.
    Can be used to navigate folders, check environment, or run scripts.
    """
    try:
        cwd = working_dir if working_dir else PROJECT_ROOT
        if not os.path.exists(cwd):
            cwd = PROJECT_ROOT
            
        result = subprocess.run(
            ["bash", "-c", command],
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60
        )
        
        output = f"Exit Code: {result.returncode}\n"
        if result.stdout:
            output += f"Stdout:\n{result.stdout}\n"
        if result.stderr:
            output += f"Stderr:\n{result.stderr}\n"
        if not result.stdout and not result.stderr:
            output += "Command completed with no output."
            
        return output[:3000]
    except subprocess.TimeoutExpired:
        return "Error: Command timed out after 60 seconds."
    except Exception as e:
        return f"Error executing command: {str(e)}"
