import urllib.request
import json
import time

SERVER_URL = "http://127.0.0.1:8000/api/chat"

questions = [
    ("alice_hr", "Are there any recent employee complaints logged in the system?"),
    ("alice_hr", "What is our executive HR strategy regarding layoffs?"),
    ("david_hr", "How much PTO do I get?"),
    ("david_hr", "What were the Q3 financial results?"),
    ("bob_eng", "What is our engineering architecture migration plan?"),
    ("bob_eng", "Are there any recent employee complaints logged in the system?"),
    ("charlie_fin", "What were the Q3 financial results?"),
    ("charlie_fin", "What are the engineering salary bands?")
]

results = []

def ask(user, query):
    req = urllib.request.Request(
        SERVER_URL,
        data=json.dumps({"username": user, "query": query}).encode("utf-8"),
        headers={"Content-Type": "application/json"}
    )
    with urllib.request.urlopen(req) as response:
        return json.loads(response.read().decode())["response"]

print("Generating responses...")
for user, query in questions:
    print(f"Asking as {user}: {query}")
    try:
        response = ask(user, query)
        results.append(f"**Q ({user}):** {query}\n**A:** {response}")
    except Exception as e:
        print(f"Error: {e}")
    time.sleep(1) # don't rate limit Groq

with open("qa_results.txt", "w") as f:
    f.write("\n\n".join(results))

print("Done! Saved to qa_results.txt")
