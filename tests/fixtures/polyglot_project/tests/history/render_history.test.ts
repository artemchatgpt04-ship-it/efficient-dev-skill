import { renderHistory } from "../../src/history/render_history";

if (renderHistory([1, 2]) !== "1, 2") {
  throw new Error("unexpected history output");
}
