from typing import Any, Dict, List, Optional
from app.models.hierarchy import HierarchyTreeNode, NetworkHierarchyResponse


class NetworkService:
    """Reconstructs and analyzes the utility network distribution hierarchy."""

    LEVELS = ["zone", "circle", "division", "subdivision", "substation", "feeder", "dt"]

    @staticmethod
    def build_hierarchy_tree(raw_meters: List[Dict[str, Any]]) -> NetworkHierarchyResponse:
        """Build a tree from raw meter hierarchy records.
        
        Topology:
        Zone -> Circle -> Division -> Subdivision -> Substation -> Feeder -> DT -> Meters
        """
        # Intermediate nested dictionary structure:
        # tree[zone_code] = {"name": ..., "code": ..., "meters": int, "children": { ... }}
        root_nodes: Dict[str, Dict[str, Any]] = {}

        for meter in raw_meters:
            h = meter.get("hierarchy") or {}

            current_dict = root_nodes
            for level in NetworkService.LEVELS:
                node_data = h.get(level)
                if not isinstance(node_data, dict):
                    continue

                code = node_data.get("code") or "UNKNOWN"
                name = node_data.get("name") or code

                if code not in current_dict:
                    current_dict[code] = {
                        "level": level,
                        "name": name,
                        "code": code,
                        "meter_count": 0,
                        "children": {},
                    }

                current_dict[code]["meter_count"] += 1
                current_dict = current_dict[code]["children"]

        def convert_dict_to_model(d: Dict[str, Any]) -> List[HierarchyTreeNode]:
            nodes = []
            for item in d.values():
                children_models = convert_dict_to_model(item["children"])
                nodes.append(
                    HierarchyTreeNode(
                        level=item["level"],
                        name=item["name"],
                        code=item["code"],
                        meter_count=item["meter_count"],
                        children=children_models,
                    )
                )
            nodes.sort(key=lambda n: n.code)
            return nodes

        zones = convert_dict_to_model(root_nodes)
        return NetworkHierarchyResponse(
            utility_name="Urja Power Distribution Utility",
            total_meters=len(raw_meters),
            zones=zones,
        )
