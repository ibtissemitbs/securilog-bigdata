# SecuriLog — Trace des tests Elasticsearch

Tests exécutés le **8 novembre 2026** depuis Ubuntu (WSL), avec Elasticsearch 8.19.0 et les index `securilog-test-*`. Les réponses ci-dessous sont des extraits des résultats observés pendant la séance. Les nombres peuvent évoluer après de nouveaux imports.

## 1. Rechercher un événement par son identifiant

```bash
curl -fsS -X POST 'http://127.0.0.1:9200/securilog-test-*/_search?pretty' \
  -H 'Content-Type: application/json' \
  -d '{"query":{"match_phrase":{"event_id":"test-002"}}}'
```

Extrait de la réponse observée (`hits.total`) :

```json
{
  "value": 2,
  "relation": "eq"
}
```

Les deux documents ont `event_id: test-002` et `event.outcome: success`. Ils se trouvent dans `securilog-test-2026.10.31` et `securilog-test-2026.11.07`.

## 2. Compter les échecs de connexion

```bash
curl -fsS -X POST 'http://127.0.0.1:9200/securilog-test-*/_count?pretty' \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {
      "bool": {
        "filter": [
          {"match_phrase": {"event.category": "authentication"}},
          {"match_phrase": {"event.outcome": "failure"}}
        ]
      }
    }
  }'
```

Extrait de la réponse observée :

```json
{
  "count": 13
}
```

## 3. Comparer les réussites et les échecs

```bash
curl -fsS -X POST 'http://127.0.0.1:9200/securilog-test-*/_search?pretty' \
  -H 'Content-Type: application/json' \
  -d '{
    "size": 0,
    "query": {"match_phrase": {"event.category": "authentication"}},
    "aggs": {
      "resultats_connexion": {
        "filters": {
          "filters": {
            "reussites": {"match_phrase": {"event.outcome": "success"}},
            "echecs": {"match_phrase": {"event.outcome": "failure"}}
          }
        }
      }
    }
  }'
```

Extrait de la réponse observée (`aggregations.resultats_connexion.buckets`) :

```json
{
  "echecs": {"doc_count": 13},
  "reussites": {"doc_count": 12}
}
```

La requête a trouvé **25 documents d’authentification**. Les trois fragments interrogés ont répondu sans erreur. Les compteurs portent sur les documents indexés.

## 4. Vérifier l’import JSONL depuis la WebApp — Semaine 3

Le 13 novembre 2026, la WebApp a affiché les 10 premiers événements en aperçu.
Après l’import, Elasticsearch a retrouvé les 11 documents du fichier déposé pour Logstash.

```bash
curl -fsS --max-time 10 'http://127.0.0.1:9200/securilog-test-*/_count?pretty' \
  -H 'Content-Type: application/json' \
  -d '{
    "query": {
      "match_phrase": {
        "log.file.path": "/ingest/import-15a65f34193f40c7bdb6bd4d1d2dc796.jsonl"
      }
    }
  }'
```

Réponse observée

```json
{
  "count": 11,
  "_shards": {
    "total": 4,
    "successful": 4,
    "skipped": 0,
    "failed": 0
  }
}
```
