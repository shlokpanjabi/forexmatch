/** The agent's mark. A small rotating aperture when it is working. */
export function AgentMark({ busy = false }: { busy?: boolean }) {
  return (
    <span
      aria-hidden
      className="relative mt-0.5 flex size-7 shrink-0 items-center justify-center rounded-full border border-ink-700 bg-ink-900"
    >
      <span
        className={`block size-2 rotate-45 bg-ember-500 ${busy ? "animate-pulse" : ""}`}
      />
      {busy && (
        <span className="absolute inset-0 animate-spin rounded-full border border-transparent border-t-ember-500/70" />
      )}
    </span>
  );
}
