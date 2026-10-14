"""
SafeDrive AI - Defect Repair Cost & Risk Savings Calculator
Calculates repair volume, asphalt needed, labor minutes, materials, labor, equipment costs,
annual vehicle damage risk based on traffic volume, and net financial savings per defect.
"""

from typing import Dict, Any

ROAD_TRAFFIC_MAP = {
    "Highway": 50000,
    "Arterial": 20000,
    "Residential": 5000
}

# Mapping of Bangalore roads to road types
ROAD_TYPE_MAPPING = {
    "Hebbal Flyover": "Highway",
    "Marathahalli Bridge": "Highway",
    "Whitefield Main Road": "Highway",
    "Yelahanka Main Road": "Highway",
    "MG Road": "Arterial",
    "Old Airport Road": "Arterial",
    "Koramangala 80ft Road": "Arterial",
    "Indiranagar 100ft Road": "Arterial",
    "Silk Board Junction": "Arterial",
    "Malleshwaram 8th Cross": "Arterial",
    "Jayanagar 4th Block": "Arterial",
    "HSR Layout Sector 2": "Arterial",
    "Rajajinagar 1st Block": "Arterial",
    "Basavanagudi Bull Temple Rd": "Arterial",
    "Domlur Layout": "Residential"
}

def get_traffic_volume(road_name: str) -> int:
    if not road_name:
        return ROAD_TRAFFIC_MAP["Arterial"]
    
    for key, road_type in ROAD_TYPE_MAPPING.items():
        if key.lower() in road_name.lower():
            return ROAD_TRAFFIC_MAP[road_type]
            
    if any(k in road_name.lower() for k in ["highway", "flyover", "bridge", "expressway", "main road"]):
        return ROAD_TRAFFIC_MAP["Highway"]
    elif any(k in road_name.lower() for k in ["cross", "layout", "sector", "block", "street", "lane"]):
        return ROAD_TRAFFIC_MAP["Residential"]
    else:
        return ROAD_TRAFFIC_MAP["Arterial"]

def calculate_defect_cost(defect: Dict[str, Any]) -> Dict[str, Any]:
    depth_cm = float(defect.get("depth_cm", 5.0))
    width_cm = float(defect.get("width_cm", 30.0))
    length_cm = float(defect.get("length_cm", 40.0))
    road_name = defect.get("road_name") or defect.get("corridor") or ""

    volume_l = round((depth_cm * width_cm * length_cm * 0.6) / 1000.0, 2)
    asphalt_kg = round(volume_l * 2.4, 2)
    labor_min = round(max(15.0, volume_l * 2.0), 1)

    materials_cost = round(asphalt_kg * 0.5, 2)
    labor_cost = round(labor_min * 0.8, 2)
    equipment_cost = 50.0

    repair_cost = round(materials_cost + labor_cost + equipment_cost, 2)

    traffic = get_traffic_volume(road_name)
    damage_probability = min(depth_cm / 30.0, 0.5)
    damage_risk_annual = round(damage_probability * traffic * 150.0 * 365.0 / 1000.0, 2)
    net_savings = round(damage_risk_annual - repair_cost, 2)

    return {
        "defect_id": defect.get("id") or defect.get("raw_id"),
        "depth_cm": depth_cm,
        "width_cm": width_cm,
        "length_cm": length_cm,
        "volume_l": volume_l,
        "asphalt_kg": asphalt_kg,
        "labor_min": labor_min,
        "materials_cost": materials_cost,
        "labor_cost": labor_cost,
        "equipment_cost": equipment_cost,
        "repair_cost": repair_cost,
        "traffic_volume": traffic,
        "damage_probability": round(damage_probability, 4),
        "damage_risk_annual": damage_risk_annual,
        "net_savings": net_savings
    }
