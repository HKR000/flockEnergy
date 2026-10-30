from app.services.meter_service import MeterService


def test_normalize_meter_summary():
    raw = {
        "meterId": "J100000",
        "serialNo": "SE33962",
        "make": "HPL",
        "phaseType": "single",
        "installStatus": "Installed",
        "installType": "Whole Current",
        "build": "legacy",
        "dtCode": "DT-001",
        "hierarchy": {
            "dt": {"name": "Malviya Nagar DT 1", "code": "DT-001"},
            "feeder": {"name": "Feeder 1", "code": "F-001"},
        },
        "geo": {"lat": 26.9389, "lng": 75.8309},
    }

    summary = MeterService.normalize_meter_summary(raw)
    assert summary.meter_id == "J100000"
    assert summary.serial_no == "SE33962"
    assert summary.make == "HPL"
    assert summary.phase_type == "single"
    assert summary.install_status == "Installed"
    assert summary.dt_code == "DT-001"
    assert summary.dt_name == "Malviya Nagar DT 1"
    assert summary.feeder_code == "F-001"
    assert summary.coordinates is not None
    assert round(summary.coordinates.latitude, 4) == 26.9389
    assert round(summary.coordinates.longitude, 4) == 75.8309


def test_normalize_meter_detail():
    raw = {
        "meterId": "J100001",
        "serialNo": "GE84132",
        "make": "L&T",
        "phaseType": "three",
        "installStatus": "Faulty",
        "installType": "CT Operated",
        "build": "v2",
        "hierarchy": {
            "zone": {"name": "Jaipur Zone 1", "code": "Z-01"},
            "circle": {"name": "Circle 1", "code": "C-01"},
            "division": {"name": "Division 1", "code": "D-01"},
            "subdivision": {"name": "Subdivision 1", "code": "SD-01"},
            "substation": {"name": "Substation 1", "code": "SS-01"},
            "feeder": {"name": "Feeder 2", "code": "F-002"},
            "dt": {"name": "Mansarovar DT 2", "code": "DT-002"},
        },
    }

    detail = MeterService.normalize_meter_detail(raw)
    assert detail.meter_id == "J100001"
    assert detail.make == "L&T"
    assert detail.hierarchy is not None
    assert detail.hierarchy.zone.code == "Z-01"
    assert detail.hierarchy.feeder.code == "F-002"
    assert detail.hierarchy.dt.name == "Mansarovar DT 2"
    assert "Manufacturer" in detail.nameplate_attributes
    assert detail.nameplate_attributes["Manufacturer"] == "L&T"


def test_consumption_summary_calculation():
    raw_readings = [
        {"timestamp": "23/06/2026 00:00", "kwh": "100.0", "kvah": "110.0", "voltR": "230.0"},
        {"timestamp": "23/06/2026 00:30", "kwh": "102.5", "kvah": "112.8", "voltR": "228.0"},
        {"timestamp": "23/06/2026 01:00", "kwh": "105.0", "kvah": "115.5", "voltR": "232.0"},
    ]

    readings = [MeterService.normalize_energy_reading(r) for r in raw_readings]
    summary = MeterService.calculate_consumption_summary(readings)

    assert summary.reading_count == 3
    assert summary.start_time == "23/06/2026 00:00"
    assert summary.end_time == "23/06/2026 01:00"
    assert summary.start_kwh == 100.0
    assert summary.end_kwh == 105.0
    assert summary.total_consumption_kwh == 5.0
    assert summary.min_voltage == 228.0
    assert summary.max_voltage == 232.0
    assert summary.avg_voltage == 230.0
