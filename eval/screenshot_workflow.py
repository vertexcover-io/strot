#!/usr/bin/env python3
"""
Screenshot-based workflow evaluation tool for ayejax.

This script provides a CLI to take screenshots and run partial workflows
for debugging and evaluation purposes. Supports both URLs and folders of screenshots.
"""

import asyncio
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

import click
from playwright.async_api import Browser, Page

import ayejax
from ayejax.logging import get_logger, setup_logging
from ayejax.logging.handlers import FileHandlerConfig
from ayejax.types import AnalysisResult

setup_logging()

ROOT_DIR = Path(__file__).parent
SCREENSHOTS_DIR = ROOT_DIR / "screenshots"
LOGS_DIR = ROOT_DIR / "logs"
RESULTS_DIR = ROOT_DIR / "results"


async def take_screenshot(
    url: str, 
    browser_mode: Literal["headed", "headless"] = "headed",
    wait_time: int = 5,
    output_dir: Path | None = None
) -> str:
    """Take a screenshot of the given URL and save it locally."""
    if output_dir is None:
        output_dir = SCREENSHOTS_DIR
    
    output_dir.mkdir(exist_ok=True)
    
    # Create filename from URL
    parsed_url = urlparse(url)
    domain = parsed_url.netloc.replace('.', '_')
    path = parsed_url.path.replace('/', '_').strip('_')
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    filename = f"{domain}_{path}_{timestamp}.png" if path else f"{domain}_{timestamp}.png"
    filepath = output_dir / filename
    
    async with ayejax.create_browser(browser_mode) as browser:
        browser_ctx = await browser.new_context(bypass_csp=True)
        page = await browser_ctx.new_page()
        
        try:
            await page.goto(url, timeout=30000, wait_until="commit")
            await page.wait_for_timeout(wait_time * 1000)
            
            screenshot = await page.screenshot(type="png", path=str(filepath))
            
            print(f"Screenshot saved: {filepath}")
            return str(filepath)
            
        finally:
            await browser_ctx.close()


async def analyze_screenshot_file(
    screenshot_path: Path,
    query: str = "All the user reviews for the product",
    url: str | None = None
) -> dict:
    """Analyze a screenshot file using LLM."""
    LOGS_DIR.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = get_logger(
        f"screenshot_analysis_{screenshot_path.stem}_{timestamp}",
        FileHandlerConfig(directory=LOGS_DIR / timestamp)
    )
    
    try:
        # Read screenshot
        screenshot_data = screenshot_path.read_bytes()
        
        # Initialize LLM client
        from ayejax import llm
        from ayejax.constants import ANALYSIS_PROMPT_TEMPLATE_WITH_SECTION_NAVIGATION
        
        llm_client = llm.LLMClient(
            provider="anthropic",
            model="claude-3-5-sonnet-20241022",
            logger=logger,
        )
        
        # Analyze screenshot
        prompt = ANALYSIS_PROMPT_TEMPLATE_WITH_SECTION_NAVIGATION % query
        llm_input = llm.LLMInput(prompt=prompt, image=screenshot_data)
        
        completion = await llm_client.get_completion(llm_input, json=True)
        logger.info("screenshot-analysis", completion=completion.value)
        
        # Parse result
        try:
            result = AnalysisResult.model_validate_json(completion.value)
            return {
                "screenshot_path": str(screenshot_path),
                "url": url,
                "success": True,
                "result": result.model_dump(),
                "cost": completion.calculate_cost(3.0, 15.0)
            }
        except Exception as e:
            logger.error("screenshot-analysis", parsing_error=str(e))
            return {
                "screenshot_path": str(screenshot_path),
                "url": url,
                "success": False,
                "error": f"Parse error: {str(e)}",
                "cost": completion.calculate_cost(3.0, 15.0)
            }
            
    except Exception as e:
        logger.error("screenshot-analysis", error=str(e))
        return {
            "screenshot_path": str(screenshot_path),
            "url": url,
            "success": False,
            "error": str(e),
            "cost": 0
        }


async def process_screenshot_folder(
    folder_path: Path,
    query: str = "All the user reviews for the product",
    output_file: str | None = None
) -> list[dict]:
    """Process all screenshots in a folder."""
    if not folder_path.exists():
        raise FileNotFoundError(f"Folder not found: {folder_path}")
    
    # Find all image files
    image_extensions = {'.png', '.jpg', '.jpeg', '.webp'}
    screenshot_files = [
        f for f in folder_path.iterdir() 
        if f.is_file() and f.suffix.lower() in image_extensions
    ]
    
    if not screenshot_files:
        print(f"No image files found in {folder_path}")
        return []
    
    print(f"Found {len(screenshot_files)} screenshots to process")
    
    results = []
    total_cost = 0
    
    for i, screenshot_file in enumerate(screenshot_files, 1):
        print(f"Processing {i}/{len(screenshot_files)}: {screenshot_file.name}")
        
        result = await analyze_screenshot_file(screenshot_file, query)
        results.append(result)
        total_cost += result.get("cost", 0)
        
        print(f"  Result: {'SUCCESS' if result['success'] else 'FAILED'}")
        if result['success']:
            keywords = result['result'].get('keywords', [])
            print(f"  Keywords: {keywords}")
        else:
            print(f"  Error: {result['error']}")
    
    print(f"\nTotal cost: ${total_cost:.4f}")
    
    # Save results
    if output_file:
        output_path = Path(output_file)
    else:
        RESULTS_DIR.mkdir(exist_ok=True)
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        output_path = RESULTS_DIR / f"batch_analysis_{timestamp}.json"
    
    with open(output_path, 'w') as f:
        json.dump({
            "folder": str(folder_path),
            "total_screenshots": len(screenshot_files),
            "total_cost": total_cost,
            "results": results
        }, f, indent=2)
    
    print(f"Results saved to: {output_path}")
    return results


async def analyze_screenshot(
    url: str,
    query: str = "All the user reviews for the product",
    browser_mode: Literal["headed", "headless"] = "headed",
    save_screenshot: bool = True
) -> AnalysisResult | None:
    """Analyze a screenshot using LLM without running full workflow."""
    LOGS_DIR.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = get_logger(
        f"screenshot_analysis_{timestamp}",
        FileHandlerConfig(directory=LOGS_DIR / timestamp)
    )
    
    async with ayejax.create_browser(browser_mode) as browser:
        browser_ctx = await browser.new_context(bypass_csp=True)
        page = await browser_ctx.new_page()
        
        try:
            await page.goto(url, timeout=30000, wait_until="commit")
            await page.wait_for_timeout(5000)
            
            # Take screenshot
            screenshot = await page.screenshot(type="png")
            
            if save_screenshot:
                SCREENSHOTS_DIR.mkdir(exist_ok=True)
                screenshot_path = SCREENSHOTS_DIR / f"analysis_{timestamp}.png"
                with open(screenshot_path, "wb") as f:
                    f.write(screenshot)
                print(f"Screenshot saved: {screenshot_path}")
            
            # Initialize LLM client
            from ayejax import llm
            from ayejax.constants import ANALYSIS_PROMPT_TEMPLATE_WITH_SECTION_NAVIGATION
            
            llm_client = llm.LLMClient(
                provider="anthropic",
                model="claude-3-5-sonnet-20241022",
                logger=logger,
            )
            
            # Analyze screenshot
            prompt = ANALYSIS_PROMPT_TEMPLATE_WITH_SECTION_NAVIGATION % query
            llm_input = llm.LLMInput(prompt=prompt, image=screenshot)
            
            completion = await llm_client.get_completion(llm_input, json=True)
            logger.info("screenshot-analysis", completion=completion.value)
            
            # Parse result
            try:
                result = AnalysisResult.model_validate_json(completion.value)
                print(f"Analysis result: {result}")
                return result
            except Exception as e:
                logger.error("screenshot-analysis", parsing_error=str(e))
                print(f"Failed to parse result: {e}")
                return None
                
        finally:
            await browser_ctx.close()


async def run_partial_workflow(
    url: str,
    max_iterations: int = 3,
    browser_mode: Literal["headed", "headless"] = "headed",
    tag: str = "reviews"
) -> dict:
    """Run a partial workflow with limited iterations for debugging."""
    LOGS_DIR.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    logger = get_logger(
        f"partial_workflow_{timestamp}",
        FileHandlerConfig(directory=LOGS_DIR / timestamp)
    )
    
    # Run limited analysis
    try:
        output, metadata = await ayejax.analyze(
            url, 
            tag, 
            browser=browser_mode,
            logger=logger,
            max_view_scrolls=max_iterations
        )
        
        result = {
            "url": url,
            "success": output is not None,
            "output": output.model_dump() if output else None,
            "metadata": {
                "extracted_keywords": metadata.extracted_keywords,
                "total_completions": len(metadata.completions),
                "total_cost": sum(c.calculate_cost(3.0, 15.0) for c in metadata.completions)
            }
        }
        
        # Save result
        result_file = ROOT_DIR / f"partial_workflow_{timestamp}.json"
        with open(result_file, "w") as f:
            json.dump(result, f, indent=2)
        
        print(f"Partial workflow result saved: {result_file}")
        return result
        
    except Exception as e:
        logger.error("partial-workflow", error=str(e))
        print(f"Partial workflow failed: {e}")
        return {"url": url, "success": False, "error": str(e)}


@click.group()
def cli():
    """Screenshot-based workflow evaluation tool for ayejax."""
    pass


@cli.command()
@click.argument("url")
@click.option("--browser-mode", type=click.Choice(["headed", "headless"]), default="headed")
@click.option("--wait-time", type=int, default=5, help="Wait time in seconds before taking screenshot")
@click.option("--output-dir", type=click.Path(path_type=Path), help="Output directory for screenshot")
def screenshot(url: str, browser_mode: str, wait_time: int, output_dir: Path):
    """Take a screenshot of the given URL and save it locally."""
    asyncio.run(take_screenshot(url, browser_mode, wait_time, output_dir))


@cli.command()
@click.argument("input_path")
@click.option("--query", default="All the user reviews for the product", help="Query for LLM analysis")
@click.option("--browser-mode", type=click.Choice(["headed", "headless"]), default="headed")
@click.option("--save-screenshot/--no-save-screenshot", default=True)
@click.option("--output-file", type=click.Path(), help="Output file for results")
def analyze(input_path: str, query: str, browser_mode: str, save_screenshot: bool, output_file: str):
    """Analyze a screenshot file/folder or URL using LLM."""
    path = Path(input_path)
    
    if path.exists():
        if path.is_file():
            # Single screenshot file
            async def analyze_single():
                result = await analyze_screenshot_file(path, query)
                print(f"Analysis result: {result}")
                if output_file:
                    with open(output_file, 'w') as f:
                        json.dump(result, f, indent=2)
            asyncio.run(analyze_single())
        else:
            # Folder of screenshots
            asyncio.run(process_screenshot_folder(path, query, output_file))
    else:
        # Treat as URL
        asyncio.run(analyze_screenshot(input_path, query, browser_mode, save_screenshot))


@cli.command()
@click.argument("url")
@click.option("--max-iterations", type=int, default=3, help="Maximum number of iterations")
@click.option("--browser-mode", type=click.Choice(["headed", "headless"]), default="headed")
@click.option("--tag", default="reviews", help="Tag to use for analysis")
def partial(url: str, max_iterations: int, browser_mode: str, tag: str):
    """Run a partial workflow with limited iterations for debugging."""
    asyncio.run(run_partial_workflow(url, max_iterations, browser_mode, tag))


@cli.command()
@click.argument("input_path")
@click.option("--query", default="All the user reviews for the product", help="Query for LLM analysis")
@click.option("--output-file", type=click.Path(), help="Output file for batch results")
def batch(input_path: str, query: str, output_file: str):
    """Process a folder of screenshots in batch mode."""
    folder_path = Path(input_path)
    
    if not folder_path.exists():
        print(f"Error: Folder {folder_path} does not exist")
        return
    
    if not folder_path.is_dir():
        print(f"Error: {folder_path} is not a directory")
        return
    
    asyncio.run(process_screenshot_folder(folder_path, query, output_file))


@cli.command()
@click.argument("url")
@click.option("--browser-mode", type=click.Choice(["headed", "headless"]), default="headed")
def interactive(url: str, browser_mode: str):
    """Run interactive workflow - take screenshot, analyze, then ask for next action."""
    async def run_interactive():
        print(f"Starting interactive workflow for: {url}")
        
        # Take initial screenshot
        screenshot_path = await take_screenshot(url, browser_mode)
        print(f"Initial screenshot: {screenshot_path}")
        
        # Analyze screenshot
        result = await analyze_screenshot(url, browser_mode=browser_mode)
        if not result:
            print("Analysis failed. Exiting.")
            return
        
        print(f"Found keywords: {result.keywords}")
        if result.navigation_element_point:
            print(f"Navigation element at: ({result.navigation_element_point.x}, {result.navigation_element_point.y})")
        if result.popup_element_point:
            print(f"Popup element at: ({result.popup_element_point.x}, {result.popup_element_point.y})")
        
        # Ask user for next action
        action = input("Next action (screenshot/analyze/partial/quit): ").strip().lower()
        
        if action == "screenshot":
            await take_screenshot(url, browser_mode)
        elif action == "analyze":
            await analyze_screenshot(url, browser_mode=browser_mode)
        elif action == "partial":
            await run_partial_workflow(url, browser_mode=browser_mode)
        elif action == "quit":
            print("Exiting interactive mode.")
        else:
            print("Invalid action. Available: screenshot, analyze, partial, quit")
    
    asyncio.run(run_interactive())


if __name__ == "__main__":
    cli()