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
