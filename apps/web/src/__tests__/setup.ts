/// <reference types="vitest/globals" />
import "@testing-library/jest-dom/vitest";

/**
 * Mock navigator.onLine for offline tests.
 */
Object.defineProperty(navigator, "onLine", {
  configurable: true,
  get: () => true,
});

/**
 * Mock crypto.randomUUID for deterministic tests.
 */
if (!globalThis.crypto?.randomUUID) {
  Object.defineProperty(globalThis, "crypto", {
    value: {
      ...globalThis.crypto,
      randomUUID: () => "00000000-0000-0000-0000-000000000099",
    },
  });
}

/**
 * Mock IndexedDB for offline-store tests — idb library uses it.
 */
const mockIDB = {
  put: vi.fn(),
  get: vi.fn(),
  delete: vi.fn(),
  getAllFromIndex: vi.fn().mockResolvedValue([]),
};

vi.mock("idb", () => ({
  openDB: vi.fn().mockResolvedValue(mockIDB),
}));
