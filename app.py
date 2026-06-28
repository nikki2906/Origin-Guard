from flask import Flask, request, jsonify
from dotenv import load_dotenv
import os
import uuid
from datetime import datetime
from signals.llm_classifier import classify_with_llm

load_dotenv()

app = Flask(__name__)

# Simple in-memory audit log
audit_log = []

@app.route("/submit", methods=["POST"])
def submit():
    data = request.get_json()
    
    # Basic validation
    if not data or "text" not in data or "creator_id" not in data:
        return jsonify({"error": "Missing required fields: text and creator_id"}), 400
    
    text = data["text"]
    creator_id = data["creator_id"]
    content_id = str(uuid.uuid4())
    
    # Signal 1
    llm_score = classify_with_llm(text)
    
    # Log the entry
    log_entry = {
        "content_id": content_id,
        "creator_id": creator_id,
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "llm_score": llm_score,
        "confidence": llm_score,
        "attribution": "likely_ai" if llm_score > 0.75 else "uncertain" if llm_score > 0.45 else "likely_human",
        "status": "classified"
    }
    audit_log.append(log_entry)
    
    return jsonify({
        "content_id": content_id,
        "attribution": log_entry["attribution"],
        "confidence": llm_score,
        "label": "placeholder"
    })

@app.route("/log", methods=["GET"])
def get_log():
    return jsonify({"entries": audit_log})

if __name__ == "__main__":
    app.run(debug=True)