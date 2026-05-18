import { defineConfig } from "vitest/config";

export default defineConfig({
  test: {
    globals: true,
    environment: "node",
    include: ["test/**/*.test.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.ts"],
      // statements/lines: 90 and branches: 80 are intentional + honest.
      // isMain()'s argv/realpath/catch branches ARE unit-tested in-process,
      // but the module-level `if (isMain()) console.log(banner())` entry
      // guard's true-branch only runs when this file is the process entry
      // point — vitest's in-process instrumented run can never take it
      // (argv[1] is the vitest runner), so that one line + branch is
      // permanently uncovered here. The subprocess test in index.test.ts
      // executes the built bin and asserts the banner, proving that path
      // end-to-end instead. Thresholds are set just below the achievable
      // ceiling (~91% stmts/lines, ~83% branches) so a real regression
      // still fails the gate.
      thresholds: { statements: 90, branches: 80, functions: 100, lines: 90 },
    },
  },
});
