from pathlib import Path
from typing import Literal

from patchright.async_api import Page

from strot.analyzer.schema import Point
from strot.analyzer.utils import text_match_ratio

__all__ = ("Plugin",)


class Plugin:
    """Playwright page plugin for Strot"""

    def __init__(self, page: Page) -> None:
        self._page = page

    async def evaluate(self, expr: str, args=None) -> bool:
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

    async def scroll_to_next_view(self, direction: Literal["up", "down"] = "down") -> bool:
        return await self.evaluate("([direction]) => window.scrollToNextView({ direction })", [direction])

    async def get_last_similar_element(self, text_sections: list[str]) -> str | None:
        texts_in_view_to_last_sibling_selectors: dict[str, str] = await self.evaluate(
            """
            () => {
                const textsInViewToLastSiblingSelector = {};
                const mapping = window.mapLastVisibleSiblings(1.25);
                mapping.forEach((lastSiblingElement, elementInView) => {
                    textsInViewToLastSiblingSelector[elementInView.textContent.trim()] = window.generateCSSSelector(lastSiblingElement);
                });
                return textsInViewToLastSiblingSelector;
            }
            """
        )

        # Sort texts by length (longer first) to prioritize longer matching texts
        for text_in_view, selector in sorted(
            texts_in_view_to_last_sibling_selectors.items(),
            key=lambda x: len(x[0]),
            reverse=True,
        ):
            best_match_ratio = 0.0
            for section in sorted(text_sections, key=len, reverse=True):
                match_ratio = text_match_ratio([section], text_in_view)

                if match_ratio > best_match_ratio:
                    best_match_ratio = match_ratio

            if best_match_ratio:
                return selector

    async def scroll_to_element(self, selector: str) -> None:
        await self._page.locator(selector).scroll_into_view_if_needed()
