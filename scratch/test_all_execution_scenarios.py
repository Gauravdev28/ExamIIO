import os
import sys
import django

# Setup Django standalone environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'codeguard.settings.development')
sys.path.insert(0, os.path.abspath('backend'))
django.setup()

from apps.evaluator.execution.service import CodeExecutionService
from apps.evaluator.execution.contract import ExecutionRequest, ExecutionStatus

def run_test(name, language, code, stdin="", expected_status=ExecutionStatus.ACCEPTED, expected_stdout_contains=""):
    print(f"\n==========================================")
    print(f"RUNNING TEST: {name} ({language})")
    print(f"==========================================")
    req = ExecutionRequest(
        source_code=code,
        language=language,
        stdin=stdin,
        cpu_time_limit_ms=2000,
        memory_limit_mb=256
    )
    res = CodeExecutionService.execute(req)
    print(f"Status: {res.status}")
    print(f"Stdout: {repr(res.stdout)}")
    print(f"Stderr: {repr(res.stderr)}")
    print(f"Compile Output: {repr(res.compile_output)}")
    print(f"Time (ms): {res.execution_time_ms}")
    print(f"Memory (KB): {res.memory_kb}")
    print(f"Exit Code: {res.exit_code}")
    
    passed = True
    if res.status != expected_status.value:
        print(f"FAIL: Expected status {expected_status.value}, got {res.status}")
        passed = False
    if expected_stdout_contains and expected_stdout_contains not in (res.stdout or ""):
        print(f"FAIL: Expected stdout to contain {repr(expected_stdout_contains)}, got {repr(res.stdout)}")
        passed = False
        
    if passed:
        print(f"RESULT: PASS")
    else:
        print(f"RESULT: FAIL")
    return passed

def main():
    results = {}
    
    # 1. PYTHON
    results['Python'] = run_test(
        name="Python Execution",
        language="python",
        code='print("Hello Python")',
        expected_stdout_contains="Hello Python"
    )
    
    # 2. C
    results['C'] = run_test(
        name="C Execution",
        language="c",
        code='#include <stdio.h>\n\nint main() {\n    printf("Hello C");\n    return 0;\n}',
        expected_stdout_contains="Hello C"
    )
    
    # 3. C++
    results['C++'] = run_test(
        name="C++ Execution",
        language="cpp",
        code='#include <iostream>\n\nint main() {\n    std::cout << "Hello C++";\n    return 0;\n}',
        expected_stdout_contains="Hello C++"
    )
    
    # 4. JAVA
    results['Java'] = run_test(
        name="Java Execution",
        language="java",
        code='public class Main {\n    public static void main(String[] args) {\n        System.out.println("Hello Java");\n    }\n}',
        expected_stdout_contains="Hello Java"
    )
    
    # 5. C STDIN
    results['C stdin'] = run_test(
        name="C Stdin (5 + 7 = 12)",
        language="c",
        code='#include <stdio.h>\n\nint main() {\n    int a, b;\n    scanf("%d %d", &a, &b);\n    printf("%d", a + b);\n    return 0;\n}',
        stdin="5 7",
        expected_stdout_contains="12"
    )
    
    # 6. PYTHON STDIN
    results['Python stdin'] = run_test(
        name="Python Stdin (5 + 7 = 12)",
        language="python",
        code='a, b = map(int, input().split())\nprint(a + b)',
        stdin="5 7",
        expected_stdout_contains="12"
    )
    
    # 7. C COMPILE ERROR
    results['C compile error'] = run_test(
        name="C Compile Error",
        language="c",
        code='#include <stdio.h>\nint main() { invalid_syntax; return 0; }',
        expected_status=ExecutionStatus.COMPILATION_ERROR
    )
    
    # 8. C RUNTIME ERROR
    results['C runtime error'] = run_test(
        name="C Runtime Error (Division by Zero / SIGFPE)",
        language="c",
        code='#include <stdio.h>\nint main() { volatile int a = 1; volatile int b = 0; volatile int c = a / b; printf("%d", c); return 0; }',
        expected_status=ExecutionStatus.RUNTIME_ERROR
    )
    
    # 9. C TIMEOUT
    results['C timeout'] = run_test(
        name="C Timeout (Infinite Loop)",
        language="c",
        code='#include <stdio.h>\nint main() { while(1) {} return 0; }',
        expected_status=ExecutionStatus.TIME_LIMIT
    )
    
    # 10. C EMPTY OUTPUT
    results['C empty output'] = run_test(
        name="C Empty Output",
        language="c",
        code='#include <stdio.h>\nint main() { return 0; }',
        expected_status=ExecutionStatus.ACCEPTED
    )
    
    print("\n==========================================")
    print("ALL TEST RESULTS SUMMARY:")
    print("==========================================")
    all_passed = True
    for test, pass_status in results.items():
        status_str = "PASS" if pass_status else "FAIL"
        print(f"{test}: {status_str}")
        if not pass_status:
            all_passed = False
            
    print(f"\nOVERALL: {'ALL PASSED' if all_passed else 'SOME FAILED'}")
    return 0 if all_passed else 1

if __name__ == '__main__':
    sys.exit(main())
