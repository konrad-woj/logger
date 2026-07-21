"""Optional, light integrations with specific cloud logging backends.

The core ``logger`` package is provider-agnostic (JSON to stdout in
production, coloured console in development) — every cloud's container
and serverless platforms scrape stdout without requiring an SDK. These
submodules are thin, opt-in helpers for the parts that stdout scraping
alone doesn't cover: GCP/AWS trace correlation and, for Azure, actually
populating Application Insights.

Nothing here is imported by ``logger`` itself — import the submodule you
need explicitly, e.g. ``from logger.integrations import gcp``.
"""
