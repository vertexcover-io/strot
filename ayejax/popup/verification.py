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
            '[role="dialog"][aria-modal="true"]',
            '[aria-modal="true"]',
            '[aria-label*="notification" i]',
            '[aria-label*="alert" i]',
            '[aria-label*="popup" i]',
            '[aria-label*="overlay" i]',
            '[aria-label="Notification"]',
            '.modal',
            '.popup',
            '.overlay',
            '.cookie-banner',
            '.notification-banner',
            '[class*="popup"]',
            '[class*="modal"]',
            '[class*="overlay"]',
            '[class*="dialog"]',
            '[class*="notification"]',
            '[id*="popup"]',
            '[id*="modal"]',
            '[id*="notification"]'
        ]
        
        popup_found = False
        found_selectors = []
        for selector in popup_selectors:
            elements = await page.query_selector_all(selector)
            # Check if any popup elements are visible
            for element in elements:
                is_visible = await element.is_visible()
                if is_visible:
                    popup_found = True
                    found_selectors.append(selector)
                    if logger:
                        logger.info("popup-verification", method="dom", action="found_visible_popup", 
                                   selector=selector, element_visible=True)
                    break
            if popup_found:
                break
                
        if popup_found:
            if logger:
                logger.info("popup-verification", method="dom", result="popup_still_present", 
                           found_selectors=found_selectors, total_selectors_checked=len(popup_selectors))
            return False
            
        # Method 2: Screenshot comparison (if before_screenshot provided)
        if before_screenshot:
            try:
                # Clear routes before verification screenshot to prevent conflicts
                await page.unroute_all()
                
                # Short timeout to avoid hanging
                after_screenshot = await page.screenshot(type="png", timeout=5000, animations="disabled")
                
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
                
                // Enhanced notification detection
                const ariaLabelElements = document.querySelectorAll('[aria-label]');
                let notificationCount = 0;
                const notificationKeywords = ['notification', 'alert', 'popup', 'modal', 'overlay', 'dialog'];
                
                ariaLabelElements.forEach(el => {
                    const label = el.getAttribute('aria-label').toLowerCase();
                    if (notificationKeywords.some(keyword => label.includes(keyword))) {
                        const isVisible = el.offsetParent !== null || 
                                        window.getComputedStyle(el).display !== 'none' ||
                                        window.getComputedStyle(el).visibility !== 'hidden';
                        if (isVisible) notificationCount++;
                    }
                });
                indicators.push({type: 'aria_label_notifications', count: notificationCount});
                
                // Check for elements with notification-related roles
                const roleElements = document.querySelectorAll('[role="alert"], [role="alertdialog"], [role="dialog"]');
                let visibleRoleElements = 0;
                roleElements.forEach(el => {
                    const isVisible = el.offsetParent !== null || 
                                    window.getComputedStyle(el).display !== 'none' ||
                                    window.getComputedStyle(el).visibility !== 'hidden';
                    if (isVisible) visibleRoleElements++;
                });
                indicators.push({type: 'notification_roles', count: visibleRoleElements});
                
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
            elif indicator.get('type') == 'aria_label_notifications' and indicator.get('count', 0) > 0:
                suspicious_indicators += 2  # Higher weight for aria-label notifications
            elif indicator.get('type') == 'notification_roles' and indicator.get('count', 0) > 0:
                suspicious_indicators += 1
                
        if suspicious_indicators >= 2:
            if logger:
                logger.debug("popup-verification", method="indicators", result="popup_likely_present", 
                           indicators=popup_indicators)
            return False
            
        if logger:
            logger.info("popup-verification", result="popup_dismissed", 
                       indicators=popup_indicators, suspicious_indicators_count=suspicious_indicators,
                       selectors_checked=len(popup_selectors), method="comprehensive")
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
    if logger:
        logger.info("popup-verification", action="detect_popup_presence_start", page_url=page.url)
    
    # Use same verification logic but invert result
    dismissed = await verify_popup_dismissed(page, logger=logger)
    popup_present = not dismissed
    
    if logger:
        logger.info("popup-verification", action="detect_popup_presence_complete", 
                   popup_present=popup_present, dismissed_result=dismissed)
    
    return popup_present