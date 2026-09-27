// Draws the mat, the robot and its path on a canvas.
// World units are millimeters, y up. The canvas is y down, so y is flipped.
// Headings are clockwise from +x in the world, which is also clockwise on
// screen, so angles can be used as-is after the flip.

import type { ColorName, Pose, RobotSpec, WorldSpec } from "../types";

export const MAT_COLORS: Record<ColorName, string> = {
  black: "#1f2328",
  gray: "#9aa0a6",
  white: "#fdfdfb",
  red: "#e5484d",
  orange: "#f59f0a",
  brown: "#8d6e63",
  yellow: "#ffd60a",
  green: "#2fb344",
  cyan: "#22c3e6",
  blue: "#2f6fed",
  violet: "#8e5cf7",
  magenta: "#e0409a",
};

const WALL = 36; // mm of table wall drawn around the mat

export interface MatScene {
  world: WorldSpec;
  robot: RobotSpec;
  pose: Pose;
  trail?: { x: number[]; y: number[]; count: number };
  hubLight?: string;
  sensorColor?: string;
  bumping?: boolean;
  showZones?: boolean;
}

export interface MatLayout {
  scale: number;
  width: number;
  height: number;
}

export function layoutFor(world: WorldSpec, cssWidth: number): MatLayout {
  const [w, h] = world.size;
  const scale = cssWidth / (w + 2 * WALL);
  return { scale, width: cssWidth, height: (h + 2 * WALL) * scale };
}

export function drawMat(ctx: CanvasRenderingContext2D, layout: MatLayout, scene: MatScene) {
  const { world } = scene;
  const [w, h] = world.size;
  const s = layout.scale;
  ctx.save();
  ctx.clearRect(0, 0, layout.width, layout.height);

  // Table wall.
  ctx.fillStyle = "#c79a64";
  roundRect(ctx, 0, 0, layout.width, layout.height, 10 * s * 3);
  ctx.fill();

  // Switch to world coordinates: origin bottom-left of the mat, y up.
  ctx.translate(WALL * s, (WALL + h) * s);
  ctx.scale(s, -s);

  ctx.fillStyle = MAT_COLORS[world.background ?? "white"];
  ctx.fillRect(0, 0, w, h);

  if (world.grid) drawGrid(ctx, w, h, world.grid, s);
  for (const shape of world.shapes ?? []) drawShape(ctx, shape);
  if (scene.showZones !== false) for (const zone of world.zones ?? []) drawZone(ctx, zone, s);
  for (const obstacle of world.obstacles ?? []) drawObstacle(ctx, obstacle, s);
  if (scene.trail) drawTrail(ctx, scene.trail, s);
  drawRobot(ctx, scene, s);

  ctx.restore();
}

function roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, r: number) {
  ctx.beginPath();
  ctx.roundRect(x, y, w, h, r);
}

function drawGrid(ctx: CanvasRenderingContext2D, w: number, h: number, step: number, s: number) {
  ctx.strokeStyle = "rgba(47, 111, 237, 0.10)";
  ctx.lineWidth = 1 / s;
  ctx.beginPath();
  for (let x = step; x < w; x += step) {
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
  }
  for (let y = step; y < h; y += step) {
    ctx.moveTo(0, y);
    ctx.lineTo(w, y);
  }
  ctx.stroke();
  // Stronger line every meter.
  ctx.strokeStyle = "rgba(47, 111, 237, 0.22)";
  ctx.beginPath();
  for (let x = 1000; x < w; x += 1000) {
    ctx.moveTo(x, 0);
    ctx.lineTo(x, h);
  }
  ctx.stroke();
}

type Shape = NonNullable<WorldSpec["shapes"]>[number];

function shapePath(ctx: CanvasRenderingContext2D, shape: Shape) {
  ctx.beginPath();
  if (shape.type === "rect") {
    const cx = shape.x + shape.w / 2;
    const cy = shape.y + shape.h / 2;
    ctx.save();
    ctx.translate(cx, cy);
    // World angles are clockwise; in this y-up frame that's a negative rotation.
    ctx.rotate((-(shape.angle ?? 0) * Math.PI) / 180);
    ctx.rect(-shape.w / 2, -shape.h / 2, shape.w, shape.h);
    ctx.restore();
  } else if (shape.type === "circle") {
    ctx.arc(shape.x, shape.y, shape.r, 0, Math.PI * 2);
  }
}

function drawShape(ctx: CanvasRenderingContext2D, shape: Shape) {
  const color = MAT_COLORS[(shape.color ?? "black") as ColorName];
  if (shape.type === "line") {
    ctx.strokeStyle = color;
    ctx.lineWidth = shape.width ?? 20;
    ctx.lineCap = "round";
    ctx.lineJoin = "round";
    ctx.beginPath();
    shape.points.forEach(([x, y], i) => (i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y)));
    if (shape.closed) ctx.closePath();
    ctx.stroke();
    return;
  }
  if (shape.type === "arc") {
    ctx.strokeStyle = color;
    ctx.lineWidth = shape.width ?? 20;
    ctx.lineCap = "round";
    ctx.beginPath();
    const full = shape.start === undefined && shape.end === undefined;
    const start = shape.start ?? 0;
    let sweep = full ? 360 : (((shape.end ?? 360) - start) % 360 + 360) % 360;
    if (sweep === 0) sweep = 360;
    // Clockwise headings are negative angles in this y-up frame.
    ctx.arc(shape.x, shape.y, shape.r, (-start * Math.PI) / 180, (-(start + sweep) * Math.PI) / 180, true);
    ctx.stroke();
    return;
  }
  ctx.fillStyle = color;
  shapePath(ctx, shape);
  ctx.fill();
}

function drawLabel(ctx: CanvasRenderingContext2D, text: string, x: number, y: number, s: number, color: string) {
  ctx.save();
  ctx.translate(x, y);
  ctx.scale(1 / s, -1 / s);
  ctx.font = "600 12px system-ui, sans-serif";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  const width = ctx.measureText(text).width + 10;
  ctx.fillStyle = "rgba(255, 255, 255, 0.85)";
  ctx.beginPath();
  ctx.roundRect(-width / 2, -9, width, 18, 9);
  ctx.fill();
  ctx.fillStyle = color;
  ctx.fillText(text, 0, 1);
  ctx.restore();
}

function drawZone(ctx: CanvasRenderingContext2D, zone: NonNullable<WorldSpec["zones"]>[number], s: number) {
  ctx.save();
  ctx.strokeStyle = "rgba(94, 60, 180, 0.8)";
  ctx.lineWidth = 2 / s;
  ctx.setLineDash([8 / s, 6 / s]);
  shapePath(ctx, zone);
  ctx.stroke();
  ctx.restore();
  const cx = zone.type === "rect" ? zone.x + zone.w / 2 : zone.x;
  const top = zone.type === "rect" ? zone.y + zone.h : zone.y + zone.r;
  drawLabel(ctx, zone.label ?? zone.id, cx, top - 14 / s, s, "#4b2a9e");
}

function drawObstacle(ctx: CanvasRenderingContext2D, obstacle: NonNullable<WorldSpec["obstacles"]>[number], s: number) {
  ctx.save();
  ctx.shadowColor = "rgba(0, 0, 0, 0.35)";
  ctx.shadowBlur = 8;
  ctx.shadowOffsetX = 3;
  ctx.shadowOffsetY = 3;
  ctx.fillStyle = "#6b7280";
  shapePath(ctx, obstacle);
  ctx.fill();
  ctx.restore();
  ctx.strokeStyle = "#374151";
  ctx.lineWidth = 2 / s;
  shapePath(ctx, obstacle);
  ctx.stroke();
  if (obstacle.label) {
    const cx = obstacle.type === "rect" ? obstacle.x + obstacle.w / 2 : obstacle.x;
    const cy = obstacle.type === "rect" ? obstacle.y + obstacle.h / 2 : obstacle.y;
    drawLabel(ctx, obstacle.label, cx, cy, s, "#1f2937");
  }
}

function drawTrail(ctx: CanvasRenderingContext2D, trail: NonNullable<MatScene["trail"]>, s: number) {
  if (trail.count < 2) return;
  ctx.save();
  ctx.strokeStyle = "rgba(229, 72, 77, 0.55)";
  ctx.lineWidth = 3 / s;
  ctx.setLineDash([6 / s, 5 / s]);
  ctx.beginPath();
  ctx.moveTo(trail.x[0], trail.y[0]);
  for (let i = 1; i < trail.count; i++) ctx.lineTo(trail.x[i], trail.y[i]);
  ctx.stroke();
  ctx.restore();
}

function drawRobot(ctx: CanvasRenderingContext2D, scene: MatScene, s: number) {
  const { robot, pose } = scene;
  const { front, back, width } = robot.body;
  const half = width / 2;
  const wheelR = robot.wheel_diameter / 2;
  const track = robot.axle_track / 2;

  ctx.save();
  ctx.translate(pose.x, pose.y);
  // Robot frame: +x forward, +y left (y-up world, clockwise-positive heading).
  ctx.rotate((-pose.heading * Math.PI) / 180);

  // Shadow + body.
  ctx.save();
  ctx.shadowColor = "rgba(0, 0, 0, 0.3)";
  ctx.shadowBlur = 10;
  ctx.fillStyle = "#f5f5f0";
  ctx.beginPath();
  ctx.roundRect(-back, -half, back + front, width, 14);
  ctx.fill();
  ctx.restore();
  ctx.strokeStyle = scene.bumping ? "#e5484d" : "#3f3f46";
  ctx.lineWidth = (scene.bumping ? 4 : 2) / s;
  ctx.beginPath();
  ctx.roundRect(-back, -half, back + front, width, 14);
  ctx.stroke();

  // Wheels.
  ctx.fillStyle = "#27272a";
  for (const side of [-1, 1]) {
    ctx.beginPath();
    ctx.roundRect(-wheelR, side * track - 7, wheelR * 2, 14, 4);
    ctx.fill();
  }

  // Hub (with its light).
  ctx.fillStyle = "#ffffff";
  ctx.strokeStyle = "#a1a1aa";
  ctx.lineWidth = 1.5 / s;
  ctx.beginPath();
  ctx.roundRect(-45, -40, 70, 80, 8);
  ctx.fill();
  ctx.stroke();
  const light = scene.hubLight && scene.hubLight !== "off" ? MAT_COLORS[scene.hubLight as ColorName] : "#d4d4d8";
  ctx.fillStyle = light ?? "#d4d4d8";
  ctx.beginPath();
  ctx.arc(-10, 0, 9, 0, Math.PI * 2);
  ctx.fill();

  // Direction arrow.
  ctx.fillStyle = "#2f6fed";
  ctx.beginPath();
  ctx.moveTo(front - 8, 0);
  ctx.lineTo(front - 26, 12);
  ctx.lineTo(front - 26, -12);
  ctx.closePath();
  ctx.fill();

  // Sensors from the port map.
  for (const port of Object.values(robot.ports)) {
    if (!port.position) continue;
    const [fx, left] = port.position;
    if (port.device === "color_sensor") {
      ctx.fillStyle = "#18181b";
      ctx.beginPath();
      ctx.arc(fx, left, 11, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = scene.sensorColor ? MAT_COLORS[scene.sensorColor as ColorName] ?? "#fff" : "#fff";
      ctx.beginPath();
      ctx.arc(fx, left, 6, 0, Math.PI * 2);
      ctx.fill();
    } else if (port.device === "ultrasonic_sensor") {
      ctx.fillStyle = "#18181b";
      for (const eye of [-16, 16]) {
        ctx.beginPath();
        ctx.arc(fx - 4, left + eye, 9, 0, Math.PI * 2);
        ctx.fill();
      }
    }
  }
  ctx.restore();
}
