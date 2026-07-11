// Minimal ESLint setup with a single purpose: block raw color literals in
// src so all colors flow through src/theme/theme.js tokens. No other rules
// are enabled; typechecking stays with tsc.
const COLOR_LITERAL = /#[0-9a-fA-F]{3}|rgba?\(|hsla?\(/.source;

const noColorLiterals = {
  "no-restricted-syntax": [
    "error",
    {
      selector: `Literal[value=/${COLOR_LITERAL}/]`,
      message: "Raw color literal. Use a palette token from src/theme/theme.js (add one there if none fits)."
    },
    {
      selector: `TemplateElement[value.raw=/${COLOR_LITERAL}/]`,
      message: "Raw color literal in template string. Use a palette token from src/theme/theme.js."
    }
  ]
};

module.exports = [
  {
    files: ["src/**/*.js"],
    ignores: ["src/theme/theme.js"],
    languageOptions: {
      ecmaVersion: 2023,
      sourceType: "module",
      parserOptions: {
        ecmaFeatures: { jsx: true }
      }
    },
    rules: noColorLiterals
  },
  {
    // Known-dirty screens deferred from the token consolidation pass; keep
    // them visible as warnings without blocking CI until they are burned down.
    files: ["src/screens/ChatScreen.js", "src/screens/CheckScreen.js"],
    rules: {
      "no-restricted-syntax": noColorLiterals["no-restricted-syntax"].map((entry, index) =>
        index === 0 ? "warn" : entry
      )
    }
  }
];
