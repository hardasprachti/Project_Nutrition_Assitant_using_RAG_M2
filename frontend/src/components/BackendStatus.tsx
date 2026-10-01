"use client";

import { useEffect, useState } from "react";

import { getHealth } from "@/lib/api";

type State = { kind: "loading" } | { kind: "ok"; vector: string } | { kind: "down"; reason: string };

export default function BackendStatus() {
  const [state, setState] = useState<State>({ kind: "loading" });

  useEffect(() => {
    getHealth()
      .then((health) => setState({ kind: "ok", vector: health.vector_extension ?? "unknown" }))
      .catch((error: unknown) =>
        setState({ kind: "down", reason: error instanceof Error ? error.message : "Unknown error" }),
      );
  }, []);

  return (
    <p role="status" aria-live="polite">
      Backend:{" "}
      {state.kind === "loading" && "checking…"}
      {state.kind === "ok" && `connected (pgvector ${state.vector})`}
      {state.kind === "down" && `unavailable (${state.reason})`}
    </p>
  );
}
