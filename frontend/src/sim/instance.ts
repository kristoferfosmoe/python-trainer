// One simulator worker for the whole app.

import { useEffect, useState } from "react";
import { SimRunner, type RunnerStatus } from "./runner";

export const runner = new SimRunner();

export function useRunnerStatus(): RunnerStatus {
  const [status, setStatus] = useState<RunnerStatus>(runner.status);
  useEffect(() => {
    setStatus(runner.status);
    const unsubscribe = runner.onStatus(setStatus);
    return () => {
      unsubscribe();
    };
  }, []);
  return status;
}
