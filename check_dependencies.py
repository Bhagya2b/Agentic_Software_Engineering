
import json
import re
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from pathlib import Path


PYPI_URL = "https://pypi.org/pypi"
TARGET_PYTHON = (3, 11, 0)
SPECIFIER_PATTERN = re.compile(r"(~=|===|==|!=|<=|>=|<|>)\s*(\S+)")


def fetch_json(url):
    """Fetch JSON from PyPI. Return None when the resource is missing."""
    request = Request(
        url,
        headers={"User-Agent": "PyPI-Dependency-Checker/1.0"}
    )

    try:
        with urlopen(request, timeout=15) as response:
            return json.load(response)

    except HTTPError as error:
        if error.code == 404:
            return None
        raise

    except URLError as error:
        raise RuntimeError(f"Could not contact PyPI: {error}") from error


def parse_dependency(line):
    """Extract the package name and an optional pinned version."""
    line = line.strip()

    # Support common requirements-file comments and blank lines.
    if not line or line.startswith("#"):
        return None

    # Accept both == and the assignment's single = notation.
    match = re.fullmatch(
        r"\s*([A-Za-z0-9][A-Za-z0-9._-]*)\s*"
        r"(?:={1,2}\s*([A-Za-z0-9][A-Za-z0-9.!+_-]*))?"
        r"\s*",
        line,
    )

    if not match:
        raise ValueError(f"Unsupported requirement format: {line}")

    name = match.group(1)
    version = match.group(2)

    return name, version


def version_tuple(version, length=3):
    """Turn '3.7' or '3.6.1' into a fixed-length tuple of ints."""
    parts = []
    for part in version.split("."):
        digits = re.match(r"\d+", part)
        if not digits:
            break
        parts.append(int(digits.group()))
    return tuple((parts + [0] * length)[:length])


def parse_specifiers(requires_python):
    """Split a requires_python string into (operator, version) pairs."""
    clauses = []
    for clause in (requires_python or "").split(","):
        match = SPECIFIER_PATTERN.fullmatch(clause.strip())
        if match:
            clauses.append(match.groups())
    return clauses


def supports_python(requires_python, python=TARGET_PYTHON):
    """Return True if the requires_python specifier allows the given Python."""
    for op, version in parse_specifiers(requires_python):
        # Wildcards such as !=3.0.* or ==3.*
        if version.endswith(".*"):
            prefix = tuple(int(p) for p in version[:-2].split("."))
            matches = python[:len(prefix)] == prefix
            if (op == "==" and not matches) or (op == "!=" and matches):
                return False
            continue

        target = version_tuple(version)
        if op == "~=":
            # ~=X.Y means >=X.Y and ==X.*
            prefix = version_tuple(version, len(version.split(".")) - 1)
            if python < target or python[:len(prefix)] != prefix:
                return False
        elif op in ("==", "===") and python != target:
            return False
        elif op == "!=" and python == target:
            return False
        elif op == ">=" and python < target:
            return False
        elif op == "<=" and python > target:
            return False
        elif op == ">" and python <= target:
            return False
        elif op == "<" and python >= target:
            return False
    return True


def minimum_python(requires_python):
    """Return the lowest Python version a specifier allows, or None."""
    minimums = [
        version_tuple(version)
        for op, version in parse_specifiers(requires_python)
        if op in (">=", ">", "~=", "==") and not version.endswith(".*")
    ]
    return max(minimums) if minimums else None


def main():
    filename = (
        sys.argv[1] if len(sys.argv) > 1 else "requirements.txt"
    )

    path = Path(filename)
    if not path.is_file():
        print(f"Error: File not found: {filename}", file=sys.stderr)
        sys.exit(1)

    # Each non-empty, non-comment requirement counts as a dependency.
    dependencies = []
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            parsed = parse_dependency(line)
            if parsed is not None:
                dependencies.append(parsed)
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        sys.exit(1)

    not_found = 0
    incompatible = 0
    requirements = []

    for name, version in dependencies:
        package_url = f"{PYPI_URL}/{name}/json"

        try:
            package_data = fetch_json(package_url)

            if package_data is None:
                not_found += 1
                continue

            # An unpinned dependency is checked against the latest release.
            if version is None:
                release_data = package_data
            else:
                version_url = f"{PYPI_URL}/{name}/{version}/json"
                release_data = fetch_json(version_url)

            if release_data is None:
                not_found += 1
                continue

            requires_python = release_data["info"].get("requires_python")
            if not supports_python(requires_python):
                incompatible += 1

            minimum = minimum_python(requires_python)
            if minimum is not None:
                label = f"{name}=={version}" if version else name
                requirements.append((minimum, label, requires_python))

        except (URLError, RuntimeError, HTTPError, TimeoutError) as error:
            print(
                f"Error checking {name}: {error}",
                file=sys.stderr
            )
            sys.exit(1)

    print(f"Dependencies checked: {len(dependencies)}")
    print(f"Not found on PyPI: {not_found}")
    print(f"Incompatible with Python 3.11: {incompatible}")

    if requirements:
        _, label, requires_python = max(requirements)
        print(f"Highest requirement: {label} (Python {requires_python})")
    else:
        print("Highest requirement: None")


if __name__ == "__main__":
    main()
