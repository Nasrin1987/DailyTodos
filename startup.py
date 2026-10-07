"""Register the current installation for Windows sign-in."""

from pathlib import Path
import subprocess
import sys

NAME = "DailyTodos"
KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def supported() -> bool:
    return sys.platform == "win32"


def command() -> str:
    executable = Path(sys.executable)
    if executable.name.lower() == "python.exe":
        executable = executable.with_name("pythonw.exe")
    if not executable.is_file():
        raise FileNotFoundError(f"Cannot find the Python launcher: {executable}")
    return subprocess.list2cmdline([str(executable), str(Path(__file__).with_name("app.py"))])


def enabled() -> bool:
    if not supported():
        return False
    import winreg

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, KEY) as key:
            value, _ = winreg.QueryValueEx(key, NAME)
            return value == command()
    except FileNotFoundError:
        return False


def set_enabled(enable: bool) -> None:
    if not supported():
        raise OSError("Startup registration is only supported on Windows.")
    import winreg

    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, KEY) as key:
        if enable:
            winreg.SetValueEx(key, NAME, 0, winreg.REG_SZ, command())
        else:
            try:
                winreg.DeleteValue(key, NAME)
            except FileNotFoundError:
                pass
