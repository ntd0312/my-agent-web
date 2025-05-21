import google.generativeai as genai
genai.configure(api_key="AIzaSyDU85Ql6xfyjOw0N4nR48lcVjtwdaW04V8")
chat = genai.GenerativeModel('models/gemini-2.0-flash').start_chat(history=[])
