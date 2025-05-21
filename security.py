import tkinter as tk
from tkinter import messagebox

def is_dangerous_code(code):
    dangerous_keywords = ["os.remove", "shutil.rmtree", "format", "rm -rf", "del C:", "shutdown", "logoff"]
    return any(kw in code for kw in dangerous_keywords)

def ask_user_confirmation(code):
    root = tk.Tk()
    root.withdraw()  # Ẩn cửa sổ chính
    result = messagebox.askyesno(
        "⚠️ Xác nhận mã nguy hiểm",
        f"Mã yêu cầu chạy:\n\n{code}\n\nBạn có chắc chắn muốn chạy mã này không?"
    )
    root.destroy()
    return result
