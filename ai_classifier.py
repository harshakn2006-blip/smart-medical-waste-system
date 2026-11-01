
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline

# Sample training data for an educational AI demo.
# These examples are not a substitute for biomedical waste rules.
training_items = [
    "blood stained gauze",
    "soiled cotton dressing",
    "human tissue waste",
    "expired medicine",
    "contaminated iv tubing",
    "used urine bag",
    "contaminated plastic gloves",
    "plastic syringe without needle",
    "used needle",
    "scalpel blade",
    "metal sharp waste",
    "contaminated glass vial",
    "used glass slide",
    "medicine glass bottle"
]

training_categories = [
    "Yellow", "Yellow", "Yellow", "Yellow",
    "Red", "Red", "Red", "Red",
    "White (translucent)", "White (translucent)",
    "White (translucent)",
    "Blue", "Blue", "Blue"
]

model = Pipeline([
    ("tfidf", TfidfVectorizer()),
    ("classifier", LogisticRegression(max_iter=1000))
])

model.fit(training_items, training_categories)


def predict_waste_category(item_name):
    item_name = item_name.strip().lower()

    if not item_name:
        return {
            "category": "Needs review",
            "confidence": 0,
            "review_required": True,
            "message": "Enter a waste item name."
        }

    probabilities = model.predict_proba([item_name])[0]
    best_index = probabilities.argmax()

    category = model.classes_[best_index]
    confidence = float(probabilities[best_index])

    # Low-confidence predictions must be reviewed.
    if confidence < 0.65:
        return {
            "category": "Needs review",
            "confidence": round(confidence * 100, 2),
            "review_required": True,
            "message": "AI is uncertain. Ask trained staff to verify."
        }

    return {
        "category": category,
        "confidence": round(confidence * 100, 2),
        "review_required": True,
        "message": "AI suggestion only. Trained staff must verify."
    }
