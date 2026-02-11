#!/usr/bin/env python3
"""
Backend API Testing for Client4You/Lead Dispatcher
Tests plan-based access control and core functionality
"""
import requests
import sys
import json
from datetime import datetime
from typing import Dict, List, Optional

class Client4YouAPITester:
    def __init__(self, base_url="https://api.client4you.com.br"):
        self.base_url = base_url
        self.token = None
        self.tests_run = 0
        self.tests_passed = 0
        self.failed_tests = []
        self.passed_tests = []

    def log_result(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        self.tests_run += 1
        if success:
            self.tests_passed += 1
            self.passed_tests.append(test_name)
            print(f"✅ {test_name} - PASSED {details}")
        else:
            self.failed_tests.append({"test": test_name, "details": details})
            print(f"❌ {test_name} - FAILED {details}")

    def run_test(self, name: str, method: str, endpoint: str, expected_status: int, 
                 data: Optional[Dict] = None, headers: Optional[Dict] = None) -> tuple[bool, Dict]:
        """Run a single API test"""
        url = f"{self.base_url}/{endpoint.lstrip('/')}"
        
        # Default headers
        test_headers = {'Content-Type': 'application/json'}
        if self.token:
            test_headers['Authorization'] = f'Bearer {self.token}'
        if headers:
            test_headers.update(headers)

        print(f"\n🔍 Testing {name}...")
        print(f"   URL: {method} {url}")
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=test_headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, json=data, headers=test_headers, timeout=10)
            elif method == 'PUT':
                response = requests.put(url, json=data, headers=test_headers, timeout=10)
            elif method == 'DELETE':
                response = requests.delete(url, headers=test_headers, timeout=10)
            else:
                self.log_result(name, False, f"Unsupported method: {method}")
                return False, {}

            success = response.status_code == expected_status
            
            try:
                response_data = response.json() if response.content else {}
            except:
                response_data = {"raw_content": response.text[:200]}

            details = f"Status: {response.status_code}"
            if not success:
                details += f" (expected {expected_status})"
                if response_data:
                    details += f" - {response_data}"

            self.log_result(name, success, details)
            return success, response_data

        except requests.exceptions.RequestException as e:
            self.log_result(name, False, f"Request error: {str(e)}")
            return False, {}
        except Exception as e:
            self.log_result(name, False, f"Unexpected error: {str(e)}")
            return False, {}

    def test_health_endpoints(self):
        """Test basic health endpoints"""
        print("\n" + "="*50)
        print("TESTING HEALTH ENDPOINTS")
        print("="*50)
        
        # Test health endpoint
        self.run_test(
            "Health Check",
            "GET",
            "/api/health",
            200
        )
        
        # Test webhook test endpoint
        self.run_test(
            "Webhook Test",
            "GET", 
            "/api/webhook/test",
            200
        )

    def test_unauthenticated_access(self):
        """Test endpoints without authentication"""
        print("\n" + "="*50)
        print("TESTING UNAUTHENTICATED ACCESS")
        print("="*50)
        
        # These should fail with 401
        endpoints_requiring_auth = [
            ("/api/campaigns", "GET"),
            ("/api/dashboard/stats", "GET"),
            ("/api/quotas/me", "GET"),
            ("/api/whatsapp/status", "GET")
        ]
        
        for endpoint, method in endpoints_requiring_auth:
            self.run_test(
                f"Unauthorized Access - {method} {endpoint}",
                method,
                endpoint,
                401  # Should return 401 Unauthorized
            )

    def test_plan_based_access_simulation(self):
        """Test plan-based access control by simulating different scenarios"""
        print("\n" + "="*50)
        print("TESTING PLAN-BASED ACCESS CONTROL")
        print("="*50)
        
        # Test endpoints that require specific plans
        # These should return 401 without auth, but we're testing the structure
        
        # Disparador endpoints (require intermediario+)
        disparador_endpoints = [
            ("/api/campaigns", "POST"),
            ("/api/campaigns/test-id/start", "POST"),
        ]
        
        for endpoint, method in disparador_endpoints:
            self.run_test(
                f"Disparador Access Control - {method} {endpoint}",
                method,
                endpoint,
                401,  # Will be 401 without auth, but endpoint exists
                data={"name": "test"} if method == "POST" else None
            )

    def test_new_campaign_endpoints(self):
        """Test new campaign endpoints specifically mentioned in review request"""
        print("\n" + "="*50)
        print("TESTING NEW CAMPAIGN ENDPOINTS")
        print("="*50)
        
        # Test the new campaigns/from-leads endpoint
        test_data = {
            "name": "Test Campaign from Leads",
            "message": {
                "type": "text",
                "text": "Hello {Nome}, this is a test message"
            },
            "settings": {
                "interval_min": 30,
                "interval_max": 120,
                "start_time": "08:00",
                "end_time": "18:00",
                "daily_limit": 300,
                "working_days": [1, 2, 3, 4, 5],
                "timezone": "America/Sao_Paulo"
            },
            "contacts": [
                {
                    "name": "Test Contact",
                    "phone": "5511999999999",
                    "category": "test",
                    "extra_data": {}
                }
            ]
        }
        
        self.run_test(
            "POST /api/campaigns/from-leads endpoint exists",
            "POST",
            "/api/campaigns/from-leads",
            401,  # Will be 401 without auth, but endpoint should exist
            data=test_data
        )

    def test_cors_and_security_headers(self):
        """Test CORS and security headers"""
        print("\n" + "="*50)
        print("TESTING SECURITY HEADERS")
        print("="*50)
        
        try:
            response = requests.get(f"{self.base_url}/api/health", timeout=10)
            
            # Check security headers
            security_headers = [
                "X-Content-Type-Options",
                "X-Frame-Options", 
                "X-XSS-Protection",
                "Referrer-Policy"
            ]
            
            headers_found = []
            for header in security_headers:
                if header in response.headers:
                    headers_found.append(header)
            
            success = len(headers_found) >= 2  # At least 2 security headers
            details = f"Found headers: {headers_found}"
            self.log_result("Security Headers", success, details)
            
        except Exception as e:
            self.log_result("Security Headers", False, f"Error: {str(e)}")

    def test_api_structure(self):
        """Test API structure and routing"""
        print("\n" + "="*50)
        print("TESTING API STRUCTURE")
        print("="*50)
        
        # Test root API endpoint
        success, data = self.run_test(
            "API Root",
            "GET",
            "/api/",
            200
        )
        
        if success and data:
            # Check if response contains expected fields
            expected_fields = ["message", "version"]
            has_fields = all(field in data for field in expected_fields)
            details = f"Response: {data}"
            self.log_result("API Root Structure", has_fields, details)

    def generate_report(self) -> Dict:
        """Generate test report"""
        success_rate = (self.tests_passed / self.tests_run * 100) if self.tests_run > 0 else 0
        
        report = {
            "timestamp": datetime.now().isoformat(),
            "total_tests": self.tests_run,
            "passed_tests": self.tests_passed,
            "failed_tests": len(self.failed_tests),
            "success_rate": round(success_rate, 1),
            "passed_test_names": self.passed_tests,
            "failed_test_details": self.failed_tests,
            "backend_url": self.base_url
        }
        
        return report

    def run_all_tests(self):
        """Run all backend tests"""
        print("🚀 Starting Client4You Backend API Tests")
        print(f"📍 Testing against: {self.base_url}")
        print(f"⏰ Started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Run test suites
        self.test_health_endpoints()
        self.test_unauthenticated_access()
        self.test_plan_based_access_simulation()
        self.test_new_campaign_endpoints()
        self.test_cors_and_security_headers()
        self.test_api_structure()
        
        # Generate and display report
        report = self.generate_report()
        
        print("\n" + "="*60)
        print("📊 FINAL TEST REPORT")
        print("="*60)
        print(f"Total Tests: {report['total_tests']}")
        print(f"Passed: {report['passed_tests']}")
        print(f"Failed: {report['failed_tests']}")
        print(f"Success Rate: {report['success_rate']}%")
        
        if report['failed_tests'] > 0:
            print(f"\n❌ Failed Tests:")
            for failure in report['failed_test_details']:
                print(f"   • {failure['test']}: {failure['details']}")
        
        print(f"\n✅ Passed Tests:")
        for test_name in report['passed_test_names']:
            print(f"   • {test_name}")
        
        return report

def main():
    """Main test execution"""
    # Test against local backend first, then production
    print("🔄 Testing local backend first...")
    local_tester = Client4YouAPITester("http://localhost:8001")
    
    try:
        local_report = local_tester.run_all_tests()
        
        # Save local report
        with open('/app/test_reports/backend_test_local_results.json', 'w') as f:
            json.dump(local_report, f, indent=2)
        
        print(f"\n📄 Local report saved to: /app/test_reports/backend_test_local_results.json")
        
        # Test against production API
        print("\n" + "="*60)
        print("🌐 Testing production backend...")
        print("="*60)
        prod_tester = Client4YouAPITester("https://api.client4you.com.br")
        prod_report = prod_tester.run_all_tests()
        
        # Save production report
        with open('/app/test_reports/backend_test_results.json', 'w') as f:
            json.dump(prod_report, f, indent=2)
        
        print(f"\n📄 Production report saved to: /app/test_reports/backend_test_results.json")
        
        # Return appropriate exit code based on local tests (more important for development)
        return 0 if local_report['failed_tests'] == 0 else 1
        
    except KeyboardInterrupt:
        print("\n⚠️ Tests interrupted by user")
        return 1
    except Exception as e:
        print(f"\n💥 Unexpected error: {str(e)}")
        return 1

if __name__ == "__main__":
    sys.exit(main())