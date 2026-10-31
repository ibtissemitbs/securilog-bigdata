# SecuriLog — Projet Big Data

Plateforme de centralisation, de recherche et de visualisation
des logs de sécurité et d’authentification.

## Réalisé par

Ibtissem Moussa — ITBS Nabeul

## Objectif

Faciliter l’analyse des événements d’authentification :
connexions réussies, tentatives échouées, adresses IP
et services concernés.

## Fonctionnalités prévues

- Importer un fichier de logs et prévisualiser son contenu.
- Traiter les événements avec Logstash.
- Indexer les événements dans Elasticsearch.
- Rechercher et filtrer les logs depuis une interface web.
- Visualiser les indicateurs dans des tableaux de bord.
- Consulter le statut et le bilan des imports.

## Technologies prévues

| Technologie | Rôle |
|---|---|
| Python / Flask | Application web et API |
| Logstash | Lecture, transformation et envoi des logs |
| Elasticsearch | Indexation et recherche des événements |
| Kibana | Visualisation et exploration des données |
| MongoDB | Métadonnées des imports et historique |
| Redis | Cache temporaire des résultats |
| Docker Compose | Déploiement des services |

## Organisation du travail

Le projet est planifié sur sept semaines.
Les tâches et leur avancement sont suivis dans Jira.

## État actuel

Semaine 1 : analyse des besoins et conception.
Le développement et le déploiement seront réalisés
pendant les étapes suivantes.

## Installation et démarrage

### Prérequis

- Git.
- Docker et Docker Compose.
- Sur Windows : Docker Desktop démarré et intégré à Ubuntu WSL 2.
- Une connexion Internet pour télécharger les images au premier lancement.
- Des ressources RAM et disque disponibles pour les six services.

### Récupérer le projet

```bash
git clone https://github.com/ibtissemitbs/securilog-bigdata.git
cd securilog-bigdata
```

### Vérifier la configuration

```bash
docker compose -p securilog -f compose.yaml config --quiet
```

L’absence de message indique que la configuration Compose est valide.

### Démarrer les services

```bash
docker compose -p securilog -f compose.yaml up -d --build
```

Le premier lancement télécharge les images et construit l’image Flask.

### Vérifier les conteneurs

```bash
docker compose -p securilog -f compose.yaml ps -a
```

Les six conteneurs doivent rester à l’état Up.

### Accès locaux

| Service | Adresse |
|---|---|
| Application Flask | http://localhost:8000 |
| Vérification Flask | http://localhost:8000/health |
| Elasticsearch | http://localhost:9200 |
| Kibana | http://localhost:5601 |

MongoDB et Redis sont accessibles aux conteneurs sur le réseau
du projet, sans publication de leurs ports sur Windows.

Cette configuration est destinée au développement local.
L’authentification Elasticsearch est désactivée et ses accès
publiés sont limités à l’adresse locale du PC.

## Vérifications techniques

### Flask

```bash
curl http://localhost:8000/health
```

Réponse attendue : `{"status":"ok"}`.
Ce contrôle vérifie Flask uniquement.

### Elasticsearch

```bash
curl "http://localhost:9200/_cluster/health?pretty"
```

### MongoDB

```bash
docker compose -p securilog -f compose.yaml exec mongodb mongosh --quiet --eval 'db.adminCommand({ping: 1})'
```

Réponse attendue : `{ ok: 1 }`.

### Redis

```bash
docker compose -p securilog -f compose.yaml exec redis redis-cli ping
```

Réponse attendue : `PONG`.

### Logstash

```bash
docker compose -p securilog -f compose.yaml logs --tail=50 logstash
```

Les logs doivent confirmer le démarrage du pipeline `main`.

## Test d’ingestion

Les fichiers dans `data/samples` contiennent des événements fictifs,
avec un événement JSON par ligne.

Copier le fichier de test dans le volume partagé :

```bash
docker compose -p securilog -f compose.yaml cp data/samples/test-auth-002.jsonl webapp:/ingest/test-auth-002.jsonl
```

Après le démarrage du pipeline et le traitement du fichier :

```bash
curl "http://localhost:9200/securilog-test-*/_search?q=event_id:test-002&pretty"
```

Le résultat doit contenir l’événement `test-002`.

Logstash mémorise sa progression dans le volume `ls_data` :
recopier un fichier déjà lu ne garantit pas une nouvelle ingestion.

Dans Kibana, créer une vue de données :

- Nom : `SecuriLog — Tests`.
- Motif d’index : `securilog-test-*`.
- Champ temporel : `@timestamp`.

Ouvrir Discover, choisir une période couvrant le test et rechercher :

```text
event_id : "test-002"
```

## Arrêt et reprise

Arrêter uniquement les services SecuriLog :

```bash
docker compose -p securilog -f compose.yaml stop
```

Les conteneurs et volumes sont conservés.

Redémarrer les services :

```bash
docker compose -p securilog -f compose.yaml start
```

## Avancement technique — Semaine 2

Réalisé :

- Configuration et démarrage des six services.
- Vérification de Flask, Elasticsearch, MongoDB et Redis.
- Lecture d’un fichier fictif par Logstash.
- Indexation et recherche de l’événement dans Elasticsearch.
- Consultation de l’événement dans Kibana.

À poursuivre :

- Sélection et analyse des données du projet.
- Définition du mapping Elasticsearch métier.
- Vérification des connexions de Flask aux bases.
- Développement de l’import depuis l’interface web.

Le pipeline actuel utilise des index de test `securilog-test-*`.
Les fichiers sont déposés par commande ; le formulaire d’import
n’est pas encore développé.
