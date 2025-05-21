import platform
import socket
import pyautogui
import psutil
import pygetwindow as gw

def find_window_by_exe(exe_name):
    for proc in psutil.process_iter(['pid', 'name']):
        if proc.info['name'] and exe_name.lower() in proc.info['name'].lower():
            pid = proc.info['pid']
            for win in gw.getAllWindows():
                if hasattr(win, '_getWindowPID') and win._getWindowPID() == pid:
                    return win
    return None

def prepare_gui_context(exe_name=None, app_name=None):
    width, height = pyautogui.size()
    win = None
    if exe_name:
        win = find_window_by_exe(exe_name)
    context = {
        "machine": socket.gethostname(),
        "os": platform.platform(),
        "arch": platform.machine(),
        "screen": {"width": width, "height": height},
        "app": {
            "name": app_name or "Không rõ",
            "exe": exe_name or "Không rõ",
            "window_size": f"{win.width}x{win.height}" if win else "Không tìm thấy",
            "maximized": win.isMaximized if win else False,
        }
    }
    return context