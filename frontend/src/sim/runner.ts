// Talks to the simulator Web Worker. If a program runs too long (a loop that
// never ends and never waits), the worker is stopped and a fresh one started.

import type { RunRequest, Trace } from "../types";
import type { WorkerRequest, WorkerResponse } from "./worker";

export type RunnerStatus = "loading" | "ready" | "running" | "broken";

/** This run took too long, so the simulator was restarted. */
export class RunTimeout extends Error {}
/** The simulator restarted (another run took too long, or Python didn't start) before this run finished. */
export class RunRestarted extends Error {}

const WALL_CLOCK_LIMIT_MS = 20_000;

/** The parts of a Worker the runner uses (tests pass a fake one). */
export type SimWorker = Pick<Worker, "postMessage" | "terminate" | "onmessage" | "onerror">;

const startWorker = (): SimWorker => new Worker(new URL("./worker.ts", import.meta.url), { type: "module" });

interface PendingRun {
  resolve: (trace: Trace) => void;
  reject: (error: Error) => void;
  timer?: ReturnType<typeof setTimeout>;
  stopWaiting?: () => void; // for Python to finish loading
}

export class SimRunner {
  private worker!: SimWorker;
  private nextId = 1;
  private pending = new Map<number, PendingRun>();
  private listeners = new Set<(status: RunnerStatus) => void>();
  status: RunnerStatus = "loading";
  pythonVersion = "";

  constructor(private readonly createWorker: () => SimWorker = startWorker) {
    this.spawn();
  }

  private spawn() {
    this.setStatus("loading");
    this.worker = this.createWorker();
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
      this.settleAll(() => new RunRestarted(message.message));
      return;
    }
    const entry = this.pending.get(message.id!);
    if (!entry) return;
    this.settle(message.id!);
    if (this.status === "running" && this.pending.size === 0) this.setStatus("ready");
    if (message.type === "result") entry.resolve(JSON.parse(message.json) as Trace);
    else entry.reject(new Error(message.message));
  }

  /** Stop tracking a run: its timer and its wait for Python go with it. */
  private settle(id: number) {
    const entry = this.pending.get(id);
    if (!entry) return;
    clearTimeout(entry.timer);
    entry.stopWaiting?.();
    this.pending.delete(id);
  }

  private settleAll(error: (id: number) => Error) {
    for (const [id, entry] of [...this.pending]) {
      this.settle(id);
      entry.reject(error(id));
    }
  }

  /** Run `id` took too long: start a fresh worker. Every other run was waiting in
   * the stuck one, so it can't finish either; each gets an answer now, rather than
   * its own timer later stopping the new worker. */
  private restart(id: number) {
    this.settleAll((other) =>
      other === id
        ? new RunTimeout("The program took too long to simulate.")
        : new RunRestarted("The simulator restarted because another program took too long."),
    );
    this.worker.terminate();
    this.spawn();
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
      const entry: PendingRun = { resolve, reject };
      this.pending.set(id, entry);
      // Loading Python doesn't count against the program's time.
      const startTimer = () => {
        if (this.pending.get(id) === entry) entry.timer = setTimeout(() => this.restart(id), WALL_CLOCK_LIMIT_MS);
      };
      if (this.status === "loading") {
        const unsubscribe = this.onStatus((status) => {
          if (status !== "loading") {
            unsubscribe();
            entry.stopWaiting = undefined;
            startTimer();
          }
        });
        entry.stopWaiting = () => {
          unsubscribe();
        };
      } else {
        startTimer();
      }
      this.worker.postMessage(message);
    });
  }
}
