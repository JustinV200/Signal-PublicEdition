"""screenshot(): returns only a path, masks secret fields, refuses while credentials are filled."""

import base64
from pathlib import Path

import pytest
from support.browser_helpers import ALLOWED_HOST, ref_for

from browser_tool.actions import (
    FILLED_CREDENTIALS_MESSAGE,
    ActionError,
    fill_login,
    navigate,
    screenshot,
    snapshot,
)

PNG_SIGNATURE = b"\x89PNG"


@pytest.mark.asyncio
async def test_screenshot_returns_a_path_and_refuses_after_fill(make_ctx, fixture_server, tmp_path):
    ctx = await make_ctx()
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/login.html"))
    path = Path(await screenshot(ctx))
    assert path.parent == tmp_path / "screenshots"
    assert path.read_bytes().startswith(PNG_SIGNATURE)

    await fill_login(ctx, "demo", False)
    with pytest.raises(ActionError) as refusal:
        await screenshot(ctx)
    assert str(refusal.value) == FILLED_CREDENTIALS_MESSAGE


# The share of a PNG's pixels in Playwright's mask colour (#FF00FF), decoded by the page.
MASKED_SHARE_JS = """async (base64) => {
  const image = new Image();
  image.src = 'data:image/png;base64,' + base64;
  await image.decode();
  const canvas = document.createElement('canvas');
  canvas.width = image.width;
  canvas.height = image.height;
  const context = canvas.getContext('2d');
  context.drawImage(image, 0, 0);
  const data = context.getImageData(0, 0, image.width, image.height).data;
  let masked = 0;
  for (let i = 0; i < data.length; i += 4) {
    if (data[i] > 240 && data[i + 1] < 15 && data[i + 2] > 240) masked++;
  }
  return masked / (data.length / 4);
}"""


@pytest.mark.asyncio
async def test_element_screenshots_mask_secret_fields_in_every_frame(make_ctx, fixture_server):
    ctx = await make_ctx()
    await navigate(ctx, fixture_server.url(ALLOWED_HOST, "/login.html"))
    text = await snapshot(ctx)
    page = await ctx.session.current_page()

    async def masked_share(label: str) -> float:
        png = Path(await screenshot(ctx, ref_for(text, label))).read_bytes()
        return await page.evaluate(MASKED_SHARE_JS, base64.b64encode(png).decode())

    assert await masked_share('textbox "Password"') > 0.9
    assert await masked_share('textbox "Frame password"') > 0.9  # inside the iframe
    assert await masked_share('searchbox "Search"') < 0.5  # a mask next to it may show at an edge
    assert Path(await screenshot(ctx, full_page=True)).read_bytes().startswith(PNG_SIGNATURE)
    with pytest.raises(ActionError, match="not both"):
        await screenshot(ctx, "e1", full_page=True)
