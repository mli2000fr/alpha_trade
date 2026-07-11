# 🧠 ISecteurs métier principaux
---
sector_code	sector_name
TECHNOLOGY	Technology
HEALTHCARE	Healthcare
FINANCIALS	Financial Services
INDUSTRIALS	Industrials
CONSUMER_CYCLICAL	Consumer Cyclical
CONSUMER_DEFENSIVE	Consumer Defensive
ENERGY	Energy
BASIC_MATERIALS	Basic Materials
REAL_ESTATE	Real Estate
UTILITIES	Utilities
COMMUNICATION_SERVICES	Communication Services
TRANSPORTATION	Transportation & Logistics
ALLOCATION	Allocation & Multi-Asset
FIXED_INCOME	Fixed Income
MUNICIPAL_BONDS	Municipal Bonds
GOVERNMENT_BONDS	Government Bonds
EMERGING_MARKETS	Emerging Markets
INTERNATIONAL_EQUITY	International Equity
COMMODITIES	Commodities
ALTERNATIVES	Alternatives & Hedge Funds
DIGITAL_ASSETS	Digital Assets
MONEY_MARKET	Money Market
TARGET_DATE	Target Date
OTHER	Other / Miscellaneous
---

# 🧠 IMPORTANT PRINCIPLE

We normalize using **provider_sector only** (Yahoo/Finnhub input).

```text
provider_sector → SQL rules → sector (final)
```

---

# 🚨 STEP 0 — SAFETY RESET (recommended)

Add provider_sector column (if not exists)
```sql
ALTER TABLE alpha_trade.stock_metadata
ADD COLUMN provider_sector VARCHAR(120) NULL
COMMENT 'Raw sector/category from Yahoo or Finnhub';
```
```sql
UPDATE alpha_trade.stock_metadata
SET sector = NULL;
```

---

# 🏗️ STEP 1 — Mapping sector

#-- Technology
UPDATE stock_metadata
SET sector = 'Technology'
WHERE provider_sector IN (
    'Technology',
    'Semiconductors',
    'Communication Services',
    'Telecommunication'
);

-- Digital Assets
UPDATE stock_metadata
SET sector = 'Digital Assets'
WHERE provider_sector IN (
    'Digital Assets',
    'Equity Digital Assets'
);

-- Healthcare
UPDATE stock_metadata
SET sector = 'Healthcare'
WHERE provider_sector IN (
    'Biotechnology',
    'Health Care',
    'Healthcare',
    'Health',
    'Pharmaceuticals',
    'Life Sciences Tools & Services'
);

-- Financial Services
UPDATE stock_metadata
SET sector = 'Financial Services'
WHERE provider_sector IN (
    'Financial Services',
    'Financial',
    'Insurance',
    'Banking',
    'Preferred Stock',
    'Bank Loan'
);

-- Industrials
UPDATE stock_metadata
SET sector = 'Industrials'
WHERE provider_sector IN (
    'Industrials',
    'Industrial Conglomerates',
    'Construction',
    'Building',
    'Machinery',
    'Electrical Equipment',
    'Commercial Services & Supplies',
    'Professional Services',
    'Trading Companies & Distributors',
    'Distributors',
    'Aerospace & Defense',
    'Infrastructure'
);

-- Transportation
UPDATE stock_metadata
SET sector = 'Transportation'
WHERE provider_sector IN (
    'Airlines',
    'Marine',
    'Road & Rail',
    'Transportation Infrastructure',
    'Logistics & Transportation'
);

-- Consumer Cyclical
UPDATE stock_metadata
SET sector = 'Consumer Cyclical'
WHERE provider_sector IN (
    'Retail',
    'Hotels, Restaurants & Leisure',
    'Consumer products',
    'Consumer Cyclical',
    'Automobiles',
    'Auto Components',
    'Leisure Products',
    'Media',
    'Diversified Consumer Services',
    'Textiles, Apparel & Luxury Goods'
);

-- Consumer Defensive
UPDATE stock_metadata
SET sector = 'Consumer Defensive'
WHERE provider_sector IN (
    'Consumer Defensive',
    'Food Products',
    'Beverages',
    'Tobacco'
);

-- Energy
UPDATE stock_metadata
SET sector = 'Energy'
WHERE provider_sector IN (
    'Energy',
    'Energy Limited Partnership',
    'Equity Energy'
);

-- Basic Materials
UPDATE stock_metadata
SET sector = 'Basic Materials'
WHERE provider_sector IN (
    'Basic Materials',
    'Chemicals',
    'Metals & Mining',
    'Paper & Forest',
    'Packaging',
    'Natural Resources'
);

-- Real Estate
UPDATE stock_metadata
SET sector = 'Real Estate'
WHERE provider_sector IN (
    'Real Estate',
    'Global Real Estate'
);

-- Utilities
UPDATE stock_metadata
SET sector = 'Utilities'
WHERE provider_sector = 'Utilities';

-- Communication Services
UPDATE stock_metadata
SET sector = 'Communication Services'
WHERE provider_sector = 'Communications';

-- Allocation
UPDATE stock_metadata
SET sector = 'Allocation'
WHERE provider_sector IN (
    'Aggressive Allocation',
    'Moderate Allocation',
    'Conservative Allocation',
    'Moderately Conservative Allocation',
    'Moderately Aggressive Allocation',
    'Global Aggressive Allocation',
    'Global Moderate Allocation',
    'Global Moderately Aggressive Allocation',
    'Global Moderately Conservative Allocation',
    'Global Conservative Allocation',
    'Tactical Allocation',
    'Miscellaneous Allocation',
    'Multi-Asset Overlay'
);

-- Fixed Income
UPDATE stock_metadata
SET sector = 'Fixed Income'
WHERE provider_sector IN (
    'Corporate Bond',
    'Multisector Bond',
    'Intermediate Core Bond',
    'Intermediate Core-Plus Bond',
    'Short-Term Bond',
    'Long-Term Bond',
    'High Yield Bond',
    'Nontraditional Bond',
    'Convertibles',
    'Emerging Markets Bond',
    'Global Bond',
    'Global Bond-USD Hedged',
    'Inflation-Protected Bond',
    'Short-Term Inflation-Protected Bond',
    'Securitized Bond - Diversified',
    'Securitized Bond - Focused',
    'Miscellaneous Fixed Income',
    'Derivative Income',
    'Ultrashort Bond'
);

-- Government Bonds
UPDATE stock_metadata
SET sector = 'Government Bonds'
WHERE provider_sector IN (
    'Intermediate Government',
    'Long Government',
    'Short Government',
    'Government Mortgage-Backed Bond'
);

-- Municipal Bonds
UPDATE stock_metadata
SET sector = 'Municipal Bonds'
WHERE provider_sector LIKE 'Muni%'
   OR provider_sector = 'High Yield Muni';

-- International Equity
UPDATE stock_metadata
SET sector = 'International Equity'
WHERE provider_sector IN (
    'Foreign Large Growth',
    'Foreign Large Blend',
    'Foreign Large Value',
    'Foreign Small/Mid Growth',
    'Foreign Small/Mid Blend',
    'Foreign Small/Mid Value',
    'Global Large-Stock Blend',
    'Global Large-Stock Growth',
    'Global Large-Stock Value',
    'Global Small/Mid Stock',
    'Europe Stock',
    'Japan Stock',
    'Pacific/Asia ex-Japan Stk',
    'Focused Region',
    'Single Currency'
);

-- Emerging Markets
UPDATE stock_metadata
SET sector = 'Emerging Markets'
WHERE provider_sector IN (
    'Greater China Region',
    'India Equity',
    'Diversified Emerging Mkts',
    'Emerging-Markets Local-Currency Bond'
);

-- Commodities
UPDATE stock_metadata
SET sector = 'Commodities'
WHERE provider_sector IN (
    'Commodities Broad Basket',
    'Commodities Focused',
    'Equity Precious Metals'
);

-- Alternatives
UPDATE stock_metadata
SET sector = 'Alternatives'
WHERE provider_sector IN (
    'Long-Short Equity',
    'Equity Hedged',
    'Equity Market Neutral',
    'Macro Trading',
    'Systematic Trend',
    'Multistrategy',
    'Event Driven',
    'Relative Value Arbitrage',
    'Defined Outcome',
    'Trading--Leveraged Equity',
    'Trading--Inverse Equity',
    'Trading--Miscellaneous',
    'Trading--Leveraged Commodities',
    'Trading--Inverse Commodities',
    'Trading--Inverse Debt',
    'Trading--Leveraged Debt'
);

-- Target Date
UPDATE stock_metadata
SET sector = 'Target Date'
WHERE provider_sector LIKE 'Target-Date%'
   OR provider_sector = 'Target Maturity';

-- Money Market
UPDATE stock_metadata
SET sector = 'Money Market'
WHERE provider_sector IN (
    'Money Market-Taxable',
    'Prime Money Market'
);

-- Other
UPDATE stock_metadata
SET sector = 'Other'
WHERE sector IS NULL;