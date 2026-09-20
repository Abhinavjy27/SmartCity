"""
Centralized Configuration for Smart City SUPADSP Backend.
Defines evaluation horizon policies, production defaults, and system constants.
"""

# Horizon Policy Constants
# Production default evaluation horizon when no duration is specified
DEFAULT_PRODUCTION_EVALUATION_DURATION_SECONDS: int = 600

# CI / smoke test horizon
CI_SMOKE_EVALUATION_DURATION_SECONDS: int = 120

# Historical supported comparison horizon
HISTORICAL_EVALUATION_DURATION_SECONDS: int = 300

# Default simulation network
DEFAULT_NETWORK_NAME: str = "narayanguda_network.net.xml"

# Default demand scenario
DEFAULT_DEMAND_SCENARIO: str = "synthetic_peak_westbound"
