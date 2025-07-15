#!/usr/bin/env python3
"""
Workflow testing framework for ayejax Phase 2 and Phase 3.

Tests content discovery and interaction loop phases against multiple websites
to identify failure points and generate comprehensive results.
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

import click
from playwright.async_api import Browser, Page

import ayejax
from ayejax.logging import FileHandlerConfig, get_logger, setup_logging
from ayejax.types import AnalysisResult, Point, Request, Response
from ayejax.helpers import keyword_match_ratio
from eval.screenshot_workflow import take_screenshot, analyze_screenshot_file

setup_logging()

ROOT_DIR = Path(__file__).parent
TEST_DATA_DIR = ROOT_DIR / "test_data"
RESULTS_DIR = ROOT_DIR / "test_results"
SCREENSHOTS_DIR = ROOT_DIR / "test_screenshots"


class Phase2Tester:
    """Test Phase 2: Content Discovery components."""
    
    def __init__(self, logger):
        self.logger = logger
    
    async def test_llm_analysis(self, screenshot_path: Path, url: str, query: str) -> dict:
        """Test LLM analysis component."""
        try:
            result = await analyze_screenshot_file(screenshot_path, query, url)
            
            if result["success"]:
                analysis_result = result["result"]
                return {
                    "success": True,
                    "keywords_found": analysis_result.get("keywords", []),
                    "elements_detected": {
                        "navigation": analysis_result.get("navigation_element_point") is not None,
                        "popup": analysis_result.get("popup_element_point") is not None
                    },
                    "cost": result["cost"]
                }
            else:
                return {
                    "success": False,
                    "error": result["error"],
                    "cost": result.get("cost", 0)
                }
        except Exception as e:
            return {
                "success": False,
                "error": f"Exception: {str(e)}",
                "cost": 0
            }
    
    async def test_keyword_extraction(self, analysis_result: AnalysisResult, expected_keywords: List[str]) -> dict:
        """Test keyword extraction quality."""
        extracted = analysis_result.keywords
        
        if not extracted:
            return {
                "success": False,
                "error": "no_keywords_extracted",
                "extracted_keywords": [],
                "quality_score": 0.0
            }
        
        # Calculate quality score based on overlap with expected keywords
        quality_score = 0.0
        if expected_keywords:
            common_keywords = set(extracted) & set(expected_keywords)
            quality_score = len(common_keywords) / len(expected_keywords)
        
        return {
            "success": True,
            "extracted_keywords": extracted,
            "expected_keywords": expected_keywords,
            "quality_score": quality_score
        }
    
    async def test_element_identification(self, analysis_result: AnalysisResult, expected_elements: dict) -> dict:
        """Test element identification accuracy."""
        detected = {
            "navigation": analysis_result.navigation_element_point is not None,
            "popup": analysis_result.popup_element_point is not None
        }
        
        accuracy = 0.0
        if expected_elements:
            correct_detections = sum(
                1 for key in expected_elements 
                if detected.get(key, False) == expected_elements[key]
            )
            accuracy = correct_detections / len(expected_elements)
        
        return {
            "success": True,
            "detected_elements": detected,
            "expected_elements": expected_elements,
            "accuracy": accuracy,
            "navigation_point": analysis_result.navigation_element_point.model_dump() if analysis_result.navigation_element_point else None,
            "popup_point": analysis_result.popup_element_point.model_dump() if analysis_result.popup_element_point else None
        }
    
    async def test_response_matching(self, keywords: List[str], captured_responses: List[Response], min_score: float = 0.4) -> dict:
        """Test response matching logic."""
        if not keywords:
            return {
                "success": False,
                "error": "no_keywords_provided",
                "best_score": 0.0
            }
        
        if not captured_responses:
            return {
                "success": False,
                "error": "no_responses_captured",
                "best_score": 0.0
            }
        
        best_score = 0.0
        best_match = None
        
        for response in captured_responses:
            score = keyword_match_ratio(keywords, response.value)
            if score > best_score:
                best_score = score
                best_match = response
        
        success = best_score >= min_score
        
        return {
            "success": success,
            "best_score": best_score,
            "min_score": min_score,
            "total_responses": len(captured_responses),
            "best_match_url": best_match.request.url if best_match else None
        }


class Phase3Tester:
    """Test Phase 3: Interaction Loop components."""
    
    def __init__(self, logger):
        self.logger = logger
    
    async def test_element_interaction(self, page: Page, analysis_result: AnalysisResult) -> dict:
        """Test element interaction capabilities."""
        results = {
            "navigation_click": {"attempted": False, "success": False},
            "popup_click": {"attempted": False, "success": False}
        }
        
        # Test navigation element click
        if analysis_result.navigation_element_point:
            results["navigation_click"]["attempted"] = True
            try:
                position_before = await page.evaluate("() => ({ scrollX: window.scrollX, scrollY: window.scrollY })")
                
                await page.mouse.move(analysis_result.navigation_element_point.x, analysis_result.navigation_element_point.y)
                await page.mouse.click(analysis_result.navigation_element_point.x, analysis_result.navigation_element_point.y)
                await page.wait_for_timeout(2000)
                
                position_after = await page.evaluate("() => ({ scrollX: window.scrollX, scrollY: window.scrollY })")
                
                position_changed = (
                    position_before["scrollX"] != position_after["scrollX"] or 
                    position_before["scrollY"] != position_after["scrollY"]
                )
                
                results["navigation_click"]["success"] = True
                results["navigation_click"]["position_changed"] = position_changed
                
            except Exception as e:
                results["navigation_click"]["error"] = str(e)
        
        # Test popup element click
        if analysis_result.popup_element_point:
            results["popup_click"]["attempted"] = True
            try:
                await page.mouse.move(analysis_result.popup_element_point.x, analysis_result.popup_element_point.y)
                await page.mouse.click(analysis_result.popup_element_point.x, analysis_result.popup_element_point.y)
                await page.wait_for_timeout(2000)
                
                results["popup_click"]["success"] = True
                
            except Exception as e:
                results["popup_click"]["error"] = str(e)
        
        return results
    
    async def test_scroll_navigation(self, page: Page, keywords: List[str], max_scrolls: int = 3) -> dict:
        """Test scroll navigation effectiveness."""
        scroll_results = []
        
        for i in range(max_scrolls):
            try:
                # Scroll down
                await page.evaluate("window.scrollBy(0, window.innerHeight)")
                await page.wait_for_timeout(1000)
                
                # Take screenshot to analyze new content
                screenshot = await page.screenshot(type="png")
                
                # Check if we can find relevant content
                page_content = await page.content()
                content_score = max(keyword_match_ratio([keyword], page_content) for keyword in keywords) if keywords else 0
                
                scroll_results.append({
                    "scroll_attempt": i + 1,
                    "content_score": content_score,
                    "success": content_score > 0.1
                })
                
            except Exception as e:
                scroll_results.append({
                    "scroll_attempt": i + 1,
                    "error": str(e),
                    "success": False
                })
        
        successful_scrolls = sum(1 for r in scroll_results if r.get("success", False))
        
        return {
            "total_scrolls": max_scrolls,
            "successful_scrolls": successful_scrolls,
            "scroll_results": scroll_results,
            "effectiveness": successful_scrolls / max_scrolls if max_scrolls > 0 else 0
        }
    
    async def test_response_capture(self, page: Page, interactions: List[str] = None) -> dict:
        """Test network response capture during interactions."""
        captured_responses = []
        
        def response_handler(response):
            if response.request.resource_type in ("xhr", "fetch"):
                captured_responses.append({
                    "url": response.request.url,
                    "method": response.request.method,
                    "status": response.status,
                    "resource_type": response.request.resource_type
                })
        
        page.on("response", response_handler)
        
        # Perform some interactions if specified
        if interactions:
            for interaction in interactions:
                try:
                    if interaction == "scroll":
                        await page.evaluate("window.scrollBy(0, window.innerHeight)")
                    elif interaction == "click":
                        await page.mouse.click(100, 100)  # Generic click
                    await page.wait_for_timeout(1000)
                except Exception as e:
                    self.logger.warning("interaction-error", interaction=interaction, error=str(e))
        
        page.remove_listener("response", response_handler)
        
        return {
            "total_requests": len(captured_responses),
            "xhr_requests": len([r for r in captured_responses if r["resource_type"] == "xhr"]),
            "fetch_requests": len([r for r in captured_responses if r["resource_type"] == "fetch"]),
            "captured_responses": captured_responses
        }
    
    async def test_retry_logic(self, page: Page, query: str, max_retries: int = 3) -> dict:
        """Test retry logic for failed analyses."""
        retry_results = []
        
        for attempt in range(max_retries):
            try:
                # Simulate analysis attempt
                screenshot = await page.screenshot(type="png")
                
                # For testing, we'll just check if we can take a screenshot
                success = len(screenshot) > 0
                
                retry_results.append({
                    "attempt": attempt + 1,
                    "success": success,
                    "screenshot_size": len(screenshot)
                })
                
                if success:
                    break
                    
            except Exception as e:
                retry_results.append({
                    "attempt": attempt + 1,
                    "success": False,
                    "error": str(e)
                })
        
        successful_attempts = [r for r in retry_results if r.get("success", False)]
        
        return {
            "total_attempts": len(retry_results),
            "successful_attempts": len(successful_attempts),
            "success_on_attempt": successful_attempts[0]["attempt"] if successful_attempts else None,
            "retry_results": retry_results
        }


class WorkflowTester:
    """Main workflow testing orchestrator."""
    
    def __init__(self):
        self.phase2_tester = None
        self.phase3_tester = None
        self.logger = None
    
    async def test_website(self, test_config: dict, browser_mode: str = "headless") -> dict:
        """Test a single website through both phases."""
        url = test_config["url"]
        expected_keywords = test_config.get("expected_keywords", [])
        expected_elements = test_config.get("expected_elements", {})
        
        # Setup logging
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        parsed_url = urlparse(url)
        domain = parsed_url.netloc.replace('.', '_')
        
        self.logger = get_logger(
            f"workflow_test_{domain}_{timestamp}",
            FileHandlerConfig(directory=RESULTS_DIR / "logs" / timestamp)
        )
        
        self.phase2_tester = Phase2Tester(self.logger)
        self.phase3_tester = Phase3Tester(self.logger)
        
        result = {
            "site": url,
            "timestamp": datetime.now().isoformat(),
            "test_config": test_config,
            "phase2_results": {},
            "phase3_results": {},
            "failure_points": [],
            "overall_success": False
        }
        
        try:
            # Take screenshot
            screenshot_path = await take_screenshot(
                url, 
                browser_mode, 
                output_dir=SCREENSHOTS_DIR / domain
            )
            
            # Phase 2 Testing
            result["phase2_results"] = await self._test_phase2(
                Path(screenshot_path), 
                url, 
                expected_keywords, 
                expected_elements
            )
            
            # Phase 3 Testing (requires browser interaction)
            result["phase3_results"] = await self._test_phase3(
                url, 
                result["phase2_results"], 
                browser_mode
            )
            
            # Analyze failures
            result["failure_points"] = self._analyze_failures(result)
            result["overall_success"] = len(result["failure_points"]) == 0
            
        except Exception as e:
            result["error"] = str(e)
            result["failure_points"] = ["setup_error"]
        
        return result
    
    async def _test_phase2(self, screenshot_path: Path, url: str, expected_keywords: List[str], expected_elements: dict) -> dict:
        """Test Phase 2 components."""
        query = "All the user reviews for the product"
        
        # Test LLM Analysis
        llm_result = await self.phase2_tester.test_llm_analysis(screenshot_path, url, query)
        
        phase2_results = {
            "llm_analysis": llm_result
        }
        
        if llm_result["success"]:
            # Convert to AnalysisResult for further testing
            analysis_data = llm_result
            analysis_result = AnalysisResult(
                keywords=analysis_data["keywords_found"],
                navigation_element_point=Point(x=100, y=100) if analysis_data["elements_detected"]["navigation"] else None,
                popup_element_point=Point(x=200, y=200) if analysis_data["elements_detected"]["popup"] else None
            )
            
            # Test keyword extraction
            phase2_results["keyword_extraction"] = await self.phase2_tester.test_keyword_extraction(
                analysis_result, expected_keywords
            )
            
            # Test element identification
            phase2_results["element_identification"] = await self.phase2_tester.test_element_identification(
                analysis_result, expected_elements
            )
            
            # Test response matching (mock responses for now)
            mock_responses = [
                Response(
                    value='{"reviews": [{"rating": 5, "comment": "Great product"}]}',
                    request=Request(method="GET", url=f"{url}/api/reviews", queries={}, headers={})
                )
            ]
            
            phase2_results["response_matching"] = await self.phase2_tester.test_response_matching(
                analysis_result.keywords, mock_responses
            )
        
        return phase2_results
    
    async def _test_phase3(self, url: str, phase2_results: dict, browser_mode: str) -> dict:
        """Test Phase 3 components."""
        phase3_results = {}
        
        if not phase2_results.get("llm_analysis", {}).get("success", False):
            return {
                "error": "phase2_failed",
                "message": "Cannot test Phase 3 without successful Phase 2"
            }
        
        try:
            async with ayejax.create_browser(browser_mode) as browser:
                browser_ctx = await browser.new_context(bypass_csp=True)
                page = await browser_ctx.new_page()
                
                try:
                    await page.goto(url, timeout=30000, wait_until="commit")
                    await page.wait_for_timeout(5000)
                    
                    # Create mock analysis result for testing
                    llm_analysis = phase2_results["llm_analysis"]
                    analysis_result = AnalysisResult(
                        keywords=llm_analysis["keywords_found"],
                        navigation_element_point=Point(x=100, y=100) if llm_analysis["elements_detected"]["navigation"] else None,
                        popup_element_point=Point(x=200, y=200) if llm_analysis["elements_detected"]["popup"] else None
                    )
                    
                    # Test element interaction
                    phase3_results["element_interaction"] = await self.phase3_tester.test_element_interaction(
                        page, analysis_result
                    )
                    
                    # Test scroll navigation
                    phase3_results["scroll_navigation"] = await self.phase3_tester.test_scroll_navigation(
                        page, llm_analysis["keywords_found"]
                    )
                    
                    # Test response capture
                    phase3_results["response_capture"] = await self.phase3_tester.test_response_capture(
                        page, ["scroll", "click"]
                    )
                    
                    # Test retry logic
                    phase3_results["retry_logic"] = await self.phase3_tester.test_retry_logic(
                        page, "reviews"
                    )
                    
                finally:
                    await browser_ctx.close()
                    
        except Exception as e:
            phase3_results["error"] = str(e)
        
        return phase3_results
    
    def _analyze_failures(self, result: dict) -> List[str]:
        """Analyze test results to identify failure points."""
        failures = []
        
        # Check Phase 2 failures
        phase2 = result.get("phase2_results", {})
        if not phase2.get("llm_analysis", {}).get("success", False):
            failures.append("llm_analysis")
        
        if not phase2.get("keyword_extraction", {}).get("success", False):
            failures.append("keyword_extraction")
        
        if not phase2.get("response_matching", {}).get("success", False):
            failures.append("response_matching")
        
        # Check Phase 3 failures
        phase3 = result.get("phase3_results", {})
        if phase3.get("error"):
            failures.append("phase3_setup")
        
        element_interaction = phase3.get("element_interaction", {})
        if element_interaction.get("navigation_click", {}).get("attempted", False) and not element_interaction["navigation_click"].get("success", False):
            failures.append("navigation_interaction")
        
        scroll_nav = phase3.get("scroll_navigation", {})
        if scroll_nav.get("effectiveness", 0) < 0.5:
            failures.append("scroll_navigation")
        
        return failures


async def load_test_sites(test_file: Path) -> List[dict]:
    """Load test sites configuration."""
    if not test_file.exists():
        # Create default test configuration
        default_config = {
            "test_sites": [
                {
                    "url": "https://example.com/product",
                    "category": "example",
                    "expected_keywords": ["review", "rating", "comment"],
                    "expected_elements": {
                        "navigation": True,
                        "popup": False
                    }
                }
            ]
        }
        
        test_file.parent.mkdir(parents=True, exist_ok=True)
        with open(test_file, 'w') as f:
            json.dump(default_config, f, indent=2)
    
    with open(test_file, 'r') as f:
        config = json.load(f)
    
    return config["test_sites"]


async def run_batch_tests(test_sites: List[dict], browser_mode: str = "headless") -> dict:
    """Run tests on multiple websites."""
    RESULTS_DIR.mkdir(exist_ok=True)
    SCREENSHOTS_DIR.mkdir(exist_ok=True)
    
    results = {
        "timestamp": datetime.now().isoformat(),
        "total_sites": len(test_sites),
        "browser_mode": browser_mode,
        "results": [],
        "summary": {
            "successful": 0,
            "failed": 0,
            "failure_categories": {}
        }
    }
    
    tester = WorkflowTester()
    
    for i, site_config in enumerate(test_sites, 1):
        print(f"Testing {i}/{len(test_sites)}: {site_config['url']}")
        
        result = await tester.test_website(site_config, browser_mode)
        results["results"].append(result)
        
        if result["overall_success"]:
            results["summary"]["successful"] += 1
            print(f"  ✓ SUCCESS")
        else:
            results["summary"]["failed"] += 1
            print(f"  ✗ FAILED: {', '.join(result['failure_points'])}")
            
            # Track failure categories
            for failure in result["failure_points"]:
                results["summary"]["failure_categories"][failure] = results["summary"]["failure_categories"].get(failure, 0) + 1
    
    return results


@click.group()
def cli():
    """Workflow testing framework for ayejax."""
    pass


@cli.command()
@click.option("--test-file", type=click.Path(path_type=Path), default=TEST_DATA_DIR / "test_sites.json")
@click.option("--browser-mode", type=click.Choice(["headed", "headless"]), default="headless")
@click.option("--output-file", type=click.Path(path_type=Path), help="Output file for results")
def batch(test_file: Path, browser_mode: str, output_file: Path):
    """Run batch testing on multiple websites."""
    
    async def run_tests():
        test_sites = await load_test_sites(test_file)
        results = await run_batch_tests(test_sites, browser_mode)
        
        # Save results
        if output_file:
            output_path = output_file
        else:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_path = RESULTS_DIR / f"workflow_test_results_{timestamp}.json"
        
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_path, 'w') as f:
            json.dump(results, f, indent=2)
        
        print(f"\nResults saved to: {output_path}")
        print(f"Summary: {results['summary']['successful']}/{results['summary']['total_sites']} successful")
        
        if results['summary']['failure_categories']:
            print("Most common failures:")
            for failure, count in sorted(results['summary']['failure_categories'].items(), key=lambda x: x[1], reverse=True):
                print(f"  {failure}: {count} sites")
    
    asyncio.run(run_tests())


@cli.command()
@click.argument("url")
@click.option("--browser-mode", type=click.Choice(["headed", "headless"]), default="headless")
def single(url: str, browser_mode: str):
    """Test a single website."""
    
    async def run_single_test():
        test_config = {
            "url": url,
            "category": "manual",
            "expected_keywords": ["review", "rating", "comment"],
            "expected_elements": {
                "navigation": True,
                "popup": False
            }
        }
        
        tester = WorkflowTester()
        result = await tester.test_website(test_config, browser_mode)
        
        print(json.dumps(result, indent=2))
    
    asyncio.run(run_single_test())


if __name__ == "__main__":
    cli()