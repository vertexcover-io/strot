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
    
    def __init__(self, logger: logging.Logger, debug_session=None):
        self.logger = logger
        self.debug_session = debug_session
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
        # DETAILED ENTRY LOGGING
        self.logger.info("popup-dismissal", 
                        action="entry", 
                        analysis_has_popup_point=analysis.popup_element_point is not None,
                        analysis_popup_point=analysis.popup_element_point.model_dump() if analysis.popup_element_point else None,
                        analysis_popup_area=analysis.popup_area.model_dump() if analysis.popup_area else None,
                        analysis_background_point=analysis.background_overlay_point.model_dump() if analysis.background_overlay_point else None,
                        analysis_popup_type=analysis.popup_type,
                        page_url=page.url,
                        max_attempts=max_attempts)
                        
        # Execution flow tracking
        if self.debug_session:
            self.debug_session.log_execution_flow("PopupDismisser", "dismiss_popup_start", {
                "has_popup_data": self._has_popup_data(analysis),
                "popup_coordinates": analysis.popup_element_point.model_dump() if analysis.popup_element_point else None,
                "popup_type": analysis.popup_type,
                "max_attempts": max_attempts
            })
        
        dismissal_log = {
            "popup_detected": self._has_popup_data(analysis),
            "popup_type": analysis.popup_type,
            "attempts": [],
            "successful_strategy": None,
            "total_duration_ms": 0,
            "popup_dismissed": False,
            "analysis_data": {
                "popup_element_point": analysis.popup_element_point.model_dump() if analysis.popup_element_point else None,
                "popup_area": analysis.popup_area.model_dump() if analysis.popup_area else None,
                "background_overlay_point": analysis.background_overlay_point.model_dump() if analysis.background_overlay_point else None,
                "popup_type": analysis.popup_type
            }
        }
        
        self.logger.info("popup-dismissal", 
                        action="initialization", 
                        dismissal_log_created=True,
                        popup_detected=dismissal_log["popup_detected"])
        
        # Check if popup is actually present before attempting dismissal
        # BUT: Skip this check if LLM detected popup data - trust the LLM analysis
        has_llm_popup_data = self._has_popup_data(analysis)
        
        self.logger.info("popup-dismissal", action="checking_popup_presence", has_llm_popup_data=has_llm_popup_data)
        
        if has_llm_popup_data:
            self.logger.info("popup-dismissal", action="skipping_presence_check", reason="llm_detected_popup_data")
            popup_present = True  # Trust LLM analysis
        else:
            popup_present = await detect_popup_presence(page, self.logger)
            
        self.logger.info("popup-dismissal", 
                        action="popup_presence_check_complete", 
                        popup_present=popup_present,
                        llm_override=has_llm_popup_data)
        
        if not popup_present:
            dismissal_log["popup_dismissed"] = True
            dismissal_log["successful_strategy"] = "none_needed"
            self.logger.info("popup-dismissal", result="no_popup_present", dismissal_log=dismissal_log)
            
            if self.debug_session:
                self.debug_session.log_execution_flow("PopupDismisser", "no_popup_detected", {
                    "result": "early_exit_no_popup"
                })
            
            return dismissal_log
            
        # Clear any active routes that might interfere with screenshot
        self.logger.info("popup-dismissal", action="clearing_routes_before_screenshot", page_url=page.url)
        try:
            # Clear all routes to prevent conflicts
            await page.unroute_all()
            self.logger.info("popup-dismissal", action="routes_cleared")
        except Exception as e:
            self.logger.warning("popup-dismissal", action="route_clearing_failed", error=str(e))
        
        # Take before screenshot for verification - proceed immediately like domcontentloaded
        self.logger.info("popup-dismissal", action="taking_before_screenshot", page_url=page.url)
        try:
            self.logger.info("popup-dismissal", action="screenshot_call_start")
            # Very short timeout and proceed without waiting for fonts
            before_screenshot = await page.screenshot(type="png", timeout=3000, animations="disabled")
            self.logger.info("popup-dismissal", action="before_screenshot_success", screenshot_size=len(before_screenshot))
        except Exception as e:
            before_screenshot = None
            self.logger.error("popup-dismissal", action="before_screenshot_failed", error=str(e), exception_type=type(e).__name__)
            self.logger.info("popup-dismissal", action="continuing_without_screenshot", reason="screenshot_failed")
            
        self.logger.info("popup-dismissal", action="screenshot_phase_complete", has_screenshot=before_screenshot is not None)
            
        import time
        start_time = time.time()
        self.logger.info("popup-dismissal", action="starting_strategy_attempts", start_time=start_time, strategies_available=len(self.strategies), max_attempts=max_attempts)
        
        # Try each strategy in order
        self.logger.info("popup-dismissal", action="entering_strategy_loop", total_strategies=len(self.strategies), max_attempts=max_attempts)
        
        for strategy_index, (strategy_name, strategy) in enumerate(self.strategies[:max_attempts]):
            attempt_start = time.time()
            
            self.logger.info("popup-dismissal", 
                            strategy=strategy_name, 
                            action="attempting",
                            strategy_index=strategy_index,
                            strategy_class=strategy.__class__.__name__,
                            attempt_start=attempt_start,
                            loop_iteration=f"{strategy_index + 1}/{max_attempts}")
            
            attempt_result = {
                "strategy": strategy_name,
                "attempted": True,
                "success": False,
                "duration_ms": 0,
                "error": None,
                "strategy_index": strategy_index,
                "strategy_class": strategy.__class__.__name__
            }
            
            try:
                # Attempt the strategy
                self.logger.info("popup-dismissal", 
                                strategy=strategy_name, 
                                action="calling_strategy_attempt", 
                                analysis_popup_point=analysis.popup_element_point.model_dump() if analysis.popup_element_point else None,
                                analysis_background_point=analysis.background_overlay_point.model_dump() if analysis.background_overlay_point else None)
                
                self.logger.info("popup-dismissal", strategy=strategy_name, action="about_to_call_strategy_attempt")
                strategy_executed = await strategy.attempt(page, analysis, self.logger)
                self.logger.info("popup-dismissal", strategy=strategy_name, action="strategy_attempt_returned", strategy_executed=strategy_executed)
                
                self.logger.info("popup-dismissal", 
                                strategy=strategy_name, 
                                action="strategy_attempt_complete", 
                                strategy_executed=strategy_executed)
                                
                if self.debug_session:
                    self.debug_session.log_execution_flow("PopupDismisser", f"strategy_{strategy_name}_complete", {
                        "strategy_executed": strategy_executed,
                        "strategy_class": strategy.__class__.__name__
                    })
                
                if strategy_executed:
                    self.logger.info("popup-dismissal", strategy=strategy_name, action="verifying_dismissal")
                    
                    # Verify if popup was actually dismissed
                    popup_dismissed = await verify_popup_dismissed(
                        page, 
                        before_screenshot, 
                        self.logger
                    )
                    
                    self.logger.info("popup-dismissal", 
                                    strategy=strategy_name, 
                                    action="verification_complete", 
                                    popup_dismissed=popup_dismissed)
                    
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
                self.logger.error("popup-dismissal", 
                                strategy=strategy_name, 
                                action="strategy_exception", 
                                error=str(e),
                                exception_type=type(e).__name__,
                                strategy_index=strategy_index,
                                page_url=page.url)
                
            # Calculate duration
            attempt_end = time.time()
            attempt_result["duration_ms"] = (attempt_end - attempt_start) * 1000
            
            self.logger.info("popup-dismissal", 
                            strategy=strategy_name,
                            action="attempt_complete",
                            duration_ms=attempt_result["duration_ms"],
                            success=attempt_result["success"],
                            attempted=attempt_result["attempted"])
            
            dismissal_log["attempts"].append(attempt_result)
            
            # If successful, break out of loop
            if attempt_result["success"]:
                self.logger.info("popup-dismissal", action="breaking_loop_success", successful_strategy=strategy_name)
                break
            else:
                self.logger.info("popup-dismissal", action="continuing_to_next_strategy", current_strategy=strategy_name, next_strategy_index=strategy_index + 1)
                
        # Calculate total duration
        end_time = time.time()
        dismissal_log["total_duration_ms"] = (end_time - start_time) * 1000
        
        self.logger.info("popup-dismissal", action="strategy_loop_complete", 
                        total_attempts=len(dismissal_log["attempts"]),
                        popup_dismissed_so_far=dismissal_log["popup_dismissed"])
        
        # Final verification
        if not dismissal_log["popup_dismissed"]:
            self.logger.info("popup-dismissal", action="running_final_verification")
            final_check = await verify_popup_dismissed(page, before_screenshot, self.logger)
            self.logger.info("popup-dismissal", action="final_verification_complete", final_check=final_check)
            dismissal_log["popup_dismissed"] = final_check
            if final_check and not dismissal_log["successful_strategy"]:
                dismissal_log["successful_strategy"] = "delayed_effect"
                self.logger.info("popup-dismissal", action="delayed_effect_detected")
        else:
            self.logger.info("popup-dismissal", action="skipping_final_verification", reason="already_dismissed")
                
        self.logger.info("popup-dismissal", 
                        result="completed",
                        success=dismissal_log["popup_dismissed"],
                        strategy=dismissal_log["successful_strategy"],
                        attempts=len(dismissal_log["attempts"]),
                        total_duration_ms=dismissal_log["total_duration_ms"])
        
        # Final execution flow tracking
        if self.debug_session:
            self.debug_session.log_execution_flow("PopupDismisser", "dismiss_popup_complete", {
                "success": dismissal_log["popup_dismissed"],
                "successful_strategy": dismissal_log["successful_strategy"],
                "total_attempts": len(dismissal_log["attempts"]),
                "total_duration_ms": dismissal_log["total_duration_ms"]
            })
        
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