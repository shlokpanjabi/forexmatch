import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { ChatPanel } from "@/components/chat/ChatPanel";
import type { StreamEvent } from "@/lib/types";
import { recommendation, sseBody, toolEvent } from "./fixtures";

function mockStream(events: StreamEvent[]) {
  vi.spyOn(globalThis, "fetch").mockResolvedValue(
    new Response(sseBody(events), {
      status: 200,
      headers: { "Content-Type": "text/event-stream" },
    }),
  );
}

const FULL_TURN: StreamEvent[] = [
  { type: "session", session_id: "session-123" },
  { type: "tool_event", event: toolEvent({ id: "a", tool_name: "search_cards", status: "started" }) },
  {
    type: "tool_event",
    event: toolEvent({ id: "a", tool_name: "search_cards", output_summary: "14 cards found" }),
  },
  { type: "text", text: "The Axis card looks like your best match." },
  { type: "recommendation", recommendation: recommendation() },
  { type: "done", message: "The Axis card looks like your best match." },
];

describe("ChatPanel", () => {
  beforeEach(() => vi.restoreAllMocks());

  it("sends a message and renders the reply", async () => {
    mockStream(FULL_TURN);
    const user = userEvent.setup();
    render(<ChatPanel />);

    await user.type(screen.getByLabelText("Message"), "I'm going to the UK");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText("I'm going to the UK")).toBeInTheDocument();
    expect(
      await screen.findByText("The Axis card looks like your best match."),
    ).toBeInTheDocument();
  });

  it("shows a loading state while the turn is in flight", async () => {
    let release: (value: Response) => void = () => {};
    vi.spyOn(globalThis, "fetch").mockReturnValue(
      new Promise<Response>((resolve) => {
        release = resolve;
      }),
    );

    const user = userEvent.setup();
    render(<ChatPanel />);
    await user.type(screen.getByLabelText("Message"), "hello");
    await user.click(screen.getByRole("button", { name: "Send" }));

    expect(await screen.findByText(/Reading the fee schedules/)).toBeInTheDocument();
    expect(screen.getByLabelText("Message")).toBeDisabled();

    release(new Response(sseBody(FULL_TURN), { status: 200 }));
    await waitFor(() => expect(screen.getByLabelText("Message")).not.toBeDisabled());
  });

  it("renders real tool activity as it streams", async () => {
    mockStream(FULL_TURN);
    const user = userEvent.setup();
    render(<ChatPanel />);
    await user.click(screen.getByRole("button", { name: /Indian student going to the UK/ }));

    const activity = await screen.findByRole("region", { name: "Agent activity" });
    expect(activity).toHaveTextContent("Searching the catalogue");
    expect(activity).toHaveTextContent("14 cards found");
    // The completed event replaces the started one rather than duplicating it.
    expect(activity.querySelectorAll("li")).toHaveLength(1);
  });

  it("renders the recommendation, its sources and the apply call to action", async () => {
    mockStream(FULL_TURN);
    const user = userEvent.setup();
    render(<ChatPanel />);
    await user.click(screen.getByRole("button", { name: /Indian student going to the UK/ }));

    expect(await screen.findByText("Multi-Currency Forex Card")).toBeInTheDocument();
    expect(screen.getByText("82%")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Apply at/ })).toBeInTheDocument();
    expect(
      screen.getByRole("link", { name: "Fees and Charges — Multi-Currency Forex Card" }),
    ).toHaveAttribute("href", "https://www.axis.bank.in/fees.pdf");
    expect(screen.getByText(/not financial advice/)).toBeInTheDocument();
  });

  it("shows assumptions and the cards that were ruled out", async () => {
    mockStream(FULL_TURN);
    const user = userEvent.setup();
    render(<ChatPanel />);
    await user.click(screen.getByRole("button", { name: /Indian student going to the UK/ }));

    // Assumptions are now always visible rather than behind a counted disclosure.
    expect(await screen.findByText(/What we assumed about you/)).toBeInTheDocument();
    expect(screen.getByText(/Cards ruled out/)).toBeInTheDocument();
    expect(screen.getByText(/No application route is published/)).toBeInTheDocument();
  });

  it("surfaces a streamed error without losing the conversation", async () => {
    mockStream([
      { type: "session", session_id: "s" },
      { type: "error", error: { code: "AGENT_FAILED", message: "The assistant could not finish." } },
    ]);
    const user = userEvent.setup();
    render(<ChatPanel />);
    await user.click(screen.getByRole("button", { name: /Indian student going to the UK/ }));

    expect(await screen.findByRole("alert")).toHaveTextContent("The assistant could not finish.");
  });

  it("explains an unreachable API rather than showing a raw failure", async () => {
    // A rejected fetch means the request never arrived — DNS, refused
    // connection, CORS or mixed content. The page is public, so this needs to
    // read as an explanation, not a stack trace.
    vi.spyOn(globalThis, "fetch").mockRejectedValue(new TypeError("Failed to fetch"));
    const user = userEvent.setup();
    render(<ChatPanel />);
    await user.click(screen.getByRole("button", { name: /Indian student going to the UK/ }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent(/API isn.t reachable/);
    expect(alert).toHaveTextContent(/not yet publicly hosted/);
    // Tells the reader how to run it, and where the page is looking.
    expect(alert).toHaveTextContent("./scripts/dev.sh");
    expect(alert).toHaveTextContent("http://localhost:8000");
    expect(screen.getByRole("link", { name: /Source and setup/ })).toHaveAttribute(
      "href",
      "https://github.com/shlokpanjabi/forexmatch",
    );
  });

  it("keeps an API-reported error distinct from an unreachable API", async () => {
    mockStream([
      { type: "session", session_id: "s" },
      { type: "error", error: { code: "AGENT_FAILED", message: "The assistant could not finish." } },
    ]);
    const user = userEvent.setup();
    render(<ChatPanel />);
    await user.click(screen.getByRole("button", { name: /Indian student going to the UK/ }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("The assistant could not finish.");
    expect(alert).not.toHaveTextContent(/not yet publicly hosted/);
  });
});
