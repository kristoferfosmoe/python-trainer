import { useEffect, useRef, useState } from "react";
import { frameIndexAt, hubAt, poseAt, recentCollision, sensorAt } from "../playback";
import { drawMat, layoutFor } from "../render/drawMat";
import type { Pose, RobotSpec, Trace, WorldSpec } from "../types";

interface Props {
  world: WorldSpec;
  robot: RobotSpec;
  start: Pose;
  trace: Trace | null;
  time: number;
}

export function MatView({ world, robot, start, trace, time }: Props) {
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(0);

  useEffect(() => {
    const observer = new ResizeObserver(([entry]) => setWidth(Math.floor(entry.contentRect.width)));
    observer.observe(wrap.current!);
    return () => observer.disconnect();
  }, []);

  useEffect(() => {
    const el = canvas.current;
    if (!el || width === 0) return;
    const layout = layoutFor(world, width);
    const ratio = window.devicePixelRatio || 1;
    el.width = Math.round(layout.width * ratio);
    el.height = Math.round(layout.height * ratio);
    el.style.width = `${layout.width}px`;
    el.style.height = `${layout.height}px`;
    const ctx = el.getContext("2d")!;
    ctx.setTransform(ratio, 0, 0, ratio, 0, 0);

    const colorPort = Object.entries(robot.ports).find(([, p]) => p.device === "color_sensor")?.[0];
    drawMat(ctx, layout, {
      world,
      robot,
      pose: trace ? poseAt(trace, time) : start,
      trail: trace
        ? { x: trace.frames.x, y: trace.frames.y, count: frameIndexAt(trace, time) + 1 }
        : undefined,
      hubLight: trace ? hubAt(trace, time).light : undefined,
      sensorColor: trace && colorPort ? (sensorAt(trace, `${colorPort}.color`, time) as string) : undefined,
      bumping: trace ? recentCollision(trace, time) : false,
    });
  }, [world, robot, start, trace, time, width]);

  return (
    <div className="mat" ref={wrap}>
      <canvas ref={canvas} role="img" aria-label={`${world.name}: the robot's mat`} />
    </div>
  );
}
