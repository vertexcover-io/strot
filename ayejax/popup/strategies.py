"""Individual popup dismissal strategies."""

import logging
from typing import Protocol, Optional
from playwright.async_api import Page

from ayejax.types import AnalysisResult, Point


class DismissalStrategy(Protocol):
    """Protocol for popup dismissal strategies."""
    
    async def attempt(self, page: Page, analysis: AnalysisResult, logger: logging.Logger) -> bool:
        """Attempt to dismiss popup using this strategy.
        
        Returns:
            True if popup was successfully dismissed, False otherwise.
        """
        ...


class ExplicitCloseStrategy:
    """Strategy 1: Click explicit close button identified by LLM."""
    
    async def attempt(self, page: Page, analysis: AnalysisResult, logger: logging.Logger) -> bool:
        if not analysis.popup_element_point:
            logger.debug("popup-dismissal", strategy="explicit_close", result="no_close_button")
            return False
            
        try:
            await page.mouse.click(
                analysis.popup_element_point.x, 
                analysis.popup_element_point.y
            )
            await page.wait_for_timeout(2000)
            logger.info("popup-dismissal", strategy="explicit_close", result="attempted", 
                       coordinates={"x": analysis.popup_element_point.x, "y": analysis.popup_element_point.y})
            return True
        except Exception as e:
            logger.error("popup-dismissal", strategy="explicit_close", result="error", error=str(e))
            return False


class ClickOutsideStrategy:
    """Strategy 2: Click on background area outside popup."""
    
    async def attempt(self, page: Page, analysis: AnalysisResult, logger: logging.Logger) -> bool:
        if not analysis.background_overlay_point:
            logger.debug("popup-dismissal", strategy="click_outside", result="no_background_point")
            return False
            
        try:
            await page.mouse.click(
                analysis.background_overlay_point.x,
                analysis.background_overlay_point.y
            )
            await page.wait_for_timeout(2000)
            logger.info("popup-dismissal", strategy="click_outside", result="attempted",
                       coordinates={"x": analysis.background_overlay_point.x, "y": analysis.background_overlay_point.y})
            return True
        except Exception as e:
            logger.error("popup-dismissal", strategy="click_outside", result="error", error=str(e))
            return False


class EscapeKeyStrategy:
    """Strategy 3: Press ESC key to dismiss popup."""
    
    async def attempt(self, page: Page, analysis: AnalysisResult, logger: logging.Logger) -> bool:
        try:
            await page.keyboard.press('Escape')
            await page.wait_for_timeout(2000)
            logger.info("popup-dismissal", strategy="escape_key", result="attempted")
            return True
        except Exception as e:
            logger.error("popup-dismissal", strategy="escape_key", result="error", error=str(e))
            return False


class CalculatedOutsideStrategy:
    """Strategy 4: Calculate safe areas outside popup boundaries."""
    
    def _calculate_safe_click_areas(self, popup_area, viewport_width=1920, viewport_height=1080) -> list[Point]:
        """Calculate safe areas outside popup for clicking."""
        safe_points = []
        
        # Top area (above popup)
        if popup_area.y > 50:
            safe_points.append(Point(x=viewport_width/2, y=popup_area.y/2))
            
        # Bottom area (below popup)
        bottom_y = popup_area.y + popup_area.height
        if bottom_y < viewport_height - 50:
            safe_points.append(Point(x=viewport_width/2, y=bottom_y + (viewport_height - bottom_y)/2))
            
        # Left area (left of popup)
        if popup_area.x > 50:
            safe_points.append(Point(x=popup_area.x/2, y=viewport_height/2))
            
        # Right area (right of popup)
        right_x = popup_area.x + popup_area.width
        if right_x < viewport_width - 50:
            safe_points.append(Point(x=right_x + (viewport_width - right_x)/2, y=viewport_height/2))
            
        return safe_points
    
    async def attempt(self, page: Page, analysis: AnalysisResult, logger: logging.Logger) -> bool:
        if not analysis.popup_area:
            logger.debug("popup-dismissal", strategy="calculated_outside", result="no_popup_area")
            return False
            
        try:
            viewport = await page.evaluate("() => ({width: window.innerWidth, height: window.innerHeight})")
            safe_points = self._calculate_safe_click_areas(
                analysis.popup_area, 
                viewport['width'], 
                viewport['height']
            )
            
            for point in safe_points:
                await page.mouse.click(point.x, point.y)
                await page.wait_for_timeout(1000)
                logger.info("popup-dismissal", strategy="calculated_outside", result="attempted", 
                           coordinates={"x": point.x, "y": point.y})
                # Note: Verification will be done by caller
                return True
                
        except Exception as e:
            logger.error("popup-dismissal", strategy="calculated_outside", result="error", error=str(e))
            return False
            
        return False