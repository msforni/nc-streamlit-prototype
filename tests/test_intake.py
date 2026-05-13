"""Tests for engine.intake — CSV schema validation."""

import pandas as pd
import pytest

from engine import intake


def _base_df():
    return pd.DataFrame({
        "segment_id": ["S-001", "S-002"],
        "estate": ["Laem Chabang", "Laem Chabang"],
        "typology": ["T1", "T2"],
        "area_m2": [5000, 4000],
        "offtaker_type": ["iea_direct", "tenant"],
        "tenant_name": [None, "Tenant X"],
        "tenant_tier": [None, "B"],
        "self_consumption_pct": [0.85, 0.85],
    })


def test_valid_df_passes():
    df = _base_df()
    result = intake.validate(df)
    assert result.is_valid, f"Expected valid but got errors: {result.errors}"


def test_missing_required_column_fails():
    df = _base_df().drop(columns=["typology"])
    result = intake.validate(df)
    assert not result.is_valid
    assert any("Missing required columns" in e for e in result.errors)


def test_invalid_typology_fails():
    df = _base_df()
    df.loc[0, "typology"] = "T99"
    result = intake.validate(df)
    assert not result.is_valid
    assert any("Invalid typology" in e for e in result.errors)


def test_t1_at_lat_krabang_fails():
    df = _base_df()
    df.loc[0, "estate"] = "Lat Krabang"  # T1 invalid here
    result = intake.validate(df)
    assert not result.is_valid
    assert any("land-lease" in e for e in result.errors)


def test_t1_at_lamphun_fails():
    df = _base_df()
    df.loc[0, "estate"] = "Lamphun"  # T1 invalid here
    result = intake.validate(df)
    assert not result.is_valid


def test_bess_at_lc_warns_but_not_fails():
    df = _base_df()
    df.loc[1, "typology"] = "BESS"
    df["kwh_capacity"] = [None, 5000]
    result = intake.validate(df)
    assert result.is_valid, f"BESS at LC should warn not fail; errors: {result.errors}"
    assert any("LC" in w or "BESS" in w for w in result.warnings)


def test_invalid_offtaker_type_fails():
    df = _base_df()
    df.loc[0, "offtaker_type"] = "weird_value"
    result = intake.validate(df)
    assert not result.is_valid


def test_self_consumption_out_of_range_fails():
    df = _base_df()
    df.loc[0, "self_consumption_pct"] = 1.5
    result = intake.validate(df)
    assert not result.is_valid


def test_missing_tenant_tier_defaults_to_c():
    df = _base_df()
    df.loc[1, "tenant_tier"] = None
    result = intake.validate(df)
    assert result.is_valid  # warning only
    assert any("tier C" in w for w in result.warnings)


def test_normalize_drops_bess_at_lc():
    df = _base_df()
    df.loc[1, "typology"] = "BESS"
    df["kwh_capacity"] = [None, 5000]
    normalized = intake.normalize(df)
    # BESS at LC is excluded
    assert not (
        (normalized["typology"] == "BESS") &
        (normalized["estate"] == "Laem Chabang")
    ).any()
