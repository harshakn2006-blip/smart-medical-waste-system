
import os
import base64
import requests


GEMINI_MODEL = "gemini-3.5-flash"


def identify_waste_image(image_bytes, mime_type):
    api_key = os.environ.get("GEMINI_API_KEY")

    if not api_key:
        raise ValueError("Gemini API key not found.")

    url = (
        f"https://generativelanguage.googleapis.com/"
        f"v1beta/models/{GEMINI_MODEL}:generateContent"
    )

    prompt = """
    Identify the main visible object in this image.
    Return only its short, common item name.
    If unclear, return UNCLEAR.
    Do not guess whether it is contaminated or infectious.
    Do not decide its biomedical waste category.
    """

    payload = {
        "contents": [{
            "parts": [
                {"text": prompt},
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": base64.b64encode(
                            image_bytes
                        ).decode("utf-8")
                    }
                }
            ]
        }]
    }

    response = requests.post(
        url,
        headers={
            "x-goog-api-key": api_key,
            "Content-Type": "application/json"
        },
        json=payload,
        timeout=120
    )

    if response.status_code != 200:
        print("GEMINI STATUS:", response.status_code)
        print("GEMINI DETAILS:", response.text)
        response.raise_for_status()

    data = response.json()
    candidates = data.get("candidates", [])

    if not candidates:
        raise ValueError("No identification returned by Gemini.")

    parts = candidates[0].get("content", {}).get("parts", [])

    identified_item = " ".join(
        part.get("text", "")
        for part in parts
        if part.get("text")
    ).strip()

    if not identified_item:
        raise ValueError("Could not identify the image.")

    return {
        "item_name": identified_item[:120],
        "review_required": True,
        "message": "AI suggestion only. Trained staff must verify."
    }
