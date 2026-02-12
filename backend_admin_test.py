#!/usr/bin/env python3
"""
Backend Admin Endpoints Test
Tests the admin functionality for suspend/activate user accounts
"""

import requests
import sys
from datetime import datetime
import json

class AdminEndpointsTest:
    def __init__(self, base_url="https://deploy-review-5.preview.emergentagent.com"):
        self.base_url = base_url
        self.tests_run = 0
        self.tests_passed = 0
        self.results = []

    def log_test(self, name, success, details="", expected_status=None, actual_status=None):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            print(f"✅ {name}")
        else:
            print(f"❌ {name}")
            if expected_status and actual_status:
                print(f"   Expected: {expected_status}, Got: {actual_status}")
            if details:
                print(f"   Details: {details}")
        
        self.results.append({
            "test": name,
            "success": success,
            "details": details,
            "expected_status": expected_status,
            "actual_status": actual_status
        })

    def test_health_endpoint(self):
        """Test health endpoint"""
        try:
            response = requests.get(f"{self.base_url}/api/health", timeout=10)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                has_status = "status" in data
                has_timestamp = "timestamp" in data
                success = has_status and has_timestamp
                details = f"Response: {data}" if success else "Missing required fields"
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Health endpoint responds", success, details, 200, response.status_code)
            return success
        except Exception as e:
            self.log_test("Health endpoint responds", False, str(e))
            return False

    def test_admin_endpoints_exist(self):
        """Test that admin endpoints exist (should return 401 without auth)"""
        endpoints = [
            ("GET", "/api/admin/users", "List users endpoint"),
            ("POST", "/api/admin/users/test-id/suspend", "Suspend user endpoint"),
            ("POST", "/api/admin/users/test-id/activate", "Activate user endpoint")
        ]
        
        all_passed = True
        
        for method, endpoint, description in endpoints:
            try:
                if method == "GET":
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                else:
                    response = requests.post(
                        f"{self.base_url}{endpoint}", 
                        json={}, 
                        headers={"Content-Type": "application/json"},
                        timeout=10
                    )
                
                # Should return 401 (Unauthorized) or 403 (Forbidden) without proper auth
                success = response.status_code in [401, 403]
                details = f"Endpoint exists, returns {response.status_code} without auth"
                
                if not success:
                    details = f"Unexpected status: {response.status_code}"
                    all_passed = False
                
                self.log_test(description, success, details, "401/403", response.status_code)
                
            except Exception as e:
                self.log_test(description, False, str(e))
                all_passed = False
        
        return all_passed

    def test_landing_page_loads(self):
        """Test that landing page loads"""
        try:
            response = requests.get(self.base_url, timeout=10)
            success = response.status_code == 200
            
            if success:
                # Check if it's HTML content
                content_type = response.headers.get('content-type', '')
                is_html = 'text/html' in content_type
                success = is_html
                details = f"Content-Type: {content_type}" if is_html else "Not HTML content"
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("Landing page loads", success, details, 200, response.status_code)
            return success
        except Exception as e:
            self.log_test("Landing page loads", False, str(e))
            return False

    def test_login_page_exists(self):
        """Test that login page exists"""
        try:
            # Try common login paths
            login_paths = ["/login", "/auth/login", "/signin"]
            
            for path in login_paths:
                try:
                    response = requests.get(f"{self.base_url}{path}", timeout=10)
                    if response.status_code == 200:
                        content_type = response.headers.get('content-type', '')
                        if 'text/html' in content_type:
                            self.log_test("Login page exists", True, f"Found at {path}", 200, response.status_code)
                            return True
                except:
                    continue
            
            # If no specific login page found, check if main page handles login
            response = requests.get(self.base_url, timeout=10)
            if response.status_code == 200:
                content = response.text.lower()
                has_login_elements = any(term in content for term in ['login', 'signin', 'email', 'password'])
                if has_login_elements:
                    self.log_test("Login page exists", True, "Login elements found on main page", 200, response.status_code)
                    return True
            
            self.log_test("Login page exists", False, "No login page or elements found")
            return False
            
        except Exception as e:
            self.log_test("Login page exists", False, str(e))
            return False

    def test_api_root(self):
        """Test API root endpoint"""
        try:
            response = requests.get(f"{self.base_url}/api/", timeout=10)
            success = response.status_code == 200
            
            if success:
                data = response.json()
                has_message = "message" in data
                has_version = "version" in data
                success = has_message and has_version
                details = f"API info: {data}" if success else "Missing required fields"
            else:
                details = f"HTTP {response.status_code}"
            
            self.log_test("API root endpoint", success, details, 200, response.status_code)
            return success
        except Exception as e:
            self.log_test("API root endpoint", False, str(e))
            return False

    def run_all_tests(self):
        """Run all tests"""
        print(f"🧪 Testing Admin Endpoints - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"🌐 Base URL: {self.base_url}")
        print("=" * 60)
        
        # Run tests
        self.test_health_endpoint()
        self.test_api_root()
        self.test_landing_page_loads()
        self.test_login_page_exists()
        self.test_admin_endpoints_exist()
        
        # Summary
        print("=" * 60)
        print(f"📊 Test Results: {self.tests_passed}/{self.tests_run} passed")
        
        if self.tests_passed == self.tests_run:
            print("🎉 All tests passed!")
            return 0
        else:
            print("⚠️  Some tests failed")
            return 1

def main():
    tester = AdminEndpointsTest()
    return tester.run_all_tests()

if __name__ == "__main__":
    sys.exit(main())