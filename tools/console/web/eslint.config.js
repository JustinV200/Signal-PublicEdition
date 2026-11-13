// Minimal ESLint flat config: TypeScript recommended rules plus the React hooks rules.
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default tseslint.config(
  { ignores: ["dist/", "node_modules/"] },
  ...tseslint.configs.recommended,
  reactHooks.configs.flat.recommended,
  {
    // A UTF-8 BOM (which some Windows editors add) once shipped mojibake in the UI text.
    rules: { "unicode-bom": ["error", "never"] },
  },
  {
    files: ["**/*.{ts,tsx}"],
    rules: {
      "@typescript-eslint/consistent-type-imports": "error",
    },
  },
);
