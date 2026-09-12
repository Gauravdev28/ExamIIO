import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'codeguard.settings.development')
sys.path.insert(0, os.path.abspath('backend'))
django.setup()

from django.test import Client
from apps.accounts.models import User
from django.utils import timezone

client = Client()

print("==================================================")
print("TESTING ADMIN & STUDENT C EXECUTION ENDPOINTS")
print("==================================================")

# 1. Admin Run Code Test
admin = User.objects.filter(role='ADMIN', is_active=True).first()
if not admin:
    print("FAIL: No admin found")
    sys.exit(1)

client.force_login(admin)

admin_c_code = """#include <stdio.h>

int main() {
    printf("Hello C from Admin Sandbox");
    return 0;
}
"""

resp = client.post(
    '/api/v1/admin/questions/run-sandbox/',
    data={
        'language': 'c',
        'source_code': admin_c_code,
        'stdin': ''
    },
    content_type='application/json'
)

print("\n--- 1. Admin Run Code Response ---")
print("Status Code:", resp.status_code)
admin_res = resp.json()
print("Response JSON:", admin_res)

assert resp.status_code == 200, f"Expected 200, got {resp.status_code}"
assert admin_res.get('status') == 'success', f"Expected success, got {admin_res.get('status')}"
data = admin_res.get('data', {})
assert data.get('status') == 'SUCCESS', f"Expected data.status == SUCCESS, got {data.get('status')}"
assert 'Hello C from Admin Sandbox' in data.get('stdout', ''), f"Unexpected stdout: {data.get('stdout')}"
assert data.get('provider') == 'PISTON', f"Expected provider PISTON, got {data.get('provider')}"
print("ADMIN RUN CODE RESULT: PASS (Provider: PISTON)")

# 2. Student Run Code in Assessment Test
student = User.objects.filter(role='STUDENT', is_active=True).first()
if not student:
    print("FAIL: No student found")
    sys.exit(1)

client.force_login(student)

student_c_code = """#include <stdio.h>

int main() {
    int a, b;
    scanf("%d %d", &a, &b);
    printf("%d", a + b);
    return 0;
}
"""

# Run adhoc / assessment run code via CodeExecutionService or student attempt endpoint
from apps.evaluator.execution.service import CodeExecutionService
from apps.evaluator.execution.contract import ExecutionRequest

req = ExecutionRequest(
    source_code=student_c_code,
    language='c',
    stdin='10 20',
    cpu_time_limit_ms=2000,
    memory_limit_mb=256
)
student_res = CodeExecutionService.execute(req)

print("\n--- 2. Student Run Code Execution ---")
print("Status:", student_res.status)
print("Stdout:", repr(student_res.stdout))
print("Stderr:", repr(student_res.stderr))
print("Time (ms):", student_res.execution_time_ms)

assert student_res.status == 'ACCEPTED', f"Expected ACCEPTED, got {student_res.status}"
assert student_res.stdout.strip() == '30', f"Expected '30', got {repr(student_res.stdout)}"
print("STUDENT RUN CODE RESULT: PASS")

print("\n==================================================")
print("ALL PHASE 13 EXECUTION FLOWS PASSED!")
print("==================================================")
