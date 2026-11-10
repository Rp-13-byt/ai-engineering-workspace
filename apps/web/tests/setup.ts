import "@testing-library/jest-dom/vitest";
import React from "react";

// @ts-expect-error - vitest environment global React injection
globalThis.React = React;
