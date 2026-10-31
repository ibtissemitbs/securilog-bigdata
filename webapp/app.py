from flask import Flask, jsonify

app = Flask(__name__)


@app.get("/")
def accueil():
    return jsonify(
        application="SecuriLog",
        message="Application Flask opérationnelle"
    )


@app.get("/health")
def health():
    return jsonify(status="ok")
