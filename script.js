function sendPrompt() {
  const prompt = document.getElementById("prompt").value;
  document.getElementById("log").innerText = `Bạn đã gửi: "${prompt}"`;
}
