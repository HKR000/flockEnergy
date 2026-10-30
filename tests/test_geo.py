from app.models.common import GeoCoordinates
from app.models.meter import MeterSummary
from app.services.geo_service import GeoService, haversine_distance_meters


def test_haversine_distance_meters():
    lat1, lon1 = 26.9189, 75.7878
    lat2, lon2 = 26.9239, 75.8267
    dist = haversine_distance_meters(lat1, lon1, lat2, lon2)
    assert 3500 < dist < 4500
    assert haversine_distance_meters(lat1, lon1, lat1, lon1) == 0.0


def test_find_nearby_meters():
    m1 = MeterSummary(
        meter_id="M1",
        serial_no="S1",
        make="HPL",
        phase_type="single",
        install_status="Installed",
        coordinates=GeoCoordinates(latitude=26.9189, longitude=75.7878),
    )
    m2 = MeterSummary(
        meter_id="M2",
        serial_no="S2",
        make="Genus",
        phase_type="three",
        install_status="Installed",
        coordinates=GeoCoordinates(latitude=26.9200, longitude=75.7880),
    )
    m3 = MeterSummary(
        meter_id="M3",
        serial_no="S3",
        make="L&T",
        phase_type="single",
        install_status="Installed",
        coordinates=GeoCoordinates(latitude=28.6139, longitude=77.2090),
    )

    results = GeoService.find_nearby_meters(
        meters=[m1, m2, m3],
        latitude=26.9189,
        longitude=75.7878,
        radius_meters=1000.0,
    )

    assert len(results) == 2
    assert results[0].meter.meter_id == "M1"
    assert results[0].distance_meters == 0.0
    assert results[1].meter.meter_id == "M2"
