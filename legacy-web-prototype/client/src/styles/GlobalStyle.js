import { createGlobalStyle } from "styled-components";

export const GlobalStyle = createGlobalStyle`
  :root {
    color-scheme: dark;
    --bg: #07111f;
    --bg-elevated: rgba(8, 20, 36, 0.88);
    --surface: rgba(16, 30, 51, 0.92);
    --surface-2: rgba(22, 40, 66, 0.94);
    --border: rgba(124, 154, 193, 0.16);
    --text: #edf3ff;
    --muted: #93a6c7;
    --positive: #51d79b;
    --negative: #ff7272;
    --accent: #6bbcff;
    --accent-2: #16e1c4;
    --shadow: 0 24px 70px rgba(0, 0, 0, 0.35);
  }

  * {
    box-sizing: border-box;
  }

  html, body, #root {
    margin: 0;
    min-height: 100%;
    font-family: "Manrope", sans-serif;
    background:
      radial-gradient(circle at top left, rgba(30, 132, 255, 0.16), transparent 32%),
      radial-gradient(circle at bottom right, rgba(22, 225, 196, 0.12), transparent 28%),
      linear-gradient(180deg, #09111d 0%, #050a13 100%);
    color: var(--text);
  }

  body {
    min-height: 100vh;
  }

  a {
    color: inherit;
    text-decoration: none;
  }

  button,
  input {
    font: inherit;
  }
`;
