async function sendPrompt() {
  const prompt = document.getElementById("prompt").value;
  document.getElementById("log").innerText = "⏳ Đang xử lý...";

  try {
    const response = await fetch("http://localhost:5000/api/prompt", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ prompt })
    });
    const data = await response.json();
    document.getElementById("log").innerText = data.reply || JSON.stringify(data);
  } catch (err) {
    document.getElementById("log").innerText = "❌ Lỗi kết nối đến backend.";
    console.error(err);
  }
}
