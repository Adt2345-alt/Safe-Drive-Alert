import random
import time
import cv2
from src.utils.config import Config

class AIDetector:
    def __init__(self):
        self.conf_threshold = Config.DETECTION_CONF_THRESHOLD
        
    def detect(self, frame, visible_obstacles):
        """
        Simulates AI inference on the camera frame.
        Takes the frame and the ground-truth obstacles visible in the camera field of view,
        and outputs simulated object detection results with confidence and bounding boxes.
        """
        start_time = time.time()
        
        detections = []
        
        # Ultra-fast AI inference simulation (sub-1ms GPU processing)
        for obs in visible_obstacles:
            dist = obs["distance"]
            if dist > 80.0:
                confidence = random.uniform(0.78, 0.88)
            elif dist > 50.0:
                confidence = random.uniform(0.85, 0.94)
            else:
                confidence = random.uniform(0.92, 0.99)
                
            if confidence < self.conf_threshold:
                continue
                
            x, y = obs["x"], obs["y"]
            w, h = obs["w"], obs["h"]
            
            jitter_x = int(random.uniform(-1, 1) * (1.0 + dist/50.0))
            jitter_y = int(random.uniform(-1, 1) * (1.0 + dist/50.0))
            
            xmin = max(0, x - w//2 + jitter_x)
            ymin = max(0, y - h//2 + jitter_y)
            xmax = min(Config.FRAME_WIDTH, x + w//2 + jitter_x)
            ymax = min(Config.FRAME_HEIGHT, y + h//2 + jitter_y)
            
            detections.append({
                "id": obs["id"],
                "class": obs["type"],
                "confidence": round(confidence, 2),
                "bbox": [xmin, ymin, xmax, ymax],
                "distance_m": round(dist, 2),
                "severity": obs["severity"],
                "gps": obs["gps"]
            })
            
        inference_time = time.time() - start_time
        return detections, inference_time

    def detect_real_frame(self, frame):
        """
        Runs an ultra-fast (<3ms per frame) computer vision pipeline to detect potholes,
        speed bumps, and road signs directly from video frames.
        """
        import numpy as np
        start_time = time.time()
        detections = []
        
        if frame is None:
            return detections, 0.0
            
        h_img, w_img, _ = frame.shape
        
        # 1. Pothole Detection (Road Surface ROI: 40% to 92% height)
        roi_ymin = int(h_img * 0.40)
        roi_ymax = int(h_img * 0.92)
        roi_xmin = int(w_img * 0.08)
        roi_xmax = int(w_img * 0.92)
        
        roi = frame[roi_ymin:roi_ymax, roi_xmin:roi_xmax]
        if roi.size > 0:
            # Downscale ROI to 320x180 for sub-millisecond adaptive thresholding
            proc_w = 320
            proc_h = 180
            scale_x = roi.shape[1] / float(proc_w)
            scale_y = roi.shape[0] / float(proc_h)
            
            small_roi = cv2.resize(roi, (proc_w, proc_h), interpolation=cv2.INTER_NEAREST)
            roi_gray = cv2.cvtColor(small_roi, cv2.COLOR_BGR2GRAY)
            blurred = cv2.GaussianBlur(roi_gray, (5, 5), 0)
            
            thresh = cv2.adaptiveThreshold(
                blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
                cv2.THRESH_BINARY_INV, 13, 3
            )
            
            contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            potholes_found = []
            pothole_id_counter = 100
            for cnt in contours:
                area_proc = cv2.contourArea(cnt)
                # Scaled area threshold (~60px in downscaled space = ~240px in full image space)
                if 50 <= area_proc <= 2500:
                    x_p, y_p, w_p, h_p = cv2.boundingRect(cnt)
                    aspect_ratio = float(w_p) / max(1, h_p)
                    
                    if 1.15 < aspect_ratio < 4.5:
                        xmin = roi_xmin + int(x_p * scale_x)
                        ymin = roi_ymin + int(y_p * scale_y)
                        xmax = xmin + int(w_p * scale_x)
                        ymax = ymin + int(h_p * scale_y)
                        
                        cnt_mask = np.zeros(roi_gray.shape, dtype=np.uint8)
                        cv2.drawContours(cnt_mask, [cnt], -1, 255, -1)
                        mean_val = cv2.mean(roi_gray, mask=cnt_mask)[0]
                        road_bg = cv2.mean(roi_gray)[0]
                        
                        if mean_val < road_bg * 0.88:
                            horizon_y = h_img * 0.40
                            y_center = (ymin + ymax) / 2.0
                            dy = max(1.0, y_center - horizon_y)
                            
                            distance_est = (h_img * 0.16 * 50.0) / dy
                            distance_est = min(80.0, max(2.0, distance_est))
                            
                            confidence = round(min(0.98, max(0.70, 0.96 - (distance_est / 250.0))), 2)
                            severity = "high" if area_proc > 800 else "medium" if area_proc > 300 else "low"
                            
                            potholes_found.append({
                                "id": pothole_id_counter,
                                "class": "pothole",
                                "confidence": confidence,
                                "area": area_proc,
                                "bbox": [xmin, ymin, xmax, ymax],
                                "distance_m": round(distance_est, 1),
                                "severity": severity,
                                "gps": (0.0, 0.0)
                            })
                            pothole_id_counter += 1

            # Keep top 6 most significant potholes by area/confidence
            potholes_found.sort(key=lambda d: d["area"], reverse=True)
            for p in potholes_found[:6]:
                del p["area"]
                detections.append(p)

        # 2. Speed Bump Detection (Yellow Stripe Masking)
        if roi.size > 0:
            hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
            lower_yellow = np.array([12, 80, 80])
            upper_yellow = np.array([32, 255, 255])
            yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
            
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
            yellow_mask = cv2.morphologyEx(yellow_mask, cv2.MORPH_OPEN, kernel)
            
            bump_contours, _ = cv2.findContours(yellow_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            bump_id_counter = 200
            for cnt in bump_contours:
                area = cv2.contourArea(cnt)
                if area > 250:
                    x, y, w, h = cv2.boundingRect(cnt)
                    aspect_ratio = float(w) / max(1, h)
                    
                    if aspect_ratio > 2.0:
                        xmin = roi_xmin + x
                        ymin = roi_ymin + y
                        xmax = xmin + w
                        ymax = ymin + h
                        
                        horizon_y = h_img * 0.40
                        y_center = (ymin + ymax) / 2.0
                        dy = max(1.0, y_center - horizon_y)
                        distance_est = (h_img * 0.16 * 50.0) / dy
                        distance_est = min(75.0, max(2.0, distance_est))
                        
                        confidence = round(min(0.98, max(0.72, 0.95 - (distance_est / 250.0))), 2)
                        
                        detections.append({
                            "id": bump_id_counter,
                            "class": "speed_bump",
                            "confidence": confidence,
                            "bbox": [xmin, ymin, xmax, ymax],
                            "distance_m": round(distance_est, 1),
                            "severity": "medium",
                            "gps": (0.0, 0.0)
                        })
                        bump_id_counter += 1

        # 3. Traffic Sign Detection (Strict Elevated Right Side ROI)
        sign_ymin = int(h_img * 0.05)
        sign_ymax = int(h_img * 0.45)
        sign_xmin = int(w_img * 0.55)
        sign_xmax = int(w_img * 0.95)
        
        sign_roi = frame[sign_ymin:sign_ymax, sign_xmin:sign_xmax]
        if sign_roi.size > 0:
            sign_hsv = cv2.cvtColor(sign_roi, cv2.COLOR_BGR2HSV)
            
            # A. Red Circular Signs (Speed Limit 60)
            lower_red1 = np.array([0, 70, 70])
            upper_red1 = np.array([10, 255, 255])
            lower_red2 = np.array([168, 70, 70])
            upper_red2 = np.array([180, 255, 255])
            
            red_mask1 = cv2.inRange(sign_hsv, lower_red1, upper_red1)
            red_mask2 = cv2.inRange(sign_hsv, lower_red2, upper_red2)
            red_mask = cv2.bitwise_or(red_mask1, red_mask2)
            
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel)
            
            red_contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            sign_id_counter = 300
            for cnt in red_contours:
                area = cv2.contourArea(cnt)
                if 120 < area < 3000:
                    perimeter = cv2.arcLength(cnt, True)
                    if perimeter > 0:
                        circularity = 4.0 * np.pi * area / (perimeter * perimeter)
                        if circularity > 0.70:
                            x, y, w, h = cv2.boundingRect(cnt)
                            aspect_ratio = float(w) / max(1, h)
                            if 0.80 < aspect_ratio < 1.25:
                                xmin = sign_xmin + x
                                ymin = sign_ymin + y
                                xmax = xmin + w
                                ymax = ymin + h
                                
                                horizon_y = h_img * 0.40
                                dy = max(1.0, ymin + h/2.0 - horizon_y)
                                distance_est = (h_img * 0.16 * 50.0) / dy
                                distance_est = min(60.0, max(2.0, distance_est))
                                
                                confidence = round(min(0.98, max(0.75, 0.95 - (distance_est / 200.0))), 2)
                                
                                detections.append({
                                    "id": sign_id_counter,
                                    "class": "speed_limit_60",
                                    "confidence": confidence,
                                    "bbox": [xmin, ymin, xmax, ymax],
                                    "distance_m": round(distance_est, 1),
                                    "severity": "low",
                                    "gps": (0.0, 0.0)
                                })
                                sign_id_counter += 1
                                break # Only 1 speed limit sign max per frame

        # Deduplicate overlapping detections with IoU NMS
        detections = self._nms(detections, iou_thresh=0.20)
        
        inf_time = time.time() - start_time
        return detections, inf_time

    def _nms(self, detections, iou_thresh=0.20):
        """
        Aggressive Non-Maximum Suppression to filter duplicate and cross-class overlapping boxes.
        """
        if not detections:
            return []
            
        dets = sorted(detections, key=lambda d: d["confidence"], reverse=True)
        keep = []
        
        while dets:
            best = dets.pop(0)
            keep.append(best)
            
            filtered = []
            for d in dets:
                boxA = best["bbox"]
                boxB = d["bbox"]
                
                xA = max(boxA[0], boxB[0])
                yA = max(boxA[1], boxB[1])
                xB = min(boxA[2], boxB[2])
                yB = min(boxA[3], boxB[3])
                
                interArea = max(0, xB - xA) * max(0, yB - yA)
                boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
                boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
                
                unionArea = float(boxAArea + boxBArea - interArea)
                iou = interArea / unionArea if unionArea > 0 else 0.0
                
                # Filter out overlapping boxes even if different class if IoU > 0.25
                if iou < (iou_thresh if d["class"] == best["class"] else 0.25):
                    filtered.append(d)
            dets = filtered
            
        return keep

