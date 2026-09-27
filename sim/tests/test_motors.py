import pytest

from conftest import printed


def test_run_angle_and_angle(run):
    result = run("""
        arm = Motor(Port.E)
        arm.run_angle(300, 45)
        print(arm.angle())
        arm.run_angle(-300, 45)
        print(arm.angle())
    """)
    assert printed(result) == ["45", "0"]


def test_run_target(run):
    result = run("""
        arm = Motor(Port.E)
        arm.run_target(500, 60)
        arm.run_target(500, -20)
        print(arm.angle())
    """)
    assert printed(result) == ["-20"]


def test_run_until_stalled_stops_at_limit(run):
    result = run("""
        arm = Motor(Port.F)
        print(arm.run_until_stalled(400))
    """)
    assert printed(result) == ["90"]


def test_run_time_and_speed(run):
    result = run("""
        arm = Motor(Port.E)
        arm.run(-200)
        wait(300)
        print(arm.speed())
        arm.stop()
        arm.reset_angle(0)
        print(arm.angle())
    """)
    assert printed(result) == ["-200", "0"]


def test_counterclockwise_flips_angle(run):
    result = run("""
        arm = Motor(Port.E, Direction.COUNTERCLOCKWISE)
        arm.run_angle(300, 30)
        print(arm.angle())
    """)
    assert printed(result) == ["30"]
    assert result["motors"]["E"][-1] == pytest.approx(-30, abs=0.5)


def test_gears(run):
    result = run("""
        arm = Motor(Port.E, gears=[12, 36])
        arm.run_angle(100, 20)
        print(arm.angle())
    """)
    assert printed(result) == ["20"]
    assert result["motors"]["E"][-1] == pytest.approx(60, abs=0.5)


def test_arm_angles_are_recorded(run):
    result = run("""
        Motor(Port.E).run_target(500, 80)
    """)
    assert result["motors"]["E"][0] == 0
    assert result["motors"]["E"][-1] == pytest.approx(80, abs=0.5)
    assert set(result["motors"]) == {"E", "F"}


def test_missing_device_gives_friendly_error(run):
    result = run("sensor = ColorSensor(Port.F)")
    error = result["end"]["error"]
    assert error["type"] == "OSError"
    assert "Port.F has a motor plugged in" in error["kid_message"]
    assert error["line"] == 11


def test_force_sensor_not_on_robot(run):
    result = run("""
        from pybricks.pupdevices import ForceSensor
        button = ForceSensor(Port.E)
    """)
    assert "not a force sensor" in result["end"]["error"]["kid_message"]
