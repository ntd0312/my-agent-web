import os
import sys
import subprocess
import importlib.util
import importlib
import time

TEMP_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'Temp'))
os.makedirs(TEMP_DIR, exist_ok=True)
if TEMP_DIR not in sys.path:
    sys.path.append(TEMP_DIR)

def install_library(library, log_callback=None):
    try:
        if log_callback:
            log_callback(f"Đang cài đặt {library}...")
        start_time = time.time()
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", library, "--target", TEMP_DIR],
            capture_output=True, text=True, timeout=300  # Timeout 5 phút
        )
        elapsed_time = time.time() - start_time
        if result.returncode == 0:
            if log_callback:
                log_callback(f"Cài đặt {library} thành công trong {elapsed_time:.2f} giây.")
            # Cố gắng tải module để xác nhận
            try:
                importlib.import_module(library.lower().replace("-", "_"))
                if log_callback:
                    log_callback(f"Xác nhận {library} đã được tải thành công.")
            except ImportError as e:
                if log_callback:
                    log_callback(f"Cảnh báo: Không thể tải {library} ngay sau cài đặt: {str(e)}")
        else:
            error_msg = result.stderr or "Lỗi không xác định khi cài đặt."
            if log_callback:
                log_callback(f"Lỗi khi cài đặt {library}: {error_msg}")
            raise Exception(error_msg)
    except subprocess.TimeoutExpired:
        if log_callback:
            log_callback(f"Lỗi: Quá thời gian cài đặt {library} (vượt quá 5 phút).")
        raise
    except Exception as e:
        if log_callback:
            log_callback(f"Lỗi không mong muốn khi cài đặt {library}: {str(e)}")
        raise

def ensure_library(library, module_name=None):
    module_name = module_name or library
    if importlib.util.find_spec(module_name) is None:
        ask = input(f"⚠️ Thư viện '{library}' chưa được cài. Bạn có muốn cài không? (Y/N): ").strip().lower()
        if ask == "y":
            install_library(library)
        else:
            print(f"❌ Bỏ qua cài đặt thư viện '{library}'.")

def check_library_installed(module_name):
    spec = importlib.util.find_spec(module_name)
    if spec is None:
        return False
    try:
        importlib.import_module(module_name)
        return True
    except ImportError:
        return False

def ensure_runtime_dependency(code):
    requirements = {
        "pyautogui": "pyautogui",
        "pytesseract": "pytesseract",
        "cv2": "opencv-python",
        "requests": "requests",
        "selenium": "selenium",
    }
    for key, lib in requirements.items():
        if key in code:
            ensure_library(lib)
