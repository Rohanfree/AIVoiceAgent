from pathlib import Path


def test_production_calculator_tests_are_wired_into_ci():
    workflow = Path(".github/workflows/test.yml").read_text()
    assert "uses: actions/setup-node@v4" in workflow
    assert "node-version: '26'" in workflow
    assert "node --check app/static/js/impact-calculator.js" in workflow
    assert "node --test tests/frontend/impact-calculator.test.cjs" in workflow
    assert "python -m pytest -q" in workflow
