"use client";

import { useEffect, useState } from "react";
import { apiGet } from "./api";

export function useApi<T>(path: string | null) {
  const [state, setState] = useState<{ status: "loading" | "error" | "ready"; data?: T; error?: string }>({ status: "loading" });
  useEffect(() => {
    if (!path) return;
    let active = true;
    setState({ status: "loading" });
    apiGet<T>(path)
      .then((data) => {
        if (active) setState({ status: "ready", data });
      })
      .catch((error: Error) => {
        if (active) setState({ status: "error", error: error.message });
      });
    return () => {
      active = false;
    };
  }, [path]);
  return state;
}
