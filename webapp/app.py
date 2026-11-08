import json

from flask import Flask, jsonify, render_template_string, request

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024

PREVIEW_PAGE = """
<!doctype html>
<html lang="fr">
<head>
    <meta charset="utf-8">
    <title>SecuriLog — Aperçu des logs</title>
</head>
<p id="erreur-taille" role="alert"></p>

<script>
    document.addEventListener("DOMContentLoaded", () => {
    const champFichier = document.getElementById("fichier");
    const message = document.getElementById("erreur-taille");
    const limite = {{ config.MAX_CONTENT_LENGTH }};

    function verifierTaille() {
        const fichier = champFichier.files[0];

        if (fichier && fichier.size >= limite) {
            champFichier.value = "";
            message.textContent = "Le fichier est trop volumineux. Choisis un fichier de moins de 2 Mio.";
            return false;
        }

        message.textContent = "";
        return true;
    }

    champFichier.addEventListener("change", verifierTaille);

    champFichier.form.addEventListener("submit", (evenement) => {
        if (!verifierTaille()) {
            evenement.preventDefault();
        }
    });
});
</script>
<body>
    <h1>SecuriLog — Aperçu des logs</h1>
    <p>Choisis un fichier JSONL pour afficher ses 10 premiers événements.</p>

    <form method="post" enctype="multipart/form-data">
        <label for="fichier">Fichier de logs</label>
        <input id="fichier" name="fichier" type="file" accept=".jsonl" required>
        <button type="submit">Prévisualiser</button>
    </form>

    {% if erreur %}
        <p role="alert">{{ erreur }}</p>
    {% endif %}

    {% if lignes %}
        <h2>{{ lignes|length }} événement(s) en aperçu</h2>
        <ol>
            {% for ligne in lignes %}
                <li><pre>{{ ligne }}</pre></li>
            {% endfor %}
        </ol>
    {% endif %}
</body>
</html>
"""


@app.get("/")
def accueil():
    return jsonify(
        application="SecuriLog",
        message="Application Flask opérationnelle"
    )


@app.get("/health")
def health():
    return jsonify(status="ok")


@app.errorhandler(413)
def fichier_trop_volumineux(_erreur):
    return render_template_string(
        PREVIEW_PAGE,
        erreur="Le fichier est trop volumineux. Choisis un fichier de moins de 2 Mio.",
    ), 413


@app.route("/preview", methods=["GET", "POST"])
def preview():
    if request.method == "GET":
        return render_template_string(PREVIEW_PAGE)

    fichier = request.files.get("fichier")
    if not fichier or not fichier.filename.lower().endswith(".jsonl"):
        return render_template_string(
            PREVIEW_PAGE, erreur="Choisis un fichier avec l’extension .jsonl."
        ), 400

    lignes = []
    for numero, ligne_brute in enumerate(fichier.stream, start=1):
        if not ligne_brute.strip():
            continue

        try:
            evenement = json.loads(ligne_brute.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return render_template_string(
                PREVIEW_PAGE, erreur=f"La ligne {numero} doit contenir du JSON en UTF-8."
            ), 400

        if not isinstance(evenement, dict):
            return render_template_string(
                PREVIEW_PAGE, erreur=f"La ligne {numero} doit contenir un objet JSON."
            ), 400

        lignes.append(json.dumps(evenement, ensure_ascii=False, indent=2))
        if len(lignes) == 10:
            break

    if not lignes:
        return render_template_string(
            PREVIEW_PAGE, erreur="Le fichier ne contient aucun événement."
        ), 400

    return render_template_string(PREVIEW_PAGE, lignes=lignes)
