from app.services.query import unsupported_numbers
from urbix_data.pipeline import normalize_complaint


def test_complaint_normalizer_drops_demographic_fields():
    row = normalize_complaint(
        {
            "cmplnt_num": "1",
            "cmplnt_fr_dt": "2026-01-02T00:00:00.000",
            "law_cat_cd": "FELONY",
            "ofns_desc": "ROBBERY",
            "boro_nm": "MANHATTAN",
            "latitude": "40.71",
            "longitude": "-74.00",
            "susp_race": "SHOULD_NOT_PERSIST",
            "vic_age_group": "SHOULD_NOT_PERSIST",
        }
    )
    assert "SHOULD_NOT_PERSIST" not in row.values()
    assert "susp_race" not in row
    assert row["law_category"] == "FELONY"


def test_summary_cannot_introduce_a_number():
    evidence = {"kpis": [{"value": 12.5, "unit": "mph"}]}
    assert unsupported_numbers("Mean link speed: 12.5 mph.", evidence) == []
    assert unsupported_numbers("Mean link speed: 99 mph.", evidence) == ["99"]
