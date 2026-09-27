import pytest

from conftest import final_pose, printed


def test_straight_drives_exact_distance(run):
    x, y, h = final_pose(run("drive_base.straight(500)"))
    assert x == pytest.approx(2000, abs=0.5)
    assert y == pytest.approx(1500, abs=0.5)
    assert h == pytest.approx(0, abs=0.01)


def test_straight_backwards(run):
    x, _, _ = final_pose(run("drive_base.straight(-300)"))
    assert x == pytest.approx(1200, abs=0.5)


def test_positive_turn_is_clockwise(run):
    result = run("""
        drive_base.turn(90)
        drive_base.straight(200)
    """)
    x, y, h = final_pose(result)
    assert h == pytest.approx(90, abs=0.01)
    # Heading 90 faces down the mat (-y) because turns are clockwise.
    assert (x, y) == (pytest.approx(1500, abs=0.5), pytest.approx(1300, abs=0.5))


def test_square_returns_home(run):
    result = run("""
        for i in range(4):
            drive_base.straight(300)
            drive_base.turn(-90)
    """)
    x, y, h = final_pose(result)
    assert (x, y) == (pytest.approx(1500, abs=0.5), pytest.approx(1500, abs=0.5))
    assert h == pytest.approx(-360, abs=0.01)


def test_distance_and_angle_readings(run):
    result = run("""
        drive_base.straight(250)
        print(drive_base.distance())
        drive_base.turn(45)
        print(drive_base.angle())
        drive_base.reset()
        print(drive_base.distance(), drive_base.angle())
    """)
    assert printed(result) == ["250", "45", "0 0"]


def test_forgetting_counterclockwise_spins_in_place(run):
    """With both motors CLOCKWISE, one wheel goes backwards, like a real robot."""
    result = run("""
        left_motor = Motor(Port.A)
        right_motor = Motor(Port.B)
        drive_base = DriveBase(left_motor, right_motor, wheel_diameter=56, axle_track=112)
        drive_base.straight(300)
    """)
    x, y, h = final_pose(result)
    assert (x, y) == (pytest.approx(1500, abs=1), pytest.approx(1500, abs=1))
    assert abs(h) > 100


def test_wrong_wheel_diameter_drives_wrong_distance(run):
    result = run("""
        drive_base = DriveBase(left_motor, right_motor, wheel_diameter=112, axle_track=112)
        drive_base.straight(400)
    """)
    x, _, _ = final_pose(result)
    # The robot thinks its wheels are twice as big, so it only goes half as far.
    assert x == pytest.approx(1700, abs=1)


def test_drive_keeps_going_while_waiting(run):
    result = run("""
        drive_base.drive(200, 0)
        wait(2000)
        drive_base.stop()
    """)
    x, _, _ = final_pose(result)
    # Ramps up at 700 mm/s^2, so a little less than 400 mm.
    assert 340 < x - 1500 < 400


def test_drive_turn_rate_curves(run):
    result = run("""
        drive_base.drive(100, 45)
        wait(4000)
        drive_base.stop()
    """)
    _, y, h = final_pose(result)
    assert h > 100
    assert y < 1500


def test_curve(run):
    result = run("drive_base.curve(200, 90)")
    x, y, h = final_pose(result)
    assert h == pytest.approx(90, abs=0.5)
    assert x == pytest.approx(1700, abs=2)
    assert y == pytest.approx(1300, abs=2)


def test_settings_change_speed(run):
    slow = run("""
        drive_base.settings(straight_speed=100)
        drive_base.straight(500)
    """)
    fast = run("""
        drive_base.settings(straight_speed=400, straight_acceleration=1000)
        drive_base.straight(500)
    """)
    assert slow["end"]["t"] > fast["end"]["t"] * 2
    assert run("print(drive_base.settings())")["prints"][0]["text"] == "(200, 700, 180, 720)"


def test_wait_false_returns_immediately(run):
    result = run("""
        drive_base.straight(500, wait=False)
        print(drive_base.done())
        while not drive_base.done():
            wait(10)
        print(drive_base.done())
    """)
    assert printed(result) == ["False", "True"]
    x, _, _ = final_pose(result)
    assert x == pytest.approx(2000, abs=0.5)


def test_stop_none_keeps_moving(run):
    result = run("""
        drive_base.straight(200, then=Stop.NONE)
        wait(500)
        drive_base.stop()
    """)
    x, _, _ = final_pose(result)
    assert x > 1700 + 50


def test_wall_stops_robot_and_records_collision(run):
    world = {"size": [1000, 1000], "start": {"x": 500, "y": 500, "heading": 0}}
    result = run("drive_base.straight(1000)", world=world)
    x, _, _ = final_pose(result)
    assert x < 1000 - 110 + 2  # the front of the robot is 110 mm ahead of its center
    kinds = [e["type"] for e in result["events"]]
    assert "collision" in kinds
    assert "stalled" in kinds
    assert result["end"]["reason"] == "finished"


def test_obstacle_blocks_robot(run):
    world = {
        "size": [2000, 1000],
        "start": {"x": 300, "y": 500, "heading": 0},
        "obstacles": [{"label": "box", "type": "rect", "x": 800, "y": 400, "w": 100, "h": 200}],
    }
    result = run("drive_base.straight(1000)", world=world)
    x, _, _ = final_pose(result)
    assert x < 800 - 110 + 2
    assert result["events"][0]["what"] == "box"


def test_realism_drifts_without_gyro_but_not_with(run):
    drift = run("drive_base.straight(1500)", realism="on")
    fixed = run("""
        drive_base.use_gyro(True)
        drive_base.straight(1500)
    """, realism="on")
    _, y_drift, h_drift = final_pose(drift)
    _, y_fixed, h_fixed = final_pose(fixed)
    assert abs(y_drift - 1500) > 150
    assert abs(y_fixed - 1500) < 30
    assert abs(h_fixed) < 2


def test_gyro_turn_is_accurate_with_realism(run):
    result = run("""
        drive_base.use_gyro(True)
        drive_base.turn(90)
        print(round(hub.imu.heading()))
    """, realism="on")
    assert abs(final_pose(result)[2] - 90) < 3


def test_driving_with_motors_directly(run):
    result = run("""
        left_motor.run_angle(500, 360, wait=False)
        right_motor.run_angle(500, 360)
    """)
    x, _, _ = final_pose(result)
    assert x - 1500 == pytest.approx(3.14159 * 56, abs=1)


def test_driving_with_motors_cancels_drive_base_move(run):
    result = run("""
        drive_base.straight(1000, wait=False)
        wait(500)
        left_motor.stop()
        right_motor.stop()
        wait(1000)
        print(drive_base.done())
    """)
    x, _, _ = final_pose(result)
    assert x < 1500 + 200
    assert printed(result) == ["True"]


def test_stop_coasts_and_brake_stops_sooner(run):
    def after(stop_call):
        result = run(f"""
            drive_base.drive(300, 0)
            wait(1500)
            print(drive_base.distance())
            drive_base.{stop_call}()
            wait(1000)
            print(drive_base.distance())
        """)
        before, later = (int(v) for v in printed(result))
        return later - before

    coasted, braked = after("stop"), after("brake")
    assert 35 < coasted < 55
    assert 12 < braked < 25


def test_robot_rolls_to_a_halt_when_the_program_ends(run):
    result = run("""
        drive_base.drive(300, 0)
        wait(1000)
    """)
    x, _, _ = final_pose(result)
    stopped_at = result["frames"]["x"][result["frames"]["t"].index(1000)]
    assert x - stopped_at > 35
    assert result["end"]["t"] > 1000


def test_motor_stop_coasts(run):
    result = run("""
        arm = Motor(Port.E)
        arm.run(500)
        wait(100)
        arm.stop()
        print(arm.angle())
        wait(500)
        print(arm.angle())
    """)
    first, second = (int(v) for v in printed(result))
    assert second > first
