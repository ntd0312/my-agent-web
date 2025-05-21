from flask import Flask, request, jsonify
from runner import handle_prompt  # nếu muốn xử lý bằng AI agent
# hoặc chỉ trả về dữ liệu test ban đầu

app = Flask(__name__)

@app.route("/api/prompt", methods=["POST"])
def process_prompt():
    data = request.json
    prompt = data.get("prompt", "")
    print(f"Prompt nhận được: {prompt}")

    # Gọi xử lý thực tế bằng AI (nếu cần)
    # result = handle_prompt(prompt, log_callback=print)
    # return jsonify(result)

    # Trả về dữ liệu test
    return jsonify({"reply": f"Tôi nhận được: '{prompt}'"})

if __name__ == "__main__":
    app.run(debug=True)
