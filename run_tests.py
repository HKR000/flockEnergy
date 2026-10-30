import os
import sys
import unittest

repo_root = os.path.abspath(os.path.dirname(__file__))
sys.path.insert(0, repo_root)

# Force offline mode during testing
os.environ["SYNC_ON_STARTUP"] = "false"
from app.config import settings
settings.SYNC_ON_STARTUP = False

from tests.test_client import test_hmac_signature_calculation, test_client_initialization_defaults
from tests.test_normalization import (
    test_normalize_meter_summary,
    test_normalize_meter_detail,
    test_consumption_summary_calculation,
)
from tests.test_hierarchy import test_build_hierarchy_tree
from tests.test_geo import test_haversine_distance_meters, test_find_nearby_meters
from tests.test_api import test_api_suite


class FullTestSuite(unittest.TestCase):
    def test_portal_client(self):
        test_hmac_signature_calculation()
        test_client_initialization_defaults()

    def test_normalization_and_calculations(self):
        test_normalize_meter_summary()
        test_normalize_meter_detail()
        test_consumption_summary_calculation()

    def test_network_hierarchy(self):
        test_build_hierarchy_tree()

    def test_geospatial(self):
        test_haversine_distance_meters()
        test_find_nearby_meters()

    def test_api_gateway_endpoints(self):
        test_api_suite()


if __name__ == "__main__":
    unittest.main()
