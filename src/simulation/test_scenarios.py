from src.simulation.road_simulator import RoadSimulator
from src.utils.logger import LogManager

class ScenarioManager:
    def __init__(self):
        self.logger = LogManager.get_system_logger()

    def load_scenario(self, scenario_id):
        """
        Creates and returns a new RoadSimulator pre-loaded with the requested scenario.
        """
        self.logger.info(f"Loading scenario configuration: {scenario_id}")
        sim = RoadSimulator(scenario_name=scenario_id)
        return sim

    def run_headless_simulation(self, scenario_id, duration_seconds=10):
        """
        Runs a headless simulator benchmark to verify simulation calculations and obstacle counts.
        """
        self.logger.info(f"Running headless scenario test: '{scenario_id}' for {duration_seconds}s")
        sim = self.load_scenario(scenario_id)
        
        start_time = sim.last_update_time
        steps = 0
        
        while sim.last_update_time - start_time < duration_seconds:
            sim.update()
            steps += 1
            # Mock update rate at 10Hz
            import time
            time.sleep(0.1)
            
        elapsed = sim.last_update_time - start_time
        self.logger.info(f"Headless simulation completed: {steps} steps in {elapsed:.2f}s.")
        self.logger.info(f"Final Vehicle Position: {sim.current_distance:.2f}m along path, coords: {sim.current_coord}")
        return {
            "scenario": scenario_id,
            "steps": steps,
            "elapsed_seconds": elapsed,
            "final_distance": sim.current_distance,
            "final_speed": sim.speed_kmh,
            "obstacles_count": len(sim.obstacles)
        }

if __name__ == "__main__":
    # Self-test code
    mgr = ScenarioManager()
    stats = mgr.run_headless_simulation("pothole_alley", duration_seconds=3)
    print(f"Scenario results: {stats}")
