"""Robot description: wheels, body outline and what's plugged into each port."""

from .shapes import ShapeError, to_world

DEVICE_KINDS = ("motor", "color_sensor", "ultrasonic_sensor", "force_sensor")
PORT_NAMES = ("A", "B", "C", "D", "E", "F")


class PortSpec:
    def __init__(self, port, spec):
        self.port = port
        self.device = spec.get("device")
        if self.device not in DEVICE_KINDS:
            raise ShapeError(f"port {port}: device must be one of {', '.join(DEVICE_KINDS)}")
        self.role = spec.get("role")
        self.label = spec.get("label", f"{self.device.replace('_', ' ')} on port {port}")
        self.mirrored = bool(spec.get("mirrored", False))
        position = spec.get("position", [0, 0])
        self.position = (float(position[0]), float(position[1]))
        self.raw = spec


class RobotSpec:
    def __init__(self, spec):
        if not isinstance(spec, dict):
            raise ShapeError("robot must be a dictionary")
        self.id = spec.get("id", "robot")
        self.name = spec.get("name", self.id)
        self.wheel_diameter = float(spec["wheel_diameter"])
        self.axle_track = float(spec["axle_track"])
        body = spec.get("body", {})
        self.front = float(body.get("front", 100))
        self.back = float(body.get("back", 60))
        self.half_width = float(body.get("width", 140)) / 2
        self.ports = {}
        for port, port_spec in spec.get("ports", {}).items():
            if port not in PORT_NAMES:
                raise ShapeError(f"unknown port '{port}'")
            self.ports[port] = PortSpec(port, port_spec)
        self.left_port = self._find_role("left_wheel")
        self.right_port = self._find_role("right_wheel")

    def _find_role(self, role):
        for port, spec in self.ports.items():
            if spec.role == role:
                if spec.device != "motor":
                    raise ShapeError(f"{role} on port {port} must be a motor")
                return port
        return None

    def motor_ports(self):
        return [(port, spec.raw) for port, spec in self.ports.items() if spec.device == "motor"]

    def sensor_ports(self, kind):
        return [port for port, spec in self.ports.items() if spec.device == kind]

    def outline(self, x, y, heading):
        """The robot's four corners in world coordinates, counterclockwise."""
        f, b, w = self.front, self.back, self.half_width
        return [
            to_world(x, y, heading, -b, -w),
            to_world(x, y, heading, f, -w),
            to_world(x, y, heading, f, w),
            to_world(x, y, heading, -b, w),
        ]

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "wheel_diameter": self.wheel_diameter,
            "axle_track": self.axle_track,
            "body": {"front": self.front, "back": self.back, "width": self.half_width * 2},
            "ports": {p: {"device": s.device, "role": s.role, "label": s.label} for p, s in self.ports.items()},
        }
