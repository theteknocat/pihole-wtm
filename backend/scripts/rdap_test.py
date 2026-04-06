#!/usr/bin/env python3
"""
Test RDAP/WHOIS enrichment for a domain with full debug logging.

Usage (via ddev):
    ddev rdap example.com

Usage (direct):
    .venv/bin/python scripts/rdap_test.py example.com
"""

import asyncio
import logging
import sys
from pathlib import Path

# Force DEBUG before any app imports so all log calls are captured
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s %(levelname)-8s %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("hpack").setLevel(logging.WARNING)

# Allow running from anywhere — add the backend root to the module path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.services.rdap import _registered_domain, _whois_fallback, lookup_company  # noqa: E402


async def _whois_raw(domain: str) -> None:
    """Dump the raw WHOIS text and all parsed fields for a domain."""
    try:
        import asyncwhois

        query_output, parsed = await asyncio.wait_for(asyncwhois.aio_whois(domain), timeout=10.0)

        print("\n--- Raw WHOIS text ---")
        print(query_output or "(empty)")

        print("\n--- Parsed fields (all non-empty) ---")
        parsed = parsed or {}
        non_empty = {k: v for k, v in parsed.items() if v is not None and v != "" and v != []}
        if non_empty:
            for k, v in sorted(non_empty.items()):
                print(f"  {k}: {v!r}")
        else:
            print("  (no non-empty fields)")

        print("\n--- Parsed fields (empty/None) ---")
        empty = [k for k, v in parsed.items() if v is None or v == "" or v == []]
        print("  " + ", ".join(sorted(empty)) if empty else "  (none)")

    except Exception as e:
        print(f"  WHOIS raw dump failed: {e}")


async def main(domain: str) -> None:
    reg = _registered_domain(domain)

    print(f"\nInput domain : {domain}")
    print(f"Registered   : {reg}")
    print()

    print("=" * 60)
    print("Full lookup (RDAP → WHOIS fallback if needed)")
    print("=" * 60)
    result = await lookup_company(domain)

    print()
    print(f"Final result : {result!r}")

    # If RDAP returned something, also run WHOIS independently so we can
    # compare — useful when suspecting RDAP returned a privacy-proxy name.
    if result is not None:
        print()
        print("=" * 60)
        print("WHOIS fallback (run independently for comparison)")
        print("=" * 60)
        whois_result = await _whois_fallback(reg)
        print()
        print(f"WHOIS result : {whois_result!r}")

    print()
    print("=" * 60)
    print("Raw WHOIS data")
    print("=" * 60)
    await _whois_raw(reg)


if __name__ == "__main__":
    if len(sys.argv) != 2:  # noqa: PLR2004
        print("Usage: rdap_test.py <domain>")
        sys.exit(1)

    asyncio.run(main(sys.argv[1]))
