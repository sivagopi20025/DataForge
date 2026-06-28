from __future__ import annotations

import os
import time

import pytest


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_UI_SELENIUM") != "1",
    reason="Selenium UI tests require RUN_UI_SELENIUM=1 and a running local app.",
)


@pytest.fixture
def driver():
    pytest.importorskip("selenium")
    from selenium import webdriver

    options = webdriver.ChromeOptions()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--window-size=1440,1200")
    browser = webdriver.Chrome(options=options)
    try:
        yield browser
    finally:
        browser.quit()


def wait_until(driver, predicate, *, timeout: int = 120):
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            value = predicate()
            if value:
                return value
        except Exception as error:  # pragma: no cover - diagnostic path
            last_error = error
        time.sleep(0.5)
    if last_error:
        raise AssertionError(f"Timed out waiting for Selenium condition: {last_error}") from last_error
    raise AssertionError("Timed out waiting for Selenium condition")


def test_generator_live_generation_and_centered_files(driver):
    pytest.importorskip("selenium")
    from selenium.webdriver.common.by import By

    base_url = os.getenv("DATAFORGE_UI_BASE_URL", "http://127.0.0.1:3000")
    driver.get(f"{base_url}/generator")

    wait_until(driver, lambda: "Generate Enterprise Datasets" in driver.find_element(By.TAG_NAME, "body").text)
    body_text = driver.find_element(By.TAG_NAME, "body").text
    assert "Unable to load table catalog" not in body_text
    assert "Categories" in body_text
    assert "Suppliers" in body_text

    driver.find_element(By.XPATH, "//button[normalize-space()='Generate Dataset']").click()

    wait_until(driver, lambda: "Generating files..." in driver.find_element(By.TAG_NAME, "body").text, timeout=10)
    pending_text = driver.find_element(By.TAG_NAME, "body").text
    assert "Your selected files are being generated now." in pending_text
    assert "LIVE GENERATION" in pending_text

    wait_until(driver, lambda: "/runs/" in driver.current_url, timeout=180)
    wait_until(driver, lambda: "Generated Files" in driver.find_element(By.TAG_NAME, "body").text)

    result_text = driver.find_element(By.TAG_NAME, "body").text
    assert "Run Results" in result_text
    assert "Generated Files" in result_text
    assert "Download" in result_text
    assert "Issues Injected" not in result_text
    assert "Weighted quality score from validation checks" not in result_text


def test_generator_navigation_stability(driver):
    from selenium.webdriver.common.by import By

    base_url = os.getenv("DATAFORGE_UI_BASE_URL", "http://127.0.0.1:3000")
    routes = ["/generator", "/history", "/generator", "/history", "/generator"]
    timings: list[float] = []

    for route in routes:
        started = time.perf_counter()
        driver.get(f"{base_url}{route}")
        wait_until(driver, lambda: driver.find_element(By.TAG_NAME, "body").text.strip())
        elapsed = time.perf_counter() - started
        timings.append(elapsed)
        body_text = driver.find_element(By.TAG_NAME, "body").text
        assert "Unhandled Runtime Error" not in body_text
        assert "Application error" not in body_text
        assert "Cannot find module" not in body_text

    assert max(timings) < 15


def test_generator_repeated_small_generation_stability(driver):
    from selenium.webdriver.common.by import By

    base_url = os.getenv("DATAFORGE_UI_BASE_URL", "http://127.0.0.1:3000")
    iterations = int(os.getenv("SELENIUM_GENERATION_ITERATIONS", "3"))
    durations: list[float] = []

    for _ in range(iterations):
        driver.get(f"{base_url}/generator")
        wait_until(driver, lambda: "Generate Dataset" in driver.find_element(By.TAG_NAME, "body").text)
        assert "Unable to load table catalog" not in driver.find_element(By.TAG_NAME, "body").text

        started = time.perf_counter()
        driver.find_element(By.XPATH, "//button[normalize-space()='Generate Dataset']").click()
        wait_until(driver, lambda: "Generating files..." in driver.find_element(By.TAG_NAME, "body").text, timeout=10)
        wait_until(driver, lambda: "/runs/" in driver.current_url, timeout=180)
        wait_until(driver, lambda: "Generated Files" in driver.find_element(By.TAG_NAME, "body").text)
        durations.append(time.perf_counter() - started)

        result_text = driver.find_element(By.TAG_NAME, "body").text
        assert "Download" in result_text
        assert "Unable to load" not in result_text
        assert "Generation failed" not in result_text

    assert max(durations) < 180
