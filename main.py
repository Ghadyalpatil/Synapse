#!/usr/bin/env python3
"""
SYNAPSE — Border Surveillance Edge Node Entry Point
Convenience executable wrapper delegating to synapse.__main__.
Zero cloud, zero remote dependencies.
"""

from synapse.__main__ import main

if __name__ == "__main__":
    main()
