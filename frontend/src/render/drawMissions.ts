// Mission Mode drawing: mission models on the mat and attachments on the robot.
// Called by drawMat only when a scene has them. World coordinates are y up,
// headings clockwise (see drawMat.ts).

import type { ArmState } from "../missions";
import type { ModelSpec, ModelState, Pose } from "../types";

export interface ModelView {
  spec: ModelSpec;
  state: ModelState;
}

const WOOD = "#b7793f";
const WOOD_EDGE = "#7a4a1d";
const STEEL = "#64748b";
const DONE = "#15803d";

type Label = (text: string, x: number, y: number) => void;

function rectAt(ctx: CanvasRenderingContext2D, x: number, y: number, w: number, h: number, angle = 0) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate((-angle * Math.PI) / 180);
  ctx.beginPath();
  ctx.rect(-w / 2, -h / 2, w, h);
  ctx.restore();
}

function circleAt(ctx: CanvasRenderingContext2D, x: number, y: number, r: number) {
  ctx.beginPath();
  ctx.arc(x, y, r, 0, Math.PI * 2);
}

/** A bar from (x, y) along a clockwise heading, `length` long and `width` wide. */
function barAt(ctx: CanvasRenderingContext2D, x: number, y: number, heading: number, length: number, width: number) {
  ctx.save();
  ctx.translate(x, y);
  ctx.rotate((-heading * Math.PI) / 180);
  ctx.beginPath();
  ctx.roundRect(0, -width / 2, Math.max(length, 1), width, width / 2);
  ctx.restore();
}

function fillStroke(ctx: CanvasRenderingContext2D, fill: string, stroke: string, s: number, width = 2) {
  ctx.fillStyle = fill;
  ctx.fill();
  ctx.strokeStyle = stroke;
  ctx.lineWidth = width / s;
  ctx.stroke();
}

export function drawModels(ctx: CanvasRenderingContext2D, models: ModelView[], s: number, label: Label) {
  for (const { spec, state } of models) {
    if (state.hidden || state.state === "removed") continue;
    const [ax, ay] = spec.at ?? spec.hinge ?? [0, 0];
    const name = spec.label ?? spec.id;
    switch (spec.type) {
      case "block": {
        const x = state.x ?? ax;
        const y = state.y ?? ay;
        if (spec.r) circleAt(ctx, x, y, spec.r);
        else rectAt(ctx, x, y, spec.size?.[0] ?? 60, spec.size?.[1] ?? 60, spec.angle ?? 0);
        ctx.save();
        ctx.shadowColor = "rgba(0, 0, 0, 0.3)";
        ctx.shadowBlur = 6;
        fillStroke(ctx, WOOD, WOOD_EDGE, s);
        ctx.restore();
        label(name, x, y - (spec.r ?? (spec.size?.[1] ?? 60) / 2) - 18);
        break;
      }
      case "lever": {
        const done = state.state === spec.states?.[1];
        barAt(ctx, ax, ay, state.angle ?? spec.angle ?? 0, spec.length ?? 100, spec.width ?? 20);
        fillStroke(ctx, done ? DONE : "#f59f0a", "#374151", s);
        circleAt(ctx, ax, ay, 12);
        fillStroke(ctx, "#374151", "#1f2937", s);
        label(name, ax, ay - 30);
        break;
      }
      case "button": {
        const [w, h] = spec.size ?? [40, 40];
        rectAt(ctx, ax, ay, w, h, spec.angle ?? 0);
        fillStroke(ctx, state.down ? "#991b1b" : "#e5484d", "#7f1d1d", s, 3);
        label(state.presses ? `${name} ×${state.presses}` : name, ax, ay + h / 2 + 22);
        break;
      }
      case "loop": {
        const r = spec.r ?? 25;
        if (state.state === "on_post") {
          circleAt(ctx, ax, ay, 10);
          fillStroke(ctx, STEEL, "#334155", s);
        }
        const x = state.x ?? ax;
        const y = state.y ?? ay;
        ctx.save();
        if (state.state === "carried") {
          ctx.shadowColor = "rgba(0, 0, 0, 0.45)";
          ctx.shadowBlur = 10;
          ctx.shadowOffsetX = 4;
          ctx.shadowOffsetY = -4;
        }
        circleAt(ctx, x, y, r - 4);
        ctx.strokeStyle = "#c026d3";
        ctx.lineWidth = 8;
        ctx.stroke();
        ctx.restore();
        if (state.state !== "carried") label(name, x, y + r + 20);
        break;
      }
      case "flag": {
        const [w, h] = spec.size ?? [60, 60];
        const raised = state.state === "raised";
        rectAt(ctx, ax, ay, w, h);
        ctx.save();
        ctx.setLineDash([6 / s, 4 / s]);
        ctx.strokeStyle = "rgba(55, 65, 81, 0.6)";
        ctx.lineWidth = 1.5 / s;
        ctx.stroke();
        ctx.restore();
        if (spec.pole) {
          const [px, py] = spec.pole;
          circleAt(ctx, px, py, 10);
          fillStroke(ctx, STEEL, "#334155", s);
          ctx.beginPath();
          if (raised) {
            ctx.moveTo(px, py);
            ctx.lineTo(px - 70, py + 30);
            ctx.lineTo(px - 70, py - 30);
          } else {
            ctx.rect(px - 60, py - 8, 50, 16);
          }
          ctx.closePath();
          fillStroke(ctx, raised ? "#e5484d" : "#9ca3af", "#374151", s);
        }
        label(raised ? `${name} ▲` : name, ax, ay - h / 2 - 20);
        break;
      }
      case "gate": {
        const [w, h] = spec.size ?? [20, 200];
        rectAt(ctx, ax, ay, w, h, spec.angle ?? 0);
        if (state.state === "open") {
          ctx.save();
          ctx.setLineDash([8 / s, 6 / s]);
          ctx.strokeStyle = STEEL;
          ctx.lineWidth = 2 / s;
          ctx.stroke();
          ctx.restore();
        } else {
          fillStroke(ctx, "#475569", "#1e293b", s);
        }
        label(name, ax, ay + h / 2 + 18);
        break;
      }
    }
  }
}

const ARM_COLORS = { lift: "#f08c00", sweep: "#7c3aed", slide: "#0891b2" } as const;

/** Attachments on the robot, seen from above. A lift arm looks shorter and lighter as it rises. */
export function drawArms(ctx: CanvasRenderingContext2D, pose: Pose, arms: ArmState[], s: number) {
  ctx.save();
  ctx.translate(pose.x, pose.y);
  ctx.rotate((-pose.heading * Math.PI) / 180);
  // Robot frame: +x forward, +y left. A clockwise direction d points at (cos d, -sin d).
  for (const { spec, angle } of arms) {
    const [forward, left] = spec.mount ?? [110, 0];
    const width = spec.width ?? 30;
    let heading = spec.direction ?? 0;
    let length = spec.length;
    let alpha = 0.95;
    if (spec.kind === "lift") {
      const a = (angle * Math.PI) / 180;
      length = spec.length * Math.cos(a);
      alpha = 0.95 - 0.5 * Math.max(0, Math.sin(a));
    } else if (spec.kind === "sweep") {
      heading += angle;
    } else {
      length = spec.length + angle * (spec.travel ?? 0.5);
    }
    ctx.save();
    ctx.globalAlpha = alpha;
    // The robot frame is y-left, so a clockwise heading is a negative rotation here too.
    barAt(ctx, forward, left, heading, length, width);
    fillStroke(ctx, ARM_COLORS[spec.kind], "#1f2937", s, 1.5);
    if (spec.kind === "lift" && spec.hook) {
      const at = typeof spec.hook === "object" ? spec.hook.at ?? spec.length : spec.length;
      const reach = at * Math.cos((angle * Math.PI) / 180);
      const r = (heading * Math.PI) / 180;
      circleAt(ctx, forward + reach * Math.cos(r), left - reach * Math.sin(r), 7);
      fillStroke(ctx, "#1f2937", "#1f2937", s, 1);
    }
    ctx.restore();
    circleAt(ctx, forward, left, 6);
    fillStroke(ctx, "#1f2937", "#1f2937", s, 1);
  }
  ctx.restore();
}
