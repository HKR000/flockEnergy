from app.services.network_service import NetworkService


def test_build_hierarchy_tree():
    sample_meters = [
        {
            "meterId": "M1",
            "hierarchy": {
                "zone": {"name": "Jaipur Zone 1", "code": "Z-01"},
                "circle": {"name": "Circle 1", "code": "C-01"},
                "division": {"name": "Division 1", "code": "D-01"},
                "subdivision": {"name": "Subdivision 1", "code": "SD-01"},
                "substation": {"name": "Substation 1", "code": "SS-01"},
                "feeder": {"name": "Feeder 1", "code": "F-001"},
                "dt": {"name": "DT 1", "code": "DT-001"},
            },
        },
        {
            "meterId": "M2",
            "hierarchy": {
                "zone": {"name": "Jaipur Zone 1", "code": "Z-01"},
                "circle": {"name": "Circle 1", "code": "C-01"},
                "division": {"name": "Division 1", "code": "D-01"},
                "subdivision": {"name": "Subdivision 1", "code": "SD-01"},
                "substation": {"name": "Substation 1", "code": "SS-01"},
                "feeder": {"name": "Feeder 1", "code": "F-001"},
                "dt": {"name": "DT 1", "code": "DT-001"},
            },
        },
        {
            "meterId": "M3",
            "hierarchy": {
                "zone": {"name": "Jaipur Zone 1", "code": "Z-01"},
                "circle": {"name": "Circle 1", "code": "C-01"},
                "division": {"name": "Division 1", "code": "D-01"},
                "subdivision": {"name": "Subdivision 1", "code": "SD-01"},
                "substation": {"name": "Substation 1", "code": "SS-01"},
                "feeder": {"name": "Feeder 2", "code": "F-002"},
                "dt": {"name": "DT 2", "code": "DT-002"},
            },
        },
    ]

    tree = NetworkService.build_hierarchy_tree(sample_meters)
    assert tree.total_meters == 3
    assert len(tree.zones) == 1

    zone = tree.zones[0]
    assert zone.code == "Z-01"
    assert zone.meter_count == 3
    assert len(zone.children) == 1

    circle = zone.children[0]
    assert circle.code == "C-01"
    assert circle.meter_count == 3
