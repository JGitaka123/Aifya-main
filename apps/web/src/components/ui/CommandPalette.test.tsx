import {
  act,
  cleanup,
  fireEvent,
  render,
  screen,
} from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const { mockApiGet, mockPush, mockRouter } = vi.hoisted(() => {
  const push = vi.fn();
  return {
    mockApiGet: vi.fn(),
    mockPush: push,
    mockRouter: { push },
  };
});

vi.mock("next-intl", () => ({
  useTranslations: () => (key: string) => key,
}));

vi.mock("@/i18n/routing", () => ({
  useRouter: () => mockRouter,
}));

vi.mock("@/components/licensing/LicenseProvider", () => ({
  useLicenseContext: () => ({ hasModule: () => true }),
}));

vi.mock("@/lib/api-client", () => ({
  apiClient: { get: mockApiGet },
}));

import { CommandPalette } from "./CommandPalette";

describe("CommandPalette", () => {
  beforeEach(() => {
    mockApiGet.mockReset();
    mockPush.mockReset();
  });

  afterEach(() => {
    cleanup();
  });

  it("opens from the global shortcut and restores focus when closed", () => {
    render(
      <>
        <button type="button">trigger</button>
        <CommandPalette />
      </>,
    );
    const trigger = screen.getByRole("button", { name: "trigger" });
    trigger.focus();

    fireEvent.keyDown(window, { key: "k", ctrlKey: true });

    const searchInput = screen.getByRole("textbox", {
      name: "globalSearch",
    });
    expect(searchInput).toHaveFocus();

    fireEvent.keyDown(window, { key: "Escape" });

    expect(screen.queryByRole("dialog")).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  it("contains keyboard focus within the open dialog", () => {
    render(<CommandPalette />);
    act(() => {
      window.dispatchEvent(new CustomEvent("aifya:open-command-palette"));
    });

    const searchInput = screen.getByRole("textbox", {
      name: "globalSearch",
    });
    const lastCommand = screen.getByRole("button", { name: "reports" });

    lastCommand.focus();
    fireEvent.keyDown(lastCommand, { key: "Tab" });
    expect(searchInput).toHaveFocus();

    searchInput.focus();
    fireEvent.keyDown(searchInput, { key: "Tab", shiftKey: true });
    expect(lastCommand).toHaveFocus();
  });
});
