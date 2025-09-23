from pathlib import Path
from typing import Any, Literal

from patchright.async_api import Page

from strot.schema.point import Point

__all__ = ("Plugin",)


class Plugin:
    """Playwright page plugin for Strot"""

    def __init__(self, page: Page) -> None:
        self._page = page

    async def evaluate(self, expr: str, args=None) -> Any:
        if not await self._page.evaluate(
            "() => window.strotPluginInjected === true",
            isolated_context=False,
        ):
            _ = await self._page.add_script_tag(path=Path(__file__).parent / "inject.js")

        await self._page.wait_for_load_state("domcontentloaded")
        result = await self._page.evaluate(expr, args, isolated_context=False)
        await self._page.wait_for_load_state("domcontentloaded")
        return result

    async def get_selectors_in_view(self) -> set[str]:
        selectors = await self.evaluate(
            """
            () => {
                const elements = window.getElementsInView(window.getElementsInDOM());
                return elements.map(element => window.generateCSSSelector(element));
            }
            """
        )
        return set(selectors)

    async def click_at_point(self, point: Point) -> bool:
        before_selectors = await self.get_selectors_in_view()
        await self._page.mouse.move(point.x, point.y)
        await self._page.mouse.click(point.x, point.y)
        await self._page.wait_for_timeout(2000)
        after_selectors = await self.get_selectors_in_view()

        added = after_selectors - before_selectors
        removed = before_selectors - after_selectors
        return len(added) > 0 or len(removed) > 0

    async def click_element(self, selector: str) -> bool:
        before_selectors = await self.get_selectors_in_view()
        try:
            await self._page.locator(selector).click(timeout=5000)
        except Exception:
            return False
        await self._page.wait_for_timeout(2000)
        after_selectors = await self.get_selectors_in_view()

        added = after_selectors - before_selectors
        removed = before_selectors - after_selectors
        return len(added) > 0 or len(removed) > 0

    async def scroll_to_next_view(self, direction: Literal["up", "down"] = "down") -> bool:
        return await self.evaluate("([direction]) => window.scrollToNextView({ direction })", [direction])

    async def find_common_parent(self, text_sections: list[str]) -> str | None:
        return await self.evaluate(
            """
            ([sections]) => {
                const parent = window.findCommonParent(sections);
                return parent ? window.generateCSSSelector(parent) : null;
            }
            """,
            [text_sections],
        )

    async def get_last_similar_children_or_sibling(
        self,
        selector: str,
        threshold: float = 0.95,
        is_outside_viewport: bool = True,
        is_visible: bool = True,
    ) -> str | None:
        return await self.evaluate(
            """
            ([selector, threshold, isOutsideViewport, isVisible]) => {
                const container = document.querySelector(selector);
                if (!container) {
                    return null;
                }

                const element = window.getLastSimilarChildrenOrSibling(container, {threshold, isOutsideViewport, isVisible});
                return element ? window.generateCSSSelector(element) : null;
            }
            """,
            [selector, threshold, is_outside_viewport, is_visible],
        )

    async def scroll_to_element(self, selector: str) -> None:
        await self._page.locator(selector).scroll_into_view_if_needed()

    async def take_screenshot(self, type: Literal["png", "jpeg"] = "png") -> bytes:
        return await self._page.screenshot(type=type)
