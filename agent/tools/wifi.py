# agent/tools/wifi.py
import subprocess

def wifi_status() -> str:
    """Check current WiFi status"""
    try:
        result = subprocess.run(
            ["nmcli", "radio", "wifi"],
            capture_output=True,
            text=True
        )
        status = result.stdout.strip().lower()
        if "enabled" in status or "on" in status:
            return "WiFi is ON"
        return "WiFi is OFF"
    except Exception as e:
        return f"Error checking WiFi status: {str(e)}"

def wifi_on() -> str:
    """Turn WiFi on"""
    try:
        subprocess.run(["nmcli", "radio", "wifi", "on"], check=True)
        return "WiFi turned ON successfully."
    except Exception as e:
        return f"Error turning WiFi ON: {str(e)}"

def wifi_off() -> str:
    """Turn WiFi off"""
    try:
        subprocess.run(["nmcli", "radio", "wifi", "off"], check=True)
        return "WiFi turned OFF successfully."
    except Exception as e:
        return f"Error turning WiFi OFF: {str(e)}"
