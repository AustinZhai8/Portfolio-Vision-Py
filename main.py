import json
from collections import defaultdict

# ── Load data ────────────────────────────────────────────────────────────────

with open("data/etf_data.json", "r") as f:
    DATA = json.load(f)

ETF_DATA = DATA["etfs"]
STOCK_DATA = DATA["stocks"]

TICKER_ALIASES = {
    "VFV": "VFV.TO",
    "QQC": "QQC.F",
    "XIU": "XIU.TO",
    "XIC": "XIC.TO",
    "VDY": "VDY.TO",
}

def resolve_ticker(ticker):
    t = ticker.upper()
    return TICKER_ALIASES.get(t, t)

# ── Helpers ──────────────────────────────────────────────────────────────────

def get_etf_holdings(etf_ticker):
    """Return list of {ticker, name, weight} for an ETF, resolving aliases."""
    etf = ETF_DATA.get(resolve_ticker(etf_ticker))
    if not etf:
        return None
    if "holdings_same_as" in etf:
        return get_etf_holdings(etf["holdings_same_as"])
    return etf["holdings"]


def is_etf(ticker):
    return resolve_ticker(ticker) in ETF_DATA


def decompose_portfolio(portfolio):
    """
    portfolio: dict of {ticker: dollar_amount}
    Returns a flat dict of {stock_ticker: dollar_exposure}
    """
    result = defaultdict(float)
    unknown = []

    for ticker, amount in portfolio.items():
        ticker = resolve_ticker(ticker)

        if is_etf(ticker):
            holdings = get_etf_holdings(ticker)
            if not holdings:
                unknown.append(ticker)
                continue

            total_weight = sum(h["weight"] for h in holdings)

            for holding in holdings:
                normalized = holding["weight"] / total_weight
                result[holding["ticker"].upper()] += amount * normalized

        else:
            # Treat as individual stock
            result[ticker] += amount

    return dict(result), unknown


def get_stock_info(ticker):
    info = STOCK_DATA.get(resolve_ticker(ticker), {})
    return {
        "name": info.get("name", ticker),
        "sector": info.get("sector", "Unknown"),
        "country": info.get("country", "Unknown"),
    }


def breakdown_by_sector(decomposed):
    sectors = defaultdict(float)
    for ticker, amount in decomposed.items():
        info = get_stock_info(ticker)
        sectors[info["sector"]] += amount
    return dict(sorted(sectors.items(), key=lambda x: x[1], reverse=True))


def breakdown_by_country(decomposed):
    countries = defaultdict(float)
    for ticker, amount in decomposed.items():
        info = get_stock_info(ticker)
        countries[info["country"]] += amount
    return dict(sorted(countries.items(), key=lambda x: x[1], reverse=True))


def print_report(portfolio, decomposed, sectors, countries, unknown):
    total = sum(decomposed.values())

    print("\n" + "=" * 60)
    print("PORTFOLIO DECOMPOSITION REPORT")
    print("=" * 60)

    print("\n── Input Portfolio ──")
    for ticker, amount in portfolio.items():
        label = "(ETF)" if is_etf(ticker.upper()) else "(Stock)"
        print(f"  {ticker:<12} {label}  ${amount:,.2f}")

    if unknown:
        print(f"\n⚠  Unrecognized tickers (skipped): {', '.join(unknown)}")

    print(f"\n── Decomposed Holdings (top 20 by exposure) ──")
    print(f"  {'Ticker':<10} {'Name':<40} {'Amount':>10}  {'%':>6}")
    print(f"  {'-'*10} {'-'*40} {'-'*10}  {'-'*6}")
    sorted_holdings = sorted(decomposed.items(), key=lambda x: x[1], reverse=True)
    for ticker, amount in sorted_holdings[:20]:
        info = get_stock_info(ticker)
        pct = (amount / total) * 100
        print(f"  {ticker:<10} {info['name']:<40} ${amount:>9,.2f}  {pct:>5.1f}%")
    if len(sorted_holdings) > 20:
        remaining = sum(v for _, v in sorted_holdings[20:])
        print(f"  {'...':<10} {'(remaining holdings)':<40} ${remaining:>9,.2f}  {(remaining/total)*100:>5.1f}%")

    print(f"\n── Sector Breakdown ──")
    for sector, amount in sectors.items():
        bar = "█" * int((amount / total) * 40)
        pct = (amount / total) * 100
        print(f"  {sector:<25} {bar:<40} {pct:>5.1f}%  (${amount:,.0f})")

    print(f"\n── Geographic Breakdown ──")
    for country, amount in countries.items():
        bar = "█" * int((amount / total) * 40)
        pct = (amount / total) * 100
        print(f"  {country:<25} {bar:<40} {pct:>5.1f}%  (${amount:,.0f})")

    print(f"\n  Total portfolio value: ${total:,.2f}")
    print("=" * 60 + "\n")


# ── Main ─────────────────────────────────────────────────────────────────────

def get_portfolio_from_user():
    print("\nEnter your portfolio.")
    print("Format: TICKER AMOUNT  (e.g. 'VFV.TO 5000' or 'AAPL 1000')")
    print("Type 'done' when finished.\n")

    portfolio = {}
    while True:
        entry = input("  > ").strip()
        if entry.lower() == "done":
            break
        parts = entry.split()
        if len(parts) != 2:
            print("  Invalid format. Add: TICKER AMOUNT")
            continue
        ticker, amount_str = parts
        try:
            amount = float(amount_str)
            portfolio[ticker.upper()] = amount
        except ValueError:
            print("  Amount must be a number.")
    return portfolio


if __name__ == "__main__":
    portfolio = get_portfolio_from_user()

    if not portfolio:
        print("No portfolio entered. Exiting.")
    else:
        decomposed, unknown = decompose_portfolio(portfolio)
        sectors = breakdown_by_sector(decomposed)
        countries = breakdown_by_country(decomposed)
        print_report(portfolio, decomposed, sectors, countries, unknown)