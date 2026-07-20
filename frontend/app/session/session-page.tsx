import { useEffect, useState } from "react";

import { loadSession, type SessionLoadResult } from "../api/session";
import { SessionShell } from "./session-shell";

export function SessionPage() {
  const [result, setResult] = useState<SessionLoadResult>({
    status: "loading",
  });

  useEffect(() => {
    let isCurrent = true;

    void loadSession().then((loadedResult) => {
      if (isCurrent) {
        setResult(loadedResult);
      }
    });

    return () => {
      isCurrent = false;
    };
  }, []);

  return <SessionShell result={result} />;
}
