# runner.py
import json
import re
import ast
import os
import difflib
import subprocess
import sys
import tkinter as tk
from tkinter import messagebox
from gemini_client import chat
from security import is_dangerous_code, ask_user_confirmation
from dependency_manager import ensure_runtime_dependency, install_library
from context_collector import prepare_gui_context

LOG_FILE = "logs.json"
RETRY_LIMIT = 3

_latest_web_content = ""  # Biến toàn cục để lưu trữ nội dung web

def load_logs():
    if os.path.exists(LOG_FILE):
        with open(LOG_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    return {}

def save_logs(logs):
    with open(LOG_FILE, 'w', encoding='utf-8') as f:
        json.dump(logs, f, ensure_ascii=False, indent=2)

def extract_user_input(prompt):
    if "*" in prompt:
        user_part = prompt.split("*", 1)[1].strip()
    else:
        user_part = prompt.strip()

    lowered = user_part.lower()

    # 🚀 Nếu là yêu cầu tạo web, chuẩn hóa nội dung thành yêu cầu thống nhất
    if any(keyword in lowered for keyword in [
        "tạo web", "giao diện web", "html", "website", "trang web", "thiết kế web", "tms"
    ]):
        user_part = (
            f"TẠO WEB CHUẨN HTML\n"
            f"{user_part.strip()}\n"
            f"- Trả về mã HTML hoàn chỉnh trong chuỗi Python, gán vào biến 'html_content'.\n"
            f"- Nếu có CSS, hãy nhúng trực tiếp bằng thẻ <style> bên trong HTML, không tạo file style.css riêng.\n"
            f"- Không sử dụng hàm mở trình duyệt.\n"
            f"- Phải kết thúc bằng '__step_success__ = True'."
        )

    return user_part.lower()


def match_existing_prompt(prompt, logs):
    user_input = extract_user_input(prompt)
    for key in logs:
        if user_input == extract_user_input(key):
            return logs[key]
    suggestions = difflib.get_close_matches(user_input, [extract_user_input(k) for k in logs.keys()], n=1, cutoff=0.8)
    if suggestions:
        root = tk.Tk()
        root.withdraw()
        confirm = messagebox.askyesno("Xác nhận", f"Yêu cầu gần giống: {suggestions[0]}?\nChọn Yes để sử dụng.")
        root.destroy()
        for key in logs:
            if extract_user_input(key) == suggestions[0] and confirm:
                return logs[key]
    return None

def get_assigned_vars(code_str):
    assigned = set()
    try:
        tree = ast.parse(code_str)
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
                assigned.add(node.id)
            elif isinstance(node, ast.arg):
                assigned.add(node.arg)
    except Exception:
        pass
    return assigned

def install_missing_software_from_error(error_msg):
    if "No module named" in str(error_msg):
        module_name = str(error_msg).split("No module named")[-1].strip().strip("'").strip()
        print(f"📦 Phát hiện thiếu module: {module_name}. Đang thử cài đặt...")
        install_library(module_name)
        return True
    elif "not recognized as an internal or external command" in str(error_msg):
        print("🛠️ Phát hiện thiếu phần mềm hệ thống. Vui lòng kiểm tra và cài đặt thủ công nếu cần.")
        return False
    return False

def build_ai_prompt(prompt_only, system_info="", gui_context={}, installed_libs=""):
    full_context = (
        system_info + "\nThông tin hệ thống chi tiết:\n" +
        json.dumps(gui_context, ensure_ascii=False) + "\n\n" +
        "Các thư viện Python đã cài (ưu tiên sử dụng các thư viện này khi sinh mã):\n" +
        installed_libs
    )

    ai_prompt = (
        "Luôn trả lời BẮT BUỘC bằng tiếng Việt trong MỌI trường hợp, bao gồm mô tả, code, và mọi nội dung khác.\n"
        + full_context + "\n"
        "Bạn là trợ lý AI có toàn quyền tương tác trên hệ thống Windows hiện tại.\n"
        "QUAN TRỌNG:\n"
        "- Chỉ trả về JSON dạng danh sách step.\n"
        "- Mỗi step có thể có:\n"
        "  - step: mô tả step\n"
        "  - purpose: mục tiêu step\n"
        "  - code: đoạn code Python đầy đủ, chạy trực tiếp, không dùng action, command, hay DSL khác\n"
        "  - condition (tuỳ chọn): code Python kiểm tra điều kiện, trả về boolean, KHÔNG sử dụng import\n"
        "  - rollback_code (tuỳ chọn): code Python rollback độc lập\n"
        "  - post_check (tuỳ chọn): code Python kiểm tra hậu kỳ, boolean thuần, KHÔNG có import\n"
        "- KHÔNG dùng action, command, object, DSL dạng automation.\n"
        "- MỌI code PHẢI là Python thuần, exec() được ngay.\n"
        "- Trả về JSON sạch, không kèm text giải thích.\n"
        "- KHÔNG thêm text mô tả ngoài JSON.\n"
        "- Ví dụ đúng:\n"
        "[\n"
        "{\n"
        "  \"step\": \"Kiểm tra dịch vụ Print Spooler\",\n"
        "  \"purpose\": \"Kiểm tra dịch vụ\",\n"
        "  \"code\": \"import psutil\\nspooler_running = any(p.name() == 'spoolsv.exe' for p in psutil.process_iter())\\nprint(spooler_running)\\n__step_success__ = True\",\n"
        "  \"post_check\": \"spooler_running == True\"\n"
        "}\n"
        "]\n"
        f"Yêu cầu: {prompt_only}"
    )
    return ai_prompt

def clean_and_validate_ai_response(raw_response, log_callback=None):
    try:
        json_text = re.search(r'\[\s*{.*?}\s*\]', raw_response, re.DOTALL).group(0)
        steps = json.loads(json_text)
        clean_steps = []
        for step in steps:
            valid_step = {
                'step': step.get('step', '').strip(),
                'purpose': step.get('purpose', '').strip(),
                'code': step.get('code', '').strip()
            }
            if 'condition' in step:
                valid_step['condition'] = step['condition'].strip()
            if 'rollback_code' in step:
                valid_step['rollback_code'] = step['rollback_code'].strip()
            if 'post_check' in step:
                valid_step['post_check'] = step['post_check'].strip()
            clean_steps.append(valid_step)
        return clean_steps
    except Exception as e:
        if log_callback: log_callback(f"❌ Lỗi trích xuất hoặc lọc JSON: {e}")
        if log_callback: log_callback(f"📄 Phản hồi:\n{raw_response}")
        return None

def handle_prompt(prompt, log_callback=None, system_info="", dashboard=None):
    logs = load_logs()
    prompt_only = extract_user_input(prompt)

    if not isinstance(prompt_only, str) or len(prompt_only.strip()) < 3:
        if log_callback: log_callback("❗ Prompt không hợp lệ hoặc quá ngắn.")
        return {} # Trả về dictionary rỗng để nhất quán

    existing = match_existing_prompt(prompt_only, logs)

    if existing:
        if log_callback: log_callback("⚡ Yêu cầu này đã từng thực thi.")
        steps = existing
    else:
        if log_callback: log_callback("Đang xử lý...")
        gui_context = prepare_gui_context()
        try:
            installed_libs = subprocess.check_output(
                [sys.executable, "-m", "pip", "freeze"],
                universal_newlines=True,
                creationflags=subprocess.CREATE_NO_WINDOW  # ← thêm dòng này
            )
        except Exception as e:
            installed_libs = f"[Lỗi khi lấy danh sách thư viện: {e}]"

        ai_prompt = build_ai_prompt(prompt_only, system_info, gui_context, installed_libs)
        response = chat.send_message(ai_prompt)

        raw = response.text.strip()
        steps = clean_and_validate_ai_response(raw, log_callback)
        if not steps:
            if log_callback: log_callback("❌ JSON không hợp lệ sau lọc.")
            return {} # Trả về dictionary rỗng

    context = {}
    all_steps_success = True
    is_web_content = False

    for i, step in enumerate(steps):
        if dashboard:
            dashboard.check_control()

        if log_callback: log_callback(f"\n🧩 Step {i+1}: {step.get('step', '')}")
        if log_callback: log_callback(f"🎯 Mục tiêu: {step.get('purpose', '')}")
        code = step.get('code', '').strip()
        if log_callback: log_callback("📜 Code:")
        if log_callback: log_callback(code)

        if 'condition' in step and step['condition']:
            try:
                if not eval(step['condition'], context):
                    if log_callback: log_callback("⚙️ Điều kiện không thỏa mãn, bỏ qua step.")
                    continue
            except Exception as e:
                if log_callback: log_callback(f"❗ Lỗi đánh giá condition: {e}")

        assigned_vars = get_assigned_vars(code)
        retry_count = 0
        while retry_count < RETRY_LIMIT:
            retry_count += 1

            if dashboard:
                dashboard.check_control()

            try:
                ensure_runtime_dependency(code)
                if is_dangerous_code(code):
                    if not ask_user_confirmation(code):
                        if log_callback: log_callback("🚫 Bỏ qua do người dùng từ chối.")
                        all_steps_success = False
                        break
                exec(code, context)
                globals().update(context)

                # Kiểm tra và lưu nội dung web nếu có
                for value in context.values():
                    if "html_content" in context and isinstance(context["html_content"], str):
                        global _latest_web_content
                        _latest_web_content = context["html_content"]
                        is_web_content = "<html" in _latest_web_content.lower()
                    else:
                        for value in context.values():
                            if isinstance(value, str) and "<html" in value.lower():
                                _latest_web_content = value
                                is_web_content = True
                                break

                if 'post_check' in step and step['post_check']:
                    try:
                        if not eval(step['post_check'], context):
                            if log_callback: log_callback(f"❌ Hậu kiểm thất bại: {step['post_check']}")
                            all_steps_success = False
                            break
                    except Exception as e:
                        if log_callback: log_callback(f"❗ Lỗi hậu kiểm: {e}")
                        all_steps_success = False
                        break
                if '__step_success__' not in context or not context['__step_success__']:
                    raise RuntimeError("❌ Step không đánh dấu '__step_success__ = True'")
                break # Step thành công, thoát khỏi vòng lặp retry

            except Exception as e:
                if log_callback: log_callback(f"❌ Step lỗi: {e}")
                installed = install_missing_software_from_error(e)
                if installed:
                    if log_callback: log_callback("🔁 Thử lại sau cài đặt...")
                    continue

                if 'rollback_code' in step and step['rollback_code']:
                    try:
                        exec(step['rollback_code'], context)
                        if log_callback: log_callback("↩️ Đã rollback step.")
                    except Exception as re:
                        if log_callback: log_callback(f"❗ Lỗi rollback step: {re}")
                all_steps_success = False
                break
        else:
            if retry_count == RETRY_LIMIT:
                all_steps_success = False # Nếu hết số lần thử mà vẫn lỗi

        if not all_steps_success:
            break

    if not existing and all_steps_success:
        root = tk.Tk()
        root.withdraw()
        save_choice = messagebox.askyesno("Lưu yêu cầu", "📦 Bạn có muốn lưu lại yêu cầu này để dùng sau không?")
        root.destroy()
        if save_choice:
            logs[prompt_only] = steps
            save_logs(logs)
            if log_callback: log_callback("✅ Đã lưu yêu cầu vào logs.")
    elif not all_steps_success:
        if log_callback: log_callback("⚠️ Một số bước đã thất bại, không lưu vào logs.")

    result = {
        "completed": all_steps_success,
        "web_content": _latest_web_content,
        "is_web_content": is_web_content
    }

    if dashboard:
        dashboard.mark_completed()
        dashboard.update_preview(_latest_web_content, is_web_content)

    return result

def get_web_content():
    return _latest_web_content
