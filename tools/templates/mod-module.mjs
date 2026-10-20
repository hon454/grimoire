// {{TITLE}}: a Claude Code mod (function hooks). Claude-only; Codex never loads this.
//
// The engine reads `on(...)` and `$.noun.method(...)` from the source, so keep
// them spelled out at the top level and never build event or method names
// dynamically. Every hook is ($, e, next): return next(e) to pass through.
// No Node, no DOM, no import(): everything outside comes through `$`.

/** @type {import("claude-code").Register} */
export const register = (on, options) => {
  on("session.start", async ($, e, next) => {
    // Observe only. A mod that changes nothing ends every hook with next(e).
    return next(e);
  });
};
