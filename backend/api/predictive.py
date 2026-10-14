"""
SafeDrive AI - Predictive Hotspot Detection API Blueprint
Provides REST endpoint for 30-day ML pothole formation predictions.
"""

from flask import Blueprint, jsonify, request
try:
    from backend.analytics.predictive_hotspot import get_predictive_hotspot_data
except ImportError:
    import sys, os
    sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    from backend.analytics.predictive_hotspot import get_predictive_hotspot_data

predictive_bp = Blueprint('predictive_bp', __name__)

@predictive_bp.route('/api/predictive/hotspots', methods=['GET'])
def get_predictive_hotspots():
    """
    GET /api/predictive/hotspots
    Returns 30-day predicted pothole formation hotspot grid cells, ML metrics, and feature importances.
    """
    try:
        data = get_predictive_hotspot_data()
        
        # Optional filter by min_risk
        min_risk = request.args.get('min_risk', type=float)
        if min_risk is not None and data.get('hotspots'):
            filtered = [h for h in data['hotspots'] if h['predicted_risk_pct'] >= min_risk]
            data['hotspots'] = filtered
            data['summary']['filtered_count'] = len(filtered)
            
        return jsonify(data), 200
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500
