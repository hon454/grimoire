// Tests for the token-weather mod, run with `claude plugin test claude-code-mods/token-weather`.
// Adapted from token-weather-usage's tests (Eric Cologni, Apache-2.0): English only, no cost
// figures, gauge keys by window kind.
import { test, expect, mock } from "claude-code/testing";
// @ts-ignore: the module is plain JavaScript.
import { toolText, batchesOf, modelId, cells } from "../hooks/token-weather.mjs";

// October 2, 2026, 13:00 UTC.
const NOW = Date.UTC(2026, 9, 2, 13, 0);
// The 5-hour reset time is shown in the machine's time zone.
const at = (ms: number) => new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(ms);
const LIMITS = [
  // 7 days: 59% used, 4 of 7 days elapsed (57%): slightly ahead, yellow.
  { kind: "seven_day", percentUsed: 59, resetsAt: new Date(NOW + 3 * 86_400_000).toISOString() },
  // 5 hours: 32% used, 2 of 5 hours elapsed (40%): behind time, green.
  { kind: "five_hour", percentUsed: 32, resetsAt: new Date(NOW + 3 * 3_600_000).toISOString() },
];

// below: what a mod placed after this one draws under the line.
function world(on: any, stored: Record<string, unknown> = {}, below?: string) {
  const clock = mock.clock(on, { now: NOW });
  mock.store(on, stored);
  mock.env(on, {});
  on("session.id", () => ({ value: "session-1" }));
  on("session.start", (_$: any, e: any) => ({ cwd: e.cwd ?? "/tmp" }));
  on("ui.invalidate", () => ({ value: undefined }));
  on("ui.render", ($: any, e: any) => (below ? $.ui.resolve(e).Text({ children: below }) : $.ui.resolve(e).Box({ children: [] })));
  return clock as any;
}

function withUsage(on: any, rateLimits: unknown[], context = { tokens: 107_000, window: 1_000_000, percent: 11 }) {
  on("session.usage", () => ({ value: { startedAt: NOW, context, rateLimits } }));
}

async function band($: any, surface: "terminal" | "desktop", columns = 200) {
  const ui = await $.ui.mount({ plugin: "token-weather", surface, component: "AbovePrompt", props: { bodyColumns: columns } as any });
  // The hover cards' lines are hidden until hovered: left out of the band's texts.
  const hidden = ((await ui.findAll({ type: "Box" })) as any[])
    .filter((b) => b.props?.position === "absolute")
    .flatMap((b) => ((b.children ?? []) as any[]).map((t) => strings(t).join("")));
  const texts: string[] = [];
  for (const t of (await ui.findAll({ type: "Text" })) as any[]) {
    const i = hidden.indexOf(t.text);
    if (i >= 0) hidden.splice(i, 1);
    else texts.push(t.text);
  }
  return { ui, texts };
}

// The hover cards drawn inside the pills, as element descriptions.
async function cardNodes(ui: any): Promise<any[]> {
  const pills = ((await ui.findAll({ type: "Box" })) as any[]).filter((b) => b.key);
  return pills.flatMap((p) => ((p.children ?? []) as any[]).filter((c) => c && typeof c === "object" && c.props?.position === "absolute"));
}

// Every string beneath a drawn element description, in order.
function strings(node: any): string[] {
  if (node == null || node === false) return [];
  if (typeof node === "string" || typeof node === "number") return [String(node)];
  if (Array.isArray(node)) return node.flatMap(strings);
  return strings(node.children ?? node.props?.children);
}

// The hover card of a pill (by its key), its lines joined by newlines; null without one.
async function cardOf(ui: any, pillKey: string): Promise<string | null> {
  const pill: any = await ui.find({ type: "Box", key: pillKey });
  const kids = (pill?.children ?? []) as any[];
  const card = kids.find((c) => c && typeof c === "object" && c.props?.position === "absolute");
  if (!card) return null;
  const lines = ((card.children ?? card.props?.children ?? []) as any[]).map((t) => strings(t).join(""));
  return lines.join("\n");
}

for (const surface of ["terminal", "desktop"] as const) {
  test(`band ${surface}`, async ($, on) => {
    world(on);
    withUsage(on, LIMITS);
    await $.session.start({ source: "startup", cwd: "/tmp" } as any);
    const { ui, texts } = await band($, surface);
    // The context in tokens alone; the weather word goes to the pill's card.
    expect(texts).toContain("107k");
    expect(texts).not.toContain("11% context");
    expect(texts).toContain("5h");
    expect(texts).toContain("32%");
    const dot = surface === "terminal" ? "· " : "";
    // The time left alone; the reset time is in the pill's card.
    expect(texts).toContain(`${dot}3h00`);
    expect(texts).not.toContain(`${dot}3h00 → ${at(NOW + 3 * 3_600_000)}`);
    expect(texts).toContain("59%");
    expect(texts).toContain(`${dot}3d00h`);
    // No request yet: the cache block waits. In the app the bolt stands for the word.
    if (surface === "terminal") expect(texts).toContain("cache");
    expect(texts).toContain("—");
    if (surface === "desktop") {
      const svgs = (await ui.findAll({ type: "Svg" })) as any[];
      // The weather word sits in the context pill's hover card; no drawing is interactive.
      expect(svgs.some((s) => s.props?.alt === "Clear · 11% of 1M")).toBe(true);
      expect(await cardOf(ui, "context")).toBe("Clear · 11% of 1M");
      for (const s of svgs) expect(s.props?.isInteractive).toBeFalsy();
      // No request yet: no card on the cache pill.
      expect(await cardOf(ui, "cache")).toBeNull();
      // Hover cards: hidden, revealed by the pill's hover, in the theme's colors.
      const cards = await cardNodes(ui);
      expect(cards.length).toBeGreaterThan(0);
      for (const c of cards) {
        expect(c.props?.display).toBe("none");
        expect((c.hover ?? c.props?.hover)?.display).toBe("flex");
        expect(c.props?.backgroundColor).toBe("background");
        expect(c.props?.key).toBeUndefined();
      }
      // Pills: tinted and rounded, without the border's vertical padding.
      const pills = ((await ui.findAll({ type: "Box" })) as any[]).filter((b) => b.props?.backgroundColor && b.props?.position !== "absolute");
      // Context, 5 hours, 7 days, cache, and the agents pill, which stays in the app.
      expect(pills.length).toBe(5);
      for (const p of pills) {
        expect(p.props?.borderStyle).toBe("round");
        expect(p.props?.paddingY).toBe(0);
      }
    } else {
      expect(texts).toContain("☀");
      expect(texts).not.toContain("Clear");
    }
    // 5 hours before 7 days, whatever the order received.
    expect(texts.indexOf("5h")).toBeLessThan(texts.indexOf("7d"));
    // A single reading: no turns chart yet.
    expect(texts).not.toContain("turns");
    // Outside an alert, the percentage keeps the theme's color.
    const value: any = await ui.find({ type: "Text", text: "59%" });
    expect(value?.props?.color).toBeUndefined();
    expect(value?.props?.bold).toBe(true);
  });
}

test("keeps what later mods draw under the line", async ($, on) => {
  world(on, {}, "drawn after this mod");
  withUsage(on, LIMITS);
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  const { texts } = await band($, "terminal");
  expect(texts).toContain("drawn after this mod");
  expect(texts.indexOf("107k")).toBeLessThan(texts.indexOf("drawn after this mod"));
});

test("cells: Hangul takes two terminal cells", () => {
  expect(cells("5h")).toBe(2);
  expect(cells("5시간")).toBe(5);
  expect(cells("캐시 3시간")).toBe(10);
  expect(cells("")).toBe(0);
});

test("a window that already reset is hidden", async ($, on) => {
  world(on);
  withUsage(on, [
    { kind: "five_hour", percentUsed: 80, resetsAt: new Date(NOW - 60_000).toISOString() },
    { kind: "seven_day", percentUsed: 59, resetsAt: new Date(NOW + 3 * 86_400_000).toISOString() },
  ]);
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  const { texts } = await band($, "terminal");
  expect(texts).not.toContain("5h");
  expect(texts).toContain("7d");
});

for (const surface of ["terminal", "desktop"] as const) {
  test(`turns after two readings ${surface}`, async ($, on) => {
    world(on);
    on("turn.complete", () => ({ text: "" }));
    // 4 readings: +20k, +80k, +10k tokens.
    const fills = [10, 12, 20, 21];
    let call = 0;
    on("session.usage", () => {
      const percent = fills[Math.min(call++, fills.length - 1)];
      return { value: { startedAt: NOW, context: { tokens: percent * 10_000, window: 1_000_000, percent }, rateLimits: LIMITS } };
    });
    await $.session.start({ source: "startup", cwd: "/tmp" } as any);
    for (let i = 0; i < 3; i++) await ($ as any).turn.complete({ answer: "ok" } as any);
    const { ui, texts } = await band($, surface);
    expect(texts).toContain("210k");
    expect(texts).toContain("▲ +10k");
    if (surface === "terminal") {
      expect(texts).toContain("☀");
      // Earlier prompts in grey (+20k then +80k, the heaviest), current prompt (+10k) in color.
      expect(texts).toContain("▃█");
      const now: any = await ui.find({ type: "Text", text: "▂" });
      expect(now?.props?.color).toBe("yellow");
    } else {
      const svgs = (await ui.findAll({ type: "Svg" })) as any[];
      // Drawn weather icon, turn bars, two gauges; every drawing carries its alt text.
      const alts = svgs.map((s) => String(s.props?.alt ?? ""));
      expect(alts.every((a) => a.length > 0)).toBe(true);
      expect(alts.filter((a) => a.startsWith("Tokens added") || a.includes(" used") || a.startsWith("Clear")).length).toBe(4);
      // Small icons: gauge, calendar, two reset clocks, cache.
      for (const a of ["5-hour limit", "7-day limit", "Resets in", "Prompt cache"]) expect(alts).toContain(a);
      expect(texts).not.toContain("☀");
    }
  });
}

test("on start, the shared reading wins over an old local one", async ($, on) => {
  // Another session measured 63% two minutes ago.
  world(on, {
    limits: { at: NOW - 120_000, list: [{ kind: "five_hour", percentUsed: 63, resetsAt: new Date(NOW + 3 * 3_600_000).toISOString() }] },
  });
  // This idle session still holds an old reading at 34%.
  withUsage(on, [{ kind: "five_hour", percentUsed: 34, resetsAt: new Date(NOW + 3 * 3_600_000).toISOString() }]);
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  const { texts } = await band($, "terminal");
  expect(texts).toContain("63%");
  expect(texts).not.toContain("34%");
});

test("alert: percentage in red at 90% or more", async ($, on) => {
  world(on);
  withUsage(on, [{ kind: "five_hour", percentUsed: 95, resetsAt: new Date(NOW + 3 * 3_600_000).toISOString() }]);
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  const { ui } = await band($, "desktop");
  const value: any = await ui.find({ type: "Text", text: "95%" });
  expect(value?.props?.color).toBe("red");
});

test("narrow terminal: no bar, no detail", async ($, on) => {
  world(on);
  withUsage(on, LIMITS);
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  const { texts } = await band($, "terminal", 60);
  expect(texts).toContain("32%");
  expect(texts).not.toContain("━");
  expect(texts).not.toContain("· 3h00");
});

test("after a restart, the turn bars come back", async ($, on) => {
  mock.clock(on, { now: NOW });
  mock.env(on, {});
  // In-memory store: this session already had 3 readings (+20k, then +80k); another one has slept for 9 days.
  const store = new Map<string, unknown>([
    ["turns:session-1", { at: NOW - 60_000, readings: [10, 12, 20].map((p) => ({ tokens: p * 10_000, window: 1_000_000, percent: p })) }],
    ["turns:old-session", { at: NOW - 9 * 86_400_000, readings: [] }],
  ]);
  on("store.get", (_$: any, e: any) => ({ value: store.get(e.key) }));
  on("store.set", (_$: any, e: any) => (store.set(e.key, e.value), { value: undefined }));
  on("store.delete", (_$: any, e: any) => (store.delete(e.key), { value: undefined }));
  on("store.keys", () => ({ value: [...store.keys()] }));
  on("session.id", () => ({ value: "session-1" }));
  on("session.start", (_$: any, e: any) => ({ cwd: e.cwd ?? "/tmp" }));
  on("ui.invalidate", () => ({ value: undefined }));
  on("ui.render", ($: any, e: any) => $.ui.resolve(e).Box({ children: [] }));
  // On reopening, the context equals the last reading: no duplicate reading.
  withUsage(on, LIMITS, { tokens: 200_000, window: 1_000_000, percent: 20 });
  await $.session.start({ source: "resume", cwd: "/tmp" } as any);
  const { texts } = await band($, "terminal");
  expect(texts).toContain("▲ +80k");
  // The session idle for more than 8 days is deleted, not this one.
  expect(store.has("turns:old-session")).toBe(false);
  expect(store.has("turns:session-1")).toBe(true);
});

for (const surface of ["terminal", "desktop"] as const) {
  test(`gap with elapsed time hatched ${surface}`, async ($, on) => {
    world(on);
    withUsage(on, [
      // 5 hours: 74% used, window 99% over: margin left.
      { kind: "five_hour", percentUsed: 74, resetsAt: new Date(NOW + 3 * 60_000).toISOString() },
      // 7 days: 80% used for 57% elapsed: ahead of time (alert).
      { kind: "seven_day", percentUsed: 80, resetsAt: new Date(NOW + 3 * 86_400_000).toISOString() },
    ]);
    await $.session.start({ source: "startup", cwd: "/tmp" } as any);
    const { ui } = await band($, surface);
    if (surface === "terminal") {
      const dashes = (await ui.findAll({ type: "Text", text: "╍" })) as any[];
      // 6 cells: 2 grey margin cells (5 h), 2 red cells ahead (7 d).
      expect(dashes.filter((d) => d.props?.dimColor).length).toBe(2);
      expect(dashes.filter((d) => d.props?.color === "red").length).toBe(2);
    } else {
      const svgs = (await ui.findAll({ type: "Svg" })) as any[];
      const gauges = svgs.filter((s) => String(s.props?.alt ?? "").includes("used"));
      expect(gauges.length).toBe(2);
      for (const g of gauges) expect(String(g.props?.source)).toContain("<pattern");
      expect(svgs.some((s) => String(s.props?.source).includes("#4f8ef7"))).toBe(false);
    }
  });
}

// ---------- Prompt cache ----------

// One main-loop request answered with this usage.
async function step($: any, usage: Record<string, unknown>, model = "claude-opus-5-5") {
  const stream = $.turn.step({ turnId: "t", index: 0, model, messageCount: 2 });
  for await (const _ of stream) {
  }
  return stream.result;
}

function engineStep(on: any, usages: Record<string, unknown>[]) {
  let call = 0;
  on("turn.step", async function* () {
    const usage = usages[Math.min(call++, usages.length - 1)];
    const queued = next.shift();
    return { turnId: "t", index: 0, answer: "", toolUses: (queued?.uses ?? []).map((name) => ({ name, input: {} })), stopReason: queued?.stop ?? "end_turn", usage };
  });
}

const HIT = { model: "claude-opus-5-5", input_tokens: 300, cache_read_input_tokens: 98_000, cache_creation_input_tokens: 1_700, output_tokens: 500 };
const MISS = { model: "claude-opus-5-5", input_tokens: 300, cache_read_input_tokens: 0, cache_creation_input_tokens: 99_700, output_tokens: 500 };

// The cache pill's hover card in the app; null without one.
async function boltTip(ui: any): Promise<string | null> {
  return cardOf(ui, "cache");
}

test("cache: share read and time left on a subscription (1 hour)", async ($, on) => {
  world(on);
  withUsage(on, LIMITS);
  engineStep(on, [HIT]);
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  await step($, HIT);
  const { ui, texts } = await band($, "terminal");
  expect(texts).toContain("cache");
  // 98% served: the time left alone (1 hour, counted from the request's start).
  expect(texts).not.toContain("98%");
  expect(texts).toContain("1h00");
  const time: any = await ui.find({ type: "Text", text: "1h00" });
  expect(time?.props?.bold).toBe(true);
  expect(time?.props?.color).toBeUndefined();
});

test("cache: yellow under 10 minutes, then expired with /compact", async ($, on) => {
  const clock = mock.clock(on, { now: NOW });
  mock.store(on, {});
  mock.env(on, {});
  on("session.id", () => ({ value: "session-1" }));
  on("session.start", (_$: any, e: any) => ({ cwd: e.cwd ?? "/tmp" }));
  on("ui.invalidate", () => ({ value: undefined }));
  on("ui.render", ($: any, e: any) => $.ui.resolve(e).Box({ children: [] }));
  withUsage(on, LIMITS);
  engineStep(on, [HIT]);
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  await step($, HIT);
  await (clock as any).advance(55 * 60_000);
  let { ui, texts } = await band($, "terminal");
  expect(texts).toContain("5 min");
  const soon: any = await ui.find({ type: "Text", text: "5 min" });
  expect(soon?.props?.color).toBe("#a8690a");
  // The time alone: no stake, no dollars, on either surface.
  expect(texts.join(" ")).not.toContain("at stake");
  expect(texts.join(" ")).not.toContain("$");
  const desktop = await band($, "desktop");
  const yellow: any = await desktop.ui.find({ type: "Text", text: "5 min" });
  expect(yellow?.props?.color).toBe("#a8690a");
  expect(desktop.texts.join(" ")).not.toContain("$");
  // The card says what lapsing would write again, in tokens.
  expect(await boltTip(desktop.ui)).toBe(`The cache expires at ${at(NOW + 3_600_000)}. Send your next message before then, or it writes 107k tokens again.`);
  await (clock as any).advance(6 * 60_000);
  ({ ui, texts } = await band($, "terminal"));
  expect(texts).toContain("expired");
  // 107k of context: past 100k, what gets written again (tokens only) and /compact before going on.
  expect(texts).toContain("· 107k to rewrite · /compact");
  expect(texts.join(" ")).not.toContain("$");
  const expired: any = await ui.find({ type: "Text", text: "expired" });
  expect(expired?.props?.color).toBe("red");
});

test("cache: a miss after a model change names the cause", async ($, on) => {
  world(on);
  withUsage(on, LIMITS);
  engineStep(on, [HIT, { ...MISS, model: "claude-sonnet-5-5" }]);
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  await step($, HIT);
  await step($, MISS, "claude-sonnet-5-5");
  const { texts } = await band($, "terminal");
  expect(texts).toContain("0%");
  // The cause on the line; the tokens written again in the card. No surcharge.
  expect(texts).toContain("· missed · model changed");
  expect(texts.join(" ")).not.toContain("$");
  const desktop = await band($, "desktop");
  expect(desktop.texts).toContain("missed · model changed");
  expect(await boltTip(desktop.ui)).toBe("This message read only 0% from the cache (model changed): it wrote 99.7k tokens again.");
});

test("cache: 5 minutes on an API key (no plan window)", async ($, on) => {
  world(on);
  withUsage(on, []);
  engineStep(on, [HIT]);
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  await step($, HIT);
  const { texts } = await band($, "terminal");
  expect(texts).toContain("5 min");
});

test("agents: a pill while subagents run, gone once they finish", async ($, on) => {
  world(on);
  withUsage(on, LIMITS);
  let list = [
    { id: "a1", description: "Review the diff", type: "Plan", status: "running" },
    { id: "a2", description: "Search the repo", type: "Explore", status: "running" },
    { id: "a0", description: "Earlier", type: "Explore", status: "completed" },
  ];
  on("agent.list", () => ({ value: list }));
  on("turn.complete", () => ({ text: "" }));
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  const desktop = await band($, "desktop");
  expect(desktop.texts).toContain("2 running · 2");
  const card = String(await cardOf(desktop.ui, "agents"));
  expect(card).toContain("Agents in this thread: 2 (2 running)");
  expect(card).toContain("Running: Plan · “Review the diff” · < 1 min");
  expect((await band($, "terminal")).texts).toContain("2 running · 2");
  list = list.map((a) => ({ ...a, status: "completed" }));
  await ($ as any).turn.complete({ answer: "ok", agentId: "a1" } as any);
  // None ran a request: the terminal drops the block, the app keeps the pill at 0.
  const after = await band($, "terminal");
  expect(after.texts.some((t: string) => t.includes("agent") || t.includes("running"))).toBe(false);
  const app = await band($, "desktop");
  expect(app.texts).toContain("0");
  expect(await cardOf(app.ui, "agents")).toBe("Agents in this thread: 0\nNo subagent in this thread yet.");
});

test("agents: those that ran a request are counted, without a cost split, and kept for a resumed thread", async ($, on) => {
  world(on);
  withUsage(on, LIMITS);
  on("agent.list", () => ({
    value: [
      { id: "h1", description: "List the files", type: "Explore", status: "completed" },
      { id: "h2", description: "Check the captures", type: "general-purpose", status: "completed" },
      { id: "s1", description: "Sum up the README", type: "general-purpose", status: "completed" },
    ],
  }));
  on("turn.complete", () => ({ text: "" }));
  const work = { input_tokens: 2_000, cache_read_input_tokens: 70_000, cache_creation_input_tokens: 6_000, output_tokens: 20_000 };
  engineStep(on, [HIT, { ...work, model: "claude-haiku-5-5" }, { ...work, model: "claude-haiku-5-5" }, { ...work, model: "claude-sonnet-5-5" }]);
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  await step($, HIT);
  for (const [agentId, model, effort] of [["h1", "claude-haiku-5-5", "medium"], ["h2", "claude-haiku-5-5", "high"], ["s1", "claude-sonnet-5-5", "high"]]) {
    const stream = ($ as any).turn.step({ turnId: "t", index: 0, model, effort, agentId, messageCount: 2 });
    for await (const _ of stream) {
    }
    await ($ as any).turn.complete({ answer: "ok", agentId } as any);
  }
  const { ui, texts } = await band($, "desktop");
  expect(texts).toContain("3");
  // The count alone: no model groups, no efforts, no dollars.
  expect(await cardOf(ui, "agents")).toBe("Agents in this thread: 3");
  expect(texts.join(" ")).not.toContain("$");
  // Kept in the store: a resumed thread finds its agents again.
  await $.session.start({ source: "resume", cwd: "/tmp" } as any);
  const resumed = await band($, "desktop");
  expect(resumed.texts).toContain("3");
  expect(await cardOf(resumed.ui, "agents")).toBe("Agents in this thread: 3");
});

test("desktop icons: gauge centred at y=12", async ($, on) => {
  world(on);
  on("turn.complete", () => ({ text: "" }));
  let call = 0;
  on("session.usage", () => ({ value: { startedAt: NOW, context: { tokens: 400_000 + call++ * 1_000, window: 1_000_000, percent: 40 }, rateLimits: LIMITS } }));
  await $.session.start({ source: "resume", cwd: "/tmp" } as any);
  await ($ as any).turn.complete({ answer: "ok" } as any);
  const { ui } = await band($, "desktop");
  const svgs = (await ui.findAll({ type: "Svg" })) as any[];
  const source = (alt: string) => String(svgs.find((s) => s.props?.alt === alt)?.props?.source);
  expect(source("5-hour limit")).toContain('<g transform="translate(0 0.5)"><path d="M3.6 18.5');
});

test("cache expired from 300k: what gets written again, and a new thread", async ($, on) => {
  const clock = mock.clock(on, { now: NOW });
  mock.store(on, {});
  mock.env(on, {});
  on("session.id", () => ({ value: "session-1" }));
  on("session.start", (_$: any, e: any) => ({ cwd: e.cwd ?? "/tmp" }));
  on("ui.invalidate", () => ({ value: undefined }));
  on("ui.render", ($: any, e: any) => $.ui.resolve(e).Box({ children: [] }));
  withUsage(on, LIMITS, { tokens: 741_000, window: 1_000_000, percent: 74 });
  engineStep(on, [HIT]);
  await $.session.start({ source: "resume", cwd: "/tmp" } as any);
  await step($, HIT);
  await (clock as any).advance(61 * 60_000);
  const { texts } = await band($, "terminal");
  // A new thread avoids rewriting the whole context; a compaction would read it all again.
  // The terminal has no card: the advice stays on the line.
  expect(texts).toContain("· 741k to rewrite · new thread");
  expect(texts.join(" ")).not.toContain("/compact");
  expect(texts.join(" ")).not.toContain("$");
  // In the app the advice moves to the bolt's card.
  const desktop = await band($, "desktop");
  expect(desktop.texts).toContain("741k to rewrite");
  expect(desktop.texts.join(" ")).not.toContain("new thread");
  const tip = String(await boltTip(desktop.ui));
  expect(tip).toContain("The next message writes the whole context (741k) again.");
  expect(tip).not.toContain("$");
  expect(tip).toContain("A new thread avoids this rewrite; a compaction would read it all again.");
  expect(tip).not.toContain("/compact");
});

test("cache: below 90% served, the share before the time", async ($, on) => {
  world(on);
  withUsage(on, LIMITS);
  const PART = { ...HIT, cache_read_input_tokens: 72_000, cache_creation_input_tokens: 0, input_tokens: 28_000 };
  engineStep(on, [PART]);
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  await step($, PART);
  const { texts } = await band($, "terminal");
  expect(texts).toContain("72%");
  expect(texts).toContain("· 1h00");
});

test("desktop: pills never shrink, and the 5-hour reset time sits in the pill's hover card", async ($, on) => {
  world(on);
  withUsage(on, LIMITS);
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  const { ui } = await band($, "desktop");
  const pills = ((await ui.findAll({ type: "Box" })) as any[]).filter((b) => b.props?.backgroundColor && b.props?.position !== "absolute");
  for (const p of pills) expect(p.props?.flexShrink).toBe(0);
  expect(await cardOf(ui, "gauge-five_hour")).toBe(`Resets at ${at(NOW + 3 * 3_600_000)}`);
});

// ---------- Compaction ----------

// A large thread whose cache expired, as the band showed it before a /compact.
async function largeExpired($: any, on: any, compaction: Record<string, unknown>) {
  const clock = mock.clock(on, { now: NOW });
  mock.store(on, {});
  mock.env(on, {});
  on("session.id", () => ({ value: "session-1" }));
  on("session.start", (_$: any, e: any) => ({ cwd: e.cwd ?? "/tmp" }));
  on("ui.invalidate", () => ({ value: undefined }));
  on("ui.render", ($: any, e: any) => $.ui.resolve(e).Box({ children: [] }));
  on("turn.complete", () => ({ text: "" }));
  on("session.compact", () => compaction);
  withUsage(on, LIMITS, { tokens: 784_000, window: 1_000_000, percent: 78 });
  engineStep(on, [
    { ...HIT, cache_read_input_tokens: 780_000 },
    // The first request after the compaction writes the whole, smaller, context.
    { ...MISS, cache_creation_input_tokens: 47_700 },
  ]);
  await $.session.start({ source: "resume", cwd: "/tmp" } as any);
  await step($, HIT);
  await (clock as any).advance(75 * 60_000);
  return clock;
}

test("compaction: the context drops at once, no expired cache", async ($, on) => {
  await largeExpired($, on, { messages: [{ role: "user", text: "Summary of the thread", toolUses: [] }], tokensBefore: 784_000, tokensAfter: 48_000 });
  const before = await band($, "terminal");
  expect(before.texts).toContain("784k");
  expect(before.texts).toContain("expired");
  expect(before.texts).toContain("· 784k to rewrite · new thread");
  await ($ as any).session.compact({ trigger: "manual", messages: [{ role: "user", text: "Go on", toolUses: [] }, { role: "assistant", text: "Done", toolUses: [] }] });
  const after = await band($, "terminal");
  expect(after.texts).toContain("48k");
  expect(after.texts).not.toContain("784k");
  expect(after.texts.join(" ")).not.toContain("new thread");
  expect(after.texts).not.toContain("expired");
  expect(after.texts).toContain("compacted");
  expect(await boltTip((await band($, "desktop")).ui)).toBe("Compacted: the next message writes a new, smaller cache.");
  // The next request writes a new cache: neither a miss nor expired.
  await step($, HIT);
  const next = await band($, "terminal");
  expect(next.texts).not.toContain("compacted");
  expect(next.texts.join(" ")).not.toContain("missed");
  expect(next.texts).toContain("1h00");
});

test("compaction: a skipped one changes nothing", async ($, on) => {
  await largeExpired($, on, { skip: "blocked by a hook" });
  await ($ as any).session.compact({ trigger: "manual", messages: [{ role: "user", text: "Go on", toolUses: [] }, { role: "assistant", text: "Done", toolUses: [] }] });
  const { texts } = await band($, "terminal");
  expect(texts).toContain("784k");
  expect(texts).toContain("expired");
  expect(texts).not.toContain("compacted");
});

// ---------- Cache card ----------

// A large thread: 289k of context, 287k of it read from the cache by the last message.
const BIG = { tokens: 289_000, window: 1_000_000, percent: 29 };
const BIG_HIT = { model: "claude-opus-5-5", input_tokens: 300, cache_read_input_tokens: 287_000, cache_creation_input_tokens: 1_700, output_tokens: 500 };

test("cache card, warm: lifetime assumed, the share read, no costs", async ($, on) => {
  world(on);
  withUsage(on, LIMITS, BIG);
  engineStep(on, [BIG_HIT]);
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  await step($, BIG_HIT);
  await step($, BIG_HIT);
  const { ui, texts } = await band($, "desktop");
  // The pill itself: the time left alone.
  expect(texts).toContain("1h00");
  expect(texts.join(" ")).not.toContain("$");
  expect(await boltTip(ui)).toBe(
    [
      `Cache warm until ${at(NOW + 3_600_000)} (1-hour lifetime, assumed).`,
      // 287k read out of a 289.3k prompt.
      "Last message: 99% read from the cache (287k).",
    ].join("\n"),
  );
});

test("cache card, warm: lifetime observed after a hit past 5 minutes", async ($, on) => {
  const clock = world(on);
  withUsage(on, LIMITS, BIG);
  engineStep(on, [BIG_HIT, BIG_HIT]);
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  await step($, BIG_HIT);
  // A hit 6 minutes later proves the 1-hour lifetime.
  await clock.advance(6 * 60_000);
  await step($, BIG_HIT);
  expect(String(await boltTip((await band($, "desktop")).ui))).toContain(`Cache warm until ${at(NOW + 6 * 60_000 + 3_600_000)} (1-hour lifetime, observed).`);
});

test("cache: under 10 minutes and under 90% served, the time in yellow after the share", async ($, on) => {
  const clock = world(on);
  withUsage(on, LIMITS);
  const PART = { ...HIT, cache_read_input_tokens: 72_000, cache_creation_input_tokens: 0, input_tokens: 28_000 };
  engineStep(on, [PART]);
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  await step($, PART);
  await clock.advance(55 * 60_000);
  const { ui, texts } = await band($, "terminal");
  expect(texts).toContain("72%");
  const time: any = await ui.find({ type: "Text", text: "· 5 min" });
  expect(time?.props?.color).toBe("#a8690a");
  expect(texts.indexOf("72%")).toBeLessThan(texts.indexOf("· 5 min"));
  expect(texts.join(" ")).not.toContain("at stake");
});

test("cache expired at 150k: the tokens in the pill, /compact in the card", async ($, on) => {
  const clock = world(on);
  withUsage(on, LIMITS, { tokens: 150_000, window: 1_000_000, percent: 15 });
  engineStep(on, [HIT]);
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  await step($, HIT);
  await clock.advance(61 * 60_000);
  const desktop = await band($, "desktop");
  expect(desktop.texts).toContain("150k to rewrite");
  expect(desktop.texts.join(" ")).not.toContain("/compact");
  expect(desktop.texts.join(" ")).not.toContain("$");
  expect(await boltTip(desktop.ui)).toBe("The next message writes the whole context (150k) again.\n/compact before going on: the context written again will be smaller.");
  // The terminal, without a card, keeps the advice on the line.
  const { texts } = await band($, "terminal");
  expect(texts).toContain("· 150k to rewrite · /compact");
});

// ---------- Agents card: each running agent's latest tool call, the last batch ----------

// Each request answers with the tools queued by use().
function crew(on: any) {
  const clock = world(on);
  withUsage(on, LIMITS);
  on("turn.complete", () => ({ text: "" }));
  on("turn.step", async function* () {
    const { uses, stop } = next.shift() ?? { uses: [], stop: "end_turn" };
    return { turnId: "t", index: 0, answer: "", toolUses: uses.map((name: string) => ({ name, input: { command: "SECRET=x" } })), stopReason: stop, usage: null };
  });
  return { advance: (ms: number) => clock.advance(ms) };
}

// The tools a subagent's response asks for; "tool_use" leaves the agent waiting on them.
const next: Array<{ uses: string[]; stop: string }> = [];
async function use($: any, agentId: string, tool?: string, stop = "end_turn") {
  next.push({ uses: tool ? [tool] : [], stop });
  const stream = $.turn.step({ turnId: "t", index: 0, model: "claude-haiku-5-5", effort: "medium", agentId, messageCount: 2 });
  for await (const _ of stream) {
  }
}

// The agents $.agent.list() names: the engine lists one from its spawn, then marks it done. A
// subagent's turn end makes the mod read the list again.
function roster(on: any, others: any[] = []) {
  const list: any[] = [];
  on("agent.list", () => ({ value: [...others, ...list] }));
  const add = async ($: any, ids: string[], parentId?: string) => {
    for (const id of ids) list.push({ id, description: id, type: "general-purpose", status: "running", ...(parentId ? { parentId } : {}) });
    await $.turn.complete({ answer: "", agentId: ids[0] } as any);
  };
  return {
    add: ($: any, ...ids: string[]) => add($, ids),
    addUnder: ($: any, parentId: string, id: string) => add($, [id], parentId),
    done: () => list.forEach((a) => (a.status = "completed")),
  };
}

// A subagent's request answered by engineStep's next usage.
async function agentStep($: any, agentId: string, model = "claude-haiku-5-5") {
  const stream = $.turn.step({ turnId: "t", index: 0, model, effort: "medium", agentId, messageCount: 2 });
  for await (const _ of stream) {
  }
}

const agentsCard = async ($: any) => String(await cardOf((await band($, "desktop")).ui, "agents"));

test("model ids: Bedrock and Vertex ids read as the same model as the API's", () => {
  for (const id of [
    "claude-sonnet-5-5",
    "claude-sonnet-5-5-20260101",
    "claude-sonnet-5-5[1m]",
    "anthropic.claude-sonnet-5-5-20260101-v1:0",
    "us.anthropic.claude-sonnet-5-5-20260101-v1:0",
    "eu.anthropic.claude-sonnet-5-5-v2",
    "claude-sonnet-5-5@20260101",
    "publishers/anthropic/models/claude-sonnet-5-5@20260101",
  ]) expect(modelId(id)).toBe("claude-sonnet-5-5");
});

test("agents: a tool's name in Claude Code's words, never its arguments", () => {
  expect(toolText("Bash")).toBe("Bash");
  expect(toolText("mcp__github__list_issues")).toBe("github:list_issues");
  // A connector's UUID says nothing; a long server name gives way to the tool's.
  expect(toolText("mcp__8377b461-f34f-4b2d-a906-1f52a65d3dc1__get-product")).toBe("get-product");
  expect(toolText("mcp__claude-in-chrome__javascript_tool")).toBe("claude-…:javascript_tool");
  for (const tool of ["mcp__claude-in-chrome__javascript_tool", "mcp__plugin_pdf-viewer_pdf__display_pdf", "Bash"]) {
    expect(`  ↳ ${toolText(tool)} · 123 calls`.length).toBeLessThanOrEqual(55);
  }
});

test("agents: a start more than 30 s after everything before it had ended opens a new batch", () => {
  const a = { id: "a", from: 0, to: 60_000, ran: true };
  expect(batchesOf([a, { id: "b", from: 90_000, to: 95_000, ran: true }]).length).toBe(1);
  expect(batchesOf([a, { id: "b", from: 90_001, to: 95_000, ran: true }]).length).toBe(2);

  const batches = batchesOf([
    { id: "a", from: 0, to: 60_000, ran: true },
    { id: "b", from: 5_000, to: 50_000, ran: true },
    { id: "c", from: 200_000, to: null, ran: true },
    { id: "d", from: 210_000, to: 220_000, ran: true },
    { id: "z", from: 0, to: 0, ran: false },
  ]);
  expect(batches.map((b: any[]) => b.map((r) => r.id))).toEqual([["a", "b"], ["c", "d"]]);
});

test("agents: each running agent's latest tool call, then the batch's receipt", async ($, on) => {
  const clock = crew(on);
  let list = [
    { id: "a", description: "Sum up the README", type: "general-purpose", status: "running" },
    { id: "b", description: "Check the captures", type: "general-purpose", status: "running" },
  ];
  on("agent.list", () => ({ value: list }));
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  await use($, "a", "Bash");
  await use($, "a", "Bash");
  await use($, "b", "Read");
  // The main thread's own calls draw no line.
  await use($, "", "Glob");
  const running = String(await cardOf((await band($, "desktop")).ui, "agents"));
  expect(running).toContain("Running: general-purpose · “Sum up the README” · < 1 min\n  ↳ Bash · 2 calls");
  expect(running).toContain("  ↳ Read · 1 call");
  // Never a tool's arguments, nor the main thread's own calls.
  expect(running).not.toContain("SECRET");
  expect(running).not.toContain("Glob");
  expect(running).not.toContain("Last batch");
  // b's last call a minute in, a's at 1 min 50; then both end and the 10-second ticker reads the
  // list again: each ends at its last trace, not at that reading.
  await clock.advance(60_000);
  await use($, "b", "Read");
  await clock.advance(50_000);
  await use($, "a", "Bash");
  list = list.map((a) => ({ ...a, status: "completed" }));
  await clock.advance(10_000);
  const done = await agentsCard($);
  expect(done).toContain("Last batch: 2 agents in 1 min 50\n  1.5× in parallel · 5 tool calls");
  expect(done).not.toContain("↳");
  // The card's lines stay short: the app wraps past about 55 characters.
  for (const line of done.split("\n").filter((l) => l.includes("batch") || l.includes("parallel"))) expect(line.length).toBeLessThanOrEqual(55);
});

test("agents: the last batch's receipt, without a cost", async ($, on) => {
  const receipt = "Last batch: 2 agents in 20 s\n  3 tool calls";
  const clock = crew(on);
  const team = roster(on);
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  await team.add($, "w1", "w2");
  await use($, "w1", "Grep");
  await use($, "w2", "Glob");
  await clock.advance(20_000);
  await use($, "w1", "Read");
  expect(String(await cardOf((await band($, "desktop")).ui, "agents"))).not.toContain(receipt.split("\n")[0]);
  team.done();
  await clock.advance(10_000);
  const card = String(await cardOf((await band($, "desktop")).ui, "agents"));
  expect(card).toContain(receipt);
  expect(card).not.toContain("$");
});

test("agents: one waiting on its own agents stays in the batch until it ends", async ($, on) => {
  const clock = crew(on);
  let list = [
    { id: "a", description: "Lead the review", type: "general-purpose", status: "running" },
    { id: "b", description: "Check the captures", type: "general-purpose", status: "running" },
  ];
  on("agent.list", () => ({ value: list }));
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  await use($, "a", "Read");
  await clock.advance(10_000);
  await use($, "b", "Read");
  list = [{ ...list[0], status: "waiting" }, { ...list[1], status: "completed" }];
  await clock.advance(70_000);
  expect(await agentsCard($)).not.toContain("Last batch");
  await use($, "a", "Write");
  list = list.map((a) => ({ ...a, status: "completed" }));
  await clock.advance(10_000);
  expect(await agentsCard($)).toContain("Last batch: 2 agents in 1 min 20\n  3 tool calls");
});

test("agents: the engine's own forks (no spawn, no list) make no batch", async ($, on) => {
  const clock = crew(on);
  on("agent.list", () => ({ value: [] }));
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  await use($, "fork-memory", "Read");
  await use($, "fork-compact", "Read");
  await clock.advance(20_000);
  await use($, "fork-memory", "Write");
  await clock.advance(120_000);
  expect(await agentsCard($)).not.toContain("Last batch");
});

test("agents: an agent resumed later starts a new run, in a new batch", async ($, on) => {
  const clock = crew(on);
  let list = [
    { id: "a", description: "Read the logs", type: "general-purpose", status: "running" },
    { id: "b", description: "Check the tests", type: "general-purpose", status: "running" },
  ];
  on("agent.list", () => ({ value: list }));
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  await use($, "a", "Read");
  await use($, "b", "Read");
  await clock.advance(20_000);
  await use($, "a", "Read");
  list = list.map((x) => ({ ...x, status: "completed" }));
  await clock.advance(10_000);
  expect(await agentsCard($)).toContain("Last batch: 2 agents in 20 s\n  3 tool calls");
  // Five minutes later, a is resumed under its id beside a new agent c.
  await clock.advance(300_000);
  list = [{ ...list[0], status: "running" }, list[1], { id: "c", description: "Fix the test", type: "general-purpose", status: "running" }];
  await use($, "a", "Edit");
  await clock.advance(10_000);
  await use($, "c", "Edit");
  await clock.advance(20_000);
  await use($, "a", "Bash");
  list = list.map((x) => ({ ...x, status: "completed" }));
  await clock.advance(10_000);
  // Only the new runs: a from its resume, c; not a's first run five minutes earlier.
  expect(await agentsCard($)).toContain("Last batch: 2 agents in 30 s\n  3 tool calls");
});

test("agents: a teammate idle at start and woken later counts from its wake", async ($, on) => {
  const clock = crew(on);
  let list = [{ id: "t1", description: "Reviewer", type: "teammate", status: "idle" }];
  on("agent.list", () => ({ value: list }));
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  await clock.advance(30 * 60_000);
  list = [{ ...list[0], status: "running" }, { id: "n1", description: "New task", type: "general-purpose", status: "running" }];
  await use($, "t1", "Read");
  await clock.advance(10_000);
  await use($, "n1", "Grep");
  await clock.advance(10_000);
  await use($, "t1", "Write");
  list = [{ ...list[0], status: "idle" }, { ...list[1], status: "completed" }];
  await clock.advance(10_000);
  expect(await agentsCard($)).toContain("Last batch: 2 agents in 20 s\n  3 tool calls");
});

test("agents: an agent stuck open with no trace for 10 minutes no longer hides later batches", async ($, on) => {
  const clock = crew(on);
  // A teammate whose pane died: listed as running for good, never heard from.
  const team = roster(on, [{ id: "z", description: "Gone", type: "teammate", status: "running" }]);
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  await clock.advance(11 * 60_000);
  await team.add($, "p", "q");
  await use($, "p", "Read");
  await use($, "q", "Read");
  await clock.advance(30_000);
  await use($, "p", "Write");
  team.done();
  await clock.advance(10_000);
  expect(await agentsCard($)).toContain("Last batch: 2 agents in 30 s\n  3 tool calls");
});

test("agents: a subagent inside its parent's time does not count as running side by side", async ($, on) => {
  const clock = crew(on);
  const team = roster(on);
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  await team.add($, "p");
  await use($, "p", "Agent");
  await clock.advance(10_000);
  await team.addUnder($, "p", "c");
  await use($, "c", "Read");
  await clock.advance(30_000);
  await use($, "c", "Read");
  await clock.advance(20_000);
  await use($, "p", "Write");
  team.done();
  await clock.advance(10_000);
  const card = await agentsCard($);
  expect(card).toContain("Last batch: 2 agents in 1 min\n  4 tool calls");
  expect(card).not.toContain("×");
});

const weekOf = (used: number, daysLeft: number) => [
  { kind: "seven_day", percentUsed: used, resetsAt: new Date(NOW + daysLeft * 86_400_000).toISOString() },
];
const runOutText = (texts: string[]) => texts.find((t) => t.startsWith("⚠"));

// 7-day estimate: the day part the run-out falls in, as the band writes it (the hours after
// midnight belong to the day before, as its night).
const DAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const PARTS = ["night", "morning", "afternoon", "evening"];
function dayPart(ms: number) {
  const d = new Date(ms);
  const h = d.getHours();
  if (h < 6) return `${DAYS[(d.getDay() + 6) % 7]} night`;
  return `${DAYS[d.getDay()]} ${PARTS[h < 12 ? 1 : h < 18 ? 2 : 3]}`;
}

test("7-day estimate: at the week's pace the limit runs out before the reset", async ($, on) => {
  world(on);
  // 70% in 4 days: 17.5% a day, the last 30% gone in about 1.7 days, before the reset in 3.
  withUsage(on, weekOf(70, 3));
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  const { ui, texts } = await band($, "terminal");
  const out = NOW + (30 / 70) * 4 * 86_400_000;
  expect(runOutText(texts)).toBe(`⚠ out ${dayPart(out)}`);
  const pill: any = await ui.find({ type: "Text", text: `⚠ out ${dayPart(out)}` });
  expect(pill?.props?.color).toBe("#a8690a");
  const card = await cardOf((await band($, "desktop")).ui, "gauge-seven_day");
  expect(card).toContain("At this week's pace (+70% in 4d00h)");
  expect(card).not.toContain("At the last ");
  expect(card).toContain("before the reset on");
});

test("7-day estimate: none when the pace lasts until the reset", async ($, on) => {
  world(on);
  // 50% in 4 days: the last 50% would take 4 more days, the reset comes in 3.
  withUsage(on, weekOf(50, 3));
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  const { texts } = await band($, "terminal");
  expect(runOutText(texts)).toBeUndefined();
});

test("7-day estimate: none in the week's first day", async ($, on) => {
  world(on);
  withUsage(on, [...weekOf(20, 6.5)]);
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  expect(runOutText((await band($, "terminal")).texts)).toBeUndefined();
});

test("7-day estimate: none under 15% used", async ($, on) => {
  world(on);
  withUsage(on, weekOf(14, 6));
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  expect(runOutText((await band($, "terminal")).texts)).toBeUndefined();
});

test("7-day estimate: the week's pace decides, the last day's shown beside it", async ($, on) => {
  const resetsAt = new Date(NOW + 3 * 86_400_000).toISOString();
  // 70% in 4 days: out in about 1.7 days. A day ago 30% was used: 40% in a day, out in 18 hours.
  world(on, { week: [{ at: NOW - 86_400_000, used: 30, resetsAt }] });
  withUsage(on, [{ kind: "seven_day", percentUsed: 70, resetsAt }]);
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  const { ui, texts } = await band($, "terminal");
  const text = runOutText(texts);
  expect(text?.startsWith("⚠ out ")).toBe(true);
  const pill: any = await ui.find({ type: "Text", text });
  expect(pill?.props?.color).toBe("#a8690a");
  const card = await cardOf((await band($, "desktop")).ui, "gauge-seven_day");
  expect(card).toContain("At this week's pace (+70% in 4d00h)");
  expect(card).toContain("At the last 1d00h's pace (+40%):");
});

test("7-day estimate: a quiet last day lasts until the reset", async ($, on) => {
  const resetsAt = new Date(NOW + 3 * 86_400_000).toISOString();
  world(on, { week: [{ at: NOW - 86_400_000, used: 68, resetsAt }] });
  withUsage(on, [{ kind: "seven_day", percentUsed: 70, resetsAt }]);
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  expect(await cardOf((await band($, "desktop")).ui, "gauge-seven_day")).toContain("it would last until the reset");
});

test("7-day estimate: red within a day", async ($, on) => {
  // 90% in 6 days: the last 10% gone in about 16 hours.
  world(on);
  withUsage(on, weekOf(90, 1));
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  const { ui, texts } = await band($, "terminal");
  const pill: any = await ui.find({ type: "Text", text: runOutText(texts) });
  expect(pill?.props?.color).toBe("red");
});

test("7-day estimate: readings are kept, at most one per half hour", async ($, on) => {
  const clock = mock.clock(on, { now: NOW }) as any;
  mock.env(on, {});
  const store = new Map<string, unknown>();
  on("store.get", (_$: any, e: any) => ({ value: store.get(e.key) }));
  on("store.set", (_$: any, e: any) => (store.set(e.key, e.value), { value: undefined }));
  on("store.delete", (_$: any, e: any) => (store.delete(e.key), { value: undefined }));
  on("store.keys", () => ({ value: [...store.keys()] }));
  on("session.id", () => ({ value: "session-1" }));
  on("session.start", (_$: any, e: any) => ({ cwd: e.cwd ?? "/tmp" }));
  on("ui.invalidate", () => ({ value: undefined }));
  const resetsAt = new Date(NOW + 3 * 86_400_000).toISOString();
  const seven = (used: number) => [{ kind: "seven_day", percentUsed: used, resetsAt }];
  on("session.usage", () => ({ value: { startedAt: NOW, context: { tokens: 1, window: 1_000_000, percent: 0 }, rateLimits: seven(60) } }));
  on("session.measure", (_$: any, e: any) => ({ changed: e.changed }));
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  await clock.advance(10 * 60_000);
  await ($ as any).session.measure({ changed: ["rateLimits"], rateLimits: seven(61) } as any);
  await clock.advance(25 * 60_000);
  await ($ as any).session.measure({ changed: ["rateLimits"], rateLimits: seven(62) } as any);
  const week = store.get("week") as any[];
  expect(week.map((s) => s.used)).toEqual([60, 62]);
});

// ---------- Regressions carried over from the original ----------

test("narrow terminal: no run-out warning either", async ($, on) => {
  world(on);
  withUsage(on, weekOf(70, 3));
  await $.session.start({ source: "startup", cwd: "/tmp" } as any);
  expect(runOutText((await band($, "terminal", 60)).texts)).toBeUndefined();
  expect(runOutText((await band($, "terminal")).texts)).toBeDefined();
});

