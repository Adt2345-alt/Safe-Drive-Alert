from src.utils.config import Config

class TrackedObject:
    def __init__(self, obj_id, class_name, bbox, distance, severity, gps):
        self.id = obj_id
        self.class_name = class_name
        self.bbox = bbox
        self.distance = distance
        self.severity = severity
        self.gps = gps
        self.disappeared = 0
        self.alert_triggered = False

class ObjectTracker:
    def __init__(self):
        self.tracked_objects = {}  # dict mapping ID to TrackedObject
        self.max_disappeared = Config.TRACKING_MAX_DISAPPEARED
        
    def update(self, detections):
        """
        Updates the tracker with the list of active detections in the current frame.
        Detections are matched using their core ID.
        """
        # Mark all existing tracked objects as potentially disappeared
        for obj_id in list(self.tracked_objects.keys()):
            self.tracked_objects[obj_id].disappeared += 1
            
        for det in detections:
            obj_id = det["id"]
            bbox = det["bbox"]
            dist = det["distance_m"]
            class_name = det["class"]
            severity = det["severity"]
            gps = det["gps"]
            
            if obj_id in self.tracked_objects:
                # Update existing tracked object
                tracked = self.tracked_objects[obj_id]
                tracked.bbox = bbox
                tracked.distance = dist
                tracked.gps = gps
                tracked.severity = severity
                tracked.disappeared = 0  # reset disappeared count
            else:
                # Create a new tracked object
                self.tracked_objects[obj_id] = TrackedObject(
                    obj_id=obj_id,
                    class_name=class_name,
                    bbox=bbox,
                    distance=dist,
                    severity=severity,
                    gps=gps
                )
                
        # Remove objects that have disappeared for too many frames
        for obj_id in list(self.tracked_objects.keys()):
            if self.tracked_objects[obj_id].disappeared > self.max_disappeared:
                del self.tracked_objects[obj_id]
                
        return list(self.tracked_objects.values())
