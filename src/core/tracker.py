from src.utils.config import Config

class TrackedObject:
    def __init__(self, obj_id, class_name, bbox, distance, severity, gps, confidence=1.0, fusion_mode="DEFAULT"):
        self.id = obj_id
        self.class_name = class_name
        self.bbox = bbox
        self.distance = distance
        self.severity = severity
        self.gps = gps
        self.confidence = confidence
        self.fusion_mode = fusion_mode
        self.disappeared = 0
        self.alert_triggered = False

class ObjectTracker:
    def __init__(self):
        self.tracked_objects = {}  # dict mapping ID to TrackedObject
        self.next_object_id = 1
        self.max_disappeared = 2  # Fast cleanup for smooth video feeds
        
    def _compute_iou(self, boxA, boxB):
        xA = max(boxA[0], boxB[0])
        yA = max(boxA[1], boxB[1])
        xB = min(boxA[2], boxB[2])
        yB = min(boxA[3], boxB[3])
        interArea = max(0, xB - xA) * max(0, yB - yA)
        boxAArea = (boxA[2] - boxA[0]) * (boxA[3] - boxA[1])
        boxBArea = (boxB[2] - boxB[0]) * (boxB[3] - boxB[1])
        unionArea = float(boxAArea + boxBArea - interArea)
        return interArea / unionArea if unionArea > 0 else 0.0

    def update(self, detections):
        """
        Updates tracker using IoU spatial matching and Exponential Moving Average (EMA)
        bounding box smoothing to guarantee clean, non-jittery tracking.
        """
        # Mark all existing tracked objects as potentially disappeared
        for obj_id in list(self.tracked_objects.keys()):
            self.tracked_objects[obj_id].disappeared += 1

        if not detections:
            # Clean up disappeared objects
            for obj_id in list(self.tracked_objects.keys()):
                if self.tracked_objects[obj_id].disappeared > self.max_disappeared:
                    del self.tracked_objects[obj_id]
            return list(self.tracked_objects.values())

        # Spatial matching based on IoU and class type
        unmatched_detections = list(detections)
        matched_pairs = []

        for obj_id, tracked in list(self.tracked_objects.items()):
            best_iou = 0.2  # minimum IoU threshold for matching
            best_det_idx = -1

            for idx, det in enumerate(unmatched_detections):
                if det["class"] == tracked.class_name:
                    iou = self._compute_iou(tracked.bbox, det["bbox"])
                    if iou > best_iou:
                        best_iou = iou
                        best_det_idx = idx

            if best_det_idx >= 0:
                matched_pairs.append((obj_id, unmatched_detections.pop(best_det_idx)))

        # Update matched objects with EMA bounding box smoothing
        for obj_id, det in matched_pairs:
            tracked = self.tracked_objects[obj_id]
            
            # EMA Smoothing factor: 60% new detection, 40% historical position
            alpha = 0.65
            old_b = tracked.bbox
            new_b = det["bbox"]
            smoothed_bbox = [
                int(alpha * new_b[0] + (1 - alpha) * old_b[0]),
                int(alpha * new_b[1] + (1 - alpha) * old_b[1]),
                int(alpha * new_b[2] + (1 - alpha) * old_b[2]),
                int(alpha * new_b[3] + (1 - alpha) * old_b[3])
            ]

            tracked.bbox = smoothed_bbox
            tracked.distance = round(0.7 * det["distance_m"] + 0.3 * tracked.distance, 1)
            tracked.severity = det.get("severity", tracked.severity)
            tracked.confidence = det.get("confidence", tracked.confidence)
            tracked.disappeared = 0

        # Create new tracked objects for remaining unmatched detections
        for det in unmatched_detections:
            assigned_id = self.next_object_id
            self.next_object_id += 1

            self.tracked_objects[assigned_id] = TrackedObject(
                obj_id=assigned_id,
                class_name=det["class"],
                bbox=det["bbox"],
                distance=det["distance_m"],
                severity=det.get("severity", "medium"),
                gps=det.get("gps", (0.0, 0.0)),
                confidence=det.get("confidence", 0.90),
                fusion_mode=det.get("fusion_mode", "DEFAULT")
            )

        # Remove dead objects that have disappeared
        for obj_id in list(self.tracked_objects.keys()):
            if self.tracked_objects[obj_id].disappeared > self.max_disappeared:
                del self.tracked_objects[obj_id]

        return list(self.tracked_objects.values())
