# Polycasquette

Bot d'analyse Polymarket : collecte, traitement et analyse de données on-chain et off-chain.

## Structure

```
├── data/
│   ├── raw/            # Données brutes (API, scraping)
│   ├── processed/      # Données nettoyées / transformées
│   └── ground_truth/   # Résolutions vérifiées des marchés
├── notebooks/          # Exploration et analyse
├── docs/               # Documentation
```

## Setup

```bash
cp .env.example .env   # Remplir les clés API
uv sync                # Installer les dépendances
```
