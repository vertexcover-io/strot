from pathlib import Path
from typing import Any, Literal

from patchright.async_api import Page

from strot.analyzer.schema import Point
from strot.analyzer.utils import text_match_ratio

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

    async def scroll_to_next_view(self, direction: Literal["up", "down"] = "down") -> bool:
        return await self.evaluate("([direction]) => window.scrollToNextView({ direction })", [direction])

    async def get_parent_container(self, text_sections: list[str]) -> str | None:
        containers: list[dict[str, Any]] = await self.evaluate(
            "([sections]) => window.getContainersWithTextSections(sections)", [text_sections]
        )

        if not containers:
            return None

        target_length = len(" ".join(text_sections))
        for container in containers:
            container["match_ratio"] = text_match_ratio(text_sections, container["text"])
            container["text_length"] = len(container["text"])
            container["extra_text_ratio"] = (
                (len(container["text"]) - target_length) / target_length if target_length > 0 else 0
            )

        # Sort by match ratio (descending), then by extra text ratio (ascending - less extra text is better)
        # Then by text length (descending - larger containers preferred if other factors are similar)
        containers.sort(key=lambda x: (-x["match_ratio"], x["extra_text_ratio"], -x["text_length"]))

        if (best_container := containers[0]) and best_container["match_ratio"] > 0.5:
            return best_container["selector"]

    async def get_last_visible_child(self, parent_container_selector: str) -> str | None:
        return await self.evaluate(
            """
            ([selector]) => {
                const parentContainer = document.querySelector(selector);
                if (!parentContainer) {
                    return null;
                }

                return window.getLastVisibleChild(parentContainer);
            }
            """,
            [parent_container_selector],
        )

    async def scroll_to_element(self, selector: str) -> None:
        await self._page.locator(selector).scroll_into_view_if_needed()

    async def take_screenshot(self, type: Literal["png", "jpeg"] = "png") -> bytes:
        return await self._page.screenshot(type=type)
