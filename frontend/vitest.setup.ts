import "@testing-library/jest-dom/vitest";

import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";

afterEach(() => {
  cleanup();
  vi.restoreAllMocks();
});

// jsdom implements neither of these, and both are used by the chat panel.
window.HTMLElement.prototype.scrollIntoView = vi.fn();
Object.defineProperty(window, "open", { writable: true, value: vi.fn() });
