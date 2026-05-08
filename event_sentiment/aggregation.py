from typing import cast

import pandas as pd


DEFAULT_ROLLING_WINDOWS = (3, 5, 10, 20)


def _safe_series_divide(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    clean_denominator = denominator.replace(0, float("nan"))
    return numerator.divide(clean_denominator).fillna(0.0)


def _coerce_trade_date(series: pd.Series) -> pd.Series:
    return cast(pd.Series, pd.to_datetime(series, errors="coerce").dt.date)


def _rolling_sum(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=1).sum()


def _rolling_max(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=1).max()


def build_ticker_daily_features(
    article_df: pd.DataFrame,
    feature_version: str = "v2",
    rolling_windows: tuple[int, ...] = DEFAULT_ROLLING_WINDOWS,
) -> pd.DataFrame:
    if article_df.empty:
        return pd.DataFrame(columns=["symbol", "trade_date"])

    df = article_df.copy()
    df = df[df["symbol"].notna()].copy()
    if df.empty:
        return pd.DataFrame(columns=["symbol", "trade_date"])

    df.loc[:, "trade_date"] = _coerce_trade_date(df["effective_trade_date"])
    df.loc[:, "after_close_flag"] = (df["market_session_tag"] == "post_market").astype(int)
    df.loc[:, "pre_market_flag"] = (df["market_session_tag"] == "pre_market").astype(int)

    # Relevance scoring (Niveau 2/3) : pondération article→symbole pour
    # les agrégats de sentiment. Rétro-compat : colonne absente ou NULL ⇒
    # poids 1.0 (les anciennes lignes / le mode ``provider_default``
    # retombent sur la moyenne arithmétique d'origine).
    if "relevance_score" not in df.columns:
        df.loc[:, "relevance_score"] = 1.0
    df.loc[:, "relevance_score"] = (
        pd.to_numeric(df["relevance_score"], errors="coerce")
        .fillna(1.0)
        .clip(lower=0.0, upper=1.0)
    )
    df.loc[:, "_w_net"] = df["sentiment_net_score"] * df["relevance_score"]
    df.loc[:, "_w_pos"] = df["positive_score"] * df["relevance_score"]
    df.loc[:, "_w_neg"] = df["negative_score"] * df["relevance_score"]
    df.loc[:, "_w_neu"] = df["neutral_score"] * df["relevance_score"]
    df.loc[:, "_w_conf"] = df["sentiment_confidence"] * df["relevance_score"]

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
            relevance_weight_sum_1d=("relevance_score", "sum"),
            _w_net_sum_1d=("_w_net", "sum"),
            _w_pos_sum_1d=("_w_pos", "sum"),
            _w_neg_sum_1d=("_w_neg", "sum"),
            _w_neu_sum_1d=("_w_neu", "sum"),
            _w_conf_sum_1d=("_w_conf", "sum"),
            major_event_flag=("inferred_major_event", "max"),
            source_diversity_count=("source", "nunique"),
            after_close_news_count=("after_close_flag", "sum"),
            pre_market_news_count=("pre_market_flag", "sum"),
            latest_event_timestamp_ny=("event_timestamp_ny", "max"),
        )
        .sort_values(["symbol", "trade_date"])
        .reset_index(drop=True)
    )

    # Moyennes pondérées par relevance_score (avec fallback w=1.0,
    # rétro-compat : produit la moyenne arithmétique).
    weight_sum = grouped["relevance_weight_sum_1d"]
    grouped["sentiment_net_mean_1d"] = _safe_series_divide(grouped["_w_net_sum_1d"], weight_sum)
    grouped["sentiment_pos_mean_1d"] = _safe_series_divide(grouped["_w_pos_sum_1d"], weight_sum)
    grouped["sentiment_neg_mean_1d"] = _safe_series_divide(grouped["_w_neg_sum_1d"], weight_sum)
    grouped["sentiment_neu_mean_1d"] = _safe_series_divide(grouped["_w_neu_sum_1d"], weight_sum)
    grouped["sentiment_confidence_mean_1d"] = _safe_series_divide(grouped["_w_conf_sum_1d"], weight_sum)
    grouped["sentiment_net_sum_1d"] = grouped["_w_net_sum_1d"]

    grouped["_major_event_day_count_1d"] = grouped["major_event_flag"].astype(int)

    for window in rolling_windows:
        grouped[f"news_count_{window}d"] = (
            grouped.groupby("symbol", group_keys=False)["news_count_1d"].transform(lambda series: _rolling_sum(series, window)).round().astype(int)
        )
        grouped[f"relevance_weight_sum_{window}d"] = grouped.groupby("symbol", group_keys=False)["relevance_weight_sum_1d"].transform(
            lambda series: _rolling_sum(series, window)
        )
        grouped[f"sentiment_net_sum_{window}d"] = grouped.groupby("symbol", group_keys=False)["_w_net_sum_1d"].transform(
            lambda series: _rolling_sum(series, window)
        )
        grouped[f"sentiment_net_mean_{window}d"] = _safe_series_divide(
            grouped[f"sentiment_net_sum_{window}d"],
            grouped[f"relevance_weight_sum_{window}d"],
        )
        confidence_sum_col = f"_w_conf_sum_{window}d"
        grouped[confidence_sum_col] = grouped.groupby("symbol", group_keys=False)["_w_conf_sum_1d"].transform(
            lambda series: _rolling_sum(series, window)
        )
        grouped[f"sentiment_confidence_mean_{window}d"] = _safe_series_divide(
            grouped[confidence_sum_col],
            grouped[f"relevance_weight_sum_{window}d"],
        )
        grouped[f"major_event_day_count_{window}d"] = (
            grouped.groupby("symbol", group_keys=False)["_major_event_day_count_1d"].transform(lambda series: _rolling_sum(series, window)).round().astype(int)
        )

    grouped = grouped.drop(
        columns=[
            "_w_net_sum_1d",
            "_w_pos_sum_1d",
            "_w_neg_sum_1d",
            "_w_neu_sum_1d",
            "_w_conf_sum_1d",
            "_major_event_day_count_1d",
        ]
        + [f"_w_conf_sum_{window}d" for window in rolling_windows]
    )
    grouped["feature_version"] = feature_version
    return grouped


def build_sector_daily_features(
    sector_article_df: pd.DataFrame,
    macro_df: pd.DataFrame,
    feature_version: str = "v2",
    rolling_windows: tuple[int, ...] = DEFAULT_ROLLING_WINDOWS,
) -> pd.DataFrame:
    if sector_article_df.empty and macro_df.empty:
        return pd.DataFrame(columns=["sector", "trade_date"])

    sector_base = pd.DataFrame(
        columns=[
            "sector",
            "trade_date",
            "sector_news_count_1d",
            "sector_sentiment_net_mean_1d",
            "sector_sentiment_net_sum_1d",
            "sector_positive_ratio",
            "sector_negative_ratio",
            "latest_event_timestamp_ny",
        ]
    )

    if not sector_article_df.empty:
        df = sector_article_df.copy()
        df = df[df["sector"].notna()].copy()
        if not df.empty:
            df.loc[:, "trade_date"] = _coerce_trade_date(df["effective_trade_date"])
            df.loc[:, "positive_flag"] = (df["sentiment_label"] == "positive").astype(int)
            df.loc[:, "negative_flag"] = (df["sentiment_label"] == "negative").astype(int)
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
        macro_agg = pd.DataFrame(columns=["sector", "trade_date", "sector_impact_score", "macro_event_intensity", "macro_event_flag"])
    else:
        macro = macro_df.copy()
        macro.loc[:, "trade_date"] = _coerce_trade_date(macro["trade_date"])
        macro_agg = (
            macro.groupby(["sector", "trade_date"], as_index=False)
            .agg(
                sector_impact_score=("impact_score", "sum"),
                macro_event_intensity=("macro_event_intensity", "max"),
            )
        )
        macro_agg["macro_event_flag"] = 1

    if sector_base.empty and macro_agg.empty:
        return pd.DataFrame(columns=["sector", "trade_date"])
    if sector_base.empty:
        merged = macro_agg.copy()
        merged["sector_news_count_1d"] = 0
        merged["sector_sentiment_net_mean_1d"] = 0.0
        merged["sector_sentiment_net_sum_1d"] = 0.0
        merged["sector_positive_ratio"] = 0.0
        merged["sector_negative_ratio"] = 0.0
        merged["latest_event_timestamp_ny"] = pd.NaT
    elif macro_agg.empty:
        merged = sector_base.copy()
        merged["sector_impact_score"] = 0.0
        merged["macro_event_flag"] = 0
        merged["macro_event_intensity"] = 0.0
    else:
        merged = sector_base.merge(macro_agg, how="outer", on=["sector", "trade_date"])

    merged = merged.sort_values(["sector", "trade_date"]).reset_index(drop=True)
    merged["sector_news_count_1d"] = merged["sector_news_count_1d"].fillna(0).astype(int)
    merged["sector_sentiment_net_mean_1d"] = merged["sector_sentiment_net_mean_1d"].fillna(0.0)
    merged["sector_sentiment_net_sum_1d"] = merged["sector_sentiment_net_sum_1d"].fillna(0.0)
    merged["sector_positive_ratio"] = merged["sector_positive_ratio"].fillna(0.0)
    merged["sector_negative_ratio"] = merged["sector_negative_ratio"].fillna(0.0)
    merged["sector_impact_score"] = merged["sector_impact_score"].fillna(0.0).clip(-1.0, 1.0)
    merged["macro_event_flag"] = merged["macro_event_flag"].fillna(0).astype(int)
    merged["macro_event_intensity"] = merged["macro_event_intensity"].fillna(0.0)
    merged["_macro_event_day_count_1d"] = merged["macro_event_flag"].astype(int)

    for window in rolling_windows:
        merged[f"sector_news_count_{window}d"] = (
            merged.groupby("sector", group_keys=False)["sector_news_count_1d"].transform(lambda series: _rolling_sum(series, window)).round().astype(int)
        )
        merged[f"sector_sentiment_net_sum_{window}d"] = merged.groupby("sector", group_keys=False)["sector_sentiment_net_sum_1d"].transform(
            lambda series: _rolling_sum(series, window)
        )
        merged[f"sector_sentiment_net_mean_{window}d"] = _safe_series_divide(
            merged[f"sector_sentiment_net_sum_{window}d"],
            merged[f"sector_news_count_{window}d"],
        )
        merged[f"sector_impact_score_{window}d"] = merged.groupby("sector", group_keys=False)["sector_impact_score"].transform(
            lambda series: series.rolling(window=window, min_periods=1).mean()
        ).clip(-1.0, 1.0)
        merged[f"macro_event_intensity_{window}d"] = merged.groupby("sector", group_keys=False)["macro_event_intensity"].transform(
            lambda series: _rolling_max(series, window)
        )
        merged[f"macro_event_day_count_{window}d"] = (
            merged.groupby("sector", group_keys=False)["_macro_event_day_count_1d"].transform(lambda series: _rolling_sum(series, window)).round().astype(int)
        )

    merged = merged.drop(columns=["_macro_event_day_count_1d"])
    merged["feature_version"] = feature_version
    return merged

