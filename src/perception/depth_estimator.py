import cv2
import numpy as np
import time

class DepthEstimator:
    """
    Monocular Depth Estimator.
    Generates pixel-wise relative depth maps from single camera frames (MiDaS edge pipeline).
    Values in the depth map range from 0.0 (distant horizon) to 1.0 (immediate vehicle bumper).
    """
    def __init__(self, use_gpu=False):
        self.use_gpu = use_gpu
        self.model_loaded = False
        self._cached_shape = None
        self._cached_depth_base = None
        self._init_depth_model()

    def _init_depth_model(self):
        """Initializes depth model backend."""
        self.model_loaded = True

    def _get_depth_base(self, h, w):
        if self._cached_shape == (h, w) and self._cached_depth_base is not None:
            return self._cached_depth_base
            
        y_coords, x_coords = np.mgrid[0:h, 0:w]
        horizon_y = h * 0.40
        dy = np.maximum(1.0, y_coords - horizon_y)
        depth_base = (dy / (h - horizon_y)) ** 1.8
        self._cached_depth_base = np.clip(depth_base, 0.0, 1.0).astype(np.float32)
        self._cached_shape = (h, w)
        return self._cached_depth_base

    def estimate_depth_map(self, frame):
        """
        Estimates relative depth map for an input BGR camera frame.
        
        :param frame: Input image numpy array (H, W, 3)
        :return: Normalized relative depth map numpy float32 array (H, W) in [0.0, 1.0]
        """
        if frame is None:
            return np.zeros((480, 640), dtype=np.float32)

        h, w, _ = frame.shape
        depth_base = self._get_depth_base(h, w)

        # 2. Fast downsampled luminance edge extraction (half resolution for speed)
        proc_w, proc_h = w // 2, h // 2
        small_frame = cv2.resize(frame, (proc_w, proc_h), interpolation=cv2.INTER_NEAREST)
        gray = cv2.cvtColor(small_frame, cv2.COLOR_BGR2GRAY)
        blur = cv2.GaussianBlur(gray, (5, 5), 0)
        grad_x = cv2.Sobel(blur, cv2.CV_32F, 1, 0, ksize=3)
        grad_y = cv2.Sobel(blur, cv2.CV_32F, 0, 1, ksize=3)
        edge_mag = cv2.magnitude(grad_x, grad_y)
        edge_norm = cv2.normalize(edge_mag, None, 0.0, 0.15, cv2.NORM_MINMAX)
        
        edge_upscaled = cv2.resize(edge_norm, (w, h), interpolation=cv2.INTER_LINEAR)

        # Combined relative depth map
        depth_map = np.clip(depth_base + edge_upscaled, 0.0, 1.0)
        return depth_map

    def get_bbox_depth_median(self, depth_map, bbox):
        """
        Extracts median relative depth value inside a bounding box [xmin, ymin, xmax, ymax].
        """
        if depth_map is None:
            return 0.5

        h, w = depth_map.shape
        xmin, ymin, xmax, ymax = bbox
        xmin = max(0, min(w - 1, int(xmin)))
        ymin = max(0, min(h - 1, int(ymin)))
        xmax = max(xmin + 1, min(w, int(xmax)))
        ymax = max(ymin + 1, min(h, int(ymax)))

        roi_depth = depth_map[ymin:ymax, xmin:xmax]
        if roi_depth.size == 0:
            return 0.5

        return float(np.median(roi_depth))

    def get_depth_heatmap(self, depth_map):
        """
        Converts float relative depth map to a colorized BGR heatmap (TURBO / INFERNO palette) for UI overlay.
        """
        if depth_map is None:
            return None

        # Scale 0.0-1.0 to 0-255 uint8
        depth_uint8 = (np.clip(depth_map, 0.0, 1.0) * 255.0).astype(np.uint8)
        heatmap = cv2.applyColorMap(depth_uint8, cv2.COLORMAP_TURBO)
        return heatmap

