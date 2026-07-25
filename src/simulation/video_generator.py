import cv2
import numpy as np
import math
import random
import time
from src.utils.config import Config

class VideoGenerator:
    def __init__(self, simulator):
        self.sim = simulator
        self.width = Config.FRAME_WIDTH
        self.height = Config.FRAME_HEIGHT
        
        # Horizon & Road geometry
        self.y_horizon = int(self.height * 0.45)
        self.y_bottom = self.height
        self.x_center = self.width // 2
        
        # Dashboard overlay assets (scenery seeds)
        self.scenery_stars = [(random.randint(0, self.width), random.randint(0, self.y_horizon)) for _ in range(30)]
        self.scenery_mountains = self._generate_mountains()
        
    def _generate_mountains(self):
        # Set of vertices for stylized cyberpunk mountains on the horizon
        mountains = []
        random.seed(100)
        curr_x = 0
        while curr_x < self.width:
            w = random.randint(80, 200)
            h = random.randint(40, 100)
            y = self.y_horizon - h
            mountains.append((curr_x, self.y_horizon, curr_x + w//2, y, curr_x + w, self.y_horizon))
            curr_x += w - random.randint(10, 40)
        return mountains

    def generate_frame(self, fps_display=0.0):
        # Create dark base canvas (Cyberpunk theme)
        frame = np.zeros((self.height, self.width, 3), dtype=np.uint8)
        
        # Sky: Dark Blue Gradient
        for y in range(self.y_horizon):
            ratio = y / self.y_horizon
            color = (int(25 * (1 - ratio)), int(10 * (1 - ratio)), int(35 * (1 - ratio) + 15 * ratio))
            frame[y, :] = color
            
        # Draw Stars
        for sx, sy in self.scenery_stars:
            color = (random.randint(180, 255), random.randint(200, 255), random.randint(220, 255))
            cv2.circle(frame, (sx, sy), 1, color, -1)
            
        # Draw neon mountains
        for x1, y1, x2, y2, x3, y3 in self.scenery_mountains:
            pts = np.array([[x1, y1], [x2, y2], [x3, y3]], np.int32)
            cv2.fillPoly(frame, [pts], (15, 10, 25))
            cv2.polylines(frame, [pts], True, (50, 20, 75), 1)

        # Horizon Line (Cyan neon glow)
        cv2.line(frame, (0, self.y_horizon), (self.width, self.y_horizon), (0, 242, 254), 1)
        
        # Ground: Dark Grey Grid
        for y in range(self.y_horizon, self.height):
            ratio = (y - self.y_horizon) / (self.height - self.y_horizon)
            color = (int(10 + 10 * ratio), int(15 + 10 * ratio), int(22 + 10 * ratio))
            frame[y, :] = color

        # Draw road perspective trapezoid
        road_pts = np.array([
            [self.x_center - 15, self.y_horizon],
            [self.x_center + 15, self.y_horizon],
            [self.x_center + 260, self.y_bottom],
            [self.x_center - 260, self.y_bottom]
        ], np.int32)
        
        # Fill road surface (darker asphalt)
        cv2.fillPoly(frame, [road_pts], (24, 28, 38))
        # Draw road shoulders (glowing cyan borders)
        cv2.polylines(frame, [road_pts], False, (0, 242, 254), 2)
        
        # Draw scrolling lane markings based on vehicle distance
        self._draw_lane_markings(frame)

        # Draw obstacles
        visible_obstacles = self._draw_obstacles(frame)

        # Draw HUD elements & Telemetry
        self._draw_hud(frame, fps_display)

        return frame, visible_obstacles

    def _draw_lane_markings(self, frame):
        # Lane divider lines scrolling down
        dist = self.sim.current_distance
        dash_len = 8.0 # meters
        gap_len = 6.0 # meters
        cycle = dash_len + gap_len
        
        # How far we are into the current dash cycle
        offset = dist % cycle
        
        # Draw 5 segments down the road
        for i in range(-1, 10):
            # Distance of segment start from the car
            z_start = (i * cycle) - offset
            z_end = z_start + dash_len
            
            # Skip if segment is out of view
            if z_end <= 0.1 or z_start > 80.0:
                continue
                
            z_start = max(0.1, z_start)
            
            # Perspective mapping
            # Perspective factor z_scale = d / (d + z)
            k_start = 2.5 / (2.5 + z_start)
            k_end = 2.5 / (2.5 + z_end)
            
            y_start = int(self.y_horizon + (self.height - self.y_horizon) * k_start)
            y_end = int(self.y_horizon + (self.height - self.y_horizon) * k_end)
            
            # Calculate coordinates for left, center, right lines
            # Middle dash line
            cv2.line(frame, (self.x_center, y_start), (self.x_center, y_end), (150, 150, 150), max(1, int(4 * k_start)))
            
            # Left lane marker
            dx_left_start = int(-120 * k_start)
            dx_left_end = int(-120 * k_end)
            cv2.line(frame, (self.x_center + dx_left_start, y_start), (self.x_center + dx_left_end, y_end), (60, 60, 80), 1)

            # Right lane marker
            dx_right_start = int(120 * k_start)
            dx_right_end = int(120 * k_end)
            cv2.line(frame, (self.x_center + dx_right_start, y_start), (self.x_center + dx_right_end, y_end), (60, 60, 80), 1)

    def _draw_obstacles(self, frame):
        visible = []
        dist = self.sim.current_distance
        total_len = self.sim.total_path_length_meters
        
        for obs in self.sim.obstacles:
            # Distance to obstacle (taking loop wrapping into account)
            z = (obs["distance"] - dist) % total_len
            
            # Obstacles are visible if they are within 60 meters ahead
            if 0.1 < z < 60.0:
                # Perspective factor
                k = 2.5 / (2.5 + z)
                
                # Screen coordinates
                y = int(self.y_horizon + (self.height - self.y_horizon) * k)
                
                # Lateral offset mapping
                # At bottom (z=0, k=1), 1 meter offset corresponds to ~120 pixels
                road_width_scale = 120.0
                dx = int(obs["lateral_offset"] * road_width_scale * k)
                x = self.x_center + dx
                
                # Scale sizing
                if obs["type"] == "pothole":
                    w = int(60 * k)
                    h = int(22 * k)
                    w = max(4, w)
                    h = max(2, h)
                    
                    # Store ground truth info for detector
                    visible.append({
                        "id": obs["id"],
                        "type": "pothole",
                        "distance": z,
                        "x": x,
                        "y": y,
                        "w": w,
                        "h": h,
                        "severity": obs["severity"],
                        "gps": obs["gps"]
                    })
                    
                    # Draw Pothole on canvas
                    # Dark center
                    cv2.ellipse(frame, (x, y), (w, h), 0, 0, 360, (20, 20, 25), -1)
                    # Outer jagged/damaged border
                    cv2.ellipse(frame, (x, y), (w, h), 0, 0, 360, (40, 45, 50), max(1, int(2 * k)))
                    
                    # Pothole inner cracks/texture
                    if k > 0.15:
                        cv2.line(frame, (x - w//3, y), (x + w//3, y - h//4), (10, 10, 12), max(1, int(1*k)))
                        cv2.line(frame, (x - w//4, y - h//3), (x + w//5, y + h//3), (10, 10, 12), max(1, int(1*k)))
                        
                elif obs["type"] == "speed_bump":
                    w = int(90 * k)
                    h = int(18 * k)
                    w = max(6, w)
                    h = max(2, h)
                    
                    visible.append({
                        "id": obs["id"],
                        "type": "speed_bump",
                        "distance": z,
                        "x": x,
                        "y": y,
                        "w": w,
                        "h": h,
                        "severity": obs["severity"],
                        "gps": obs["gps"]
                    })
                    
                    # Draw Speed Bump (yellow and black diagonal striped ramp)
                    # Draw base black polygon
                    bump_poly = np.array([
                        [x - w//2, y + h//2],
                        [x - w//3, y - h//2],
                        [x + w//3, y - h//2],
                        [x + w//2, y + h//2]
                    ], np.int32)
                    cv2.fillPoly(frame, [bump_poly], (30, 30, 30))
                    
                    # Draw yellow diagonal stripes inside the speed bump
                    if k > 0.05:
                        num_stripes = 6
                        for s in range(num_stripes):
                            # Interpolate stripes left-to-right
                            frac = s / (num_stripes - 1)
                            sx = int(x - w//2 + frac * w)
                            
                            # Yellow diagonal lines
                            cv2.line(frame, 
                                     (sx - int(8*k), y + h//2), 
                                     (sx + int(8*k) - int(w*0.1), y - h//2), 
                                     (0, 200, 230), # Neon Yellow-orange
                                     max(1, int(6 * k)))
                                     
                    # Draw neon border around the bump
                    cv2.polylines(frame, [bump_poly], True, (0, 200, 230), max(1, int(1.5 * k)))
                    
                elif obs["type"] == "speed_limit_60" or obs["type"] == "hard_turn_ahead":
                    sign_type = obs["type"]
                    # Elevation parameters: post height is ~1.2m
                    post_h = int(140 * k)
                    sign_r = int(20 * k)
                    sign_r = max(4, sign_r)
                    post_h = max(10, post_h)
                    
                    # Sign center coordinate
                    cy = y - post_h - sign_r
                    
                    # Add to visible list (for detector)
                    visible.append({
                        "id": obs["id"],
                        "type": sign_type,
                        "distance": z,
                        "x": x,
                        "y": cy,
                        "w": sign_r * 2,
                        "h": sign_r * 2,
                        "severity": obs["severity"],
                        "gps": obs["gps"]
                    })
                    
                    # Draw grey sign post
                    cv2.line(frame, (x, y), (x, y - post_h), (80, 85, 90), max(1, int(3 * k)))
                    
                    # Draw sign panel
                    if sign_type == "speed_limit_60":
                        # White circle
                        cv2.circle(frame, (x, cy), sign_r, (255, 255, 255), -1)
                        # Red border (BGR: red is (73, 73, 255))
                        cv2.circle(frame, (x, cy), sign_r, (73, 73, 255), max(1, int(3.5 * k)))
                        # Black text "60" inside
                        if k > 0.08:
                            font_scale = 0.28 * k * 10
                            cv2.putText(frame, "60", (x - int(7*k), cy + int(3*k)), cv2.FONT_HERSHEY_SIMPLEX, 
                                        font_scale, (15, 15, 15), max(1, int(2 * k)), cv2.LINE_AA)
                    elif sign_type == "hard_turn_ahead":
                        # Yellow diamond
                        diamond_pts = np.array([
                            [x, cy - sign_r],      # Top
                            [x + sign_r, cy],      # Right
                            [x, cy + sign_r],      # Bottom
                            [x - sign_r, cy]       # Left
                        ], np.int32)
                        cv2.fillPoly(frame, [diamond_pts], (0, 206, 245)) # Yellow BGR: (0, 206, 245)
                        cv2.polylines(frame, [diamond_pts], True, (15, 20, 25), max(1, int(1.5 * k)))
                        
                        # Black curving arrow inside
                        if k > 0.08:
                            # Draw chevron-like shape or curved line curving right
                            cv2.ellipse(frame, (x - int(4*k), cy + int(4*k)), (int(10*k), int(10*k)), 
                                        0, 270, 360, (15, 15, 15), max(1, int(2.5 * k)))
                            # Arrow tip
                            tip_pts = np.array([
                                [x + int(6*k), cy - int(2*k)],
                                [x + int(6*k), cy + int(4*k)],
                                [x + int(1*k), cy + int(2*k)]
                            ], np.int32)
                            cv2.fillPoly(frame, [tip_pts], (15, 15, 15))
                    
        # Sort visible obstacles by distance (closest last, so they are drawn on top)
        visible.sort(key=lambda o: o["distance"], reverse=True)
        return visible

    def _draw_hud(self, frame, fps_display):
        # Futuristic HUD overlays
        # 1. Outer cyan bounding frame corners
        c_len = 25
        # Top-Left
        cv2.line(frame, (10, 10), (10 + c_len, 10), (0, 242, 254), 1)
        cv2.line(frame, (10, 10), (10, 10 + c_len), (0, 242, 254), 1)
        # Top-Right
        cv2.line(frame, (self.width - 10, 10), (self.width - 10 - c_len, 10), (0, 242, 254), 1)
        cv2.line(frame, (self.width - 10, 10), (self.width - 10, 10 + c_len), (0, 242, 254), 1)
        # Bottom-Left
        cv2.line(frame, (10, self.height - 10), (10 + c_len, self.height - 10), (0, 242, 254), 1)
        cv2.line(frame, (10, self.height - 10), (10, self.height - 10 - c_len), (0, 242, 254), 1)
        # Bottom-Right
        cv2.line(frame, (self.width - 10, self.height - 10), (self.width - 10 - c_len, self.height - 10), (0, 242, 254), 1)
        cv2.line(frame, (self.width - 10, self.height - 10), (self.width - 10, self.height - 10 - c_len), (0, 242, 254), 1)

        # 2. HUD Info Banner at the top (semi-transparent black strip)
        hud_bg = frame[12:35, 12:self.width-12].copy()
        cv2.addWeighted(hud_bg, 0.3, np.zeros_like(hud_bg), 0.7, 0, hud_bg)
        frame[12:35, 12:self.width-12] = hud_bg
        cv2.rectangle(frame, (12, 12), (self.width - 12, 35), (50, 75, 100), 1)

        # Text overlay
        font = cv2.FONT_HERSHEY_SIMPLEX
        lat, lon = self.sim.current_coord
        scenario_title = self.sim.config["name"].upper()
        
        cv2.putText(frame, f"SYS: ACTIVE", (20, 27), font, 0.38, (0, 255, 128), 1, cv2.LINE_AA)
        cv2.putText(frame, f"SCENARIO: {scenario_title}", (120, 27), font, 0.38, (200, 200, 200), 1, cv2.LINE_AA)
        cv2.putText(frame, f"GPS: {lat:.6f}, {lon:.6f}", (320, 27), font, 0.38, (0, 242, 254), 1, cv2.LINE_AA)
        cv2.putText(frame, f"FPS: {fps_display:.1f}", (self.width - 80, 27), font, 0.38, (150, 150, 150), 1, cv2.LINE_AA)

        # 3. Telemetry Overlay at Bottom Left (Speedometer and Stats)
        speed = self.sim.speed_kmh
        cv2.putText(frame, f"{int(speed)}", (25, self.height - 40), font, 1.2, (0, 242, 254), 2, cv2.LINE_AA)
        cv2.putText(frame, "KM/H", (85, self.height - 40), font, 0.4, (0, 242, 254), 1, cv2.LINE_AA)
        cv2.putText(frame, f"THR: {self.sim.target_speed_kmh:.0f} KM/H", (25, self.height - 22), font, 0.35, (100, 150, 150), 1, cv2.LINE_AA)

        # Small speedometer visual bar
        bar_x = 25
        bar_y = self.height - 15
        bar_w = 120
        bar_h = 5
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + bar_w, bar_y + bar_h), (30, 40, 50), -1)
        speed_ratio = min(1.0, speed / self.sim.config["max_speed"])
        filled_w = int(bar_w * speed_ratio)
        # Bar color goes from green to red based on speed ratio
        bar_color = (0, 242, 254) if speed_ratio < 0.7 else (0, 128, 255) if speed_ratio < 0.9 else (0, 0, 255)
        cv2.rectangle(frame, (bar_x, bar_y), (bar_x + filled_w, bar_y + bar_h), bar_color, -1)

        # Distance indicator
        cv2.putText(frame, f"DIST: {self.sim.current_distance:.1f}m / {self.sim.total_path_length_meters:.0f}m", 
                    (self.width - 200, self.height - 22), font, 0.38, (180, 180, 180), 1, cv2.LINE_AA)
