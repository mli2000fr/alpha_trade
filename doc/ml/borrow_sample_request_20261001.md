# Draft request — historical securities-lending sample

**Status:** local draft only; not sent to any vendor.

**Subject:** Point-in-time US equity securities-lending sample for research feasibility

Hello,

We are evaluating whether historical securities-lending data can support a point-in-time research study. Before discussing a full license, could you provide a sample for the **50 US equity tickers** in the attached `borrow_pilot_50_symbols_20261001.csv`, covering **2018-07-05 through 2025-07-11**? If available, data beginning in 2016 would let us compute trailing changes. Please also include a separate small example of **ten delisted equities**, with permanent identifiers and delisting dates, so we can verify historical identity handling.

For each security, observation and revision, we need:

1. Historical ticker and permanent security identifier, including ticker and corporate-action mapping.
2. Observation timestamp and **first time the exact value was available to a customer**, both with time zone. Please identify whether an EOD value published on T+1 would have been available before 09:25 Eastern Time on T+1.
3. Borrow fee or rebate rate, with units and a precise definition (indicative, bid/offer, new loan, outstanding loan or executable broker quote).
4. Shares available or lendable supply, with the contributing-lender universe and units.
5. Utilization and shares on loan if available.
6. Revision/correction history and method changes. We need original versions as they appeared at the time, not only values restated in today's backfill.

Could you also provide a field dictionary, sample coverage by year and symbol, the distinction between aggregated market availability and an executable locate, and the terms for local retention, historical backtesting and ML training? Please state any charge for this sample separately from a full historical license. We will first evaluate coverage and temporal integrity; this request is not a commitment to purchase.

Thank you.

---

**Internal handling:** Attach only `D:\Projet\doc\ml\borrow_pilot_50_symbols_20261001.csv`. Keep Oracle labels, OOF scores and model artifacts internal. Run the local PIT audit described in `D:\Projet\doc\ml\borrow_pilot_feasibility_20261001.md` on any sample received. No message has been sent from this draft.
