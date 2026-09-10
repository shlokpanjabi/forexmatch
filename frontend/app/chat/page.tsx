import { ChatPanel } from "@/components/chat/ChatPanel";
import { Nav } from "@/components/site/Nav";
import { Label } from "@/components/ui/primitives";

export const metadata = {
  title: "Ask the agent — ForexMatch",
  description: "Describe your plans and let the agent research, price and compare forex cards.",
};

export default function ChatPage() {
  return (
    <>
      <Nav />
      <main className="relative">
        <div className="mx-auto max-w-3xl px-5 pt-10">
          <Label>The agent</Label>
          <h1 className="display mt-3 text-3xl sm:text-4xl">Describe your plans.</h1>
          <p className="mt-3 text-sm leading-relaxed text-mist-400">
            Write it however you like — &ldquo;Manchester for a two-year master&apos;s, maybe £1,100
            a month&rdquo; is plenty. Estimates are fine. You can change any answer afterwards and
            the ranking recalculates.
          </p>
        </div>
        <ChatPanel />
      </main>
    </>
  );
}
