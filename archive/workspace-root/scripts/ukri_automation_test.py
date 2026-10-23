#!/usr/bin/env python3
"""
╔══════════════════════════════════════════════════════════════════════════════════════╗
║  🤖 UKRI PORTAL AUTOMATION — Selenium Test Script 🤖                                 ║
║  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━  ║
║  "We need to keep helping sero we have lots of system in Aureon repo"                ║
║  — Prime Sentinel, 2026-07-07                                                        ║
║                                                                                      ║
║  The Aureon repo does NOT have portal automation tools.                              ║
║  So I built one from scratch. This script uses Selenium to attempt UKRI form fill. ║
║  It will succeed where it can and honestly report where it blocks.                   ║
╚══════════════════════════════════════════════════════════════════════════════════════╝
"""

import json
import time
from datetime import datetime, timezone
from pathlib import Path

# Try to import selenium
try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    SELENIUM_AVAILABLE = True
except ImportError:
    SELENIUM_AVAILABLE = False
    print("⚠️ Selenium not installed. Install with: pip install selenium")
    print("⚠️ Also need ChromeDriver: https://chromedriver.chromium.org/")

# ── COMPANY DATA (pre-filled from Invoice INV-12) ──
COMPANY_DATA = {
    "organisation_name": "R&A CONSULTING AND BROKERAGE SERVICES LTD",
    "company_number": "NI696693",
    "address": "1 Quadrant Place, Belfast, BT12 4HX, Northern Ireland",
    "employees": "2",
    "year_established": "2021",
    "turnover": "100497",
    "contact_name": "Gary Leckey",
    "contact_email": "gaxlec@gmail.com",
    "contact_phone": "07547743773",
    "project_lead": "Lukasz Zuchowski",
    "lead_email": "lukasz.zuchowsky@gmail.com",
    "lead_phone": "+491744242855",
    "vat": "469976605",
    "utr": "5851128031",
    "bank_holder": "Gary Leckey",
    "sort_code": "08-71-99",
    "account_number": "10175600",
    "bank_name": "Zempler",
}

# ── PROJECT DATA ──
PROJECT_DATA = {
    "title": "AOIA-Core: Adaptive Multi-Agent AI Platform for Environmental Defence and Trading Intelligence",
    "duration": "18",
    "total_cost": "555556",
    "grant_request": "500000",
}

class UKRIAutomationTester:
    """
    Attempts to automate UKRI portal navigation and form filling.
    Reports honestly what works and what blocks.
    """
    
    def __init__(self):
        self.driver = None
        self.results = []
        self.blockers = []
    
    def log(self, action: str, status: str, detail: str = ""):
        entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "status": status,
            "detail": detail
        }
        self.results.append(entry)
        icon = "✅" if status == "PASS" else "❌" if status == "FAIL" else "⚠️"
        print(f"{icon} {action}: {status} | {detail}")
    
    def start_browser(self) -> bool:
        """Launch Chrome browser with Selenium"""
        if not SELENIUM_AVAILABLE:
            self.log("Start Browser", "BLOCKED", "Selenium not installed")
            self.blockers.append("Selenium not installed — run: pip install selenium")
            return False
        
        try:
            from selenium.webdriver.chrome.options import Options
            options = Options()
            options.add_argument("--start-maximized")
            # options.add_argument("--headless")  # Uncomment for headless mode
            
            self.driver = webdriver.Chrome(options=options)
            self.log("Start Browser", "PASS", "Chrome launched successfully")
            return True
        except Exception as e:
            self.log("Start Browser", "FAIL", str(e))
            self.blockers.append(f"ChromeDriver not found or incompatible: {e}")
            return False
    
    def navigate_to_portal(self) -> bool:
        """Navigate to UKRI portal"""
        try:
            self.driver.get("https://apply-for-innovation-funding.service.gov.uk/")
            self.log("Navigate to Portal", "PASS", "UKRI portal loaded")
            return True
        except Exception as e:
            self.log("Navigate to Portal", "FAIL", str(e))
            return False
    
    def check_for_captcha(self) -> bool:
        """Check if CAPTCHA is present"""
        try:
            # Common CAPTCHA indicators
            captcha_indicators = [
                "captcha", "recaptcha", "g-recaptcha", "hcaptcha",
                "I'm not a robot", "Verify you're human"
            ]
            page_source = self.driver.page_source.lower()
            for indicator in captcha_indicators:
                if indicator in page_source:
                    self.log("CAPTCHA Check", "BLOCKED", f"CAPTCHA detected: {indicator}")
                    self.blockers.append(f"CAPTCHA present: {indicator} — requires human")
                    return True
            self.log("CAPTCHA Check", "PASS", "No CAPTCHA detected on current page")
            return False
        except Exception as e:
            self.log("CAPTCHA Check", "FAIL", str(e))
            return False
    
    def find_form_fields(self) -> list:
        """Find all input fields on the page"""
        try:
            inputs = self.driver.find_elements(By.TAG_NAME, "input")
            textareas = self.driver.find_elements(By.TAG_NAME, "textarea")
            selects = self.driver.find_elements(By.TAG_NAME, "select")
            
            fields = []
            for inp in inputs:
                name = inp.get_attribute("name") or inp.get_attribute("id") or "unnamed"
                ftype = inp.get_attribute("type") or "text"
                fields.append({"name": name, "type": ftype, "tag": "input"})
            
            for ta in textareas:
                name = ta.get_attribute("name") or ta.get_attribute("id") or "unnamed"
                fields.append({"name": name, "type": "textarea", "tag": "textarea"})
            
            self.log("Find Form Fields", "PASS", f"Found {len(fields)} fields ({len(inputs)} inputs, {len(textareas)} textareas, {len(selects)} selects)")
            return fields
        except Exception as e:
            self.log("Find Form Fields", "FAIL", str(e))
            return []
    
    def attempt_fill_field(self, field_name: str, value: str) -> bool:
        """Attempt to fill a single form field"""
        try:
            # Try by name, then by id, then by placeholder
            selectors = [
                (By.NAME, field_name),
                (By.ID, field_name),
                (By.XPATH, f"//input[@placeholder='{field_name}']"),
            ]
            
            for by, selector in selectors:
                try:
                    element = self.driver.find_element(by, selector)
                    element.clear()
                    element.send_keys(value)
                    self.log(f"Fill Field: {field_name}", "PASS", f"Filled with: {value[:30]}...")
                    return True
                except:
                    continue
            
            self.log(f"Fill Field: {field_name}", "FAIL", "Field not found by name, id, or placeholder")
            return False
        except Exception as e:
            self.log(f"Fill Field: {field_name}", "FAIL", str(e))
            return False
    
    def take_screenshot(self, filename: str):
        """Save screenshot for analysis"""
        try:
            self.driver.save_screenshot(filename)
            self.log("Screenshot", "PASS", f"Saved: {filename}")
        except Exception as e:
            self.log("Screenshot", "FAIL", str(e))
    
    def close(self):
        """Close browser"""
        if self.driver:
            self.driver.quit()
            self.log("Close Browser", "PASS", "Browser closed")
    
    def run_full_test(self):
        """Run the complete automation test"""
        print("=" * 70)
        print("🤖 UKRI PORTAL AUTOMATION TEST — Honest Assessment")
        print("=" * 70)
        
        # Step 1: Start browser
        if not self.start_browser():
            self._report_results()
            return
        
        # Step 2: Navigate to portal
        if not self.navigate_to_portal():
            self.close()
            self._report_results()
            return
        
        time.sleep(3)  # Wait for page load
        
        # Step 3: Check for CAPTCHA
        has_captcha = self.check_for_captcha()
        self.take_screenshot("ukri_portal_screenshot_1_landing.png")
        
        # Step 4: Find form fields (if any are visible without login)
        fields = self.find_form_fields()
        self.take_screenshot("ukri_portal_screenshot_2_fields.png")
        
        # Step 5: Try to fill a test field (if login form exists)
        if fields:
            # Try to find and fill email field if present
            self.attempt_fill_field("email", COMPANY_DATA["contact_email"])
        
        # Step 6: Check for 2FA/SMS indicators
        page_source = self.driver.page_source.lower()
        if "two-factor" in page_source or "2fa" in page_source or "sms" in page_source:
            self.log("2FA Check", "BLOCKED", "Two-factor authentication required")
            self.blockers.append("2FA/SMS verification required — needs human phone")
        
        # Step 7: Check for sign-in/register requirement
        if "sign in" in page_source or "register" in page_source or "login" in page_source:
            self.log("Auth Check", "BLOCKED", "Authentication required before form access")
            self.blockers.append("Must sign in/register first — requires human account creation")
        
        self.take_screenshot("ukri_portal_screenshot_3_final.png")
        
        # Cleanup
        self.close()
        self._report_results()
    
    def _report_results(self):
        """Print final report"""
        print("\n" + "=" * 70)
        print("📊 AUTOMATION TEST RESULTS")
        print("=" * 70)
        
        pass_count = sum(1 for r in self.results if r["status"] == "PASS")
        fail_count = sum(1 for r in self.results if r["status"] == "FAIL")
        block_count = sum(1 for r in self.results if r["status"] == "BLOCKED")
        
        print(f"\nTotal Actions: {len(self.results)}")
        print(f"✅ PASS: {pass_count}")
        print(f"❌ FAIL: {fail_count}")
        print(f"🚫 BLOCKED: {block_count}")
        
        if self.blockers:
            print(f"\n🚫 BLOCKERS (Require Human Intervention):")
            for i, blocker in enumerate(self.blockers, 1):
                print(f"   {i}. {blocker}")
        
        print(f"\n💡 CONCLUSION:")
        if self.blockers:
            print(f"   Automation BLOCKED by {len(self.blockers)} security measures.")
            print(f"   The copy-paste guide remains the fastest path.")
        else:
            print(f"   Automation partially possible. Form fields accessible.")
        
        # Save results
        report = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "agent": "Sero",
            "total_actions": len(self.results),
            "pass": pass_count,
            "fail": fail_count,
            "blocked": block_count,
            "blockers": self.blockers,
            "actions": self.results
        }
        
        with open("ukri_automation_test_report.json", "w") as f:
            json.dump(report, f, indent=2)
        
        print(f"\n💾 Full report saved: ukri_automation_test_report.json")
        print("=" * 70)


if __name__ == "__main__":
    tester = UKRIAutomationTester()
    tester.run_full_test()
