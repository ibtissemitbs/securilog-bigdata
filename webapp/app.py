from flask import send_file
from tempfile import SpooledTemporaryFile
import csv
import io
import json
from redis.exceptions import RedisError
from hashlib import sha256
from datetime import date, datetime, timezone
from urllib.error import URLError
from urllib.request import Request as RequeteHTTP, urlopen
from datetime import date
import os
from datetime import datetime, timezone
from pathlib import Path
from tempfile import NamedTemporaryFile
from uuid import uuid4
from redis import Redis
from flask import Flask, jsonify, render_template_string, request, send_from_directory
from flask_swagger_ui import get_swaggerui_blueprint
from pymongo import MongoClient
from pymongo.errors import PyMongoError

COLONNES_CSV = ("timestamp", "event_id", "service", "category", "code", "outcome")
LIMITE_APERCU = 10

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 2 * 1024 * 1024
app.config["INGEST_DIRECTORY"] = Path("/ingest")
mongo = MongoClient(
    os.getenv("SECURILOG_MONGO_URI", "mongodb://mongodb:27017"),
    serverSelectionTimeoutMS=2000,
    connect=False,
)
collection_imports = mongo["securilog"]["imports"]
cache_redis = Redis(
    host="redis",
    port=6379,
    socket_connect_timeout=2,
    socket_timeout=2,
)

app.register_blueprint(
    get_swaggerui_blueprint(
        "/docs", "/openapi.json", config={"validatorUrl": None}
    )
)


@app.get("/openapi.json")
def specification_openapi():
    return send_from_directory(app.root_path, "openapi.json")

PREVIEW_PAGE = '\n<!doctype html>\n<html lang="fr">\n<head>\n    <meta charset="utf-8">\n    <title>Importer des logs | SecuriLog</title>\n\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<style id="securilog-import-design-v1">\n* { box-sizing: border-box; }\nbody { margin: 2rem auto; padding: 0 1.25rem 3rem; max-width: 80rem;\n       font: 1rem/1.6 system-ui, sans-serif; color: #172c3a; background: #f5f7f9; }\na { color: #1659a0; text-underline-offset: .2em; }\nnav { align-items: center; padding-bottom: 1.25rem; border-bottom: 1px solid #dbe3eb; }\nnav a { padding: .3rem 0; }\nnav a[aria-current="page"] { color: #172c3a; font-weight: 700; }\nh1 { font-size: clamp(1.8rem, 4vw, 2.5rem); line-height: 1.2; margin: 2rem 0 .75rem; }\nbody > p:first-of-type { color: #587086; margin-bottom: 1.5rem; }\nform { background: #fff; border: 1px solid #dbe3eb; border-radius: .75rem; padding: 1.5rem; }\nlabel { display: block; font-weight: 600; margin-bottom: .65rem; }\ninput[type="file"] { display: block; max-width: 100%; width: 100%; font: inherit;\n    border: 1px solid #aab8c4; background: #f8fafc; border-radius: .35rem; padding: .75rem; }\ninput::file-selector-button { font: inherit; background: #eaf1f7; color: #194970;\n    border: 1px solid #bdcddd; border-radius: .3rem; padding: .45rem .8rem; margin-right: 1rem; cursor: pointer; }\n.aide-import { color: #587086; font-size: .9rem; margin: .65rem 0 1.1rem; }\n.actions-import { display: flex; flex-wrap: wrap; gap: .65rem; }\nbutton { font: inherit; min-height: 44px; padding: .6rem 1rem; border-radius: .3rem;\n    background: #fff; border: 1px solid #aab8c4; color: #194970; cursor: pointer; }\nbutton[name="action"] { background: #194970; color: white; border-color: #194970; }\nbutton:hover { background: #eaf1f7; }\nbutton[name="action"]:hover { background: #123754; }\nbutton:disabled { opacity: .55; cursor: wait; }\n:focus-visible { outline: 3px solid #4e94cf; outline-offset: 3px; }\n[hidden] { display: none !important; }\n#erreur-taille:empty { display: none; }\n[role="alert"] { color: #922c39; border: 1px solid #efc5cc; background: #fff2f4;\n    padding: 1rem; border-radius: .5rem; overflow-wrap: anywhere; }\n[role="status"] { color: #12645f; background: #eaf7f4; border: 1px solid #b7ded5;\n    padding: 1rem; border-radius: .5rem; overflow-wrap: anywhere; }\nprogress { width: 100%; height: 1rem; margin-top: 1.25rem; accent-color: #194970; }\n#resultat-envoi { margin-top: 1.5rem; }\n#resultat-envoi:empty { display: none; }\nh2 { font-size: 1.4rem; margin: 1.5rem 0 1rem; }\nol { padding: 0; list-style-position: inside; counter-reset: evenement; }\nli { background: white; padding: 1rem 1.25rem; margin-bottom: 1rem;\n    border: 1px solid #dbe3eb; border-radius: .6rem; }\npre { font: .9rem/1.5 ui-monospace, monospace; white-space: pre-wrap;\n    overflow-wrap: anywhere; margin: .5rem 0; }\n@media (max-width: 600px) {\n    body { margin-top: 1rem; padding-inline: 1rem; }\n    form { padding: 1rem; }\n    .actions-import button { flex: 1 1 10rem; }\n}\n</style>\n\n\n<!-- securilog-theme-v1 -->\n<style>\nhtml[data-theme="dark"] { color-scheme: dark; background: #0c1522; }\nhtml[data-theme="dark"] body { background: #0c1522; color: #e3eaf2; }\nhtml[data-theme="dark"] :is(header, form, .resultats, .carte, .panneau, .centre, dialog) {\n    background: #172437; color: #e3eaf2; border-color: #3a4e65; }\nhtml[data-theme="dark"] :is(nav, th, td) { border-color: #3a4e65; }\nhtml[data-theme="dark"] th { background: #22354b; color: #edf4fc; }\nhtml[data-theme="dark"] :is(input, select, button) {\n    background: #142135; color: #e3eaf2; border-color: #678099; }\nhtml[data-theme="dark"] input::placeholder { color: #a8b9cc; opacity: 1; }\nhtml[data-theme="dark"] input::file-selector-button {\n    background: #294560; color: #edf4fc; border-color: #678099; }\nhtml[data-theme="dark"] button:hover { background: #294560; }\nhtml[data-theme="dark"] :is(button[type="submit"], button[name="action"], #actualiser) {\n    background: #286699; color: #fff; border-color: #629bca; }\nhtml[data-theme="dark"] a { color: #91c9ff; }\nhtml[data-theme="dark"] :is(a[aria-current], .marque) { color: #edf4fc; }\nhtml[data-theme="dark"] :is(.note, .nom-interne, .aide-import, body > p:first-of-type) { color: #afc1d5; }\nhtml[data-theme="dark"] .succes { color: #64dac5; }\nhtml[data-theme="dark"] .echecs { color: #ff919e; }\nhtml[data-theme="dark"] .statut { background: #263b54; color: #d9e8f9; }\nhtml[data-theme="dark"] .depose { background: #203d59; color: #a5d4ff; }\nhtml[data-theme="dark"] :is(.echec, [role="alert"]) {\n    background: #422635; color: #ffb8c2; border-color: #a56376; }\nhtml[data-theme="dark"] [role="status"] {\n    background: #163b39; color: #9ce5d7; border-color: #427a72; }\nhtml[data-theme="dark"] #resultat-envoi li {\n    background: #172437; color: #e3eaf2; border-color: #3a4e65; }\nhtml[data-theme="dark"] dialog::backdrop { background: #020810bb; }\nhtml[data-theme="dark"] :focus-visible { outline-color: #91c9ff; }\n#securilog-theme-toggle { font: inherit; line-height: 1.3; min-height: 44px;\n    padding: .55rem .85rem; border: 1px solid #8ba0b5; border-radius: .4rem;\n    background: #fff; color: #194970; cursor: pointer; white-space: nowrap; }\nhtml[data-theme="dark"] #securilog-theme-toggle { background: #22354b; color: #edf4fc; }\n</style>\n<script>\n(() => {\n    const cle = \'securilog-theme\';\n    const racine = document.documentElement;\n    const preference = window.matchMedia(\'(prefers-color-scheme: dark)\');\n    let choix = null;\n    try { choix = localStorage.getItem(cle); } catch (_) {}\n    if (choix !== \'dark\' && choix !== \'light\') choix = null;\n    function appliquer(theme) {\n        racine.dataset.theme = theme;\n        const bouton = document.getElementById(\'securilog-theme-toggle\');\n        if (bouton) {\n            bouton.textContent = theme === \'dark\' ? \'Mode clair\' : \'Mode sombre\';\n            bouton.setAttribute(\'aria-pressed\', String(theme === \'dark\'));\n        }\n    }\n    appliquer(choix || (preference.matches ? \'dark\' : \'light\'));\n    document.addEventListener(\'DOMContentLoaded\', () => {\n        const bouton = document.getElementById(\'securilog-theme-toggle\');\n        if (!bouton) return;\n        appliquer(racine.dataset.theme);\n        bouton.addEventListener(\'click\', () => {\n            choix = racine.dataset.theme === \'dark\' ? \'light\' : \'dark\';\n            appliquer(choix);\n            try { localStorage.setItem(cle, choix); } catch (_) {}\n        });\n    });\n    preference.addEventListener(\'change\', evenement => {\n        if (!choix) appliquer(evenement.matches ? \'dark\' : \'light\');\n    });\n    window.addEventListener(\'storage\', evenement => {\n        if (evenement.key !== cle) return;\n        choix = [\'dark\', \'light\'].includes(evenement.newValue) ? evenement.newValue : null;\n        appliquer(choix || (preference.matches ? \'dark\' : \'light\'));\n    });\n})();\n</script>\n\n</head>\n<body>\n<nav aria-label="Navigation principale" style="display:flex;flex-wrap:wrap;gap:1rem;margin:1rem 0">\n<a href="{{ url_for(\'tableau_de_bord\') }}">Tableau de bord</a>\n<a href="{{ url_for(\'page_evenements\') }}">Rechercher</a>\n<a href="{{ url_for(\'preview\') }}" aria-current="page">Importer</a>\n<a href="{{ url_for(\'page_fichiers_importes\') }}">Fichiers importés</a>\n<button id="securilog-theme-toggle" type="button" aria-label="Basculer le mode sombre" aria-pressed="false">Mode sombre</button>\n<a href="{{ url_for(\'page_analyses_kibana\') }}">Analyses Kibana</a>\n</nav>\n    <h1>Importer des logs</h1>\n    <p>Choisis un fichier JSONL ou CSV pour afficher ses 10 premiers événements ou l’importer.</p>\n\n    <form method="post" enctype="multipart/form-data">\n        <label for="fichier">Fichier de logs</label>\n        <input id="fichier" name="fichier" type="file" accept=".jsonl,.csv" required>\n        <p class="aide-import">Formats acceptés : JSONL et CSV · Taille inférieure à 2 Mio. La prévisualisation affiche les 10 premiers événements.</p>\n<div class="actions-import">\n<button type="submit">Prévisualiser</button>\n        <button type="submit" name="action" value="importer">Importer</button>\n    </div>\n</form>\n\n    <p id="erreur-taille" role="alert"></p>\n    <progress id="progression-envoi" max="100" aria-label="Progression de l’envoi" hidden></progress>\n    <div id="resultat-envoi">\n\n    {% if fichier_depose %}\n        <p role="status">Fichier déposé pour Logstash — {{ fichier_depose }}</p>\n    {% endif %}\n\n    {% if erreur %}\n        <p role="alert">{{ erreur }}</p>\n    {% endif %}\n\n    {% if lignes %}\n        <h2>{{ lignes|length }} événement(s) en aperçu</h2>\n        <ol>\n            {% for ligne in lignes %}\n                <li><pre>{{ ligne }}</pre></li>\n            {% endfor %}\n        </ol>\n    {% endif %}\n\n    </div>\n<script>\n        const champFichier = document.getElementById("fichier");\n        const message = document.getElementById("erreur-taille");\n        const limite = {{ config.MAX_CONTENT_LENGTH }};\n\n        function verifierTaille() {\n            const fichier = champFichier.files[0];\n            if (fichier && fichier.size >= limite) {\n                champFichier.value = "";\n                message.textContent = "Le fichier est trop volumineux. Choisis un fichier de moins de 2 Mio.";\n                return false;\n            }\n            message.textContent = "";\n            return true;\n        }\n\n        champFichier.addEventListener("change", verifierTaille);\n\tconst barre = document.getElementById("progression-envoi");\n\n        champFichier.form.addEventListener("submit", (evenement) => {\n            evenement.preventDefault();\n            if (!verifierTaille()) return;\n\n            const formulaire = evenement.currentTarget;\n            const donnees = new FormData(formulaire);\n            if (evenement.submitter?.name === "action") {\n                donnees.set("action", evenement.submitter.value);\n            }\n\n            const boutons = formulaire.querySelectorAll(\'button[type="submit"]\');\n            const requete = new XMLHttpRequest();\n            requete.open("POST", formulaire.getAttribute("action") || window.location.href);\n            requete.timeout = 30000;\n\n            barre.value = 0;\n            barre.hidden = false;\n            boutons.forEach((bouton) => { bouton.disabled = true; });\n\n            requete.upload.addEventListener("progress", (envoi) => {\n                if (envoi.lengthComputable && envoi.total > 0) {\n                    barre.value = 100 * envoi.loaded / envoi.total;\n                } else {\n                    barre.removeAttribute("value");\n                }\n            });\n\n            function afficherErreur() {\n                barre.hidden = true;\n                message.textContent = "La réponse du serveur est indisponible.";\n            }\n\n            requete.onload = () => {\n                const page = new DOMParser().parseFromString(requete.responseText, "text/html");\n                const resultat = page.getElementById("resultat-envoi");\n                if (!resultat) {\n                    afficherErreur();\n                    return;\n                }\n\n                document.getElementById("resultat-envoi").replaceWith(resultat);\n                if (requete.status >= 200 && requete.status < 300) {\n                    barre.value = 100;\n                } else {\n                    barre.hidden = true;\n                }\n            };\n\n            requete.onerror = afficherErreur;\n            requete.ontimeout = afficherErreur;\n            requete.onloadend = () => {\n                boutons.forEach((bouton) => { bouton.disabled = false; });\n            };\n\n            requete.send(donnees);\n        });\n    </script>\n</body>\n</html>\n'


@app.get("/")
def accueil():
    return jsonify(
        application="SecuriLog",
        message="Application Flask opérationnelle",
    )
@app.get("/evenements")
def page_evenements():
    return render_template_string('\n<!doctype html>\n<html lang="fr">\n<head>\n    <meta charset="utf-8">\n    <meta name="viewport" content="width=device-width, initial-scale=1">\n    <title>Événements | SecuriLog</title>\n    <style>\n        * { box-sizing: border-box; }\n        body { font: 1rem system-ui, sans-serif; color: #172c3a; background: #f5f7f9;\n               max-width: 80rem; margin: 2rem auto; padding: 0 1rem; }\n        a { color: #1659a0; }\n        h1 { margin-bottom: 1.5rem; }\n        form, .resultats { background: white; border: 1px solid #dbe1e7;\n                            border-radius: .6rem; padding: 1.25rem; }\n        .filtres { display: grid; grid-template-columns: repeat(auto-fit, minmax(10rem, 1fr));\n                   gap: 1rem; margin-bottom: 1rem; }\n        label { display: grid; gap: .35rem; }\n        input, select, button { font: inherit; border: 1px solid #aab8c4;\n                               border-radius: .25rem; padding: .5rem; }\n        input, select { width: 100%; min-width: 0; background: white; color: inherit; }\n        button { cursor: pointer; background: white; color: #17466d; }\n        button[type=submit] { background: #17466d; color: white; border-color: #17466d; }\n        button:disabled { cursor: default; opacity: .5; }\n        :focus-visible { outline: 3px solid #5e9bd1; outline-offset: 2px; }\n        .table-scroll { overflow-x: auto; }\n        table { width: 100%; border-collapse: collapse; }\n        th, td { text-align: left; padding: .65rem; border-bottom: 1px solid #e1e7ec; }\n        th { background: #edf2f6; white-space: nowrap; }\n        td { font-size: .9rem; }\n        nav { display: flex; align-items: center; flex-wrap: wrap; gap: 1rem; margin-top: 1rem; }\n        dialog { width: min(55rem, 95vw); max-height: 85vh; overflow: auto;\n                 border: 1px solid #aab8c4; border-radius: .6rem; padding: 1.5rem; }\n        dialog::backdrop { background: #12253699; }\n        .dialogue-titre { display: flex; justify-content: space-between; align-items: center; gap: 1rem; }\n        pre { white-space: pre-wrap; overflow-wrap: anywhere; font-size: .9rem; }\n        [hidden] { display: none !important; }\n    </style>\n\n<!-- securilog-theme-v1 -->\n<style>\nhtml[data-theme="dark"] { color-scheme: dark; background: #0c1522; }\nhtml[data-theme="dark"] body { background: #0c1522; color: #e3eaf2; }\nhtml[data-theme="dark"] :is(header, form, .resultats, .carte, .panneau, .centre, dialog) {\n    background: #172437; color: #e3eaf2; border-color: #3a4e65; }\nhtml[data-theme="dark"] :is(nav, th, td) { border-color: #3a4e65; }\nhtml[data-theme="dark"] th { background: #22354b; color: #edf4fc; }\nhtml[data-theme="dark"] :is(input, select, button) {\n    background: #142135; color: #e3eaf2; border-color: #678099; }\nhtml[data-theme="dark"] input::placeholder { color: #a8b9cc; opacity: 1; }\nhtml[data-theme="dark"] input::file-selector-button {\n    background: #294560; color: #edf4fc; border-color: #678099; }\nhtml[data-theme="dark"] button:hover { background: #294560; }\nhtml[data-theme="dark"] :is(button[type="submit"], button[name="action"], #actualiser) {\n    background: #286699; color: #fff; border-color: #629bca; }\nhtml[data-theme="dark"] a { color: #91c9ff; }\nhtml[data-theme="dark"] :is(a[aria-current], .marque) { color: #edf4fc; }\nhtml[data-theme="dark"] :is(.note, .nom-interne, .aide-import, body > p:first-of-type) { color: #afc1d5; }\nhtml[data-theme="dark"] .succes { color: #64dac5; }\nhtml[data-theme="dark"] .echecs { color: #ff919e; }\nhtml[data-theme="dark"] .statut { background: #263b54; color: #d9e8f9; }\nhtml[data-theme="dark"] .depose { background: #203d59; color: #a5d4ff; }\nhtml[data-theme="dark"] :is(.echec, [role="alert"]) {\n    background: #422635; color: #ffb8c2; border-color: #a56376; }\nhtml[data-theme="dark"] [role="status"] {\n    background: #163b39; color: #9ce5d7; border-color: #427a72; }\nhtml[data-theme="dark"] #resultat-envoi li {\n    background: #172437; color: #e3eaf2; border-color: #3a4e65; }\nhtml[data-theme="dark"] dialog::backdrop { background: #020810bb; }\nhtml[data-theme="dark"] :focus-visible { outline-color: #91c9ff; }\n#securilog-theme-toggle { font: inherit; line-height: 1.3; min-height: 44px;\n    padding: .55rem .85rem; border: 1px solid #8ba0b5; border-radius: .4rem;\n    background: #fff; color: #194970; cursor: pointer; white-space: nowrap; }\nhtml[data-theme="dark"] #securilog-theme-toggle { background: #22354b; color: #edf4fc; }\n</style>\n<script>\n(() => {\n    const cle = \'securilog-theme\';\n    const racine = document.documentElement;\n    const preference = window.matchMedia(\'(prefers-color-scheme: dark)\');\n    let choix = null;\n    try { choix = localStorage.getItem(cle); } catch (_) {}\n    if (choix !== \'dark\' && choix !== \'light\') choix = null;\n    function appliquer(theme) {\n        racine.dataset.theme = theme;\n        const bouton = document.getElementById(\'securilog-theme-toggle\');\n        if (bouton) {\n            bouton.textContent = theme === \'dark\' ? \'Mode clair\' : \'Mode sombre\';\n            bouton.setAttribute(\'aria-pressed\', String(theme === \'dark\'));\n        }\n    }\n    appliquer(choix || (preference.matches ? \'dark\' : \'light\'));\n    document.addEventListener(\'DOMContentLoaded\', () => {\n        const bouton = document.getElementById(\'securilog-theme-toggle\');\n        if (!bouton) return;\n        appliquer(racine.dataset.theme);\n        bouton.addEventListener(\'click\', () => {\n            choix = racine.dataset.theme === \'dark\' ? \'light\' : \'dark\';\n            appliquer(choix);\n            try { localStorage.setItem(cle, choix); } catch (_) {}\n        });\n    });\n    preference.addEventListener(\'change\', evenement => {\n        if (!choix) appliquer(evenement.matches ? \'dark\' : \'light\');\n    });\n    window.addEventListener(\'storage\', evenement => {\n        if (evenement.key !== cle) return;\n        choix = [\'dark\', \'light\'].includes(evenement.newValue) ? evenement.newValue : null;\n        appliquer(choix || (preference.matches ? \'dark\' : \'light\'));\n    });\n})();\n</script>\n\n</head>\n<body>\n<main>\n    <nav aria-label="Navigation principale" style="display:flex;flex-wrap:wrap;gap:1rem;margin:1rem 0">\n<a href="{{ url_for(\'tableau_de_bord\') }}">Tableau de bord</a>\n<a href="{{ url_for(\'page_evenements\') }}">Rechercher</a>\n<a href="{{ url_for(\'preview\') }}">Importer</a>\n<a href="{{ url_for(\'page_fichiers_importes\') }}">Fichiers importés</a>\n<button id="securilog-theme-toggle" type="button" aria-label="Basculer le mode sombre" aria-pressed="false">Mode sombre</button>\n<a href="{{ url_for(\'page_analyses_kibana\') }}">Analyses Kibana</a>\n</nav>\n    <h1>Rechercher des événements</h1>\n    <form id="formulaire" action="{{ url_for(\'rechercher_evenements\') }}" method="get">\n        <div class="filtres">\n            <label>Mot-clé <input name="q"></label>\n            <label>Du (UTC) <input type="date" name="debut"></label>\n            <label>Au (UTC) <input type="date" name="fin"></label>\n            <label>Service <input name="service" placeholder="windows"></label>\n            <label>Code <input name="code" placeholder="4624 ou 4625"></label>\n            <label>Résultat\n                <select name="resultat">\n                    <option value="">Tous</option>\n                    <option value="success">Succès</option>\n                    <option value="failure">Échec</option>\n                </select>\n            </label>\n            <label>Origine\n                <select name="origine">\n                    <option value="">Toutes</option>\n                    <option value="windows_real">Windows réel</option>\n                    <option value="simulated">Simulée</option>\n                </select>\n            </label>\n            <label>Niveau <input name="niveau" placeholder="info, error…"></label>\n            <label>Tri par date\n                <select name="ordre">\n                    <option value="desc">Plus récents d’abord</option>\n                    <option value="asc">Plus anciens d’abord</option>\n                </select>\n            </label>\n        </div>\n        <button type="submit">Rechercher</button>\n    <button id="exporter-csv" type="button">Exporter en CSV</button>\n    </form>\n    <p id="statut-export" role="status" aria-live="polite"></p>\n    <p id="statut" role="status" aria-live="polite">Renseigne tes filtres, puis lance la recherche.</p>\n    <section id="resultats" class="resultats" aria-label="Résultats de la recherche" hidden>\n        <div class="table-scroll">\n            <table>\n                <thead><tr>\n                    <th scope="col">Date (UTC)</th><th scope="col">Identifiant</th>\n                    <th scope="col">Service</th><th scope="col">Code</th>\n                    <th scope="col">Résultat</th><th scope="col">Origine</th>\n                    <th scope="col">Niveau</th><th scope="col">Détail</th>\n                </tr></thead>\n                <tbody id="lignes"></tbody>\n            </table>\n        </div>\n        <nav aria-label="Pagination">\n            <button id="precedent" type="button">Précédent</button>\n            <span id="page-courante"></span>\n            <button id="suivant" type="button">Suivant</button>\n        </nav>\n    </section>\n    <dialog id="detail" aria-labelledby="titre-detail">\n        <div class="dialogue-titre">\n            <h2 id="titre-detail">Détail de l’événement</h2>\n            <button id="fermer-detail" type="button" autofocus>Fermer</button>\n        </div>\n        <pre id="contenu-detail"></pre>\n    </dialog>\n</main>\n<script>\n    const formulaire = document.querySelector("#formulaire");\n    const bouton = formulaire.querySelector(\'button[type="submit"]\');\n    const statut = document.querySelector("#statut");\n    const resultats = document.querySelector("#resultats");\n    const lignes = document.querySelector("#lignes");\n    const precedent = document.querySelector("#precedent");\n    const suivant = document.querySelector("#suivant");\n    const pageCourante = document.querySelector("#page-courante");\n    const detail = document.querySelector("#detail");\n    const contenuDetail = document.querySelector("#contenu-detail");\n    let filtresActifs = null;\n    let page = 1;\n    let pagesAccessibles = 0;\n    let chargement = false;\n\n    async function chargerPage(numero) {\n        if (chargement || !filtresActifs) return;\n        chargement = true;\n        bouton.disabled = true;\n        precedent.disabled = true;\n        suivant.disabled = true;\n        resultats.hidden = true;\n        statut.textContent = "Recherche en cours…";\n        const parametres = new URLSearchParams(filtresActifs);\n        parametres.set("page", numero);\n        try {\n            const reponse = await fetch(`${formulaire.action}?${parametres}`);\n            const donnees = await reponse.json();\n            if (!reponse.ok) {\n                statut.textContent = donnees.erreur || "La recherche a échoué.";\n                return;\n            }\n            lignes.replaceChildren();\n            page = donnees.page;\n            pagesAccessibles = donnees.pages_accessibles;\n            for (const evenement of donnees.evenements) {\n                const ligne = lignes.insertRow();\n                const valeurs = [\n                    evenement["@timestamp"], evenement.event_id, evenement.service,\n                    evenement.event?.code, evenement.event?.outcome,\n                    evenement.data_origin, evenement.log?.level\n                ];\n                for (const valeur of valeurs) {\n                    ligne.insertCell().textContent = valeur ?? "—";\n                }\n                const ouvrir = document.createElement("button");\n                ouvrir.type = "button";\n                ouvrir.textContent = "Détail";\n                ouvrir.setAttribute("aria-label", `Détail de ${evenement.event_id || "l’événement"}`);\n                ouvrir.addEventListener("click", () => {\n                    contenuDetail.textContent = JSON.stringify(evenement, null, 2);\n                    detail.showModal();\n                });\n                ligne.insertCell().append(ouvrir);\n            }\n            const nombre = donnees.evenements.length;\n            resultats.hidden = nombre === 0;\n            if (nombre === 0) {\n                statut.textContent = "Aucun événement trouvé sur cette page.";\n            } else {\n                const debut = (page - 1) * donnees.taille_page + 1;\n                const fin = debut + nombre - 1;\n                statut.textContent = `${donnees.total} événement(s) trouvé(s) — résultats ${debut} à ${fin}.`;\n                pageCourante.textContent = `Page ${page} sur ${donnees.total_pages}`;\n                if (donnees.total_pages > pagesAccessibles) {\n                    statut.textContent += " Affichage limité aux 10 000 premiers résultats. Précise les filtres pour consulter les suivants.";\n                }\n            }\n        } catch {\n            statut.textContent = "Impossible de charger les résultats. Relance la recherche.";\n        } finally {\n            chargement = false;\n            bouton.disabled = false;\n            precedent.disabled = resultats.hidden || page <= 1;\n            suivant.disabled = resultats.hidden || page >= pagesAccessibles;\n        }\n    }\n    formulaire.addEventListener("submit", (event) => {\n        event.preventDefault();\n        filtresActifs = new URLSearchParams(new FormData(formulaire));\n        chargerPage(1);\n    });\n    precedent.addEventListener("click", () => chargerPage(page - 1));\n    suivant.addEventListener("click", () => chargerPage(page + 1));\n    document.querySelector("#fermer-detail").addEventListener("click", () => detail.close());\n\n    // Reprendre les filtres transmis par le tableau de bord.\n    const filtresURL = new URLSearchParams(window.location.search);\n    for (const [nom, valeur] of filtresURL) {\n        const champ = formulaire.elements.namedItem(nom);\n        if (champ) champ.value = valeur;\n    }\n    if (window.location.search) formulaire.requestSubmit();\n\n    const boutonExport = document.querySelector(\'#exporter-csv\');\n    const statutExport = document.querySelector(\'#statut-export\');\n    boutonExport.addEventListener(\'click\', async () => {\n        const parametres = new URLSearchParams(new FormData(formulaire));\n        boutonExport.disabled = true;\n        statutExport.textContent = \'Préparation du fichier CSV…\';\n        try {\n            const reponse = await fetch(`{{ url_for(\'exporter_evenements_csv\') }}?${parametres}`);\n            if (!reponse.ok) {\n                const erreur = await reponse.json();\n                statutExport.textContent = erreur.erreur || \'L’export a échoué.\';\n                return;\n            }\n            const fichier = await reponse.blob();\n            const adresse = URL.createObjectURL(fichier);\n            const lien = document.createElement(\'a\');\n            lien.href = adresse;\n            lien.download = \'securilog-evenements.csv\';\n            document.body.append(lien);\n            lien.click();\n            lien.remove();\n            setTimeout(() => URL.revokeObjectURL(adresse), 1000);\n            const nombre = reponse.headers.get(\'X-Export-Count\');\n            statutExport.textContent = `${nombre} événement(s) exporté(s). Le fichier est dans tes téléchargements.`;\n        } catch {\n            statutExport.textContent = \'Impossible de télécharger le CSV. Relance l’export.\';\n        } finally {\n            boutonExport.disabled = false;\n        }\n    });\n</script>\n</body>\n</html>\n')



def construire_requete_evenements():
    ordre = request.args.get("ordre", "desc")
    if ordre not in ("asc", "desc"):
        raise ValueError("Le tri doit être asc ou desc.")

    criteres = {}
    for nom in ("q", "debut", "fin", "service", "code", "resultat", "origine", "niveau"):
        valeur = request.args.get(nom, "").strip()
        if valeur:
            criteres[nom] = valeur

    requete = {
        "track_total_hits": True,
        "sort": [
            {"@timestamp": {"order": ordre, "missing": "_last", "unmapped_type": "date"}},
            {"_index": "asc"},
            {"_doc": "asc"},
        ],
        "query": {"match_all": {}},
    }

    if "q" in criteres:
        requete["query"] = {
            "multi_match": {
                "query": criteres["q"],
                "fields": ["event_id", "message"],
                "type": "phrase",
            }
        }

    debut_saisi = criteres.get("debut")
    fin_saisie = criteres.get("fin")

    try:
        debut = date.fromisoformat(debut_saisi) if debut_saisi else None
        fin = date.fromisoformat(fin_saisie) if fin_saisie else None
    except ValueError:
        raise ValueError("Saisis les dates au format AAAA-MM-JJ.") from None

    if debut and fin and debut > fin:
        raise ValueError("La date de début doit précéder ou égaler la date de fin.")

    filtres = []
    bornes = {}

    if debut:
        bornes["gte"] = f"{debut.isoformat()}T00:00:00Z"

    if fin:
        bornes["lt"] = f"{fin.isoformat()}T00:00:00Z||+1d"

    if bornes:
        filtres.append({"range": {"@timestamp": bornes}})

    if "origine" in criteres:
        filtres.append({"term": {"data_origin": criteres["origine"]}})

    champs_filtres = (
        ("service", "service"),
        ("code", "event.code"),
        ("resultat", "event.outcome"),
        ("niveau", "log.level"),
    )

    for parametre, champ in champs_filtres:
        valeur = criteres.get(parametre)
        if not valeur:
            continue

        champ_keyword = f"{champ}.keyword"
        filtres.append({
            "bool": {
                "should": [
                    {"term": {champ_keyword: valeur}},
                    {
                        "bool": {
                            "filter": [{"term": {champ: valeur}}],
                            "must_not": [{"exists": {"field": champ_keyword}}],
                        }
                    },
                ],
                "minimum_should_match": 1,
            }
        })

    if filtres:
        requete["query"] = {
            "bool": {
                "must": [requete["query"]],
                "filter": filtres,
            }
        }

    return requete, criteres, ordre


def requete_elasticsearch_export(chemin, donnees, methode="POST"):
    appel = RequeteHTTP(
        "http://elasticsearch:9200" + chemin,
        data=json.dumps(donnees).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method=methode,
    )
    with urlopen(appel, timeout=8) as reponse:
        return json.load(reponse)


def cellule_csv_evenement(valeur):
    if valeur is None:
        return ""
    if isinstance(valeur, (dict, list)):
        valeur = json.dumps(valeur, ensure_ascii=False)
    texte = str(valeur)
    # Conserver les textes de logs comme du texte lors de l’ouverture dans un tableur.
    if texte.lstrip().startswith(("=", "+", "-", "@")) or texte.startswith(("\t", "\r", "\n")):
        return "'" + texte
    return texte


@app.get("/export.csv")
def exporter_evenements_csv():
    try:
        requete, _criteres, _ordre = construire_requete_evenements()
    except ValueError as erreur:
        return jsonify(erreur=str(erreur)), 400

    requete["size"] = 1000
    fichier = SpooledTemporaryFile(max_size=1024 * 1024, mode="w+b")
    fichier.write(b"\xef\xbb\xbf")
    ligne_csv = io.StringIO(newline="")
    ecrivain = csv.writer(ligne_csv)
    colonnes = (
        "timestamp", "event_id", "service", "category", "code", "outcome",
        "data_origin", "level", "source_file", "message",
    )
    ecrivain.writerow(colonnes)
    fichier.write(ligne_csv.getvalue().encode("utf-8"))
    ligne_csv.seek(0)
    ligne_csv.truncate(0)
    curseur = None
    nombre_exporte = 0

    try:
        donnees = requete_elasticsearch_export(
            "/securilog-test-*/_search?scroll=1m&allow_partial_search_results=false",
            requete,
        )
        curseur = donnees.get("_scroll_id")
        total_attendu = donnees["hits"]["total"]["value"]

        while True:
            if donnees["timed_out"] or donnees["_shards"]["failed"]:
                raise ValueError("Les résultats Elasticsearch sont incomplets.")
            documents = donnees["hits"]["hits"]
            if not documents:
                break
            for document in documents:
                evenement = document["_source"]
                informations = evenement.get("event") or {}
                log = evenement.get("log") or {}
                valeurs = (
                    evenement.get("@timestamp"),
                    evenement.get("event_id"),
                    evenement.get("service"),
                    informations.get("category"),
                    informations.get("code"),
                    informations.get("outcome"),
                    evenement.get("data_origin"),
                    log.get("level"),
                    (log.get("file") or {}).get("path"),
                    evenement.get("message"),
                )
                ecrivain.writerow([cellule_csv_evenement(valeur) for valeur in valeurs])
            fichier.write(ligne_csv.getvalue().encode("utf-8"))
            ligne_csv.seek(0)
            ligne_csv.truncate(0)
            nombre_exporte += len(documents)
            if nombre_exporte >= total_attendu:
                break
            if not curseur:
                raise ValueError("Le curseur d’export Elasticsearch est absent.")
            donnees = requete_elasticsearch_export(
                "/_search/scroll", {"scroll": "1m", "scroll_id": curseur}
            )
            curseur = donnees.get("_scroll_id", curseur)

        if nombre_exporte != total_attendu:
            raise ValueError("Le nombre de documents exportés est incomplet.")
        fichier.seek(0)
        nom = "securilog-evenements-" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S") + ".csv"
        reponse = send_file(
            fichier,
            mimetype="text/csv; charset=utf-8",
            as_attachment=True,
            download_name=nom,
            conditional=False,
            etag=False,
            max_age=0,
        )
        reponse.headers["Cache-Control"] = "no-store"
        reponse.headers["X-Export-Count"] = str(nombre_exporte)
        reponse.call_on_close(fichier.close)
        return reponse
    except (URLError, TimeoutError, ValueError, KeyError, TypeError, AttributeError, OSError):
        fichier.close()
        app.logger.exception("Impossible de terminer l’export CSV")
        return jsonify(erreur="L’export a échoué. Réessaie dans un instant."), 503
    finally:
        ligne_csv.close()
        if curseur:
            try:
                requete_elasticsearch_export("/_search/scroll", {"scroll_id": [curseur]}, "DELETE")
            except (URLError, TimeoutError, ValueError, OSError):
                app.logger.warning("Impossible de fermer le curseur d’export", exc_info=True)


@app.get("/recherche")

def rechercher_evenements():
    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        return jsonify(erreur="Le numéro de page doit être un entier."), 400

    if page < 1:
        return jsonify(
            erreur="Le numéro de page doit être supérieur ou égal à 1."
        ), 400

    if page > 200:
        return jsonify(erreur="Précise les filtres pour rester dans les 10 000 premiers résultats."), 400

    taille_page = 50
    try:
        requete, criteres, ordre = construire_requete_evenements()
    except ValueError as erreur:
        return jsonify(erreur=str(erreur)), 400
    requete["from"] = (page - 1) * taille_page
    requete["size"] = taille_page

    requete_json = json.dumps(requete, sort_keys=True).encode("utf-8")
    cle_cache = f"securilog:recherche:v2:{sha256(requete_json).hexdigest()}"

    resultats = None

    try:
        valeur_cache = cache_redis.get(cle_cache)
        if valeur_cache is not None:
            resultats = json.loads(valeur_cache)
    except (RedisError, ValueError):
        app.logger.warning("Impossible de lire le cache Redis", exc_info=True)

    statut_cache = "HIT" if resultats is not None else "MISS"

    if resultats is None:
        appel = RequeteHTTP(
            "http://elasticsearch:9200/securilog-test-*/_search?preference=securilog-pagination",
            data=requete_json,
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        try:
            with urlopen(appel, timeout=5) as reponse_es:
                donnees = json.load(reponse_es)
                if donnees["timed_out"] or donnees["_shards"]["failed"]:
                    return jsonify(erreur="Recherche incomplète. Réessaie dans un instant."), 503
                resultats = donnees["hits"]
        except (URLError, TimeoutError):
            app.logger.exception("Échec de la recherche dans Elasticsearch")
            return jsonify(
                erreur="La recherche est temporairement indisponible."
            ), 503

        if not donnees["timed_out"] and donnees["_shards"]["failed"] == 0:
            try:
                cache_redis.set(cle_cache, json.dumps(resultats), ex=60)
            except RedisError:
                app.logger.warning(
                    "Impossible d’écrire dans le cache Redis",
                    exc_info=True,
                )

    total = resultats["total"]["value"]

    try:
        mongo["securilog"]["recherches"].insert_one({
            "date_recherche": datetime.now(timezone.utc),
            "criteres": criteres,
            "page": page,
            "ordre": ordre,
            "total": total,
        })
    except PyMongoError:
        app.logger.warning(
            "Impossible d’enregistrer la recherche dans MongoDB",
            exc_info=True,
        )

    reponse = jsonify(
        total=total,
        page=page,
        ordre=ordre,
        pages_accessibles=min(200, (total + taille_page - 1) // taille_page),
        taille_page=taille_page,
        total_pages=(total + taille_page - 1) // taille_page,
        evenements=[document["_source"] for document in resultats["hits"]],
    )
    reponse.headers["X-Cache"] = statut_cache
    return reponse

# BEGIN SECURILOG DASHBOARD
DASHBOARD_PAGE = '\n<!doctype html>\n<html lang="fr">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>Tableau de bord | SecuriLog</title>\n<style>\n* { box-sizing: border-box; }\nbody { margin: 0; color: #172c3a; background: #f5f7f9; font: 1rem system-ui, sans-serif; }\nheader { background: white; border-bottom: 1px solid #dbe1e7; }\nheader > div, main { max-width: 80rem; margin: auto; padding: 1.25rem; }\nheader > div { display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }\n.marque { font-size: 1.35rem; font-weight: 750; letter-spacing: -.03em; color: #17466d; }\nnav { display: flex; gap: 1.25rem; flex-wrap: wrap; }\na { color: #1659a0; text-underline-offset: .25rem; }\nnav a[aria-current] { color: #172c3a; font-weight: 650; }\nh1 { font-size: clamp(1.7rem, 3vw, 2.3rem); margin: 1rem 0 .5rem; letter-spacing: -.03em; }\n.intro, .note { color: #536878; }\nform { display: flex; flex-wrap: wrap; align-items: end; gap: 1rem; margin: 1.5rem 0; }\nlabel { display: grid; gap: .4rem; }\ninput, button { font: inherit; border: 1px solid #aab8c4; border-radius: .3rem; padding: .55rem .7rem; }\ninput { background: white; color: inherit; max-width: 100%; }\nbutton { background: #17466d; color: white; cursor: pointer; border-color: #17466d; }\nbutton:disabled { opacity: .6; cursor: wait; }\n:focus-visible { outline: 3px solid #6ba6d9; outline-offset: 3px; }\n.cartes { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 1rem; }\n.carte, .panneau { background: white; border: 1px solid #dbe1e7; border-radius: .6rem; padding: 1.25rem; }\n.carte p { margin: 0; }\n.carte strong { display: block; font-size: 2.25rem; line-height: 1.3; margin: .6rem 0 .3rem; font-variant-numeric: tabular-nums; }\n.carte a { display: inline-block; margin-top: .6rem; font-size: .9rem; }\n.succes { color: #0f766e; }\n.echecs { color: #b23c48; }\n.graphiques { display: grid; grid-template-columns: 1fr 1.6fr; gap: 1rem; margin-top: 1rem; }\nh2 { font-size: 1.1rem; margin: 0 0 1.25rem; }\n.repartition { display: flex; align-items: center; justify-content: space-evenly; gap: 1.5rem; flex-wrap: wrap; }\n.anneau { width: 11rem; height: 11rem; border-radius: 50%; background: #e2e8ee; display: grid; place-items: center; }\n.centre { width: 7.5rem; height: 7.5rem; border-radius: 50%; background: white; display: grid; place-content: center; text-align: center; }\n.centre strong { font-size: 1.6rem; }\nul { list-style: none; padding: 0; margin: 0; }\nli { margin: .6rem 0; }\n.point { display: inline-block; width: .7rem; height: .7rem; border-radius: 50%; margin-right: .5rem; }\n.vert { background: #0f766e; }.rouge { background: #b23c48; }.gris { background: #94a3b8; }\n.legende { display: flex; gap: 1rem; flex-wrap: wrap; font-size: .9rem; margin: .5rem 0 1rem; }\n.histogramme { display: flex; align-items: stretch; gap: .6rem; overflow-x: auto; padding-bottom: .5rem; }\n.jour { flex: 1 0 4.8rem; text-align: center; min-width: 4.8rem; }\n.valeur { font-size: .85rem; font-variant-numeric: tabular-nums; }\n.piste { height: 12rem; display: flex; align-items: end; justify-content: center; border-bottom: 1px solid #dbe1e7; }\n.barre { width: 2rem; display: flex; flex-direction: column-reverse; min-height: 0; }\n.segment { display: block; }\n.jour time { display: block; font-size: .75rem; margin-top: .7rem; white-space: nowrap; }\n.table-scroll { overflow-x: auto; }\ntable { width: 100%; border-collapse: collapse; margin-top: .75rem; }\nth, td { text-align: left; padding: .5rem; border-bottom: 1px solid #e1e7ec; }\n.note { font-size: .85rem; line-height: 1.6; }\n#etat { min-height: 1.5rem; }\n[hidden] { display: none !important; }\n@media (max-width: 900px) { .cartes { grid-template-columns: repeat(2, minmax(0, 1fr)); }.graphiques { grid-template-columns: 1fr; } }\n@media (max-width: 480px) { .cartes { grid-template-columns: 1fr; }form label { width: 100%; }input { width: 100%; } }\n</style>\n\n<!-- securilog-theme-v1 -->\n<style>\nhtml[data-theme="dark"] { color-scheme: dark; background: #0c1522; }\nhtml[data-theme="dark"] body { background: #0c1522; color: #e3eaf2; }\nhtml[data-theme="dark"] :is(header, form, .resultats, .carte, .panneau, .centre, dialog) {\n    background: #172437; color: #e3eaf2; border-color: #3a4e65; }\nhtml[data-theme="dark"] :is(nav, th, td) { border-color: #3a4e65; }\nhtml[data-theme="dark"] th { background: #22354b; color: #edf4fc; }\nhtml[data-theme="dark"] :is(input, select, button) {\n    background: #142135; color: #e3eaf2; border-color: #678099; }\nhtml[data-theme="dark"] input::placeholder { color: #a8b9cc; opacity: 1; }\nhtml[data-theme="dark"] input::file-selector-button {\n    background: #294560; color: #edf4fc; border-color: #678099; }\nhtml[data-theme="dark"] button:hover { background: #294560; }\nhtml[data-theme="dark"] :is(button[type="submit"], button[name="action"], #actualiser) {\n    background: #286699; color: #fff; border-color: #629bca; }\nhtml[data-theme="dark"] a { color: #91c9ff; }\nhtml[data-theme="dark"] :is(a[aria-current], .marque) { color: #edf4fc; }\nhtml[data-theme="dark"] :is(.note, .nom-interne, .aide-import, body > p:first-of-type) { color: #afc1d5; }\nhtml[data-theme="dark"] .succes { color: #64dac5; }\nhtml[data-theme="dark"] .echecs { color: #ff919e; }\nhtml[data-theme="dark"] .statut { background: #263b54; color: #d9e8f9; }\nhtml[data-theme="dark"] .depose { background: #203d59; color: #a5d4ff; }\nhtml[data-theme="dark"] :is(.echec, [role="alert"]) {\n    background: #422635; color: #ffb8c2; border-color: #a56376; }\nhtml[data-theme="dark"] [role="status"] {\n    background: #163b39; color: #9ce5d7; border-color: #427a72; }\nhtml[data-theme="dark"] #resultat-envoi li {\n    background: #172437; color: #e3eaf2; border-color: #3a4e65; }\nhtml[data-theme="dark"] dialog::backdrop { background: #020810bb; }\nhtml[data-theme="dark"] :focus-visible { outline-color: #91c9ff; }\n#securilog-theme-toggle { font: inherit; line-height: 1.3; min-height: 44px;\n    padding: .55rem .85rem; border: 1px solid #8ba0b5; border-radius: .4rem;\n    background: #fff; color: #194970; cursor: pointer; white-space: nowrap; }\nhtml[data-theme="dark"] #securilog-theme-toggle { background: #22354b; color: #edf4fc; }\n</style>\n<script>\n(() => {\n    const cle = \'securilog-theme\';\n    const racine = document.documentElement;\n    const preference = window.matchMedia(\'(prefers-color-scheme: dark)\');\n    let choix = null;\n    try { choix = localStorage.getItem(cle); } catch (_) {}\n    if (choix !== \'dark\' && choix !== \'light\') choix = null;\n    function appliquer(theme) {\n        racine.dataset.theme = theme;\n        const bouton = document.getElementById(\'securilog-theme-toggle\');\n        if (bouton) {\n            bouton.textContent = theme === \'dark\' ? \'Mode clair\' : \'Mode sombre\';\n            bouton.setAttribute(\'aria-pressed\', String(theme === \'dark\'));\n        }\n    }\n    appliquer(choix || (preference.matches ? \'dark\' : \'light\'));\n    document.addEventListener(\'DOMContentLoaded\', () => {\n        const bouton = document.getElementById(\'securilog-theme-toggle\');\n        if (!bouton) return;\n        appliquer(racine.dataset.theme);\n        bouton.addEventListener(\'click\', () => {\n            choix = racine.dataset.theme === \'dark\' ? \'light\' : \'dark\';\n            appliquer(choix);\n            try { localStorage.setItem(cle, choix); } catch (_) {}\n        });\n    });\n    preference.addEventListener(\'change\', evenement => {\n        if (!choix) appliquer(evenement.matches ? \'dark\' : \'light\');\n    });\n    window.addEventListener(\'storage\', evenement => {\n        if (evenement.key !== cle) return;\n        choix = [\'dark\', \'light\'].includes(evenement.newValue) ? evenement.newValue : null;\n        appliquer(choix || (preference.matches ? \'dark\' : \'light\'));\n    });\n})();\n</script>\n\n</head>\n<body>\n<header><div>\n    <span class="marque">SecuriLog</span>\n    <nav aria-label="Navigation principale">\n        <a href="{{ url_for(\'tableau_de_bord\') }}" aria-current="page">Tableau de bord</a>\n        <a href="{{ url_for(\'page_evenements\') }}">Rechercher</a>\n        <a href="{{ url_for(\'preview\') }}">Importer</a>\n    <a href="{{ url_for(\'page_fichiers_importes\') }}">Fichiers importés</a>\n<button id="securilog-theme-toggle" type="button" aria-label="Basculer le mode sombre" aria-pressed="false">Mode sombre</button>\n<a href="{{ url_for(\'page_analyses_kibana\') }}">Analyses Kibana</a>\n</nav>\n</div></header>\n<main>\n    <h1>Tableau de bord des événements</h1>\n    <p class="intro">Consulte les succès, les échecs et l’activité des événements enregistrés.</p>\n    <form id="filtres" action="{{ url_for(\'statistiques_dashboard\') }}">\n        <label>Service <input name="service" value="windows" placeholder="Tous les services si vide"></label>\n        <label>Du (UTC) <input type="date" name="debut"></label>\n        <label>Au (UTC) <input type="date" name="fin"></label>\n        <button type="submit">Actualiser</button>\n    </form>\n    <p id="etat" role="status" aria-live="polite">Chargement des statistiques…</p>\n    <div id="contenu" hidden>\n        <section class="cartes" aria-label="Indicateurs">\n            <article class="carte"><p>Événements</p><strong id="total">—</strong><a id="voir-tous" href="#">Voir les événements</a></article>\n            <article class="carte"><p>Succès</p><strong id="succes" class="succes">—</strong><a id="voir-succes" href="#">Voir les succès</a></article>\n            <article class="carte"><p>Échecs</p><strong id="echecs" class="echecs">—</strong><a id="voir-echecs" href="#">Voir les échecs</a></article>\n            <article class="carte"><p>Taux d’échec</p><strong id="taux">—</strong><p class="note">Parmi les événements avec résultat succès ou échec.</p></article>\n        </section>\n        <section class="graphiques" aria-label="Graphiques">\n            <article class="panneau">\n                <h2>Répartition des résultats</h2>\n                <div class="repartition">\n                    <div id="anneau" class="anneau" aria-hidden="true"><div class="centre"><strong id="total-anneau">—</strong><span>événements</span></div></div>\n                    <ul>\n                        <li><span class="point vert"></span>Succès <strong id="legende-succes"></strong></li>\n                        <li><span class="point rouge"></span>Échecs <strong id="legende-echecs"></strong></li>\n                        <li><span class="point gris"></span>Autre résultat ou absent <strong id="legende-autres"></strong></li>\n                    </ul>\n                </div>\n            </article>\n            <article class="panneau">\n                <h2>Événements par jour (UTC)</h2>\n                <div class="legende"><span><span class="point vert"></span>Succès</span><span><span class="point rouge"></span>Échecs</span><span><span class="point gris"></span>Autres</span></div>\n                <div id="histogramme" class="histogramme" aria-hidden="true"></div>\n                <p id="note-dates" class="note"></p>\n                <details><summary>Voir les valeurs du graphique</summary><div class="table-scroll"><table>\n                    <thead><tr><th scope="col">Date</th><th scope="col">Total</th><th scope="col">Succès</th><th scope="col">Échecs</th><th scope="col">Autres</th></tr></thead>\n                    <tbody id="valeurs-jours"></tbody>\n                </table></div></details>\n            </article>\n        </section>\n        <p class="note">Les compteurs représentent les documents enregistrés. Un événement importé plusieurs fois est compté plusieurs fois.</p>\n    </div>\n</main>\n<script>\nconst formulaire = document.querySelector(\'#filtres\');\nconst bouton = formulaire.querySelector(\'button\');\nconst etat = document.querySelector(\'#etat\');\nconst contenu = document.querySelector(\'#contenu\');\nconst nombre = new Intl.NumberFormat(\'fr-FR\');\nconst pourcentage = new Intl.NumberFormat(\'fr-FR\', {maximumFractionDigits: 1});\nlet chargement = false;\nfunction afficher(id, valeur) { document.getElementById(id).textContent = valeur; }\nfunction dessinerJours(donnees) {\n    const graphique = document.querySelector(\'#histogramme\');\n    const tableau = document.querySelector(\'#valeurs-jours\');\n    graphique.replaceChildren();\n    tableau.replaceChildren();\n    const jours = donnees.par_jour.slice(-30);\n    const maximum = Math.max(1, ...jours.map(jour => jour.total));\n    for (const jour of jours) {\n        const autres = Math.max(0, jour.total - jour.succes - jour.echecs);\n        const colonne = document.createElement(\'div\');\n        colonne.className = \'jour\';\n        const valeur = document.createElement(\'div\');\n        valeur.className = \'valeur\';\n        valeur.textContent = nombre.format(jour.total);\n        const piste = document.createElement(\'div\');\n        piste.className = \'piste\';\n        const barre = document.createElement(\'div\');\n        barre.className = \'barre\';\n        barre.style.height = `${100 * jour.total / maximum}%`;\n        for (const [compte, couleur] of [[jour.succes, \'vert\'], [jour.echecs, \'rouge\'], [autres, \'gris\']]) {\n            const segment = document.createElement(\'span\');\n            segment.className = `segment ${couleur}`;\n            segment.style.height = jour.total ? `${100 * compte / jour.total}%` : \'0%\';\n            barre.append(segment);\n        }\n        piste.append(barre);\n        const date = document.createElement(\'time\');\n        date.dateTime = jour.date;\n        date.textContent = jour.date;\n        colonne.append(valeur, piste, date);\n        graphique.append(colonne);\n        const ligne = tableau.insertRow();\n        for (const valeur of [jour.date, jour.total, jour.succes, jour.echecs, autres]) {\n            ligne.insertCell().textContent = typeof valeur === \'number\' ? nombre.format(valeur) : valeur;\n        }\n    }\n    let note = jours.length ? \'Chaque barre représente une journée.\' : \'Aucun événement daté sur cette sélection.\';\n    if (donnees.par_jour.length > 30) note += \' Les 30 dernières journées sont représentées. Les compteurs couvrent toute la sélection.\';\n    if (donnees.sans_date) note += ` ${nombre.format(donnees.sans_date)} événement(s) sans date sont exclus de ce graphique.`;\n    afficher(\'note-dates\', note);\n}\nasync function actualiser() {\n    if (chargement) return;\n    chargement = true;\n    bouton.disabled = true;\n    contenu.hidden = true;\n    etat.textContent = \'Chargement des statistiques…\';\n    const filtres = new URLSearchParams(new FormData(formulaire));\n    try {\n        const reponse = await fetch(`${formulaire.action}?${filtres}`);\n        const donnees = await reponse.json();\n        if (!reponse.ok) {\n            etat.textContent = donnees.erreur || \'Impossible de charger les statistiques.\';\n            return;\n        }\n        for (const cle of [\'total\', \'succes\', \'echecs\']) afficher(cle, nombre.format(donnees[cle]));\n        afficher(\'taux\', donnees.taux_echec === null ? \'—\' : `${pourcentage.format(donnees.taux_echec)} %`);\n        afficher(\'total-anneau\', nombre.format(donnees.total));\n        for (const cle of [\'succes\', \'echecs\', \'autres\']) afficher(`legende-${cle}`, nombre.format(donnees[cle]));\n        const finSucces = donnees.total ? 100 * donnees.succes / donnees.total : 0;\n        const finEchecs = donnees.total ? finSucces + 100 * donnees.echecs / donnees.total : 0;\n        document.querySelector(\'#anneau\').style.background = donnees.total\n            ? `conic-gradient(#0f766e 0% ${finSucces}%, #b23c48 ${finSucces}% ${finEchecs}%, #94a3b8 ${finEchecs}% 100%)`\n            : \'#e2e8ee\';\n        dessinerJours(donnees);\n        for (const [id, resultat] of [[\'voir-tous\', \'\'], [\'voir-succes\', \'success\'], [\'voir-echecs\', \'failure\']]) {\n            const parametres = new URLSearchParams(filtres);\n            if (resultat) parametres.set(\'resultat\', resultat);\n            document.getElementById(id).href = `{{ url_for(\'page_evenements\') }}?${parametres}`;\n        }\n        contenu.hidden = false;\n        etat.textContent = donnees.total === 0 ? \'Aucun événement pour ces filtres.\' : \'Statistiques actualisées à partir des événements enregistrés.\';\n    } catch {\n        etat.textContent = \'Impossible de joindre le serveur. Réessaie avec Actualiser.\';\n    } finally {\n        chargement = false;\n        bouton.disabled = false;\n    }\n}\nformulaire.addEventListener(\'submit\', event => { event.preventDefault(); actualiser(); });\nactualiser();\n</script>\n</body>\n</html>\n'

@app.get("/dashboard")
def tableau_de_bord():
    return render_template_string(DASHBOARD_PAGE)


def filtre_exact_dashboard(champ, valeur):
    champ_keyword = f"{champ}.keyword"
    return {
        "bool": {
            "should": [
                {"term": {champ_keyword: valeur}},
                {"bool": {
                    "filter": [{"term": {champ: valeur}}],
                    "must_not": [{"exists": {"field": champ_keyword}}],
                }},
            ],
            "minimum_should_match": 1,
        }
    }


@app.get("/stats")
def statistiques_dashboard():
    service = request.args.get("service", "").strip()
    debut_saisi = request.args.get("debut", "").strip()
    fin_saisie = request.args.get("fin", "").strip()
    try:
        debut = date.fromisoformat(debut_saisi) if debut_saisi else None
        fin = date.fromisoformat(fin_saisie) if fin_saisie else None
    except ValueError:
        return jsonify(erreur="Saisis les dates au format AAAA-MM-JJ."), 400
    if debut and fin and debut > fin:
        return jsonify(erreur="La date de début doit précéder ou égaler la date de fin."), 400

    filtres = []
    if service:
        filtres.append(filtre_exact_dashboard("service", service))
    bornes = {}
    if debut:
        bornes["gte"] = f"{debut.isoformat()}T00:00:00Z"
    if fin:
        bornes["lt"] = f"{fin.isoformat()}T00:00:00Z||+1d"
    if bornes:
        filtres.append({"range": {"@timestamp": bornes}})

    par_resultat = {
        "filters": {
            "filters": {
                "succes": filtre_exact_dashboard("event.outcome", "success"),
                "echecs": filtre_exact_dashboard("event.outcome", "failure"),
            }
        }
    }
    requete = {
        "size": 0,
        "track_total_hits": True,
        "query": {"bool": {"filter": filtres}},
        "aggs": {
            "resultats": par_resultat,
            "sans_date": {"missing": {"field": "@timestamp"}},
            "par_jour": {
                "date_histogram": {
                    "field": "@timestamp",
                    "calendar_interval": "day",
                    "time_zone": "UTC",
                    "format": "yyyy-MM-dd",
                    "min_doc_count": 0,
                },
                "aggs": {"resultats": par_resultat},
            },
        },
    }
    appel = RequeteHTTP(
        "http://elasticsearch:9200/securilog-test-*/_search?allow_partial_search_results=false",
        data=json.dumps(requete).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urlopen(appel, timeout=8) as reponse_es:
            donnees = json.load(reponse_es)
        if donnees.get("timed_out") or donnees["_shards"]["failed"]:
            return jsonify(erreur="Les statistiques sont incomplètes. Réessaie dans un instant."), 503
        total = donnees["hits"]["total"]["value"]
        aggs = donnees["aggregations"]
        succes = aggs["resultats"]["buckets"]["succes"]["doc_count"]
        echecs = aggs["resultats"]["buckets"]["echecs"]["doc_count"]
        serie = []
        for jour in aggs["par_jour"]["buckets"]:
            resultats = jour["resultats"]["buckets"]
            serie.append({
                "date": jour["key_as_string"],
                "total": jour["doc_count"],
                "succes": resultats["succes"]["doc_count"],
                "echecs": resultats["echecs"]["doc_count"],
            })
    except (URLError, TimeoutError, ValueError, KeyError, TypeError):
        app.logger.exception("Impossible de charger les statistiques Elasticsearch")
        return jsonify(erreur="Statistiques indisponibles. Réessaie dans un instant."), 503

    connus = succes + echecs
    return jsonify(
        total=total,
        succes=succes,
        echecs=echecs,
        autres=max(0, total - connus),
        taux_succes=round(100 * succes / connus, 1) if connus else None,
        taux_echec=round(100 * echecs / connus, 1) if connus else None,
        sans_date=aggs["sans_date"]["doc_count"],
        par_jour=serie,
        calcule_a=datetime.now(timezone.utc).isoformat(),
    )

# END SECURILOG DASHBOARD


# BEGIN SECURILOG FILES
FICHIERS_IMPORTES_PAGE = '\n<!doctype html>\n<html lang="fr">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>Fichiers importés | SecuriLog</title>\n<style>\n* { box-sizing: border-box; }\nbody { margin: 0; background: #f5f7f9; color: #172c3a; font: 1rem system-ui, sans-serif; }\nheader { background: white; border-bottom: 1px solid #dbe1e7; }\nheader > div, main { max-width: 80rem; margin: auto; padding: 1.25rem; }\nheader > div, .titre { display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }\n.marque { font-weight: 750; font-size: 1.35rem; color: #17466d; }\nnav { display: flex; gap: 1.25rem; flex-wrap: wrap; align-items: center; }\na { color: #1659a0; text-underline-offset: .25rem; }\na[aria-current] { color: #172c3a; font-weight: 650; }\nh1 { font-size: clamp(1.7rem, 3vw, 2.3rem); margin: 1rem 0 .5rem; letter-spacing: -.03em; }\n.note, .nom-interne { color: #536878; font-size: .9rem; line-height: 1.6; }\nbutton { font: inherit; border: 1px solid #aab8c4; border-radius: .3rem; padding: .55rem .8rem; color: #17466d; background: white; cursor: pointer; }\n#actualiser { background: #17466d; color: white; }\nbutton:disabled { opacity: .5; cursor: default; }\n:focus-visible { outline: 3px solid #6ba6d9; outline-offset: 3px; }\n.panneau { margin-top: 1rem; background: white; border: 1px solid #dbe1e7; border-radius: .6rem; padding: 1.25rem; }\n.table-scroll { overflow-x: auto; }\ntable { width: 100%; border-collapse: collapse; }\nth, td { text-align: left; padding: .85rem .65rem; border-bottom: 1px solid #e1e7ec; vertical-align: top; }\nth { background: #edf2f6; white-space: nowrap; }\n.nom-interne { display: block; font-size: .75rem; overflow-wrap: anywhere; }\n.statut { display: inline-block; padding: .2rem .5rem; border-radius: .25rem; background: #edf2f6; white-space: nowrap; }\n.depose { color: #17466d; background: #e6eff7; }\n.echec { color: #9b2938; background: #fcebef; }\n.pagination { margin-top: 1.25rem; }\n#etat { min-height: 1.5rem; }\n[hidden] { display: none !important; }\n</style>\n\n<!-- securilog-theme-v1 -->\n<style>\nhtml[data-theme="dark"] { color-scheme: dark; background: #0c1522; }\nhtml[data-theme="dark"] body { background: #0c1522; color: #e3eaf2; }\nhtml[data-theme="dark"] :is(header, form, .resultats, .carte, .panneau, .centre, dialog) {\n    background: #172437; color: #e3eaf2; border-color: #3a4e65; }\nhtml[data-theme="dark"] :is(nav, th, td) { border-color: #3a4e65; }\nhtml[data-theme="dark"] th { background: #22354b; color: #edf4fc; }\nhtml[data-theme="dark"] :is(input, select, button) {\n    background: #142135; color: #e3eaf2; border-color: #678099; }\nhtml[data-theme="dark"] input::placeholder { color: #a8b9cc; opacity: 1; }\nhtml[data-theme="dark"] input::file-selector-button {\n    background: #294560; color: #edf4fc; border-color: #678099; }\nhtml[data-theme="dark"] button:hover { background: #294560; }\nhtml[data-theme="dark"] :is(button[type="submit"], button[name="action"], #actualiser) {\n    background: #286699; color: #fff; border-color: #629bca; }\nhtml[data-theme="dark"] a { color: #91c9ff; }\nhtml[data-theme="dark"] :is(a[aria-current], .marque) { color: #edf4fc; }\nhtml[data-theme="dark"] :is(.note, .nom-interne, .aide-import, body > p:first-of-type) { color: #afc1d5; }\nhtml[data-theme="dark"] .succes { color: #64dac5; }\nhtml[data-theme="dark"] .echecs { color: #ff919e; }\nhtml[data-theme="dark"] .statut { background: #263b54; color: #d9e8f9; }\nhtml[data-theme="dark"] .depose { background: #203d59; color: #a5d4ff; }\nhtml[data-theme="dark"] :is(.echec, [role="alert"]) {\n    background: #422635; color: #ffb8c2; border-color: #a56376; }\nhtml[data-theme="dark"] [role="status"] {\n    background: #163b39; color: #9ce5d7; border-color: #427a72; }\nhtml[data-theme="dark"] #resultat-envoi li {\n    background: #172437; color: #e3eaf2; border-color: #3a4e65; }\nhtml[data-theme="dark"] dialog::backdrop { background: #020810bb; }\nhtml[data-theme="dark"] :focus-visible { outline-color: #91c9ff; }\n#securilog-theme-toggle { font: inherit; line-height: 1.3; min-height: 44px;\n    padding: .55rem .85rem; border: 1px solid #8ba0b5; border-radius: .4rem;\n    background: #fff; color: #194970; cursor: pointer; white-space: nowrap; }\nhtml[data-theme="dark"] #securilog-theme-toggle { background: #22354b; color: #edf4fc; }\n</style>\n<script>\n(() => {\n    const cle = \'securilog-theme\';\n    const racine = document.documentElement;\n    const preference = window.matchMedia(\'(prefers-color-scheme: dark)\');\n    let choix = null;\n    try { choix = localStorage.getItem(cle); } catch (_) {}\n    if (choix !== \'dark\' && choix !== \'light\') choix = null;\n    function appliquer(theme) {\n        racine.dataset.theme = theme;\n        const bouton = document.getElementById(\'securilog-theme-toggle\');\n        if (bouton) {\n            bouton.textContent = theme === \'dark\' ? \'Mode clair\' : \'Mode sombre\';\n            bouton.setAttribute(\'aria-pressed\', String(theme === \'dark\'));\n        }\n    }\n    appliquer(choix || (preference.matches ? \'dark\' : \'light\'));\n    document.addEventListener(\'DOMContentLoaded\', () => {\n        const bouton = document.getElementById(\'securilog-theme-toggle\');\n        if (!bouton) return;\n        appliquer(racine.dataset.theme);\n        bouton.addEventListener(\'click\', () => {\n            choix = racine.dataset.theme === \'dark\' ? \'light\' : \'dark\';\n            appliquer(choix);\n            try { localStorage.setItem(cle, choix); } catch (_) {}\n        });\n    });\n    preference.addEventListener(\'change\', evenement => {\n        if (!choix) appliquer(evenement.matches ? \'dark\' : \'light\');\n    });\n    window.addEventListener(\'storage\', evenement => {\n        if (evenement.key !== cle) return;\n        choix = [\'dark\', \'light\'].includes(evenement.newValue) ? evenement.newValue : null;\n        appliquer(choix || (preference.matches ? \'dark\' : \'light\'));\n    });\n})();\n</script>\n\n</head>\n<body>\n<header><div>\n    <span class="marque">SecuriLog</span>\n    <nav aria-label="Navigation principale">\n        <a href="{{ url_for(\'tableau_de_bord\') }}">Tableau de bord</a>\n        <a href="{{ url_for(\'page_evenements\') }}">Rechercher</a>\n        <a href="{{ url_for(\'preview\') }}">Importer</a>\n        <a href="{{ url_for(\'page_fichiers_importes\') }}" aria-current="page">Fichiers importés</a>\n    <button id="securilog-theme-toggle" type="button" aria-label="Basculer le mode sombre" aria-pressed="false">Mode sombre</button>\n<a href="{{ url_for(\'page_analyses_kibana\') }}">Analyses Kibana</a>\n</nav>\n</div></header>\n<main>\n    <div class="titre"><h1>Fichiers importés</h1><button id="actualiser" type="button">Actualiser</button></div>\n    <p class="note">Historique des imports enregistrés dans MongoDB, du plus récent au plus ancien.</p>\n    <p id="etat" role="status" aria-live="polite">Chargement des fichiers…</p>\n    <section id="contenu" class="panneau" aria-label="Liste des fichiers importés" hidden>\n        <div class="table-scroll"><table>\n            <thead><tr><th scope="col">Fichier</th><th scope="col">Date d’import (UTC)</th>\n            <th scope="col">Taille</th><th scope="col">Événements validés</th><th scope="col">Statut</th></tr></thead>\n            <tbody id="fichiers"></tbody>\n        </table></div>\n        <nav class="pagination" aria-label="Pagination">\n            <button id="precedent" type="button">Précédent</button>\n            <span id="page-courante"></span>\n            <button id="suivant" type="button">Suivant</button>\n        </nav>\n    </section>\n    <p class="note">« Déposé pour Logstash » indique que le fichier a été déposé pour traitement. Le nombre d’événements validés correspond au contrôle effectué par la WebApp avant le dépôt.</p>\n</main>\n<script>\nconst actualiser = document.querySelector(\'#actualiser\');\nconst etat = document.querySelector(\'#etat\');\nconst contenu = document.querySelector(\'#contenu\');\nconst lignes = document.querySelector(\'#fichiers\');\nconst precedent = document.querySelector(\'#precedent\');\nconst suivant = document.querySelector(\'#suivant\');\nconst entier = new Intl.NumberFormat(\'fr-FR\');\nconst formatDate = new Intl.DateTimeFormat(\'fr-FR\', {dateStyle: \'short\', timeStyle: \'medium\', timeZone: \'UTC\'});\nconst statuts = {preparation: \'Préparation\', depose: \'Déposé pour Logstash\', echec_depot: \'Échec du dépôt\'};\nlet page = 1;\nlet totalPages = 0;\nlet chargement = false;\nfunction afficherDate(valeur) {\n    if (!valeur) return \'—\';\n    const date = new Date(valeur);\n    return Number.isNaN(date.getTime()) ? valeur : formatDate.format(date);\n}\nasync function charger(numero) {\n    if (chargement) return;\n    chargement = true;\n    actualiser.disabled = true;\n    precedent.disabled = true;\n    suivant.disabled = true;\n    contenu.hidden = true;\n    etat.textContent = \'Chargement des fichiers…\';\n    try {\n        const reponse = await fetch(`{{ url_for(\'lister_fichiers_importes\') }}?page=${numero}`, {cache: \'no-store\'});\n        const donnees = await reponse.json();\n        if (!reponse.ok) {\n            etat.textContent = donnees.erreur || \'Impossible de charger les imports.\';\n            return;\n        }\n        lignes.replaceChildren();\n        page = donnees.page;\n        totalPages = donnees.total_pages;\n        for (const fichier of donnees.files) {\n            const ligne = lignes.insertRow();\n            const celluleNom = ligne.insertCell();\n            const nom = document.createElement(\'strong\');\n            nom.textContent = fichier.filename || \'Nom absent\';\n            const nomInterne = document.createElement(\'span\');\n            nomInterne.className = \'nom-interne\';\n            nomInterne.textContent = fichier.ingest_filename || \'\';\n            celluleNom.append(nom, nomInterne);\n            ligne.insertCell().textContent = afficherDate(fichier.created_at);\n            ligne.insertCell().textContent = fichier.size_bytes === null ? \'—\' : `${entier.format(fichier.size_bytes)} octets`;\n            const valides = fichier.counters.validated;\n            ligne.insertCell().textContent = valides === null ? \'—\' : entier.format(valides);\n            const statut = document.createElement(\'span\');\n            statut.className = \'statut\';\n            if (fichier.status === \'depose\') statut.classList.add(\'depose\');\n            if (fichier.status === \'echec_depot\') statut.classList.add(\'echec\');\n            statut.textContent = statuts[fichier.status] || fichier.status || \'Non renseigné\';\n            ligne.insertCell().append(statut);\n        }\n        contenu.hidden = donnees.files.length === 0;\n        document.querySelector(\'#page-courante\').textContent = `Page ${page} sur ${totalPages}`;\n        etat.textContent = donnees.total === 0 ? \'Aucun import enregistré. Utilise la page Importer pour déposer un fichier.\'\n            : contenu.hidden ? \'Aucun fichier sur cette page. Clique sur Actualiser pour revenir à la première page.\'\n            : `${entier.format(donnees.total)} import(s) enregistré(s) — ${donnees.files.length} affiché(s).`;\n    } catch {\n        etat.textContent = \'Impossible de joindre le serveur. Réessaie avec Actualiser.\';\n    } finally {\n        chargement = false;\n        actualiser.disabled = false;\n        precedent.disabled = contenu.hidden || page <= 1;\n        suivant.disabled = contenu.hidden || page >= totalPages;\n    }\n}\nactualiser.addEventListener(\'click\', () => charger(1));\nprecedent.addEventListener(\'click\', () => charger(page - 1));\nsuivant.addEventListener(\'click\', () => charger(page + 1));\ncharger(1);\n</script>\n</body>\n</html>\n'

@app.get("/fichiers-importes")
def page_fichiers_importes():
    return render_template_string(FICHIERS_IMPORTES_PAGE)


@app.get("/files")
def lister_fichiers_importes():
    try:
        page = int(request.args.get("page", "1"))
    except ValueError:
        return jsonify(erreur="Le numéro de page doit être un entier."), 400
    if page < 1:
        return jsonify(erreur="Le numéro de page doit être supérieur ou égal à 1."), 400

    taille_page = 50
    documents = []
    try:
        total = collection_imports.count_documents({}, maxTimeMS=3000)
        position = (page - 1) * taille_page
        if position < total:
            projection = {
                "filename": 1, "ingest_filename": 1, "created_at": 1,
                "size_bytes": 1, "status": 1, "counters.validated": 1,
            }
            with collection_imports.find({}, projection).sort([
                ("created_at", -1), ("_id", -1)
            ]).skip(position).limit(taille_page).max_time_ms(3000) as curseur:
                documents = list(curseur)
    except PyMongoError:
        app.logger.exception("Impossible de consulter les imports MongoDB")
        return jsonify(erreur="La liste des imports est indisponible. Vérifie que MongoDB est démarré."), 503

    fichiers = []
    for document in documents:
        date_creation = document.get("created_at")
        if isinstance(date_creation, datetime):
            if date_creation.tzinfo is None:
                date_creation = date_creation.replace(tzinfo=timezone.utc)
            date_creation = date_creation.astimezone(timezone.utc).isoformat()
        elif not isinstance(date_creation, str):
            date_creation = None
        compteurs = document.get("counters")
        valides = compteurs.get("validated") if isinstance(compteurs, dict) else None
        taille = document.get("size_bytes")
        fichiers.append({
            "id": str(document["_id"]),
            "filename": document.get("filename"),
            "ingest_filename": document.get("ingest_filename"),
            "created_at": date_creation,
            "size_bytes": taille if isinstance(taille, int) else None,
            "status": document.get("status"),
            "counters": {"validated": valides if isinstance(valides, int) else None},
        })

    reponse = jsonify(
        files=fichiers,
        total=total,
        page=page,
        taille_page=taille_page,
        total_pages=(total + taille_page - 1) // taille_page,
    )
    reponse.headers["Cache-Control"] = "no-store"
    return reponse

# END SECURILOG FILES

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
    extension = Path(fichier.filename).suffix.lower() if fichier else ""
    if extension not in {".jsonl", ".csv"}:
        return render_template_string(
            PREVIEW_PAGE, erreur="Choisis un fichier avec l’extension .jsonl ou .csv."
        ), 400

    try:
        if extension == ".csv":
            lignes = lire_csv(fichier)
        else:
            lignes = lire_jsonl(fichier)
    except ValueError as erreur:
        return render_template_string(PREVIEW_PAGE, erreur=str(erreur)), 400

    if request.form.get("action") != "importer":
        apercu = [
            json.dumps(ligne, ensure_ascii=False, indent=2)
            for ligne in lignes[:LIMITE_APERCU]
        ]
        return render_template_string(PREVIEW_PAGE, lignes=apercu)

    taille = fichier.stream.seek(0, os.SEEK_END)
    if extension == ".csv":
        lignes = [
            {
                "@timestamp": ligne["timestamp"],
                "event_id": ligne["event_id"],
                "service": ligne["service"],
                "event": {
                    "category": ligne["category"],
                    "code": ligne["code"],
                    "outcome": ligne["outcome"],
                },
            }
            for ligne in lignes
        ]

    return importer_evenements(fichier.filename, taille, lignes)


def lire_csv(fichier):
    lignes = []
    try:
        contenu = fichier.read().decode("utf-8-sig")
        lecteur = csv.DictReader(io.StringIO(contenu, newline=""), strict=True)

        if tuple(lecteur.fieldnames or []) != COLONNES_CSV:
            raise ValueError("En-tête CSV attendu : " + ", ".join(COLONNES_CSV))

        for ligne in lecteur:
            if None in ligne or any(
                valeur is None or not valeur.strip()
                for valeur in ligne.values()
            ):
                raise ValueError(
                    f"Ligne CSV {lecteur.line_num} : colonnes manquantes, vides ou en trop."
                )
            lignes.append(ligne)
    except (UnicodeDecodeError, csv.Error) as erreur:
        raise ValueError("Le fichier doit être un CSV valide en UTF-8.") from erreur

    if not lignes:
        raise ValueError("Le CSV ne contient aucun événement.")

    return lignes


def lire_jsonl(fichier):
    lignes = []
    for numero, ligne_brute in enumerate(fichier.stream, start=1):
        if not ligne_brute.strip():
            continue

        try:
            evenement = json.loads(ligne_brute.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as erreur:
            raise ValueError(f"La ligne {numero} doit contenir du JSON en UTF-8.") from erreur

        if not isinstance(evenement, dict):
            raise ValueError(f"La ligne {numero} doit contenir un objet JSON.")

        lignes.append(evenement)

    if not lignes:
        raise ValueError("Le fichier ne contient aucun événement.")

    return lignes


def deposer_fichier_ingest(dossier, nom, evenements):
    with NamedTemporaryFile(
        mode="w", encoding="utf-8", newline="\n", dir=dossier, suffix=".tmp", delete=False
    ) as temporaire:
        chemin = Path(temporaire.name)
        try:
            for evenement in evenements:
                temporaire.write(json.dumps(evenement, ensure_ascii=True) + "\n")

            temporaire.close()
            chemin.chmod(0o644)
            chemin.rename(dossier / nom)
        finally:
            chemin.unlink(missing_ok=True)


def importer_evenements(nom_original, taille, evenements):
    import_id = uuid4().hex
    nom_depose = f"import-{import_id}.jsonl"
    try:
        fiche = collection_imports.insert_one({
            "filename": nom_original,
            "ingest_filename": nom_depose,
            "created_at": datetime.now(timezone.utc),
            "size_bytes": taille,
            "status": "preparation",
            "counters": {"validated": len(evenements)},
        })
    except PyMongoError:
        app.logger.exception("Impossible d’enregistrer l’import dans MongoDB")
        return render_template_string(
            PREVIEW_PAGE, erreur="MongoDB est indisponible. Le fichier n’a pas été déposé."
        ), 503

    try:
        deposer_fichier_ingest(app.config["INGEST_DIRECTORY"], nom_depose, evenements)
    except OSError:
        app.logger.exception("Impossible de déposer le fichier pour Logstash")
        mettre_a_jour_statut(fiche.inserted_id, "echec_depot")
        return render_template_string(
            PREVIEW_PAGE, erreur="Le fichier n’a pas pu être déposé pour Logstash."
        ), 500

    if not mettre_a_jour_statut(fiche.inserted_id, "depose"):
        return render_template_string(
            PREVIEW_PAGE,
            fichier_depose=nom_depose,
            erreur="Le dépôt a réussi. La mise à jour du statut MongoDB a échoué.",
        ), 202

    return render_template_string(PREVIEW_PAGE, fichier_depose=nom_depose), 202


def mettre_a_jour_statut(import_id, statut):
    try:
        resultat = collection_imports.update_one({"_id": import_id}, {"$set": {"status": statut}})
    except PyMongoError:
        app.logger.exception("Impossible de mettre à jour le suivi de l’import %s", import_id)
        return False
    return resultat.matched_count == 1



# BEGIN SECURILOG KIBANA
KIBANA_PAGE = '\n<!doctype html>\n<html lang="fr">\n<head>\n<meta charset="utf-8">\n<meta name="viewport" content="width=device-width, initial-scale=1">\n<title>Analyses Kibana | SecuriLog</title>\n<style>\n* { box-sizing: border-box; }\nbody { margin: 0; background: #f5f7f9; color: #172c3a; font: 1rem system-ui, sans-serif; }\nheader { background: white; border-bottom: 1px solid #dbe1e7; }\nheader > div, main { max-width: 80rem; margin: auto; padding: 1.25rem; }\nheader > div, .titre { display: flex; align-items: center; justify-content: space-between; gap: 1rem; flex-wrap: wrap; }\n.marque { font-weight: 750; font-size: 1.35rem; color: #17466d; }\nnav { display: flex; gap: 1.25rem; flex-wrap: wrap; align-items: center; }\na { color: #1659a0; text-underline-offset: .25rem; }\na[aria-current] { color: #172c3a; font-weight: 650; }\nh1 { font-size: clamp(1.7rem, 3vw, 2.3rem); margin: 1rem 0 .5rem; letter-spacing: -.03em; }\n.note, .nom-interne { color: #536878; font-size: .9rem; line-height: 1.6; }\nbutton { font: inherit; border: 1px solid #aab8c4; border-radius: .3rem; padding: .55rem .8rem; color: #17466d; background: white; cursor: pointer; }\n#actualiser { background: #17466d; color: white; }\nbutton:disabled { opacity: .5; cursor: default; }\n:focus-visible { outline: 3px solid #6ba6d9; outline-offset: 3px; }\n.panneau { margin-top: 1rem; background: white; border: 1px solid #dbe1e7; border-radius: .6rem; padding: 1.25rem; }\n.table-scroll { overflow-x: auto; }\ntable { width: 100%; border-collapse: collapse; }\nth, td { text-align: left; padding: .85rem .65rem; border-bottom: 1px solid #e1e7ec; vertical-align: top; }\nth { background: #edf2f6; white-space: nowrap; }\n.nom-interne { display: block; font-size: .75rem; overflow-wrap: anywhere; }\n.statut { display: inline-block; padding: .2rem .5rem; border-radius: .25rem; background: #edf2f6; white-space: nowrap; }\n.depose { color: #17466d; background: #e6eff7; }\n.echec { color: #9b2938; background: #fcebef; }\n.pagination { margin-top: 1.25rem; }\n#etat { min-height: 1.5rem; }\n[hidden] { display: none !important; }\n</style>\n\n<!-- securilog-theme-v1 -->\n<style>\nhtml[data-theme="dark"] { color-scheme: dark; background: #0c1522; }\nhtml[data-theme="dark"] body { background: #0c1522; color: #e3eaf2; }\nhtml[data-theme="dark"] :is(header, form, .resultats, .carte, .panneau, .centre, dialog) {\n    background: #172437; color: #e3eaf2; border-color: #3a4e65; }\nhtml[data-theme="dark"] :is(nav, th, td) { border-color: #3a4e65; }\nhtml[data-theme="dark"] th { background: #22354b; color: #edf4fc; }\nhtml[data-theme="dark"] :is(input, select, button) {\n    background: #142135; color: #e3eaf2; border-color: #678099; }\nhtml[data-theme="dark"] input::placeholder { color: #a8b9cc; opacity: 1; }\nhtml[data-theme="dark"] input::file-selector-button {\n    background: #294560; color: #edf4fc; border-color: #678099; }\nhtml[data-theme="dark"] button:hover { background: #294560; }\nhtml[data-theme="dark"] :is(button[type="submit"], button[name="action"], #actualiser) {\n    background: #286699; color: #fff; border-color: #629bca; }\nhtml[data-theme="dark"] a { color: #91c9ff; }\nhtml[data-theme="dark"] :is(a[aria-current], .marque) { color: #edf4fc; }\nhtml[data-theme="dark"] :is(.note, .nom-interne, .aide-import, body > p:first-of-type) { color: #afc1d5; }\nhtml[data-theme="dark"] .succes { color: #64dac5; }\nhtml[data-theme="dark"] .echecs { color: #ff919e; }\nhtml[data-theme="dark"] .statut { background: #263b54; color: #d9e8f9; }\nhtml[data-theme="dark"] .depose { background: #203d59; color: #a5d4ff; }\nhtml[data-theme="dark"] :is(.echec, [role="alert"]) {\n    background: #422635; color: #ffb8c2; border-color: #a56376; }\nhtml[data-theme="dark"] [role="status"] {\n    background: #163b39; color: #9ce5d7; border-color: #427a72; }\nhtml[data-theme="dark"] #resultat-envoi li {\n    background: #172437; color: #e3eaf2; border-color: #3a4e65; }\nhtml[data-theme="dark"] dialog::backdrop { background: #020810bb; }\nhtml[data-theme="dark"] :focus-visible { outline-color: #91c9ff; }\n#securilog-theme-toggle { font: inherit; line-height: 1.3; min-height: 44px;\n    padding: .55rem .85rem; border: 1px solid #8ba0b5; border-radius: .4rem;\n    background: #fff; color: #194970; cursor: pointer; white-space: nowrap; }\nhtml[data-theme="dark"] #securilog-theme-toggle { background: #22354b; color: #edf4fc; }\n</style>\n<script>\n(() => {\n    const cle = \'securilog-theme\';\n    const racine = document.documentElement;\n    const preference = window.matchMedia(\'(prefers-color-scheme: dark)\');\n    let choix = null;\n    try { choix = localStorage.getItem(cle); } catch (_) {}\n    if (choix !== \'dark\' && choix !== \'light\') choix = null;\n    function appliquer(theme) {\n        racine.dataset.theme = theme;\n        const bouton = document.getElementById(\'securilog-theme-toggle\');\n        if (bouton) {\n            bouton.textContent = theme === \'dark\' ? \'Mode clair\' : \'Mode sombre\';\n            bouton.setAttribute(\'aria-pressed\', String(theme === \'dark\'));\n        }\n    }\n    appliquer(choix || (preference.matches ? \'dark\' : \'light\'));\n    document.addEventListener(\'DOMContentLoaded\', () => {\n        const bouton = document.getElementById(\'securilog-theme-toggle\');\n        if (!bouton) return;\n        appliquer(racine.dataset.theme);\n        bouton.addEventListener(\'click\', () => {\n            choix = racine.dataset.theme === \'dark\' ? \'light\' : \'dark\';\n            appliquer(choix);\n            try { localStorage.setItem(cle, choix); } catch (_) {}\n        });\n    });\n    preference.addEventListener(\'change\', evenement => {\n        if (!choix) appliquer(evenement.matches ? \'dark\' : \'light\');\n    });\n    window.addEventListener(\'storage\', evenement => {\n        if (evenement.key !== cle) return;\n        choix = [\'dark\', \'light\'].includes(evenement.newValue) ? evenement.newValue : null;\n        appliquer(choix || (preference.matches ? \'dark\' : \'light\'));\n    });\n})();\n</script>\n\n</head><body>\n<header><div>\n    <span class="marque">SecuriLog</span>\n    <nav aria-label="Navigation principale">\n        <a href="{{ url_for(\'tableau_de_bord\') }}">Tableau de bord</a>\n        <a href="{{ url_for(\'page_evenements\') }}">Rechercher</a>\n        <a href="{{ url_for(\'preview\') }}">Importer</a>\n        <a href="{{ url_for(\'page_fichiers_importes\') }}">Fichiers importés</a>\n    <button id="securilog-theme-toggle" type="button" aria-label="Basculer le mode sombre" aria-pressed="false">Mode sombre</button>\n<a href="{{ url_for(\'page_analyses_kibana\') }}" aria-current="page">Analyses Kibana</a>\n</nav>\n</div></header>\n<main>\n<h1>Analyses Kibana</h1>\n<p class="note">Explore les authentifications à l’aide des indicateurs et des filtres du dashboard Kibana.</p>\n<p><a class="ouvrir-kibana" href="{{ adresse_kibana }}" target="_blank" rel="noopener noreferrer">Ouvrir dans Kibana ↗</a></p>\n<p class="note">Si le tableau ne s’affiche pas, ouvre-le avec le bouton ci-dessus. Kibana doit être démarré sur cet ordinateur.</p>\n<iframe title="SecuriLog — Analyse des authentifications dans Kibana"\n        src="{{ adresse_integree }}" loading="lazy" referrerpolicy="strict-origin-when-cross-origin"\n        style="display:block;width:100%;height:80vh;min-height:650px;border:1px solid #678099;border-radius:.6rem;background:white;">\n</iframe>\n</main>\n</body></html>\n'
KIBANA_DASHBOARD_URL = 'http://localhost:5601/app/dashboards#/view/94c286d4-d3b2-4629-8c28-4079efb2eb39?_g=(filters:!(),refreshInterval:(pause:!t,value:60000),time:(from:now-30d%2Fd,to:now))'
KIBANA_EMBED_URL = 'http://localhost:5601/app/dashboards#/view/94c286d4-d3b2-4629-8c28-4079efb2eb39?embed=true&show-query-input=true&show-time-filter=true&_g=(filters:!(),refreshInterval:(pause:!t,value:60000),time:(from:now-30d%2Fd,to:now))'

@app.get("/analyses-kibana")
def page_analyses_kibana():
    return render_template_string(KIBANA_PAGE,
        adresse_kibana=KIBANA_DASHBOARD_URL, adresse_integree=KIBANA_EMBED_URL)
# END SECURILOG KIBANA
