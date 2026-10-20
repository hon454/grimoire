# Writing good tests

Read this when writing or changing a test, adding a mock, or adding a test helper. Two principles govern everything here:

```
1. Every test names the break it catches.
2. Every test exercises the real thing.
```

Strict TDD produces both naturally: a test written first and watched failing against real code has already proven it can fail, and it only earns a mock when the real dependency proves slow or external.

## Principle 1: name the break

Before writing the test body, answer: **what production change would make this test fail, and is that change a bug or a decision?** A test earns its place by catching a wrong branch, a missing side effect, a wrong argument, a boundary case or a broken contract.

**Test behaviour through the public interface.** A good test reads like a specification: "user can check out with a valid cart" says exactly what capability exists, and it survives refactors because it does not care about internal structure.

```typescript
// Good: observable behaviour through the interface
test('user can check out with a valid cart', async () => {
  const cart = createCart();
  cart.add(product);
  const result = await checkout(cart, paymentMethod);
  expect(result.status).toBe('confirmed');
});

// Bad: coupled to implementation
test('checkout calls paymentService.process', async () => {
  const mockPayment = jest.mock(paymentService);
  await checkout(cart, payment);
  expect(mockPayment.process).toHaveBeenCalledWith(cart.total);
});

// Bad: verifies through a side channel instead of the interface
test('createUser saves to database', async () => {
  await createUser({ name: 'Alice' });
  const row = await db.query('SELECT * FROM users WHERE name = ?', ['Alice']);
  expect(row).toBeDefined();
});

// Good: verifies through the interface
test('createUser makes the user retrievable', async () => {
  const user = await createUser({ name: 'Alice' });
  expect((await getUser(user.id)).name).toBe('Alice');
});
```

The tell of an implementation-coupled test: it breaks when you refactor but behaviour has not changed.

**Derive expectations independently.** Use literals and hand-checked fixtures. Table-driven tests with literal `want` values are the preferred shape. An expectation computed by the code under test, or by its helpers, passes no matter what that code does. This is a **tautological** test.

```typescript
// Bad: the same logic computes both sides, so the test is always true
const items = [{ price: 10 }, { price: 5 }];
const expected = items.reduce((sum, i) => sum + i.price, 0);
expect(calculateTotal(items)).toBe(expected);

// Good: hand-derived literal
expect(calculateTotal([{ price: 10 }, { price: 5 }])).toBe(15);
```

**No change detectors.** If only an intentional decision can fail a test (a constant's value, exact message wording, private structure), it fires on redesign and sleeps through bugs. Test the behaviour that depends on the decision: not `expect(MAX_RETRIES).toBe(5)` but "a failing call is retried 5 times and a 6th attempt never happens".

**Behaviour, not text.** Asserting that a script, skill or config file contains an exact line proves only that the source is the source. Run scripts against controlled inputs and assert outputs, side effects or exit codes. Prose for humans earns no test at all.

**Your code, not the framework.** Test the contract your code makes at its boundaries: the route you register, the query you emit, the payload you produce. Asserting that a router invokes a registered handler is the framework's test, not yours. Constructors, getters, constants and trivial forwarding earn tests only when they validate, normalize, default, derive, enforce or cause side effects.

### Gate before writing a test body

```
Name the production change that would make this test fail.
  Cannot name one             -> redesign around an observable behaviour
  "The source text changed"   -> run the artifact and assert its effects
  Only an intentional decision -> change detector; test the behaviour that depends on it

Confirm the expected value is derived without the code under test.
  It reuses the code's logic or helpers -> replace it with a literal or hand-checked fixture
```

## Principle 2: exercise the real thing

**Mock only at system boundaries.** External APIs (payment, email), time and randomness, sometimes the database (prefer a test database) and sometimes the file system. Never mock your own classes, modules or internal collaborators: anything you control stays real.

**The mock earns no assertions.** A mock assertion passes when the mock is present and fails when it is absent. It says nothing about the component. If the mock is what you are checking, unmock it or delete the assertion.

```typescript
// Good: real behaviour
expect(screen.getByRole('navigation')).toBeInTheDocument();

// Bad: the mock's existence
expect(screen.getByTestId('sidebar-mock')).toBeInTheDocument();
```

**Mock at the right level.** Learn every side effect of the real method before replacing it; mock the slow or external operation and keep what the test depends on real. When unsure, run the test against the real implementation first and observe what actually has to happen.

```typescript
// Bad: the mock swallows the config write that duplicate detection reads
vi.mock('ToolCatalog', () => ({ discoverAndCacheTools: vi.fn().mockResolvedValue(undefined) }));

// Good: mock only the slow server startup; the config write stays real
vi.mock('MCPServerManager');
```

**Make doubles specific.** When arguments, call counts or ordering are part of the contract, assert them. A fake that accepts anything verifies nothing. Give each branch (success, error, malformed) its own fixture or spy so the wrong branch cannot satisfy the expectation.

**Mirror real data completely.** Mock the full structure as it exists in reality, not only the fields your test reads. Partial mocks fail silently when downstream code reads an omitted field.

**Design boundaries for mockability.** Inject external dependencies instead of constructing them inside, and prefer one specific function per external operation (`api.getUser(id)`, `api.createOrder(data)`) over one generic fetcher with conditional logic. Each mock then returns one shape and the test shows which operations it exercises.

**Production classes carry production methods only.** Cleanup that only tests need lives in test utilities, never as a `destroy()` on the production class. Is this method called only from tests? Then it belongs in a test utility.

**Prefer real components over complex mocks.** When mock setup outgrows the test logic, when mocks miss methods the real components have, or when tests break because a mock changed, switch to an integration test with real components.

### Gate before adding a mock or helper

```
List the real method's side effects; keep the ones the test depends on real.
Mock the slow or external level below them.
Mock responses mirror the complete real structure.
A method only tests call lives in test utilities, not production.
About to assert on the mock itself? Unmock it or delete the assertion.
```

## The mutation check

Before finishing a test file, mentally mutate the production code. At least one test should fail for each realistic mutation:

- wrong constant or argument;
- wrong branch handler;
- missing state change or side effect;
- empty or default return;
- missing validation for zero, empty, nil, unauthorized or malformed input.

A mutation nothing catches marks the behaviour as unprotected, or the test as tautological.

## Quick reference

| When you... | Do |
|---|---|
| Write any test | Name the break it catches: a bug, not a decision |
| Build an expected value | Derive it by hand, never with the code under test |
| Test a script or document | Run it and assert its effects; never grep its text |
| Reach for a dependency test | Test your boundary contract, not the dependency's mechanics |
| Want to assert on a mocked element | Test the real component, or unmock it |
| Are about to mock a method | Learn its side effects; mock the slow or external level |
| Build a mock response | Mirror the real structure completely |
| Need cleanup only tests use | Put it in test utilities |
| Watch mock setup balloon | Switch to an integration test with real components |
| Finish a test file | Run the mutation check |

## Warning signs

- Setup and assertion share the same object, guaranteeing equality.
- The test can fail only through a crash or a missing selector.
- The test fails on every intentional change and never on accidental breakage.
- Expected values hide behind loops, builders or helpers.
- The test greps source text, or asserts that a removed symbol stays removed.
- The test would still matter if only the framework remained.
- The test exists for coverage and checks no outcome.
- An assertion checks a `*-mock` test id, or fails if you remove the mock.
- A method is called only from test files.
- Mock setup is more than half the test, or you cannot explain why the mock is needed.
