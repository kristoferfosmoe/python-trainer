// Talks to the simulator Web Worker. If a program runs too long (a loop that
// never ends and never waits), the worker is stopped and a fresh one started.

import type { RunRequest, Trace } from "../types";
import type { WorkerRequest, WorkerResponse } from "./worker";

export type RunnerStatus = "loading" | "ready" | "running" | "broken";

export class RunTimeout extends Error {}

const WALL_CLOCK_LIMIT_MS = 20_000;

export class SimRunner {
  private worker!: Worker;
  private nextId = 1;
  private pending = new Map<number, { resolve: (t: Trace) => void; reject: (e: Error) => void }>();
  private listeners = new Set<(status: RunnerStatus) => void>();
  status: RunnerStatus = "loading";
  pythonVersion = "";

  constructor() {
    this.spawn();
  }

  private spawn() {
    this.setStatus("loading");
    this.worker = new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });
    this.worker.onmessage = (event: MessageEvent<WorkerResponse>) => this.onMessage(event.data);
    this.worker.onerror = (event) => {
      this.setStatus("broken");
      console.error("Simulator worker error", event);
    };
  }

  private onMessage(message: WorkerResponse) {
    if (message.type === "ready") {
      this.pythonVersion = message.pythonVersion;
      this.setStatus(this.pending.size ? "running" : "ready");
      return;
    }
    if (message.type === "failed" && message.id === null) {
      this.setStatus("broken");
      return;
    }
    const entry = this.pending.get(message.id!);
    if (!entry) return;
    this.pending.delete(message.id!);
    if (this.status === "running" && this.pending.size === 0) this.setStatus("ready");
    if (message.type === "result") entry.resolve(JSON.parse(message.json) as Trace);
    else entry.reject(new Error(message.message));
  }

  private setStatus(status: RunnerStatus) {
    this.status = status;
    this.listeners.forEach((listener) => listener(status));
  }

  onStatus(listener: (status: RunnerStatus) => void) {
    this.listeners.add(listener);
    return () => this.listeners.delete(listener);
  }

  run(request: RunRequest): Promise<Trace> {
    const id = this.nextId++;
    const message: WorkerRequest = { type: "run", id, payload: JSON.stringify(request) };
    if (this.status === "ready") this.setStatus("running");
    return new Promise<Trace>((resolve, reject) => {
      // Loading Python doesn't count against the program's time.
      let timer: ReturnType<typeof setTimeout> | undefined;
      const startTimer = () => {
        timer = setTimeout(() => {
          this.pending.delete(id);
          this.worker.terminate();
          this.spawn();
          reject(new RunTimeout("The program took too long to simulate."));
        }, WALL_CLOCK_LIMIT_MS);
      };
      if (this.status === "loading") {
        const unsubscribe = this.onStatus((status) => {
          if (status !== "loading") {
            unsubscribe();
            startTimer();
          }
        });
      } else {
        startTimer();
      }
      this.pending.set(id, {
        resolve: (trace) => {
          clearTimeout(timer);
          resolve(trace);
        },
        reject: (error) => {
          clearTimeout(timer);
          reject(error);
        },
      });
      this.worker.postMessage(message);
    });
  }
}
