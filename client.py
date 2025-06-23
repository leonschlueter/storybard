import requests

API_URL = "http://localhost:8000/api/turn"

def send_turn(input_text: str):
    response = requests.post(API_URL, json={"input_text": input_text})
    
    if response.status_code == 200:
        data = response.json()
        print("\n🎭 Narration:")
        print(data.get("narration", "<No narration returned>"))
    else:
        print(f"❌ Error {response.status_code}: {response.text}")

if __name__ == "__main__":
    print("🧙 Enter your action below. Type 'exit' to quit.\n")

    while True:
        user_input = input("🧑 You: ")
        if user_input.lower() in ["exit", "quit"]:
            break
        send_turn(user_input)
