import eslint from "@eslint/js";
import importX from "eslint-plugin-import-x";
import vue from "eslint-plugin-vue";
import globals from "globals";
import tseslint from "typescript-eslint";

export default [
  {
    ignores: ["dist/**", "node_modules/**"],
  },
  eslint.configs.recommended,
  ...tseslint.configs.recommended,
  ...vue.configs["flat/recommended"],
  {
    files: ["**/*.{ts,vue}"],
    languageOptions: {
      globals: globals.browser,
      parserOptions: {
        parser: tseslint.parser,
      },
    },
    plugins: {
      "import-x": importX,
    },
    rules: {
      "import-x/extensions": [
        "error",
        "never",
        {
          css: "always",
          vue: "always",
        },
      ],
      "vue/multi-word-component-names": "off",
    },
  },
];
