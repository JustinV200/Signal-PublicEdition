// A quiet reason disables the button and says why in its tooltip only, so a
// reason coming and going (Send's empty draft) never shifts the layout.
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { Button } from "../../src/ui";

const REASON = "type a message first";

describe("Button quietReason", () => {
  it("disables with the reason as tooltip and no caption", () => {
    const html = renderToStaticMarkup(
      <Button onClick={() => {}} quietReason={REASON}>
        Send
      </Button>,
    );
    expect(html).toContain(`title="${REASON}"`);
    expect(html).toContain("disabled");
    // Once in the title, never again as a caption.
    expect(html.split(REASON)).toHaveLength(2);
  });
});
