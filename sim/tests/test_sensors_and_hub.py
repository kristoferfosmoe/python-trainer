import pytest

from conftest import SETUP_LINES, final_pose, printed
from trainer_sim.world import World

LINE_WORLD = {
    "size": [2000, 1000],
    "start": {"x": 300, "y": 500, "heading": 0},
    "shapes": [
        {"type": "line", "points": [[1000, 100], [1000, 900]], "width": 20, "color": "black"},
        {"type": "rect", "x": 1400, "y": 400, "w": 200, "h": 200, "color": "red"},
    ],
}


def test_reflection_white_black_and_edge():
    world = World(LINE_WORLD)
    assert world.reflection(500, 500) == pytest.approx(98)
    assert world.reflection(1000, 500) == pytest.approx(9)
    # Exactly on the edge of the line: half and half.
    assert world.reflection(1010, 500) == pytest.approx((98 + 9) / 2, abs=0.5)


def test_reflection_changes_smoothly_across_edge():
    world = World(LINE_WORLD)
    readings = [world.reflection(x, 500) for x in range(1000, 1022, 2)]
    assert readings == sorted(readings)
    steps = [b - a for a, b in zip(readings, readings[1:])]
    assert max(steps) < 20


def test_color_names():
    world = World(LINE_WORLD)
    assert world.color_at(500, 500) == "white"
    assert world.color_at(1000, 500) == "black"
    assert world.color_at(1500, 500) == "red"


def test_color_sensor_in_program(run):
    result = run("""
        sensor = ColorSensor(Port.C)
        print(sensor.color(), sensor.reflection())
        drive_base.drive(200, 0)
        while sensor.color() != Color.BLACK:
            pass
        drive_base.stop()
        print(sensor.color(), sensor.reflection() < 50)
    """, world=LINE_WORLD)
    assert printed(result) == ["Color.WHITE 98", "Color.BLACK True"]


def test_detectable_colors_picks_nearest(run):
    over_red = dict(LINE_WORLD, start={"x": 1425, "y": 500, "heading": 0})
    result = run("""
        sensor = ColorSensor(Port.C)
        print(sensor.color())
        sensor.detectable_colors([Color.WHITE, Color.BLACK])
        print(sensor.color())
    """, world=over_red)
    assert printed(result) == ["Color.RED", "Color.WHITE"]


def test_ultrasonic_sees_wall_and_obstacles(run):
    world = {
        "size": [2000, 5000],
        "start": {"x": 300, "y": 500, "heading": 0},
        "obstacles": [{"type": "circle", "x": 1000, "y": 500, "r": 100}],
    }
    result = run("""
        eyes = UltrasonicSensor(Port.D)
        print(eyes.distance())
        drive_base.turn(180)
        print(eyes.distance())
        drive_base.turn(90)
        print(eyes.distance())
    """, world=world)
    # Sensor is 105 mm in front of the center. Facing up, the far wall is out of range.
    assert printed(result) == [str(1000 - 100 - 405), str(300 - 105), "2000"]


def test_gyro_heading_and_reset(run):
    result = run("""
        drive_base.turn(90)
        print(hub.imu.heading())
        hub.imu.reset_heading(0)
        drive_base.turn(-30)
        print(hub.imu.heading())
    """)
    assert printed(result) == ["90.0", "-30.0"]


def test_hub_display_light_and_sounds(run):
    result = run("""
        hub.light.on(Color.RED)
        hub.display.text("Hi")
        hub.speaker.beep(440, 200)
        hub.speaker.play_notes(["C4/4", "R/4", "E4/8"], tempo=120)
        hub.light.off()
    """)
    events = [(e["type"], e.get("color") or e.get("text") or e.get("frequency")) for e in result["events"]]
    assert events == [
        ("light", "red"), ("display", "Hi"), ("beep", 440), ("beep", 262), ("beep", 330), ("light", "off"),
    ]
    # text() blocks 2 chars x 550 ms; beep 200 ms; notes: 500 + 500 + 250 ms.
    assert result["end"]["t"] == pytest.approx(1100 + 200 + 1250, abs=5)


def test_stopwatch(run):
    result = run("""
        watch = StopWatch()
        wait(1500)
        print(watch.time())
        watch.pause()
        wait(1000)
        print(watch.time())
        watch.resume()
        wait(500)
        print(watch.time())
    """)
    times = [int(t) for t in printed(result)]
    assert times[0] == pytest.approx(1500, abs=5)
    assert times[1] == times[0]
    assert times[2] == pytest.approx(2000, abs=10)


def test_buttons_follow_schedule(run):
    result = run("""
        while not hub.buttons.pressed():
            wait(10)
        print(hub.buttons.pressed())
    """, buttons=[{"at": 1000, "button": "LEFT", "duration": 500}])
    assert printed(result) == ["{Button.LEFT}"]
    assert result["end"]["t"] == pytest.approx(1000, abs=20)


def test_center_button_stops_the_program_like_a_real_hub(run):
    result = run("""
        print("waiting")
        while not hub.buttons.pressed():
            wait(10)
        print("never printed")
    """, buttons=[{"at": 1000, "button": "CENTER", "duration": 300}])
    assert printed(result) == ["waiting"]
    end = result["end"]
    assert end["reason"] == "error"
    assert end["t"] == pytest.approx(1000, abs=10)
    assert end["error"]["type"] == "SystemExit"
    assert end["error"]["line"] == SETUP_LINES + 3  # stopped inside wait()
    assert "set_stop_button(Button.BLUETOOTH)" in end["error"]["kid_message"]


def test_center_button_stops_the_robot_mid_drive(run):
    result = run("drive_base.straight(1000)", buttons=[{"at": 500, "button": "CENTER"}])
    assert result["end"]["error"]["type"] == "SystemExit"
    x, _, _ = final_pose(result)
    assert x - 1500 < 200  # stopped (and rolled a little), far short of 1000 mm


def test_another_stop_button_frees_the_center_button(run):
    result = run("""
        from pybricks.parameters import Button
        hub.system.set_stop_button(Button.BLUETOOTH)
        while not hub.buttons.pressed():
            wait(10)
        print(hub.buttons.pressed())
    """, buttons=[{"at": 1000, "button": "CENTER"}])
    assert result["end"]["reason"] == "finished"
    assert printed(result) == ["{Button.CENTER}"]


def test_no_stop_button_and_button_combinations(run):
    code = """
        from pybricks.parameters import Button
        hub.system.set_stop_button({stop})
        wait(3000)
        print("done")
    """
    presses = [{"at": 500, "button": "CENTER"}, {"at": 1000, "button": "LEFT"}, {"at": 2000, "button": "LEFT"},
               {"at": 2050, "button": "RIGHT"}]
    assert printed(run(code.format(stop="None"), buttons=presses)) == ["done"]
    both = run(code.format(stop="(Button.LEFT, Button.RIGHT)"), buttons=presses)
    assert both["end"]["t"] == pytest.approx(2050, abs=10)
    assert "Button.LEFT + Button.RIGHT" in both["end"]["error"]["kid_message"]


def test_set_stop_button_needs_buttons(run):
    result = run("hub.system.set_stop_button('center')")
    assert result["end"]["error"]["type"] == "TypeError"
    assert "Button.BLUETOOTH" in result["end"]["error"]["kid_message"]


def test_presses_after_the_program_ends_are_ignored(run):
    result = run("""
        drive_base.drive(300, 0)
        wait(500)
    """, buttons=[{"at": 600, "button": "CENTER"}])
    assert result["end"]["reason"] == "finished"


def test_sensor_noise_is_repeatable(run):
    code = """
        sensor = ColorSensor(Port.C)
        values = []
        for i in range(5):
            values.append(sensor.reflection())
            wait(10)
        print(values)
    """
    a = run(code, realism="on", seed=7)
    b = run(code, realism="on", seed=7)
    assert printed(a) == printed(b)
    assert len(set(eval(printed(a)[0]))) > 1
