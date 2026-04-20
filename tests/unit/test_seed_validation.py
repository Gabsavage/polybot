"""Validate config/tracked_wallets_seed.yaml against its JSON schema."""

import json
from pathlib import Path

import jsonschema
import yaml

ROOT = Path(__file__).parents[2]
SEED_PATH = ROOT / "config" / "tracked_wallets_seed.yaml"
SCHEMA_PATH = ROOT / "config" / "schemas" / "tracked_wallets_seed.schema.json"


def _load():
    with open(SEED_PATH) as f:
        data = yaml.safe_load(f)
    with open(SCHEMA_PATH) as f:
        schema = json.load(f)
    return data, schema


def test_seed_validates_against_schema():
    """The seed YAML must conform to the JSON schema."""
    data, schema = _load()
    jsonschema.validate(instance=data, schema=schema)


def test_seed_has_wallets():
    """Seed list must contain at least one wallet."""
    data, _ = _load()
    assert len(data["wallets"]) >= 1


def test_all_addresses_are_unique():
    """No duplicate addresses."""
    data, _ = _load()
    addresses = [w["address"] for w in data["wallets"]]
    assert len(addresses) == len(set(addresses))


def test_all_addresses_are_checksumless_lowercase():
    """Addresses should be lowercase hex (no EIP-55 mixed case)."""
    data, _ = _load()
    for w in data["wallets"]:
        assert w["address"] == w["address"].lower(), f"{w['alias']} address not lowercase"


def test_tier_a_wallets_have_rationale():
    """Every Tier A wallet must have at least one signal."""
    data, _ = _load()
    for w in data["wallets"]:
        if w["tier"] == "A":
            signals = w["selection_rationale"]["tier_a_signals"]
            assert len(signals) >= 1, f"{w['alias']} has no tier_a_signals"
