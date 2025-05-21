import subprocess
import sys
import os
import threading
import tkinter as tk
from tkinter import filedialog, messagebox
from tkinterdnd2 import DND_FILES, TkinterDnD
from PIL import Image
import pytesseract
from docx import Document
import fitz
import pandas as pd
import platform
import json
import pyperclip
from tkhtmlview import HTMLLabel
import tempfile
from PIL import Image, ImageGrab

CHAT_HISTORY_FILE = "chat_history.json"

# Utility functions
def ensure_lib_installed(lib_name, module_name=None):
    module_name = module_name or lib_name
    try:
        __import__(module_name)
    except ImportError:
        print(f"Đang cài đặt thư viện: {lib_name}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", lib_name])

def load_chat_history():
    try:
        if os.path.exists(CHAT_HISTORY_FILE):
            with open(CHAT_HISTORY_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data if isinstance(data, list) else []
    except json.JSONDecodeError:
        print("Lỗi đọc lịch sử chat, khởi tạo mới.")
    return []

def save_chat_history(history):
    with open(CHAT_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)

def bind_mousewheel(widget, command):
    def _on_mousewheel(event):
        command("scroll", -1 * int(event.delta / 120), "units")
        return "break"

    widget.bind_all("<MouseWheel>", _on_mousewheel)
    
def extract_text_from_file(file_path):
    import zipfile
    ext = file_path.lower()
    try:
        if ext.endswith(".zip"):
            result = []
            with zipfile.ZipFile(file_path, 'r') as zipf:
                text_files = [f for f in zipf.namelist() if f.endswith((
                    ".py", ".js", ".ts", ".html", ".css", ".json", ".csv", ".txt", ".md"
                ))]
                for f in text_files:
                    try:
                        with zipf.open(f) as zf:
                            content = zf.read().decode("utf-8", errors="ignore")
                            result.append(f"--- {f} ---\n{content}")
                    except Exception as e:
                        result.append(f"--- {f} ---\n[Lỗi đọc: {e}]")
            return "\n\n".join(result) or "[Zip không có file hợp lệ]"

        elif ext.endswith((".png", ".jpg", ".jpeg", ".bmp")):
            img = Image.open(file_path)
            return pytesseract.image_to_string(img) or "[Ảnh không có text]"

        elif ext.endswith(".docx"):
            doc = Document(file_path)
            return "\n".join(p.text for p in doc.paragraphs if p.text.strip()) or "[Docx không có text]"

        elif ext.endswith(".pdf"):
            doc = fitz.open(file_path)
            return "\n".join(page.get_text() for page in doc) or "[PDF không có text/scan]"

        elif ext.endswith(".xlsx"):
            df = pd.read_excel(file_path)
            return df.to_string(index=False) or "[Excel trống]"

        elif ext.endswith(".csv"):
            df = pd.read_csv(file_path)
            return df.to_string(index=False) or "[CSV trống]"

        elif ext.endswith((".txt", ".py", ".log", ".json", ".md", ".html", ".css", ".js")):
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read() or "[File trống]"
        else:
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    return f.read() or "[File trống]"
            except Exception:
                return f"[Không hỗ trợ định dạng {os.path.basename(file_path)}]"

    except Exception as e:
        return f"[Lỗi trích xuất {os.path.basename(file_path)}: {e}]"

def split_text_smart(text, max_length):
    lines = text.splitlines()
    chunks = []
    current = []
    total = 0

    for line in lines:
        total += len(line) + 1
        current.append(line)
        if total >= max_length:
            chunks.append("\n".join(current))
            current = []
            total = 0
    if current:
        chunks.append("\n".join(current))

    return chunks

# UI Components
class Dashboard:
    def __init__(self, parent_frame, output_canvas):
        self.frame = tk.Frame(parent_frame, bg=BG_COLOR, width=400)
        self.frame.pack(fill="both", expand=True)
        self.text_log = tk.Text(
            self.frame, height=10, width=50, bg=INPUT_BG_COLOR, fg=TEXT_COLOR,
            wrap=tk.WORD, state='disabled'
        )
        self.text_log.pack(side=tk.LEFT, fill="both", expand=True)
        self.output_canvas = output_canvas
        self.control_frame = tk.Frame(self.frame, bg=BG_COLOR)
        self.control_frame.pack(fill="x")
        self.paused = False
        self.stopped = False
        self.skipped = False
        self.running = False
        self.completed = False
        self.preview_text = None
        self.preview_window = None
        self.is_web_content = False

        # Cập nhật các nút
        self.pause_button = tk.Button(self.control_frame, text="⏸️", command=self.toggle_pause, bg=BUTTON_BG_COLOR, fg=BUTTON_TEXT_COLOR, relief=tk.FLAT)
        self.pause_button.pack(side=tk.TOP, padx=2, pady=2, fill="x")
        self.skip_button = tk.Button(self.control_frame, text="⏭️", command=self.skip, bg=BUTTON_BG_COLOR, fg=BUTTON_TEXT_COLOR, relief=tk.FLAT)
        self.skip_button.pack(side=tk.TOP, padx=2, pady=2, fill="x")
        self.stop_button = tk.Button(self.control_frame, text="⏹️", command=self.stop, bg=BUTTON_BG_COLOR, fg=BUTTON_TEXT_COLOR, relief=tk.FLAT)
        self.stop_button.pack(side=tk.TOP, padx=2, pady=2, fill="x")
        self.hide_button = tk.Button(self.control_frame, text="❌", command=self.hide, bg=BUTTON_BG_COLOR, fg=BUTTON_TEXT_COLOR, relief=tk.FLAT)
        self.hide_button.pack(side=tk.TOP, padx=2, pady=2, fill="x")
        self.preview_button = tk.Button(self.control_frame, text="👀", command=self.show_preview, bg=BUTTON_BG_COLOR, fg=BUTTON_TEXT_COLOR, relief=tk.FLAT)
        self.export_button = tk.Button(self.control_frame, text="📤", command=self.export_web_content, bg=BUTTON_BG_COLOR, fg=BUTTON_TEXT_COLOR, relief=tk.FLAT)

    def log(self, message):
        if not hasattr(self, 'log_scrollbar'):
            self.log_scrollbar = tk.Scrollbar(self.frame)
            self.log_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
            self.text_log.configure(yscrollcommand=self.log_scrollbar.set)
            self.log_scrollbar.config(command=self.text_log.yview)

        self.text_log.configure(state='normal')
        self.text_log.insert(tk.END, message + "\n")
        self.text_log.see(tk.END)
        self.text_log.configure(state='disabled')

    def toggle_pause(self):
        self.paused = not self.paused
        self.pause_button.config(text="▶️" if self.paused else "⏸️")
        self.log("Đã tạm dừng." if self.paused else "Đã tiếp tục.")

    def skip(self):
        self.skipped = True
        self.log("Đã bỏ qua.")

    def stop(self):
        self.stopped = True
        self.running = False
        self.log("Đã dừng.")
        self.hide()

    def hide(self):
        self.running = False
        self.frame.master.grid_remove()

    def check_control(self):
        if self.stopped:
            raise RuntimeError("Đã dừng bởi người dùng.")
        if self.paused:
            self.log("Đang tạm dừng... đợi tiếp tục.")
            while self.paused and not self.stopped and not self.completed:
                self.frame.update()
        if self.skipped:
            self.log("Đã bỏ qua bước.")
            self.skipped = False
            raise RuntimeError("Bước bị bỏ qua bởi người dùng.")

    def mark_completed(self):
        self.completed = True
        self.log("Đã hoàn thành tất cả các bước.")
        if self.is_web_content:
            self.preview_button.pack(side=tk.LEFT, padx=2)
            self.export_button.pack(side=tk.LEFT, padx=2)
        else:
            self.preview_button.pack_forget()
            self.export_button.pack_forget()

    def start(self):
        self.running = True
        while self.running:
            self.frame.update()

    def stop_dashboard(self):
        self.running = False
        self.frame.destroy()

    def show_preview(self):
        import subprocess
        import shutil
        from tempfile import NamedTemporaryFile
        from runner import get_web_content

        try:
            html = get_web_content()
            if not html or "<html" not in html.lower():
                self.log("Không có nội dung HTML.")
                return

            with NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as f:
                f.write(html)
                temp_file_path = f.name

            edge_path = shutil.which("msedge") or shutil.which("C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe")
            if not edge_path:
                self.log("Không tìm thấy trình duyệt Microsoft Edge.")
                return

            subprocess.Popen([edge_path, temp_file_path])
            self.log("Đã mở Microsoft Edge để xem thử.")

        except Exception as e:
            self.log(f"Lỗi xem thử: {e}")

    def export_web_content(self):
        from tkinter import filedialog
        from runner import get_web_content

        html = get_web_content()
        if not html or "<html" not in html.lower():
            self.log("Không có nội dung HTML.")
            return

        file_path = filedialog.asksaveasfilename(
            title="Lưu file HTML",
            defaultextension=".html",
            filetypes=[("HTML Files", "*.html"), ("All Files", "*.*")]
        )

        if not file_path:
            self.log("Đã hủy xuất.")
            return

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(html)
            self.log(f"Nội dung HTML đã xuất tới: {file_path}")
        except Exception as e:
            self.log(f"Lỗi xuất: {e}")

    def update_preview(self, content, is_web_content=False):
        self.is_web_content = is_web_content
        if self.preview_text:
            self.preview_text.set_html(content)
        if is_web_content and self.completed:
            self.preview_button.pack(side=tk.LEFT, padx=2)
            self.export_button.pack(side=tk.LEFT, padx=2)
        else:
            self.preview_button.pack_forget()
            self.export_button.pack_forget()

    def refresh_preview(self):
        self.log("Đang làm mới bản xem thử...")
        try:
            from runner import get_web_content
            new_content = get_web_content()
            self.update_preview(new_content, self.is_web_content)
        except Exception as e:
            self.log(f"Lỗi lấy nội dung web: {e}")

class FileProcessor:
    def __init__(self):
        self.file_paths = []

    def load_files(self, paths):
        for path in paths:
            if path not in self.file_paths:
                self.file_paths.append(path)
                add_message_to_canvas(f"Đã tải: {os.path.basename(path)}", "success")
                add_file_preview_to_canvas(path)
    def open_file_dialog(self):
        file_paths = filedialog.askopenfilenames(filetypes=[("All Files", "*.*")])
        if file_paths:
            self.load_files(file_paths)

    def process_files(self):
        if not self.file_paths:
            add_message_to_canvas("Chưa có file nào được tải.", "error")
            return []

        parts = []
        max_chunk_size = 20000

        for file_path in self.file_paths:
            text = extract_text_from_file(file_path)
            chunks = split_text_smart(text, max_chunk_size)
            for i, chunk in enumerate(chunks):
                parts.append((f"{os.path.basename(file_path)} [Phần {i+1}]", chunk))

        return parts

    def clear_files(self):
        self.file_paths = []
        add_message_to_canvas("Đã xóa tất cả các file.", "info")

# Canvas Management
def handle_drop(event):
    import re
    raw = event.data.strip()

    # Loại bỏ dấu ngoặc nhọn bao quanh nếu có
    if raw.startswith("{") and raw.endswith("}"):
        raw = raw[1:-1]

    # Nếu kéo nhiều file thì sẽ có chuỗi như: {C:/file 1.txt} {C:/file 2.txt}
    # Tách chính xác từng file bằng regex (dùng để bắt cả đường dẫn có dấu cách)
    pattern = r'{(.*?)}' if "{" in event.data else r'".+?"|\S+'
    files = re.findall(pattern, event.data)

    # Làm sạch dấu nháy nếu có
    cleaned_files = [f.strip('"') for f in files if os.path.isfile(f.strip('"'))]

    if cleaned_files:
        file_processor.load_files(cleaned_files)
    else:
        add_message_to_canvas("❌ Không tìm thấy file hợp lệ trong dữ liệu kéo thả.", "error")

def start_new_session():
    global chat_session, chat_history
    chat_session = []
    update_sidebar()
    clear_canvas()
    #add_message_to_canvas("Đã bắt đầu chat mới.", "success")
    input_text.focus_set()  # ✅ Focus lại khung nhập mỗi khi bắt đầu

def delete_chat_session(index):
    if messagebox.askyesno("Xác nhận", "Bạn có chắc chắn muốn xóa chat này?"):
        chat_history.pop(index)
        save_chat_history(chat_history)
        update_sidebar()

def update_sidebar():
    for widget in chat_listbox_frame.winfo_children():
        widget.destroy()

    for i in range(len(chat_history)):
        title = next((msg['content'][:20] for msg in chat_history[i] if msg['role'] == 'user'), f"Chat {i+1}")

        frame = tk.Frame(chat_listbox_frame, bg=SIDEBAR_BG_COLOR)
        frame.pack(fill="x", padx=5, pady=2)

        label = tk.Label(frame, text=title, bg=SIDEBAR_BG_COLOR, fg=TEXT_COLOR, font=("Segoe UI", 11), anchor="w")
        label.pack(side="left", fill="x", expand=True)
        label.bind("<Button-1>", lambda event, idx=i: show_chat_session(idx))

        delete_button = tk.Button(frame, text="❌", command=lambda idx=i: delete_chat_session(idx), bg=SIDEBAR_BG_COLOR, fg=TEXT_COLOR, font=("Segoe UI", 10), relief="flat")
        delete_button.pack(side="right")

def clear_canvas():
    for widget in output_canvas.winfo_children():
        widget.destroy()
    output_canvas.delete("all")
    output_canvas.yview_moveto(0)
    global current_y
    current_y = 10

def add_message_to_canvas(message, tag):
    global current_y

    if tag == "agent":
        display_text = f"🤖 Agent: {message}"
    elif tag == "user":
        display_text = f"👤 Bạn: {message}"
    else:
        display_text = message

    msg_frame = tk.Frame(
        output_canvas,
        bg=MSG_BG_COLORS.get(tag, BG_COLOR),
        padx=10,
        pady=5,
        borderwidth=2,
        relief="groove"
    )
    msg_frame.columnconfigure(0, weight=1)

    msg_text = tk.Text(
        msg_frame,
        font=("Segoe UI", 12),
        wrap="word",
        height=1,
        bg=MSG_BG_COLORS.get(tag, BG_COLOR),
        fg=TEXT_COLOR,
        relief="flat",
        bd=0
    )
    msg_text.insert("1.0", display_text)

    num_lines = display_text.count('\n') + 1
    avg_chars_per_line = 60
    estimated_lines = max(num_lines, len(display_text) // avg_chars_per_line + 1)
    msg_text.configure(height=estimated_lines)
    msg_text.configure(state="disabled")
    msg_text.grid(row=0, column=0, sticky="ew")

    copy_button = tk.Button(
        msg_frame,
        text="Sao chép",
        command=lambda: pyperclip.copy(message),
        bg=BUTTON_BG_COLOR,
        fg=BUTTON_TEXT_COLOR,
        relief="flat",
        padx=8,
        pady=3
    )
    copy_button.grid(row=1, column=0, sticky="se", columnspan=2)

    output_canvas.update_idletasks()
    canvas_width = output_canvas.winfo_width()
    msg_width = min(700, canvas_width - 60)
    msg_frame.configure(width=msg_width)
    msg_frame.pack_propagate(False)

    # ✅ Chính xác hóa vị trí: user bên phải, agent bên trái
    if tag == "user":
        x_pos = canvas_width - msg_width - 20  # sát lề phải
        anchor = "nw"
    else:
        x_pos = 20  # sát lề trái
        anchor = "nw"

    output_canvas.create_window((x_pos, current_y), window=msg_frame, anchor=anchor)
    output_canvas.update_idletasks()
    current_y += msg_frame.winfo_reqheight() + 10
    output_canvas.configure(scrollregion=output_canvas.bbox("all"))
    output_canvas.yview_moveto(1)

def show_chat_session(index):
    clear_canvas()
    add_message_to_canvas(f"Chat #{index+1}", "success")
    for message in chat_history[index]:
        add_message_to_canvas(message['content'], message["role"])

    output_canvas.configure(scrollregion=output_canvas.bbox("all"))
    output_canvas.yview_moveto(0)

# Core Interaction
def process_input():
    prompt = input_text.get("1.0", tk.END).strip()
    if not prompt:
        return

    if prompt.lower() in ["darkmode", "lightmode"]:
        set_theme(prompt.lower())
        add_message_to_canvas(f"Đã chuyển sang {prompt.lower()}.","success")
        input_text.delete("1.0", tk.END)
        return

    add_message_to_canvas(prompt, "user")
    chat_session.append({"role": "user", "content": prompt})
    input_text.delete("1.0", tk.END)

    # ✅ Đảm bảo luôn cập nhật vào chat_history
    if not chat_history or chat_session is not chat_history[0]:
        chat_history.insert(0, chat_session)
    save_chat_history(chat_history)
    update_sidebar()

    def run_prompt():
        try:
            from gemini_client import chat
            from runner import handle_prompt, get_web_content

            #add_message_to_canvas("Đang xử lý ...", "info")

            if prompt.startswith("*"):
                #add_message_to_canvas("Đang xử lý ...", "info")
                system_info = f"Hệ điều hành: {platform.system()} {platform.release()} | Phiên bản: {platform.version()} | Kiến trúc: {platform.machine()}"

                dashboard_frame.grid()
                dashboard = Dashboard(dashboard_frame, output_canvas)
                dashboard_thread = threading.Thread(target=dashboard.start, daemon=True)
                dashboard_thread.start()
                handle_prompt(prompt, dashboard.log, system_info, dashboard=dashboard)

                add_message_to_canvas("Thành công." if not dashboard.stopped else "Thất bại.", "success" if not dashboard.stopped else "error")

                if not dashboard.stopped:
                    dashboard.text_log.configure(state='normal')
                    result_text = dashboard.text_log.get("1.0", tk.END).strip()
                    dashboard.text_log.configure(state='disabled')

                    if result_text:
                        add_message_to_canvas(result_text, "agent")  # ✅ Hiển thị lên chat
                        chat_session.append({"role": "agent", "content": result_text})
                        chat_history[0] = chat_session
                        save_chat_history(chat_history)
                        update_sidebar()

            else:
                responses = []

                if file_processor.file_paths:
                    for file_path in file_processor.file_paths:
                        try:
                            ext = file_path.lower()
                            if ext.endswith((".png", ".jpg", ".jpeg", ".bmp")):
                                img = Image.open(file_path)
                                response = chat.model.generate_content([prompt, img])
                            elif ext.endswith((".py", ".txt", ".log", ".json", ".csv")):
                                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                                    file_text = f.read()
                                combined_prompt = f"{prompt}\n\nNội dung file {os.path.basename(file_path)}:\n\n{file_text}"
                                response = chat.send_message(combined_prompt)
                            else:
                                file_text = extract_text_from_file(file_path)
                                combined_prompt = f"{prompt}\n\nNội dung file:\n{file_text}"
                                response = chat.send_message(combined_prompt)

                            content = response.parts[0].text.strip() if response.parts and response.parts[0].text.strip() else "[Không có phản hồi từ Agent]"
                            responses.append(content)
                            add_message_to_canvas(content, "agent")

                        except Exception as e:
                            error_msg = f"Lỗi xử lý file {os.path.basename(file_path)}: {e}"
                            add_message_to_canvas(error_msg, "error")

                else:
                    try:
                        vietnamese_prompt = (
                            "Trả lời BẮT BUỘC bằng tiếng Việt. Không dịch, không giải thích thêm.\n\n"
                            f"{prompt}"
                        )
                        response = chat.send_message(vietnamese_prompt)
                        content = response.parts[0].text.strip() if response.parts and response.parts[0].text.strip() else "[Không có phản hồi từ Agent]"
                        add_message_to_canvas(content, "agent")
                        responses.append(content)
                    except Exception as e:
                        add_message_to_canvas(f"Lỗi khi phản hồi: {e}", "error")

                if responses:
                    full_response = "\n\n".join(responses)
                    chat_session.append({"role": "agent", "content": full_response})
                    chat_history[0] = chat_session
                    save_chat_history(chat_history)
                    update_sidebar()

        except Exception as e:
            add_message_to_canvas(f"❌ Lỗi tổng: {e}", "error")
            if 'dashboard' in locals():
                dashboard.stop_dashboard()
                dashboard_frame.grid_remove()

    threading.Thread(target=run_prompt, daemon=True).start()

def add_file_preview_to_canvas(file_path):
    from PIL import ImageTk
    import mimetypes

    frame = tk.Frame(output_canvas, bg=MSG_BG_COLORS["info"], padx=10, pady=5, relief="groove", borderwidth=2)
    frame.columnconfigure(0, weight=1)

    file_name = os.path.basename(file_path)
    label = tk.Label(frame, text=f"📎 {file_name}", font=("Segoe UI", 12), bg=MSG_BG_COLORS["info"], fg=TEXT_COLOR, anchor="w", cursor="hand2")
    label.grid(row=0, column=0, sticky="ew")

    def open_preview():
        ext = file_path.lower()
        try:
            if ext.endswith((".png", ".jpg", ".jpeg", ".bmp")):
                top = tk.Toplevel(root)
                top.title(file_name)
                img = Image.open(file_path)

                # Xử lý tương thích với Pillow >=10
                try:
                    resample_filter = Image.Resampling.LANCZOS
                except AttributeError:
                    resample_filter = Image.ANTIALIAS  # Cho Pillow < 10

                img = img.resize((min(800, img.width), min(600, img.height)), resample_filter)
                photo = ImageTk.PhotoImage(img)

                panel = tk.Label(top, image=photo)
                panel.image = photo
                panel.pack()

            elif ext.endswith((".xlsx", ".csv")):
                df = pd.read_excel(file_path) if ext.endswith(".xlsx") else pd.read_csv(file_path)
                top = tk.Toplevel(root)
                top.title(file_name)

                text_widget = tk.Text(top, wrap="none", font=("Courier New", 10))
                text_widget.insert("1.0", df.to_string(index=False))
                text_widget.pack(fill="both", expand=True)

                # Cho phép copy, chặn chỉnh sửa
                text_widget.bind("<Key>", lambda e: "break")

                copy_btn = tk.Button(top, text="📋 Sao chép tất cả", command=lambda: pyperclip.copy(text_widget.get("1.0", tk.END)))
                copy_btn.pack(pady=5)

            else:
                content = extract_text_from_file(file_path)
                top = tk.Toplevel(root)
                top.title(file_name)

                text_widget = tk.Text(top, wrap="word", font=("Segoe UI", 11))
                text_widget.insert("1.0", content)
                text_widget.pack(fill="both", expand=True)

                # Cho phép copy, chặn chỉnh sửa
                text_widget.bind("<Key>", lambda e: "break")

                copy_btn = tk.Button(top, text="📋 Sao chép tất cả", command=lambda: pyperclip.copy(text_widget.get("1.0", tk.END)))
                copy_btn.pack(pady=5)

        except Exception as e:
            messagebox.showerror("Lỗi", f"Không thể xem trước file:\n{e}")

    label.bind("<Button-1>", lambda e: open_preview())

    global current_y
    output_canvas.create_window((30, current_y), window=frame, anchor="nw")
    output_canvas.update_idletasks()
    current_y += frame.winfo_reqheight() + 10
    output_canvas.configure(scrollregion=output_canvas.bbox("all"))

# Theme Management
def set_theme(theme):
    global current_theme
    current_theme = theme
    colors = THEMES.get(theme, THEMES["darkmode"])
    root.configure(bg=colors["bg"])
    sidebar_frame.configure(bg=colors["bg"])
    chat_listbox_frame.configure(bg=colors["bg"])
    new_chat_button.configure(bg=colors["bg"], fg=colors["fg"])
    main_frame.configure(bg=colors["bg"])
    output_canvas.configure(bg=colors["bg"])
    bottom_frame.configure(bg=colors["bg"])
    input_text.configure(bg=colors["text"], fg=colors["fg"], insertbackground=colors["fg"])
    button_frame.configure(bg=colors["bg"])
    separator_line.configure(bg=colors["border"])

# --- Style Constants ---
FONT = ("Segoe UI", 12)
TEXT_COLOR = "#ffffff"
BG_COLOR = "#2a2a2a"
SIDEBAR_BG_COLOR = "#333333"
INPUT_BG_COLOR = "#444444"
BUTTON_BG_COLOR = "#555555"
BUTTON_TEXT_COLOR = "#ffffff"

MSG_BG_COLORS = {
    "user": "#4CAF50",
    "agent": "#3F51B5",
    "success": "#43A047",
    "error": "#D32F2F",
    "info": "#1976D2"
}

THEMES = {
    "darkmode": {"bg": "#2a2a2a", "text": "#333333", "fg": "#ffffff", "border": "#444"},
    "lightmode": {"bg": "#f0f0f0", "text": "#ffffff", "fg": "#000000", "border": "#ccc"}
}

# --- Initialization ---
REQUIRED_LIBS = [
    ("tkinterdnd2", "tkinterdnd2"),
    ("pillow", "PIL"),
    ("pytesseract", "pytesseract"),
    ("python-docx", "docx"),
    ("pymupdf", "fitz"),
    ("pandas", "pandas"),
    ("tkhtmlview", "tkhtmlview"),
    ("pyperclip", "pyperclip")
]

for lib, module in REQUIRED_LIBS:
    ensure_lib_installed(lib, module)

chat_history = load_chat_history()
chat_session = []
current_theme = "darkmode"
file_processor = FileProcessor()
current_y = 10

# --- Main Window ---
root = TkinterDnD.Tk()
root.title("Smart Agent")
root.state("zoomed")

# --- Layout ---
root.grid_rowconfigure(0, weight=1)
root.grid_columnconfigure(1, weight=1)

# Sidebar
sidebar_frame = tk.Frame(root, width=250, bg=SIDEBAR_BG_COLOR)
sidebar_frame.grid(row=0, column=0, sticky="nsw")
sidebar_frame.pack_propagate(False)

new_chat_button = tk.Button(sidebar_frame, text="Cuộc hội thoại mới", command=start_new_session, bg="#666", fg="#fff", font=("Segoe UI", 11), relief="raised", bd=2)
new_chat_button.pack(fill="x", padx=5, pady=5)

chat_listbox_frame = tk.Frame(sidebar_frame, bg=SIDEBAR_BG_COLOR)
chat_listbox_frame.pack(fill="both", expand=True, padx=5, pady=5)

update_sidebar()

# Main Area
main_frame = tk.Frame(root, bg=BG_COLOR)
main_frame.grid(row=0, column=1, sticky="nsew")
main_frame.grid_rowconfigure(0, weight=1)
main_frame.grid_columnconfigure(0, weight=1)
main_frame.grid_columnconfigure(1, weight=0)

# Chat Canvas
output_canvas = tk.Canvas(main_frame, bg=BG_COLOR, bd=0, highlightthickness=0)
scrollbar = tk.Scrollbar(main_frame, orient="vertical", command=output_canvas.yview)
output_canvas.configure(yscrollcommand=scrollbar.set)
bind_mousewheel(output_canvas, output_canvas.yview)

output_canvas.grid(row=0, column=0, sticky="nsew", padx=5, pady=5)
scrollbar.grid(row=0, column=1, sticky="ns")

separator_line = tk.Frame(main_frame, height=1, bg="#444")
separator_line.grid(row=1, column=0, sticky="ew", pady=5)

# Input Area
bottom_frame = tk.Frame(main_frame, bg=BG_COLOR)
bottom_frame.grid(row=2, column=0, sticky="ew", padx=5, pady=5)
bottom_frame.grid_columnconfigure(0, weight=1)

input_text = tk.Text(bottom_frame, height=3, font=FONT, bg=INPUT_BG_COLOR, fg=TEXT_COLOR, insertbackground=TEXT_COLOR, bd=0, highlightthickness=0)
input_text.grid(row=0, column=0, sticky="ew", padx=5, pady=5)

# Buttons
button_frame = tk.Frame(bottom_frame, bg=BG_COLOR)
button_frame.grid(row=0, column=1, sticky="e")

import_button = tk.Button(button_frame, text="Đính kèm 📎", command=file_processor.open_file_dialog, bg=BUTTON_BG_COLOR, fg=BUTTON_TEXT_COLOR, font=FONT, relief="flat", bd=0, highlightthickness=0)
import_button.pack(side="right", padx=5, pady=5, fill="y", ipadx=10, ipady=10)

send_button = tk.Button(button_frame, text="Gửi", command=process_input, bg=BUTTON_BG_COLOR, fg=BUTTON_TEXT_COLOR, font=FONT, relief="flat", bd=0, highlightthickness=0)
send_button.pack(side="right", padx=5, pady=5, fill="y", ipadx=10, ipady=10)

# Dashboard
dashboard_frame = tk.Frame(main_frame, bg=BG_COLOR, width=400)
dashboard_frame.grid(row=0, column=2, rowspan=3, sticky="nsew", padx=5, pady=5)
dashboard_frame.grid_remove()

# --- Bindings ---
def handle_paste(event):
    import tempfile
    from PIL import ImageGrab

    # 1. Thử kiểu Windows Explorer (copy file)
    try:
        clipboard_data = root.clipboard_get(type="CF_HDROP")
        if clipboard_data:
            files = clipboard_data.strip().split("\n")
            file_processor.load_files(files)
            add_message_to_canvas("📂 Đã dán và tải file từ clipboard.", "success")
            return "break"
    except tk.TclError:
        pass  # Không phải kiểu CF_HDROP, thử cách khác

    # 2. Thử kiểu text chứa path (copy path hoặc drag-drop fail)
    try:
        text_data = root.clipboard_get().strip()
        if os.path.isfile(text_data):
            file_processor.load_files([text_data])
            add_message_to_canvas("📄 Đã dán file từ clipboard (dạng text).", "success")
            return "break"
    except Exception:
        pass

    # 3. Thử xem clipboard có ảnh (image data từ snipping tool, Ctrl+C ảnh)
    try:
        image = ImageGrab.grabclipboard()
        if isinstance(image, Image.Image):
            temp_img_path = os.path.join(tempfile.gettempdir(), "clipboard_image.png")
            image.save(temp_img_path)
            file_processor.load_files([temp_img_path])
            add_message_to_canvas("🖼️ Đã dán ảnh từ clipboard.", "success")
            return "break"
    except Exception as e:
        add_message_to_canvas(f"Lỗi khi xử lý ảnh clipboard: {e}", "error")

    # 4. Nếu không xử lý được gì
    add_message_to_canvas("❌ Clipboard không chứa nội dung hợp lệ (file/ảnh/text path).", "error")
    return "break"


input_text.bind("<Control-v>", handle_paste)
input_text.bind("<Return>", lambda event: [process_input(), "break"])
root.drop_target_register(DND_FILES)
root.dnd_bind("<<Drop>>", handle_drop)

# --- Start ---
input_text.focus_set()
set_theme("darkmode")
root.mainloop()
