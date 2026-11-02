log = ["read_file:ok:120","run_tests:fail:900","edit_file:ok:45","run_test:ok:610","search","read_file:fail:30"]
counts = {}
slow = 0
total = 0
for entry in log:
    parts = entry.split(":")
    if len(parts) < 3:
        continue
    tool, status, ms = parts
    if status == "fail":
        counts[tool] = counts.get(tool, 0) + 1
        continue
    ms = int(ms)
    total += ms
    if ms > 100:
        slow += 1
n = len(log) - len(counts)
print(f"failures: {counts}")
print(f"slow calls: {slow}")
print(f"average ok time: {total/n}")
print(f"last tool: {tool}[::-1][:4]")

