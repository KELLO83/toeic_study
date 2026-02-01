import requests
import json

def check_word_with_ollama(word, meaning):
    # Ollama API Endpoint (Default)
    url = "http://localhost:11434/api/generate"
    
    # Prompt design is key
    prompt = f"""
    You are a strict TOEIC vocabulary corrector.
    
    Task: Check if the word '{word}' matches the meaning '{meaning}'.
    1. If the spelling is wrong, provide the correct spelling.
    2. If the meaning is completely wrong, provide the correct Korean meaning.
    3. If mostly correct (minor typo or acceptable meaning), output 'OK'.
    
    Output JSON only: {{"status": "OK" or "FIX", "word": "corrected_word", "meaning": "corrected_meaning"}}
    """
    
    payload = {
        "model": "llama3",  # or mistral, solar, etc.
        "prompt": prompt,
        "format": "json",    # Force JSON output
        "stream": False
    }
    
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            result = response.json()
            return result['response'] # This will be the JSON string from LLM
        else:
            return f"Error: {response.status_code}"
            
    except Exception as e:
        return f"Connection Failed: {e}"

# Test
if __name__ == "__main__":
    print("Asking Ollama...")
    # Test case: Typo 'applam' -> 'apple'
    print(check_word_with_ollama("applam", "사과"))
