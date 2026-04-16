import pandas as pd


def build_ticker_daily_features(article_df: pd.DataFrame, feature_version: str = "v1") -> pd.DataFrame:
    if article_df.empty:
        return pd.DataFrame(columns=["symbol", "trade_date"])

    df = article_df.copy()
    df = df[df["symbol"].notna()].copy()
    if df.empty:
        return pd.DataFrame(columns=["symbol", "trade_date"])

    df["trade_date"] = pd.to_datetime(df["effective_trade_date"]).dt.date
    df["after_close_flag"] = (df["market_session_tag"] == "post_market").astype(int)
    df["pre_market_flag"] = (df["market_session_tag"] == "pre_market").astype(int)

    inferred_major = (
        (df["is_major_event"].fillna(0).astype(int) == 1)
        | (
            (df["sentiment_confidence"].fillna(0.0) >= 0.85)
            & (df["sentiment_net_score"].abs().fillna(0.0) >= 0.60)
        )
    ).astype(int)

    grouped = (
        df.assign(inferred_major_event=inferred_major)
        .groupby(["symbol", "trade_date"], as_index=False)
        .agg(
            news_count_1d=("article_id", "nunique"),
            sentiment_pos_mean_1d=("positive_score", "mean"),
            sentiment_neg_mean_1d=("negative_score", "mean"),
            sentiment_neu_mean_1d=("neutral_score", "mean"),
            sentiment_net_mean_1d=("sentiment_net_score", "mean"),
            sentiment_net_sum_1d=("sentiment_net_score", "sum"),
            sentiment_confidence_mean_1d=("sentiment_confidence", "mean"),
            major_event_flag=("inferred_major_event", "max"),
            source_diversity_count=("source", "nunique"),
            after_close_news_count=("after_close_flag", "sum"),
            pre_market_news_count=("pre_market_flag", "sum"),
            latest_event_timestamp_ny=("event_timestamp_ny", "max"),
        )
    )
    grouped["feature_version"] = feature_version
    return grouped


def build_sector_daily_features(
    sector_article_df: pd.DataFrame,
    macro_df: pd.DataFrame,
    feature_version: str = "v1",
) -> pd.DataFrame:
    if sector_article_df.empty and macro_df.empty:
        return pd.DataFrame(columns=["sector", "trade_date"])

    sector_base = pd.DataFrame(columns=[
        "sector",
        "trade_date",
        "sector_news_count_1d",
        "sector_sentiment_net_mean_1d",
        "sector_sentiment_net_sum_1d",
        "sector_positive_ratio",
        "sector_negative_ratio",
        "latest_event_timestamp_ny",
    ])

    if not sector_article_df.empty:
        df = sector_article_df.copy()
        df = df[df["sector"].notna()].copy()
        if not df.empty:
            df["trade_date"] = pd.to_datetime(df["effective_trade_date"]).dt.date
            df["positive_flag"] = (df["sentiment_label"] == "positive").astype(int)
            df["negative_flag"] = (df["sentiment_label"] == "negative").astype(int)
            df = df.drop_duplicates(subset=["article_id", "sector", "trade_date"])
            sector_base = (
                df.groupby(["sector", "trade_date"], as_index=False)
                .agg(
                    sector_news_count_1d=("article_id", "nunique"),
                    sector_sentiment_net_mean_1d=("sentiment_net_score", "mean"),
                    sector_sentiment_net_sum_1d=("sentiment_net_score", "sum"),
                    sector_positive_ratio=("positive_flag", "mean"),
                    sector_negative_ratio=("negative_flag", "mean"),
                    latest_event_timestamp_ny=("event_timestamp_ny", "max"),
                )
            )

    if macro_df.empty:
        sector_base["sector_impact_score"] = 0.0
        sector_base["macro_event_flag"] = 0
        sector_base["macro_event_intensity"] = 0.0
        sector_base["feature_version"] = feature_version
        return sector_base

    macro = macro_df.copy()
    macro["trade_date"] = pd.to_datetime(macro["trade_date"]).dt.date
    macro_agg = (
        macro.groupby(["sector", "trade_date"], as_index=False)
        .agg(
            sector_impact_score=("impact_score", "sum"),
            macro_event_intensity=("macro_event_intensity", "max"),
        )
    )
    macro_agg["macro_event_flag"] = 1

    if sector_base.empty:
        merged = macro_agg.copy()
        merged["sector_news_count_1d"] = 0
        merged["sector_sentiment_net_mean_1d"] = 0.0
        merged["sector_sentiment_net_sum_1d"] = 0.0
        merged["sector_positive_ratio"] = 0.0
        merged["sector_negative_ratio"] = 0.0
        merged["latest_event_timestamp_ny"] = pd.NaT
    else:
        merged = sector_base.merge(macro_agg, how="outer", on=["sector", "trade_date"])

    merged["sector_news_count_1d"] = merged["sector_news_count_1d"].fillna(0).astype(int)
    merged["sector_sentiment_net_mean_1d"] = merged["sector_sentiment_net_mean_1d"].fillna(0.0)
    merged["sector_sentiment_net_sum_1d"] = merged["sector_sentiment_net_sum_1d"].fillna(0.0)
    merged["sector_positive_ratio"] = merged["sector_positive_ratio"].fillna(0.0)
    merged["sector_negative_ratio"] = merged["sector_negative_ratio"].fillna(0.0)
    merged["sector_impact_score"] = merged["sector_impact_score"].fillna(0.0).clip(-1.0, 1.0)
    merged["macro_event_flag"] = merged["macro_event_flag"].fillna(0).astype(int)
    merged["macro_event_intensity"] = merged["macro_event_intensity"].fillna(0.0)
    merged["feature_version"] = feature_version
    return merged

