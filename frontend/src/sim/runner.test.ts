import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import type { RunRequest } from "../types";
import { RunRestarted, RunTimeout, SimRunner, type SimWorker } from "./runner";
import type { WorkerResponse } from "./worker";

class FakeWorker implements SimWorker {
  onmessage: SimWorker["onmessage"] = null;
  onerror: SimWorker["onerror"] = null;
  sent: { id: number }[] = [];
  terminated = false;
  postMessage(message: { id: number }) {
    this.sent.push(message);
  }
  terminate() {
    this.terminated = true;
  }
  reply(message: WorkerResponse) {
    this.onmessage?.call(this as unknown as Worker, { data: message } as MessageEvent);
  }
}

const request = {} as RunRequest;

describe("SimRunner", () => {
  let workers: FakeWorker[];
  let runner: SimRunner;

  beforeEach(() => {
    vi.useFakeTimers();
    workers = [];
    runner = new SimRunner(() => {
      const worker = new FakeWorker();
      workers.push(worker);
      return worker;
    });
    workers[0].reply({ type: "ready", pythonVersion: "3.13", loadMs: 1 });
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  it("answers a run with its trace and forgets its timer", async () => {
    const run = runner.run(request);
    workers[0].reply({ type: "result", id: workers[0].sent[0].id, json: '{"ok": true}' });
    await expect(run).resolves.toEqual({ ok: true });
    vi.advanceTimersByTime(60_000);
    expect(workers).toHaveLength(1);
    expect(workers[0].terminated).toBe(false);
  });

  it("settles every waiting run when one takes too long, and restarts once", async () => {
    const stuck = runner.run(request);
    const waiting = runner.run(request);
    const stuckResult = expect(stuck).rejects.toBeInstanceOf(RunTimeout);
    const waitingResult = expect(waiting).rejects.toBeInstanceOf(RunRestarted);
    vi.advanceTimersByTime(20_000);
    await stuckResult;
    await waitingResult;
    expect(workers).toHaveLength(2);
    expect(workers[0].terminated).toBe(true);

    // The waiting run's old timer must not stop the new worker later.
    workers[1].reply({ type: "ready", pythonVersion: "3.13", loadMs: 1 });
    const next = runner.run(request);
    vi.advanceTimersByTime(15_000);
    workers[1].reply({ type: "result", id: workers[1].sent[0].id, json: "{}" });
    await expect(next).resolves.toEqual({});
    vi.advanceTimersByTime(60_000);
    expect(workers).toHaveLength(2);
    expect(workers[1].terminated).toBe(false);
  });

  it("runs sent while Python loads wait for it, and answer if it never starts", async () => {
    const stuck = runner.run(request);
    const stuckResult = expect(stuck).rejects.toBeInstanceOf(RunTimeout);
    vi.advanceTimersByTime(20_000); // restart: the new worker is loading
    await stuckResult;
    const early = runner.run(request);
    const earlyResult = expect(early).rejects.toBeInstanceOf(RunRestarted);
    vi.advanceTimersByTime(60_000); // loading time doesn't count
    expect(workers).toHaveLength(2);
    workers[1].reply({ type: "failed", id: null, message: "Python failed to start" });
    await earlyResult;
    expect(runner.status).toBe("broken");
    vi.advanceTimersByTime(60_000);
    expect(workers).toHaveLength(2);
  });
});
