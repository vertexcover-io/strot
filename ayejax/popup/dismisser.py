"""Main popup dismisser with cascading strategies."""

import logging
from typing import Optional, Dict, Any, List
from playwright.async_api import Page

from ayejax.types import AnalysisResult
from .strategies import (
    ExplicitCloseStrategy,
    ClickOutsideStrategy, 
    EscapeKeyStrategy,
    CalculatedOutsideStrategy
)
from .verification import verify_popup_dismissed, detect_popup_presence


class PopupDismisser:
    """Main popup dismissal coordinator with multiple strategies."""
    
    def __init__(self, logger: logging.Logger):
        self.logger = logger
        self.strategies = [
            ("explicit_close", ExplicitCloseStrategy()),
            ("click_outside", ClickOutsideStrategy()),
            ("escape_key", EscapeKeyStrategy()),
            ("calculated_outside", CalculatedOutsideStrategy())
        ]
        
    async def dismiss_popup(
        self, 
        page: Page, 
        analysis: AnalysisResult,
        max_attempts: int = 4
    ) -> Dict[str, Any]:
        """Attempt to dismiss popup using cascading strategies.
        
        Args:
            page: Playwright page instance
            analysis: LLM analysis result containing popup information
            max_attempts: Maximum number of strategies to attempt
            
        Returns:
            Dictionary containing dismissal attempt results and metadata
        """
        dismissal_log = {
            "popup_detected": self._has_popup_data(analysis),
            "popup_type": analysis.popup_type,
            "attempts": [],
            "successful_strategy": None,
            "total_duration_ms": 0,
            "popup_dismissed": False
        }
        
        # Check if popup is actually present before attempting dismissal
        popup_present = await detect_popup_presence(page, self.logger)
        if not popup_present:
            dismissal_log["popup_dismissed"] = True
            dismissal_log["successful_strategy"] = "none_needed"
            self.logger.info("popup-dismissal", result="no_popup_present")
            return dismissal_log
            
        # Take before screenshot for verification
        try:
            before_screenshot = await page.screenshot(type="png")
        except Exception:
            before_screenshot = None
            
        start_time = page.clock.current_time if hasattr(page, 'clock') else 0
        
        # Try each strategy in order
        for strategy_name, strategy in self.strategies[:max_attempts]:
            attempt_start = page.clock.current_time if hasattr(page, 'clock') else 0
            
            self.logger.info("popup-dismissal", strategy=strategy_name, action="attempting")
            
            attempt_result = {
                "strategy": strategy_name,
                "attempted": True,
                "success": False,
                "duration_ms": 0,
                "error": None
            }
            
            try:
                # Attempt the strategy
                strategy_executed = await strategy.attempt(page, analysis, self.logger)
                
                if strategy_executed:
                    # Verify if popup was actually dismissed
                    popup_dismissed = await verify_popup_dismissed(
                        page, 
                        before_screenshot, 
                        self.logger
                    )
                    
                    attempt_result["success"] = popup_dismissed
                    
                    if popup_dismissed:
                        dismissal_log["successful_strategy"] = strategy_name
                        dismissal_log["popup_dismissed"] = True
                        self.logger.info("popup-dismissal", strategy=strategy_name, result="success")
                        break
                    else:
                        self.logger.warning("popup-dismissal", strategy=strategy_name, result="executed_but_popup_remains")
                else:
                    self.logger.debug("popup-dismissal", strategy=strategy_name, result="strategy_not_applicable")
                    attempt_result["attempted"] = False
                    
            except Exception as e:
                attempt_result["error"] = str(e)
                self.logger.error("popup-dismissal", strategy=strategy_name, error=str(e))
                
            # Calculate duration
            attempt_end = page.clock.current_time if hasattr(page, 'clock') else 0
            attempt_result["duration_ms"] = attempt_end - attempt_start
            
            dismissal_log["attempts"].append(attempt_result)
            
            # If successful, break out of loop
            if attempt_result["success"]:
                break
                
        # Calculate total duration
        end_time = page.clock.current_time if hasattr(page, 'clock') else 0
        dismissal_log["total_duration_ms"] = end_time - start_time
        
        # Final verification
        if not dismissal_log["popup_dismissed"]:
            final_check = await verify_popup_dismissed(page, before_screenshot, self.logger)
            dismissal_log["popup_dismissed"] = final_check
            if final_check and not dismissal_log["successful_strategy"]:
                dismissal_log["successful_strategy"] = "delayed_effect"
                
        self.logger.info("popup-dismissal", 
                        result="completed",
                        success=dismissal_log["popup_dismissed"],
                        strategy=dismissal_log["successful_strategy"],
                        attempts=len(dismissal_log["attempts"]))
        
        return dismissal_log
        
    def _has_popup_data(self, analysis: AnalysisResult) -> bool:
        """Check if analysis contains any popup-related data."""
        return any([
            analysis.popup_element_point is not None,
            analysis.popup_area is not None,
            analysis.background_overlay_point is not None,
            analysis.popup_type is not None
        ])
        
    async def quick_dismiss(self, page: Page, analysis: AnalysisResult) -> bool:
        """Quick popup dismissal attempt using only the most likely successful strategy.
        
        Args:
            page: Playwright page instance
            analysis: LLM analysis result
            
        Returns:
            True if popup was dismissed, False otherwise
        """
        result = await self.dismiss_popup(page, analysis, max_attempts=2)
        return result["popup_dismissed"]