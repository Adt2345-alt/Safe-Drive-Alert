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
        
        # Simulate PyTorch / YOLO GPU inference latency (e.g. 5ms to 12ms)
        inference_latency = random.uniform(0.005, 0.012)
        time.sleep(inference_latency)
        
        for obs in visible_obstacles:
            # AI model confidence score
            # Close obstacles are easier to detect (higher confidence)
            # Far obstacles have slightly lower confidence
            dist = obs["distance"]
            if dist > 55.0:
                confidence = random.uniform(0.40, 0.65)
            elif dist > 40.0:
                confidence = random.uniform(0.65, 0.85)
            else:
                confidence = random.uniform(0.85, 0.98)
                
            # Skip if confidence is below threshold (simulate missed detection)
            if confidence < self.conf_threshold:
                continue
                
            # Bounding box jitter (simulate bbox regression inaccuracy)
            x, y = obs["x"], obs["y"]
            w, h = obs["w"], obs["h"]
            
            # Apply slight coordinate noise
            jitter_x = int(random.uniform(-2, 2) * (1.0 + dist/20.0))
            jitter_y = int(random.uniform(-1, 1) * (1.0 + dist/20.0))
            jitter_w = int(random.uniform(-2, 2))
            jitter_h = int(random.uniform(-1, 1))
            
            # Calculate bbox corners
            xmin = max(0, x - w//2 + jitter_x)
            ymin = max(0, y - h//2 + jitter_y)
            xmax = min(Config.FRAME_WIDTH, x + w//2 + jitter_x + jitter_w)
            ymax = min(Config.FRAME_HEIGHT, y + h//2 + jitter_y + jitter_h)
            
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
        Runs a pixel-based computer vision pipeline to detect potholes and speed bumps
        directly from image frames (used for uploaded videos).
        """
        import numpy as np
        start_time = time.time()
        detections = []
        
        if frame is None:
            return detections, 0.0
            
        h_img, w_img, _ = frame.shape
        
        # Define road floor Region of Interest (ROI): lower 45% of the image, middle 80% width
        roi_ymin = int(h_img * 0.50)
        roi_ymax = int(h_img * 0.95)
        roi_xmin = int(w_img * 0.10)
        roi_xmax = int(w_img * 0.90)
        
        roi = frame[roi_ymin:roi_ymax, roi_xmin:roi_xmax]
        if roi.size == 0:
            return detections, 0.0
            
        # 1. Pothole Detection via Adaptive Thresholding & Dark Contour Analysis
        # Potholes appear as darker, irregular elliptical shapes on the road surface
        roi_gray = cv2.cvtColor(roi, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(roi_gray, (7, 7), 0)
        
        # Adaptive thresholding to isolate darker regions
        thresh = cv2.adaptiveThreshold(
            blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, 
            cv2.THRESH_BINARY_INV, 15, 4
        )
        
        # Find contours of dark spots
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        pothole_id_counter = 100
        for cnt in contours:
            area = cv2.contourArea(cnt)
            # Filter by size to ignore tiny noise and massive layout components
            if 150 < area < 5000:
                x, y, w, h = cv2.boundingRect(cnt)
                aspect_ratio = float(w) / h
                
                # Potholes in perspective appear wider than they are tall (typically aspect_ratio > 1.2)
                if 1.1 < aspect_ratio < 5.0:
                    # Map ROI coordinates back to full image space
                    xmin = roi_xmin + x
                    ymin = roi_ymin + y
                    xmax = xmin + w
                    ymax = ymin + h
                    
                    # Confirm that the center of the detection is relatively dark compared to surroundings
                    # (Potholes have shadow depth)
                    cnt_mask = np.zeros(roi_gray.shape, dtype=np.uint8)
                    cv2.drawContours(cnt_mask, [cnt], -1, 255, -1)
                    mean_val = cv2.mean(roi_gray, mask=cnt_mask)[0]
                    
                    # Calculate surrounding road brightness estimate
                    road_bg = cv2.mean(roi_gray)[0]
                    
                    if mean_val < road_bg * 0.95:  # center is darker than average road
                        # Distance estimation based on screen position (perspective)
                        # Lower y means closer distance
                        horizon_y = h_img * 0.45
                        y_center = (ymin + ymax) / 2.0
                        dy = max(1.0, y_center - horizon_y)
                        
                        # Distance scale constant (focal_length * camera_height)
                        distance_est = (h_img * 0.15 * 50.0) / dy
                        distance_est = min(60.0, max(2.0, distance_est))
                        
                        confidence = 0.90 - (distance_est / 150.0)  # closer = higher confidence
                        confidence = round(min(0.98, max(0.50, confidence)), 2)
                        
                        severity = "high" if area > 2000 else "medium" if area > 800 else "low"
                        
                        detections.append({
                            "id": pothole_id_counter,
                            "class": "pothole",
                            "confidence": confidence,
                            "bbox": [xmin, ymin, xmax, ymax],
                            "distance_m": round(distance_est, 1),
                            "severity": severity,
                            "gps": (0.0, 0.0) # Coordinates are not pre-mapped for uploads
                        })
                        pothole_id_counter += 1

        # 2. Speed Bump Detection via HSV Yellow Range Masking
        # Speed bumps are painted with high-contrast yellow lines
        hsv = cv2.cvtColor(roi, cv2.COLOR_BGR2HSV)
        lower_yellow = np.array([12, 70, 70])
        upper_yellow = np.array([32, 255, 255])
        yellow_mask = cv2.inRange(hsv, lower_yellow, upper_yellow)
        
        # Clean up binary mask
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        yellow_mask = cv2.morphologyEx(yellow_mask, cv2.MORPH_OPEN, kernel)
        
        bump_contours, _ = cv2.findContours(yellow_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        bump_id_counter = 200
        for cnt in bump_contours:
            area = cv2.contourArea(cnt)
            if area > 100:
                x, y, w, h = cv2.boundingRect(cnt)
                aspect_ratio = float(w) / h
                
                # Speed bumps stretch horizontally across road lines (aspect ratio should be very high)
                if aspect_ratio > 1.8:
                    xmin = roi_xmin + x
                    ymin = roi_ymin + y
                    xmax = xmin + w
                    ymax = ymin + h
                    
                    # Estimate distance
                    horizon_y = h_img * 0.45
                    y_center = (ymin + ymax) / 2.0
                    dy = max(1.0, y_center - horizon_y)
                    distance_est = (h_img * 0.15 * 50.0) / dy
                    distance_est = min(60.0, max(2.0, distance_est))
                    
                    confidence = 0.95 - (distance_est / 200.0)
                    confidence = round(min(0.98, max(0.50, confidence)), 2)
                    
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

        # 3. Traffic Sign Detection (Phase 3)
        # Sign ROI: upper/middle height, middle-to-right width (where elevated signs are)
        sign_ymin = int(h_img * 0.10)
        sign_ymax = int(h_img * 0.65)
        sign_xmin = int(w_img * 0.45)
        sign_xmax = int(w_img * 0.98)
        
        sign_roi = frame[sign_ymin:sign_ymax, sign_xmin:sign_xmax]
        if sign_roi.size > 0:
            sign_hsv = cv2.cvtColor(sign_roi, cv2.COLOR_BGR2HSV)
            
            # A. Red Circular Signs (Speed Limit 60)
            # Red color wraps around Hue 0 and Hue 180
            lower_red1 = np.array([0, 60, 50])
            upper_red1 = np.array([10, 255, 255])
            lower_red2 = np.array([165, 60, 50])
            upper_red2 = np.array([180, 255, 255])
            
            red_mask1 = cv2.inRange(sign_hsv, lower_red1, upper_red1)
            red_mask2 = cv2.inRange(sign_hsv, lower_red2, upper_red2)
            red_mask = cv2.bitwise_or(red_mask1, red_mask2)
            
            # Clean mask
            kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (3, 3))
            red_mask = cv2.morphologyEx(red_mask, cv2.MORPH_OPEN, kernel)
            
            red_contours, _ = cv2.findContours(red_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            sign_id_counter = 300
            for cnt in red_contours:
                area = cv2.contourArea(cnt)
                if 100 < area < 4000:
                    perimeter = cv2.arcLength(cnt, True)
                    if perimeter > 0:
                        # Circularity index: 4*pi*area / perimeter^2
                        circularity = 4.0 * np.pi * area / (perimeter * perimeter)
                        if circularity > 0.65:
                            x, y, w, h = cv2.boundingRect(cnt)
                            aspect_ratio = float(w) / h
                            if 0.75 < aspect_ratio < 1.3:
                                xmin = sign_xmin + x
                                ymin = sign_ymin + y
                                xmax = xmin + w
                                ymax = ymin + h
                                
                                # Distance estimation
                                distance_est = (h_img * 0.15 * 50.0) / max(1.0, ymin + h/2.0 - h_img * 0.45)
                                distance_est = min(60.0, max(2.0, distance_est))
                                
                                detections.append({
                                    "id": sign_id_counter,
                                    "class": "speed_limit_60",
                                    "confidence": 0.92,
                                    "bbox": [xmin, ymin, xmax, ymax],
                                    "distance_m": round(distance_est, 1),
                                    "severity": "low",
                                    "gps": (0.0, 0.0)
                                    
                                })
                                sign_id_counter += 1
                                
            # B. Yellow Warning Signs (Hard Turn Ahead)
            yellow_sign_mask = cv2.inRange(sign_hsv, np.array([12, 70, 70]), np.array([32, 255, 255]))
            yellow_sign_mask = cv2.morphologyEx(yellow_sign_mask, cv2.MORPH_OPEN, kernel)
            
            yellow_contours, _ = cv2.findContours(yellow_sign_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            for cnt in yellow_contours:
                area = cv2.contourArea(cnt)
                if 120 < area < 4000:
                    x, y, w, h = cv2.boundingRect(cnt)
                    aspect_ratio = float(w) / h
                    perimeter = cv2.arcLength(cnt, True)
                    approx = cv2.approxPolyDP(cnt, 0.04 * perimeter, True)
                    
                    if 0.8 < aspect_ratio < 1.25 and len(approx) == 4:
                        xmin = sign_xmin + x
                        ymin = sign_ymin + y
                        xmax = xmin + w
                        ymax = ymin + h
                        
                        # Distance estimation
                        distance_est = (h_img * 0.15 * 50.0) / max(1.0, ymin + h/2.0 - h_img * 0.45)
                        distance_est = min(60.0, max(2.0, distance_est))
                        
                        detections.append({
                            "id": sign_id_counter,
                            "class": "hard_turn_ahead",
                            "confidence": 0.90,
                            "bbox": [xmin, ymin, xmax, ymax],
                            "distance_m": round(distance_est, 1),
                            "severity": "low",
                            "gps": (0.0, 0.0)
                        })
                        sign_id_counter += 1

        # Deduplicate detections that are highly overlapping to keep boxes clean
        detections = self._nms(detections)
        
        inf_time = time.time() - start_time
        return detections, inf_time

    def _nms(self, detections, iou_thresh=0.4):
        """
        Simple Non-Maximum Suppression to filter duplicate boxes.
        """
        if not detections:
            return []
            
        # Sort by confidence descending
        dets = sorted(detections, key=lambda d: d["confidence"], reverse=True)
        keep = []
        
        while dets:
            best = dets.pop(0)
            keep.append(best)
            
            # Filter remaining
            filtered = []
            for d in dets:
                if d["class"] != best["class"]:
                    filtered.append(d)
                    continue
                # Calculate IOU
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
                
                if iou < iou_thresh:
                    filtered.append(d)
            dets = filtered
            
        return keep

