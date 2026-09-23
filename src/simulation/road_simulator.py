import math
import random
import time
from src.utils.config import Config
from src.utils.logger import LogManager

class RoadSimulator:
    def __init__(self, scenario_name=Config.DEFAULT_SCENARIO):
        self.logger = LogManager.get_system_logger()
        self.scenario_name = scenario_name
        self.config = Config.SCENARIOS[scenario_name]
        
        # Simulation state
        self.running = True
        self.speed_kmh = self.config["base_speed"]
        self.target_speed_kmh = self.config["base_speed"]
        
        # Generate base route (closed loop)
        self.route = self._generate_route_loop()
        self.total_path_length_meters = self._calculate_route_length()
        
        # Vehicle state
        self.current_distance = 0.0  # meters along route
        self.current_coord = self.route[0]
        self.current_heading = 0.0  # degrees
        
        # Obstacles registry
        self.obstacles = []
        self._generate_obstacles()
        
        self.last_update_time = time.time()
        self.logger.info(f"Initialized RoadSimulator with scenario: {self.config['name']}")

    def change_scenario(self, scenario_name):
        if scenario_name not in Config.SCENARIOS:
            self.logger.error(f"Unknown scenario name: {scenario_name}")
            return
        self.scenario_name = scenario_name
        self.config = Config.SCENARIOS[scenario_name]
        self.speed_kmh = self.config["base_speed"]
        self.target_speed_kmh = self.config["base_speed"]
        self.obstacles = []
        self._generate_obstacles()
        self.logger.info(f"Switched scenario to: {self.config['name']}")

    def toggle_pause(self):
        self.running = not self.running
        self.logger.info(f"Simulation {'Resumed' if self.running else 'Paused'}")
        return self.running

    def update(self):
        now = time.time()
        dt = now - self.last_update_time
        self.last_update_time = now
        
        if not self.running or dt <= 0:
            return

        # Cap dt to avoid huge jumps on lag
        dt = min(dt, 0.1)

        # Handle vehicle speed adjustment (gradual acceleration/deceleration)
        self._adjust_speed(dt)

        # Move vehicle forward: distance = speed (m/s) * time (s)
        speed_mps = (self.speed_kmh * 1000.0) / 3600.0
        distance_moved = speed_mps * dt
        self.current_distance = (self.current_distance + distance_moved) % self.total_path_length_meters

        # Update current coordinate and heading based on distance along route
        self.current_coord, self.current_heading = self._interpolate_position(self.current_distance)

    def set_target_speed(self, speed_kmh):
        self.target_speed_kmh = min(max(0.0, speed_kmh), self.config["max_speed"])

    def _adjust_speed(self, dt):
        # Check if there are any obstacles immediately ahead (within 30 meters)
        slow_down = False
        min_dist = float('inf')
        for obs in self.obstacles:
            # Distance to obstacle wrapping around loop
            dist_to_obs = (obs["distance"] - self.current_distance) % self.total_path_length_meters
            if 0 < dist_to_obs < 30.0:
                slow_down = True
                min_dist = min(min_dist, dist_to_obs)

        if slow_down:
            # Slow down proportionally to proximity to the obstacle
            # E.g., target 20 km/h as we get closer to the pothole
            factor = max(0.2, min_dist / 30.0)
            target = self.config["base_speed"] * factor
            self.target_speed_kmh = max(15.0, target)
        else:
            self.target_speed_kmh = self.config["base_speed"]

        # Accelerate or brake smoothly (e.g. 15 km/h per second)
        accel_rate = 15.0  # km/h/s
        speed_diff = self.target_speed_kmh - self.speed_kmh
        
        if abs(speed_diff) > 0.1:
            step = math.copysign(accel_rate * dt, speed_diff)
            if abs(step) > abs(speed_diff):
                self.speed_kmh = self.target_speed_kmh
            else:
                self.speed_kmh += step
        else:
            self.speed_kmh = self.target_speed_kmh

    def _generate_route_loop(self):
        # Generate route loop in Bengaluru, India (MG Road / Indiranagar Corridor)
        # Center: 12.9716, 77.5946
        center_lat = 12.9716
        center_lon = 77.5946
        
        # Radii in lat/lon space
        r_lat = 0.008
        r_lon = 0.015
        
        points = []
        num_points = 200
        
        for i in range(num_points):
            angle = (i / num_points) * 2 * math.pi
            
            # Deform the circle to make it look like an interesting road course
            distortion = 1.0 + 0.15 * math.sin(3 * angle) + 0.08 * math.cos(5 * angle)
            
            lat = center_lat + r_lat * math.sin(angle) * distortion
            lon = center_lon + r_lon * math.cos(angle) * distortion
            points.append((lat, lon))
            
        # Ensure it's a closed loop by matching first and last point
        points.append(points[0])
        return points


    def _calculate_route_length(self):
        total_len = 0.0
        for i in range(len(self.route) - 1):
            total_len += self._distance_between_coords(self.route[i], self.route[i+1])
        return total_len

    def _distance_between_coords(self, coord1, coord2):
        # Returns distance in meters using Haversine
        R = 6371000.0  # Earth's radius in meters
        lat1, lon1 = math.radians(coord1[0]), math.radians(coord1[1])
        lat2, lon2 = math.radians(coord2[0]), math.radians(coord2[1])
        
        d_lat = lat2 - lat1
        d_lon = lon2 - lon1
        
        a = math.sin(d_lat / 2) ** 2 + \
            math.cos(lat1) * math.cos(lat2) * \
            math.sin(d_lon / 2) ** 2
            
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def _interpolate_position(self, distance):
        accumulated_dist = 0.0
        
        for i in range(len(self.route) - 1):
            p1 = self.route[i]
            p2 = self.route[i+1]
            segment_len = self._distance_between_coords(p1, p2)
            
            if accumulated_dist + segment_len >= distance:
                # Interpolate on this segment
                ratio = (distance - accumulated_dist) / segment_len
                lat = p1[0] + (p2[0] - p1[0]) * ratio
                lon = p1[1] + (p2[1] - p1[1]) * ratio
                
                # Calculate bearing (heading)
                d_lon = math.radians(p2[1] - p1[1])
                y = math.sin(d_lon) * math.cos(math.radians(p2[0]))
                x = math.cos(math.radians(p1[0])) * math.sin(math.radians(p2[0])) - \
                    math.sin(math.radians(p1[0])) * math.cos(math.radians(p2[0])) * math.cos(d_lon)
                bearing = math.degrees(math.atan2(y, x))
                heading = (bearing + 360) % 360
                
                return (lat, lon), heading
            
            accumulated_dist += segment_len
            
        return self.route[-1], 0.0

    def _generate_obstacles(self):
        # Distribute obstacles along the length of the road
        obstacle_freq = self.config["obstacle_frequency"]
        pothole_ratio = self.config["pothole_ratio"]
        
        # Estimate number of obstacles based on length and frequency
        # Frequency is approximately obstacles per 100 meters
        approx_num_obstacles = int((self.total_path_length_meters / 100.0) * obstacle_freq * 10.0)
        approx_num_obstacles = max(5, approx_num_obstacles)
        
        # Distribute them spaced out
        min_spacing = 60.0  # meters between obstacles
        allocated_distances = []
        
        random.seed(42)  # Seed for deterministic layout per scenario
        
        attempts = 0
        while len(allocated_distances) < approx_num_obstacles and attempts < 1000:
            attempts += 1
            dist = random.uniform(20.0, self.total_path_length_meters - 20.0)
            
            # Check spacing with existing obstacles
            valid = True
            for existing_dist in allocated_distances:
                diff = abs(existing_dist - dist)
                # Wrap around check
                diff = min(diff, self.total_path_length_meters - diff)
                if diff < min_spacing:
                    valid = False
                    break
            
            if valid:
                allocated_distances.append(dist)
                
        allocated_distances.sort()
        
        obstacle_id = 1
        for dist in allocated_distances:
            obs_type = "pothole" if random.random() < pothole_ratio else "speed_bump"
            # Random lateral offset from centerline:
            # -1.2 (left lane center), 0.0 (middle), 1.2 (right lane center)
            lateral_offset = random.choice([-1.2, 0.0, 1.2])
            severity = random.choice(["low", "medium", "high"])
            if obs_type == "speed_bump":
                # Speed bumps are usually across the road, so offset is small or spans center
                lateral_offset = random.choice([-0.4, 0.0, 0.4])
            
            # Calculate actual GPS coordinate for this obstacle
            gps_coord, heading = self._interpolate_position(dist)
            
            # Apply lateral offset to GPS coordinate perpendicular to road heading
            heading_rad = math.radians(heading)
            # Perpendicular angle (to the right of heading)
            perp_angle = heading_rad + math.pi / 2
            
            # Earth radius
            R = 6371000.0
            d_lat = (lateral_offset * math.sin(perp_angle)) / R
            d_lon = (lateral_offset * math.cos(perp_angle)) / (R * math.cos(math.radians(gps_coord[0])))
            
            obs_lat = gps_coord[0] + math.degrees(d_lat)
            obs_lon = gps_coord[1] + math.degrees(d_lon)
            
            self.obstacles.append({
                "id": obstacle_id,
                "type": obs_type,
                "distance": dist,          # distance along path
                "lateral_offset": lateral_offset, # meters from lane center
                "severity": severity,
                "gps": (obs_lat, obs_lon),
                "heading": heading,
                "detected": False
            })
            obstacle_id += 1

        # Generate Traffic Signs (Phase 3)
        sign_freq = self.config.get("sign_frequency", 0.03)
        approx_num_signs = int((self.total_path_length_meters / 100.0) * sign_freq * 10.0)
        approx_num_signs = max(4, approx_num_signs)
        
        sign_distances = []
        attempts = 0
        while len(sign_distances) < approx_num_signs and attempts < 1000:
            attempts += 1
            dist = random.uniform(30.0, self.total_path_length_meters - 30.0)
            
            # Check spacing with existing items (both obstacles and other signs)
            valid = True
            for existing_dist in allocated_distances + sign_distances:
                diff = abs(existing_dist - dist)
                diff = min(diff, self.total_path_length_meters - diff)
                if diff < 45.0:
                    valid = False
                    break
            if valid:
                sign_distances.append(dist)
                
        sign_distances.sort()
        
        for dist in sign_distances:
            # Alternating sign types: speed limit 60 vs hard turn ahead
            sign_type = "speed_limit_60" if obstacle_id % 2 == 0 else "hard_turn_ahead"
            lateral_offset = 2.2 # Right side road shoulder
            
            gps_coord, heading = self._interpolate_position(dist)
            
            # Apply lateral offset to GPS coordinate perpendicular to road heading
            heading_rad = math.radians(heading)
            perp_angle = heading_rad + math.pi / 2
            
            R = 6371000.0
            d_lat = (lateral_offset * math.sin(perp_angle)) / R
            d_lon = (lateral_offset * math.cos(perp_angle)) / (R * math.cos(math.radians(gps_coord[0])))
            
            obs_lat = gps_coord[0] + math.degrees(d_lat)
            obs_lon = gps_coord[1] + math.degrees(d_lon)
            
            self.obstacles.append({
                "id": obstacle_id,
                "type": sign_type,
                "distance": dist,
                "lateral_offset": lateral_offset,
                "severity": "low",
                "gps": (obs_lat, obs_lon),
                "heading": heading,
                "detected": False
            })
            obstacle_id += 1

        self.logger.info(f"Generated {len(self.obstacles)} obstacles/signs along the {self.total_path_length_meters:.1f}m route.")
