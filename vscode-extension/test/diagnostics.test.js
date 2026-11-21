"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { problemsFrom } = require("../src/diagnostics");

test("a file and line in the detail becomes a problem on that line", () => {
  const problems = problemsFrom([
    { description: "`hello.py` is valid Python", ok: false, optional: false,
      detail: "SyntaxError in hello.py line 3: '(' was never closed" },
  ]);
  assert.deepEqual(problems.map((p) => [p.file, p.line, p.severity]), [["hello.py", 3, "error"]]);
  assert.match(problems[0].message, /never closed/);
});

test("several lines in one detail each get a problem", () => {
  const problems = problemsFrom([
    { description: "every block in `mood.py` is pushed in by exactly 4 spaces", ok: false, optional: false,
      detail: "mood.py line 7 is pushed in by 2 spaces\nmood.py line 9 is indented with a TAB" },
  ]);
  assert.deepEqual(problems.map((p) => p.line), [7, 9]);
});

test("a lone 'line N' uses the file named in backticks", () => {
  const problems = problemsFrom([
    { description: "no magic numbers left in `critters/actions.py`", ok: false, optional: false,
      detail: "line 12: `100` (give it a name in rules.py)" },
  ]);
  assert.equal(problems[0].file, "critters/actions.py");
  assert.equal(problems[0].line, 12);
});

test("a named file with no line goes on line 1; optional items are warnings; passes are skipped", () => {
  const problems = problemsFrom([
    { description: "`hello.py` exists", ok: true, optional: false, detail: null },
    { description: "you left a # comment in `hello.py`", ok: false, optional: true, detail: null },
    { description: "all your tests are GREEN", ok: false, optional: false, detail: "2 failed" },
  ]);
  assert.deepEqual(problems.map((p) => [p.file, p.line, p.severity]), [["hello.py", 1, "warning"]]);
});
