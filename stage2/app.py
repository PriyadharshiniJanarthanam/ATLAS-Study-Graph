from flask import Flask, jsonify, request, send_from_directory
import os
import sys

# Add project root to Python path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.study_graph import StudyGraph
from src.atlas import Atlas
from stage2.crew import ReviewCrew


app = Flask(__name__)


# -----------------------------
# LOAD PROBLEM 1
# -----------------------------

graph = StudyGraph("hackathon-data/data")
graph.build()

atlas = Atlas(graph)


# -----------------------------
# CREATE PROBLEM 2 CREW
# -----------------------------

crew = ReviewCrew(
    "http://localhost:8000",
    "http://localhost:8001",
    "TEAM1",
    atlas
)


# Store the latest report
latest_report = None


# -----------------------------
# FRONTEND
# -----------------------------

@app.route("/")
def home():
    return send_from_directory(
        os.path.dirname(os.path.abspath(__file__)),
        "index.html"
    )


# -----------------------------
# RUN REVIEW CYCLE
# -----------------------------

@app.route("/api/cycle")
def cycle():

    global latest_report

    cut = int(request.args.get("cut", 6))
    protocol = int(request.args.get("protocol", 2))

    # Run the review cycle only once.
    # Later requests return the same report.
    if latest_report is None:

        latest_report = crew.run_cycle(
            cut,
            protocol
        )

    return jsonify({
        "summary": latest_report.summary,
        "findings": latest_report.findings,
        "escalations": latest_report.escalations,
        "queries": latest_report.queries,
        "deviations": latest_report.deviations,
        "trace": latest_report.trace,
        "approved_actions": latest_report.approved_actions
    })


# -----------------------------
# HUMAN GATE DECISION
# -----------------------------

@app.route("/api/decision", methods=["POST"])
def decision():

    data = request.get_json()

    if data is None:
        return jsonify({
            "error": "No JSON data received"
        }), 400

    code = data.get("code")
    subject = data.get("usubjid")
    decision_value = data.get("decision")
    reason = data.get("reason", "")

    if not code or not subject or not decision_value:
        return jsonify({
            "error": "code, usubjid and decision are required"
        }), 400

    key = f"{code}:{subject}"

    try:

        crew.set_human_decision(
            key,
            decision_value,
            reason
        )

    except ValueError as e:

        return jsonify({
            "error": str(e)
        }), 400

    return jsonify({
        "message": "Decision recorded successfully",
        "code": code,
        "usubjid": subject,
        "decision": decision_value,
        "reason": reason
    })


# -----------------------------
# PATIENT 360
# -----------------------------

@app.route("/api/patient/<usubjid>")
def patient(usubjid):

    result = atlas.graph.patient_data.get(usubjid)

    if result is None:

        return jsonify({
            "error": "Patient not found"
        }), 404

    return jsonify(result)


# -----------------------------
# TEST SERVER
# -----------------------------

@app.route("/api/health")
def health():

    return jsonify({
        "status": "running",
        "problem1": "Atlas loaded",
        "problem2": "ReviewCrew loaded"
    })


# -----------------------------
# START SERVER
# -----------------------------

if __name__ == "__main__":

    app.run(
        host="127.0.0.1",
        port=5000,
        debug=True
    )