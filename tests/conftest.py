import sys

# Ensure backend config gets required arguments during test runs
if "--node-id" not in sys.argv:
    sys.argv.extend(["--node-id", "TEST_NODE", "--port", "9000"])
