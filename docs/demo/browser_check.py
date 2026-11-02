"""Browser check of the demo journey (not part of the pytest suite; Playwright is NOT a project dependency).

Run with a Python that has playwright and Google Chrome installed, while the demo server is up on 127.0.0.1:8000:
    python docs/demo/browser_check.py docs/demo/screenshots
Exits 1 if any check fails. Screenshots are overwritten in the given directory.
"""
import json, os, sys

from playwright.sync_api import sync_playwright

OUT = sys.argv[1] if len(sys.argv) > 1 else "docs/demo/screenshots"
URL = "http://127.0.0.1:8000/"
os.makedirs(OUT, exist_ok=True)
errors, fails = [], []


def check(name, ok, info=""):
    print(("PASS " if ok else "FAIL ") + name, info)
    if not ok:
        fails.append(name)


def cards(pg):
    return pg.eval_on_selector_all("article.card", "c=>c.map(x=>x.querySelector('h3').textContent+' | '+x.querySelector('.badge').textContent)")


with sync_playwright() as p:
    b = p.chromium.launch(channel="chrome", headless=True)
    pg = b.new_page(viewport={"width": 1280, "height": 900})
    pg.on("console", lambda m: errors.append(m.text) if m.type in ("error", "warning") else None)
    pg.on("pageerror", lambda e: errors.append(str(e)))
    pg.goto(URL); pg.wait_for_selector("#status .chip")
    check("age field visible without opening a disclosure", pg.is_visible("#age"))
    check("default example is the sewing helper (pre-filled, not yet submitted)",
          pg.input_value("#current") == "GARMENT" and pg.input_value("#education") == "G10"
          and pg.input_value("#years") == "2" and pg.input_value("#age") == "30" and pg.locator("article.card").count() == 0)
    check("how it works: open, three steps", pg.locator("details#how").get_attribute("open") is not None
          and pg.locator("details#how ol.steps li").count() == 3 and "Hypothetical profile" in pg.inner_text("details#how")
          and "Documented entry-rule evaluation" in pg.inner_text("details#how") and "Evidence-backed results" in pg.inner_text("details#how"))
    check("prototype disclaimers kept", "Not a prediction" in pg.inner_text(".caveat") and "NO_GO" in pg.inner_text("#status")
          and "Prototype" in pg.inner_text("#status"))
    pg.screenshot(path=f"{OUT}/01_start.png")

    pg.click("#go"); pg.wait_for_selector("article.card")  # the default example, submitted with the main button
    check("default example: SMO first and met", "Sewing Machine Operator | ✓" in cards(pg)[0], cards(pg))
    check("how it works collapses after the first results and can be reopened", pg.locator("details#how").get_attribute("open") is None
          and (pg.click("details#how > summary") or True) and pg.locator("details#how ol.steps li").first.is_visible())
    pg.click("details#how > summary")  # collapse again so later screenshots are unchanged in layout

    pg.click("[data-sample=helper]"); pg.wait_for_selector("article.card")
    c = cards(pg)
    check("helper: SMO met, IC conditional, SSMO unknown", len(c) == 3 and "Operator | ✓" in c[0] and "◐" in c[1] and "?" in c[2], c)
    check("legend shown", pg.locator("ul.legend li").count() == 4)
    unk = pg.locator("article.card.v-UNKNOWN")
    check("every UNKNOWN card lists its reasons (none hidden, none turned positive)", unk.count() >= 1 and all(
        unk.nth(i).locator(".unk-box h4:has-text('Why this can’t be decided')").count() == 1
        and unk.nth(i).locator(".unk-box ul.reasons li").count() >= 1 and unk.nth(i).locator(".badge.UNKNOWN").count() == 1
        for i in range(unk.count())))
    check("UNKNOWN reasons are grouped with counts and codes", unk.first.locator(".rmeta code").count() >= 1
          and "requirement part" in unk.first.inner_text())
    check("age-not-stated notice absent when age given", pg.locator("text=Age not stated").count() == 0)
    pg.screenshot(path=f"{OUT}/02_results.png", full_page=True)

    pg.click("article.card >> nth=0 >> text=See evidence"); pg.wait_for_selector("#det-h")
    t = pg.inner_text("main")
    check("detail: no object leak", "[object" not in t)
    check("detail: sources shown", pg.locator("text=Source:").count() > 5)
    check("detail: non-deciding rows collapsed", pg.locator("details.collapsible summary:has-text('Other documented routes')").count() == 1
          and not pg.locator("details.collapsible:has(summary:has-text('Other documented routes'))").first.get_attribute("open"))
    check("detail: enrolment/deadline not verified", "not verified" in t.lower())
    check("detail: no multi-step routes shown, neutral note instead", "Routes that end here" not in t
          and "total official hours" not in t and pg.locator("#routes-unavailable").count() == 1
          and "not available in this prototype" in pg.inner_text("#routes-unavailable"))
    check("detail: Operator shows 300 h official total", pg.locator("tr:has-text('Total') td.n:has-text('300')").count() >= 1)
    pg.screenshot(path=f"{OUT}/03_detail.png", full_page=True)
    pg.click("text=Back to options"); pg.wait_for_selector("article.card")
    pg.click("article.card >> nth=2 >> text=See evidence"); pg.wait_for_selector("#det-h")
    check("detail (unknown): resolve section", pg.locator("text=What would resolve this").count() == 1)
    pg.screenshot(path=f"{OUT}/04_detail_unknown.png", full_page=True)

    pg.click("[data-sample=smo]"); pg.wait_for_selector("article.card")
    check("holds SMO: SMO not offered", not any("Sewing Machine Operator |" in x and "Specialized" not in x for x in cards(pg)), cards(pg))
    pg.screenshot(path=f"{OUT}/05_holds_smo.png", full_page=True)

    pg.click("[data-sample=minor]"); pg.wait_for_selector("text=No option is open")
    check("under 18: empty state, 0 cards", pg.locator("article.card").count() == 0)
    pg.screenshot(path=f"{OUT}/06_empty_under18.png", full_page=True)

    pg.fill("#age", ""); pg.select_option("#education", "G10"); pg.fill("#years", "2"); pg.click("#go")
    pg.wait_for_selector("text=Age not stated")
    check("no age: notice shown and nothing MET", pg.locator(".card.v-MET").count() == 0)
    pg.screenshot(path=f"{OUT}/07_no_age.png", full_page=True)

    pg.fill("#years", "99"); pg.click("#go")
    check("validation: years", "0 to 60" in pg.inner_text("#years-err"))
    pg.fill("#years", "2"); pg.fill("#age", "5"); pg.click("#go")
    check("validation: age", "14 to 80" in pg.inner_text("#age-err"))

    m = b.new_page(viewport={"width": 390, "height": 844}); m.goto(URL); m.wait_for_selector("#status .chip")
    check("390px: how-it-works starts collapsed so the form comes first", m.locator("details#how").get_attribute("open") is None)
    m.click("[data-sample=helper]"); m.wait_for_selector("article.card")
    check("390px: no horizontal overflow", not m.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"))
    check("390px: results scrolled into view", m.evaluate("document.getElementById('out').getBoundingClientRect().top < 120"))
    m.screenshot(path=f"{OUT}/08_mobile_results.png")
    m.screenshot(path=f"{OUT}/08_mobile_full.png", full_page=True)
    m.click("article.card >> nth=0 >> text=See evidence"); m.wait_for_selector("#det-h")
    check("390px detail: no horizontal overflow", not m.evaluate("document.documentElement.scrollWidth > document.documentElement.clientWidth"))
    m.screenshot(path=f"{OUT}/09_mobile_detail.png", full_page=True)

    e1 = b.new_page(); e1.route("**/demo/explore", lambda r: r.abort()); e1.goto(URL)
    e1.click("[data-sample=helper]"); e1.wait_for_selector(".state.error")
    check("network failure state", "Server not reachable" in e1.inner_text(".state.error"))
    e1.screenshot(path=f"{OUT}/10_error_network.png")
    e2 = b.new_page(); e2.route("**/demo/explore", lambda r: r.fulfill(status=503, content_type="application/json",
        body=json.dumps({"error": "DATA_NOT_BUILT", "message": "NOT_BUILT: no curated build is available"}))); e2.goto(URL)
    e2.click("[data-sample=helper]"); e2.wait_for_selector(".state.error")
    check("503 state", "Data not available" in e2.inner_text(".state.error"))

    w = b.new_page(viewport={"width": 1920, "height": 1080}); w.goto(URL); w.click("[data-sample=helper]"); w.wait_for_selector("article.card")
    w.screenshot(path=f"{OUT}/11_1920.png")
    b.close()
check("no console errors or warnings", not errors, errors)
print("RESULT:", "FAILED " + str(fails) if fails else "ALL CHECKS PASSED")
sys.exit(1 if fails else 0)
