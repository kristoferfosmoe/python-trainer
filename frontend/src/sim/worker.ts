/// <reference lib="webworker" />
// Runs Python (Pyodide) and the robot simulator off the main thread, so a
// stuck student program can never freeze the page.

import { loadPyodide } from "pyodide";

// The simulator's Python source, bundled from sim/src (the lesson checker,
// trainer_content, is only for tests and the server).
const simFiles = import.meta.glob(["../../../sim/src/**/*.py", "!../../../sim/src/trainer_content/**"], {
  query: "?raw",
  import: "default",
  eager: true,
}) as Record<string, string>;

const SIM_ROOT = "/home/pyodide/trainer";

export type WorkerRequest = { type: "run"; id: number; payload: string };
export type WorkerResponse =
  | { type: "ready"; pythonVersion: string; loadMs: number }
  | { type: "result"; id: number; json: string }
  | { type: "failed"; id: number | null; message: string };

let runProgram: ((payload: string) => string) | null = null;

async function start() {
  const started = performance.now();
  const pyodide = await loadPyodide({
    indexURL: new URL(`${import.meta.env.BASE_URL}pyodide/`, self.location.origin).href,
  });
  for (const [path, source] of Object.entries(simFiles)) {
    const relative = path.split("/sim/src/")[1];
    const target = `${SIM_ROOT}/${relative}`;
    pyodide.FS.mkdirTree(target.slice(0, target.lastIndexOf("/")));
    pyodide.FS.writeFile(target, source);
  }
  pyodide.runPython(`import sys\nsys.path.insert(0, "${SIM_ROOT}")`);
  const runner = pyodide.pyimport("trainer_sim.runner");
  runProgram = runner.run_program_json as (payload: string) => string;
  const version = pyodide.runPython("import sys; sys.version.split()[0]") as string;
  post({ type: "ready", pythonVersion: version, loadMs: Math.round(performance.now() - started) });
}

function post(message: WorkerResponse) {
  self.postMessage(message);
}

const ready = start().catch((error: unknown) => {
  post({ type: "failed", id: null, message: `Python failed to start: ${String(error)}` });
  throw error;
});

self.onmessage = async (event: MessageEvent<WorkerRequest>) => {
  const request = event.data;
  if (request.type !== "run") return;
  try {
    await ready;
    post({ type: "result", id: request.id, json: runProgram!(request.payload) });
  } catch (error) {
    post({ type: "failed", id: request.id, message: String(error) });
  }
};
