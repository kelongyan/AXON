"use client";

import { useState } from "react";

import { errorMessage } from "./error-message";

export function useRunAction() {
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  async function run(action: () => Promise<void>): Promise<void> {
    try {
      setBusy(true);
      setMessage(null);
      await action();
    } catch (error) {
      setMessage(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }

  return { busy, message, run, setBusy, setMessage };
}
