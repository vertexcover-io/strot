"""Popup verification utilities."""

import logging
from typing import Optional
from playwright.async_api import Page


async def verify_popup_dismissed(
    page: Page, 
    before_screenshot: Optional[bytes] = None,
    logger: Optional[logging.Logger] = None
) -> bool:
    """Verify if popup has been successfully dismissed.
    
    Args:
        page: Playwright page instance
        before_screenshot: Screenshot before dismissal attempt (optional)
        logger: Logger instance (optional)
        
    Returns:
        True if popup appears to be dismissed, False otherwise
    """
    try:
        # Method 1: DOM-based detection
        popup_selectors = [
            '[role="dialog"]',
            '[role="alertdialog"]', 
            '.modal',
            '.popup',
            '.overlay',
            '.cookie-banner',
            '.notification-banner',
            '[class*="popup"]',
            '[class*="modal"]',
            '[class*="overlay"]',
            '[class*="dialog"]',
            '[id*="popup"]',
            '[id*="modal"]'
        ]
        
        popup_found = False
        for selector in popup_selectors:
            elements = await page.query_selector_all(selector)
            # Check if any popup elements are visible
            for element in elements:
                is_visible = await element.is_visible()
                if is_visible:
                    popup_found = True
                    break
            if popup_found:
                break
                
        if popup_found:
            if logger:
                logger.debug("popup-verification", method="dom", result="popup_still_present")
            return False
            
        # Method 2: Screenshot comparison (if before_screenshot provided)
        if before_screenshot:
            try:
                after_screenshot = await page.screenshot(type="png")
                
                # Simple comparison - if screenshots are identical, popup likely still there
                if before_screenshot == after_screenshot:
                    if logger:
                        logger.debug("popup-verification", method="screenshot", result="no_change")
                    return False
                    
                # If different, popup likely dismissed
                if logger:
                    logger.debug("popup-verification", method="screenshot", result="changed")
                    
            except Exception as e:
                if logger:
                    logger.warning("popup-verification", method="screenshot", error=str(e))
                    
        # Method 3: Check for common popup-indicating attributes
        popup_indicators = await page.evaluate("""
            () => {
                // Check for modal/popup indicating styles
                const indicators = [];
                
                // Check for backdrop/overlay elements
                const backdrops = document.querySelectorAll('[class*="backdrop"], [class*="overlay"], [style*="position: fixed"]');
                indicators.push({type: 'backdrop', count: backdrops.length});
                
                // Check for z-index indicating popup layers
                const highZElements = Array.from(document.querySelectorAll('*')).filter(el => {
                    const zIndex = window.getComputedStyle(el).zIndex;
                    return zIndex && parseInt(zIndex) > 1000;
                });
                indicators.push({type: 'high_z_index', count: highZElements.length});
                
                // Check body scroll lock (common popup behavior)
                const bodyOverflow = window.getComputedStyle(document.body).overflow;
                indicators.push({type: 'body_scroll_locked', value: bodyOverflow === 'hidden'});
                
                return indicators;
            }
        """)
        
        # Analyze indicators
        suspicious_indicators = 0
        for indicator in popup_indicators:
            if indicator.get('type') == 'backdrop' and indicator.get('count', 0) > 0:
                suspicious_indicators += 1
            elif indicator.get('type') == 'high_z_index' and indicator.get('count', 0) > 3:
                suspicious_indicators += 1
            elif indicator.get('type') == 'body_scroll_locked' and indicator.get('value'):
                suspicious_indicators += 1
                
        if suspicious_indicators >= 2:
            if logger:
                logger.debug("popup-verification", method="indicators", result="popup_likely_present", 
                           indicators=popup_indicators)
            return False
            
        if logger:
            logger.info("popup-verification", result="popup_dismissed", 
                       indicators=popup_indicators)
        return True
        
    except Exception as e:
        if logger:
            logger.error("popup-verification", error=str(e))
        # Default to assuming popup is dismissed on error
        return True


async def detect_popup_presence(page: Page, logger: Optional[logging.Logger] = None) -> bool:
    """Detect if any popup is currently present on the page.
    
    Args:
        page: Playwright page instance
        logger: Logger instance (optional)
        
    Returns:
        True if popup detected, False otherwise
    """
    # Use same verification logic but invert result
    dismissed = await verify_popup_dismissed(page, logger=logger)
    return not dismissed