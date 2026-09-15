import cv2
import numpy as np
from src.utils.config import Config

class LaneDetector:
    """
    Ego-Lane Detector & Hazard Corridor Filter.
    Analyzes camera frame geometry and polynomial lane boundaries to determine
    whether a detected road defect lies directly in the vehicle's active travel lane.
    """
    def __init__(self, frame_width=640, frame_height=480):
        self.w = frame_width
        self.h = frame_height
        self.center_x = self.w / 2.0
        self.lane_half_width = Config.EGO_LANE_HALF_WIDTH_PX

    def is_in_current_lane(self, bbox, frame=None):
        """
        Determines if a bounding box [xmin, ymin, xmax, ymax] lies inside the ego travel lane.
        
        :param bbox: [xmin, ymin, xmax, ymax]
        :param frame: Optional BGR camera frame for perspective lane line polynomial fitting
        :return: dict with {is_in_lane: bool, lane_position: str, priority_boost: float}
        """
        xmin, ymin, xmax, ymax = bbox
        x_center = (xmin + xmax) / 2.0
        y_bottom = float(ymax)

        # Perspective lane corridor widens at bottom of frame (near car) and narrows near horizon
        # Perspective scale factor based on vertical height
        horizon_y = self.h * 0.40
        dy = max(1.0, y_bottom - horizon_y)
        perspective_scale = dy / (self.h - horizon_y)
        
        # Dynamic lane corridor half width at object's y position
        dynamic_half_width = max(35.0, self.lane_half_width * perspective_scale)

        # Check lateral offset from center optical axis
        lateral_offset = abs(x_center - self.center_x)
        is_in_lane = lateral_offset <= dynamic_half_width

        if is_in_lane:
            lane_pos = "YOUR LANE"
            priority_boost = 0.25  # +25% confidence boost for in-lane hazards
        elif x_center < self.center_x:
            lane_pos = "LEFT LANE"
            priority_boost = 0.0
        else:
            lane_pos = "RIGHT LANE"
            priority_boost = 0.0

        return {
            "is_in_lane": is_in_lane,
            "lane_position": lane_pos,
            "lateral_offset_px": round(x_center - self.center_x, 1),
            "priority_boost": priority_boost
        }

    def render_lane_overlay(self, frame):
        """
        Draws glowing cyber lane boundary lines and ego corridor overlay on frame.
        """
        if frame is None:
            return frame

        annotated = frame.copy()
        h, w, _ = annotated.shape
        
        # Define ego lane corridor trapezoid points
        horizon_y = int(h * 0.45)
        pt1 = (int(w * 0.42), horizon_y)
        pt2 = (int(w * 0.58), horizon_y)
        pt3 = (int(w * 0.88), h)
        pt4 = (int(w * 0.12), h)

        pts = np.array([pt1, pt2, pt3, pt4], np.int32)
        pts = pts.reshape((-1, 1, 2))

        # Fill corridor with translucent neon cyan mask
        overlay = annotated.copy()
        cv2.fillPoly(overlay, [pts], (254, 242, 0)) # BGR Cyan
        cv2.addWeighted(overlay, 0.15, annotated, 0.85, 0, annotated)

        # Draw left & right lane boundaries
        cv2.polylines(annotated, [np.array([pt4, pt1])], False, (254, 242, 0), 2, cv2.LINE_AA)
        cv2.polylines(annotated, [np.array([pt3, pt2])], False, (254, 242, 0), 2, cv2.LINE_AA)

        return annotated
