class TrafficImpactAnalyzer:
    """
    Traffic Impact & Volume Priority Scoring Engine.
    Computes vehicle traffic volume per day per hotspot corridor and formulates municipal priority scores:
    Priority Score = f(vehicles_per_day, severity_weight, growth_rate)
    """
    def __init__(self):
        # Default corridor daily traffic volume database (vehicles/day)
        self.corridor_traffic = {
            "Market St & 5th St Corridor": 42000,
            "Golden Park South Avenue": 28000,
            "Tenderloin District Intersection": 51000,
            "Mission District 16th St Transit": 34000,
            "Potrero Hill Heavy Freight Zone": 39000
        }

    def compute_priority_score(self, vehicles_per_day, severity_str="high", growth_rate_daily=0.03):
        """
        Formulates municipal priority score (0 to 100 scale).
        
        :param vehicles_per_day: Daily vehicle count on corridor
        :param severity_str: Severity string ('high', 'medium', 'low')
        :param growth_rate_daily: Predicted daily degradation growth rate
        :return: dict with {priority_score, priority_rank, dispatch_urgency}
        """
        sev_weights = {"high": 1.0, "medium": 0.65, "low": 0.35}
        w_sev = sev_weights.get(severity_str.lower(), 0.5)

        # Traffic volume normalized factor (0 to 1 scale for up to 60,000 vpd)
        norm_traffic = min(1.0, vehicles_per_day / 50000.0)

        # Priority formulation: 50% traffic volume + 35% severity + 15% growth rate
        score = (norm_traffic * 50.0) + (w_sev * 35.0) + (min(1.0, growth_rate_daily * 20.0) * 15.0)
        score = round(min(100.0, max(5.0, score)), 1)

        if score >= 75.0:
            urgency = "DISPATCH IMMEDIATE (24-48 Hours)"
            rank = "P1_URGENT"
        elif score >= 50.0:
            urgency = "SCHEDULED REPAIR (7 Days)"
            rank = "P2_HIGH"
        else:
            urgency = "ROUTINE MAINTENANCE (30 Days)"
            rank = "P3_ROUTINE"

        return {
            "priority_score": score,
            "vehicles_per_day": vehicles_per_day,
            "priority_rank": rank,
            "dispatch_urgency": urgency
        }

    def evaluate_hotspot_traffic(self, hotspots):
        """Attaches traffic volume metrics & priority scores to a list of municipal hotspots."""
        enriched = []
        for h in hotspots:
            name = h.get("name", f"Hotspot #{h.get('hotspot_id', 1)}")
            vpd = self.corridor_traffic.get(name, 25000 + (h.get("defect_count", 5) * 1200))
            p_res = self.compute_priority_score(vpd, severity_str=h.get("risk_level", "HIGH").lower())
            
            h_copy = dict(h)
            h_copy["vehicles_per_day"] = vpd
            h_copy["priority_score"] = p_res["priority_score"]
            h_copy["dispatch_urgency"] = p_res["dispatch_urgency"]
            enriched.append(h_copy)

        enriched.sort(key=lambda item: item["priority_score"], reverse=True)
        return enriched
