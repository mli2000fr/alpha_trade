import argparse
import logging
import json
from pathlib import Path
import uuid
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import text
from common.universe_files import (
    is_universe_file_source,
    load_universe_file_symbols,
    normalize_universe_file_source,
)
from common.utils import configure_root_logging
from database.connection import get_sqlalchemy_engine
from event_sentiment.ingestion import NewsIngestionService
from event_sentiment.config import EventSentimentConfig
from event_sentiment.db_io import EventSentimentRepository
from event_sentiment.import_runtime import load_import_runtime, write_report, coverage_decision
from service._http_retry import _redact_sensitive_text

STOCK_BARS_DAILY_WARNING_THRESHOLD = 2000


def _normalize_symbols(symbols: list[str]) -> list[str]:
    seen: set[str] = set()
    normalized: list[str] = []
    for value in symbols:
        symbol = str(value).strip().upper()
        if not symbol or symbol in seen:
            continue
        seen.add(symbol)
        normalized.append(symbol)
    return normalized


def _load_distinct_symbols(query: str) -> list[str]:
    engine = get_sqlalchemy_engine()
    with engine.connect() as conn:
        result = conn.execute(text(query)).fetchall()
    return _normalize_symbols([row[0] for row in result])


def get_all_symbols_from_stock_bars_daily():
    """Retourne tous les symboles distincts présents dans stock_bars_daily."""
    return _load_distinct_symbols("SELECT DISTINCT symbol FROM stock_bars_daily ORDER BY symbol ASC")


def get_all_symbols_from_stock_scores(*, selected_only: bool = False) -> list[str]:
    """Retourne les symboles distincts présents dans stock_scores."""
    where_clause = "WHERE selection_rank IS NOT NULL" if selected_only else ""
    return _load_distinct_symbols(
        f"""
        SELECT DISTINCT symbol
        FROM stock_scores
        {where_clause}
        ORDER BY symbol ASC
        """
    )


def get_all_symbols_from_stock_scores_history() -> list[str]:
    """Retourne les symboles distincts présents dans stock_scores_history."""
    return _load_distinct_symbols(
        """
        SELECT DISTINCT symbol
        FROM stock_scores_history
        ORDER BY symbol ASC
        """
    )


def get_all_symbols_from_stock_scores_all() -> list[str]:
    """Retourne l'union dédupliquée des symboles présents dans stock_scores ou stock_scores_history."""
    return _load_distinct_symbols(
        """
        SELECT DISTINCT symbol
        FROM (
            SELECT symbol FROM stock_scores
            UNION
            SELECT symbol FROM stock_scores_history
        ) AS combined_symbols
        ORDER BY symbol ASC
        """
    )


def get_all_symbols_from_tradable_universe() -> list[str]:
    """Charge le dernier univers tradable PIT canonique et complet."""
    engine = get_sqlalchemy_engine()
    with engine.connect() as conn:
        run = conn.execute(
            text(
                """
                SELECT universe_run_id
                FROM tradable_universe_runs
                WHERE snapshot_date <= :trade_date
                  AND status = 'completed'
                  AND is_canonical = 1
                  AND rows_written = rows_expected
                  AND data_quality_grade = 'full'
                ORDER BY snapshot_date DESC, finished_at DESC
                LIMIT 1
                """
            ),
            {"trade_date": date.today()},
        ).scalar_one_or_none()
        if run is None:
            raise RuntimeError("Aucun univers tradable PIT canonique complet disponible pour le sentiment.")
        rows = conn.execute(
            text(
                """
                SELECT symbol
                FROM tradable_universe_history
                WHERE universe_run_id = :universe_run_id
                  AND is_tradable = 1
                ORDER BY symbol ASC
                """
            ),
            {"universe_run_id": run},
        ).fetchall()
    return _normalize_symbols([row[0] for row in rows])


def resolve_symbols_from_inputs(
    *,
    symbols_csv: str | None,
    symbol_source: str,
    repository: EventSentimentRepository,
    logger: logging.Logger | None = None,
) -> tuple[list[str], str]:
    if symbols_csv:
        return _normalize_symbols(symbols_csv.split(",")), "explicit"

    if is_universe_file_source(symbol_source):
        normalized_source = normalize_universe_file_source(symbol_source)
        return _normalize_symbols(load_universe_file_symbols(normalized_source)), normalized_source

    if symbol_source == "stock_bars_daily":
        return _normalize_symbols(get_all_symbols_from_stock_bars_daily()), "stock_bars_daily"

    if symbol_source == "stock_scores":
        return _normalize_symbols(get_all_symbols_from_stock_scores()), "stock_scores"

    if symbol_source == "stock_scores_history":
        return _normalize_symbols(get_all_symbols_from_stock_scores_history()), "stock_scores_history"

    if symbol_source == "stock_scores_all":
        return _normalize_symbols(get_all_symbols_from_stock_scores_all()), "stock_scores_all"

    if symbol_source == "tradable-universe":
        return _normalize_symbols(get_all_symbols_from_tradable_universe()), "tradable-universe"

    if symbol_source != "stock_scores_all" and logger is not None:
        logger.warning("Source de symboles inconnue '%s' ; fallback stock_scores_all.", symbol_source)
    return _normalize_symbols(get_all_symbols_from_stock_scores_all()), "stock_scores_all"


def resolve_symbols(
    args: argparse.Namespace,
    repository: EventSentimentRepository,
    logger: logging.Logger,
) -> tuple[list[str], str]:
    return resolve_symbols_from_inputs(
        symbols_csv=args.symbols,
        symbol_source=str(args.symbol_source),
        repository=repository,
        logger=logger,
    )


def _apply_symbol_guardrails(
    *,
    symbol_source: str,
    symbols: list[str],
    max_symbols: int | None,
    logger: logging.Logger,
    parser: argparse.ArgumentParser,
) -> None:
    symbol_count = len(symbols)
    if symbol_source == "stock_bars_daily" and symbol_count > STOCK_BARS_DAILY_WARNING_THRESHOLD:
        logger.warning(
            "Univers d'import très large détecté | source=%s symbol_count=%s threshold=%s. "
            "Préférez --symbol-source tradable-universe, une shortlist --symbols ou un cap --max-symbols.",
            symbol_source,
            symbol_count,
            STOCK_BARS_DAILY_WARNING_THRESHOLD,
        )
    if max_symbols is not None and max_symbols > 0 and symbol_count > max_symbols:
        parser.error(
            "Le nombre de symboles résolus ({0}) dépasse --max-symbols={1}. "
            "Réduisez l'univers (--symbol-source / --symbols) ou augmentez explicitement la limite.".format(
                symbol_count,
                max_symbols,
            )
        )


def _warn_ignored_scoring_flags(args: argparse.Namespace, logger: logging.Logger) -> None:
    ignored_flags: list[str] = []
    if args.sentiment_pending_limit is not None:
        ignored_flags.append("--sentiment-pending-limit")
    if args.sentiment_pending_max_batches is not None:
        ignored_flags.append("--sentiment-pending-max-batches")
    if args.finbert_batch_size is not None:
        ignored_flags.append("--finbert-batch-size")
    if ignored_flags:
        logger.warning(
            "Flags de scoring ignorés par importe_news.py : %s. "
            "Utilisez `python -m event_sentiment --skip-ingestion ...` ou le wrapper auto pour le scoring FinBERT.",
            ", ".join(ignored_flags),
        )


def _coerce_utc_datetime(value: object) -> datetime | None:
    if not isinstance(value, datetime):
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _resolve_checkpoint_aware_import_scope(
    *,
    symbols: list[str],
    start_utc: datetime,
    end_utc: datetime,
    repository: EventSentimentRepository,
    config: EventSentimentConfig,
    logger: logging.Logger,
) -> tuple[list[str], dict[str, datetime], dict[str, bool], int]:
    checkpoints = repository.get_checkpoints(config.source_name, symbols)
    start_overrides: dict[str, datetime] = {}
    resume_overrides: dict[str, bool] = {}
    selected_symbols: list[str] = []
    skipped_symbols = 0

    overlap = getattr(config, "checkpoint_overlap_minutes", 0)

    for symbol in symbols:
        checkpoint = checkpoints.get(symbol) or {}
        watermark = _coerce_utc_datetime(checkpoint.get("watermark_published_at_utc"))
        updated_at = _coerce_utc_datetime(checkpoint.get("updated_at"))
        successful = (checkpoint.get('status') in ('success', 'completed')
                      or ('status' not in checkpoint and watermark is not None))
        anchor = (watermark or updated_at) if successful else None
        if anchor is None:
            selected_symbols.append(symbol)
            start_overrides[symbol] = start_utc
            resume_overrides[symbol] = False
            continue

        if anchor >= end_utc:
            skipped_symbols += 1
            logger.info(
                "Import ignoré (checkpoint déjà à jour) | symbol=%s checkpoint=%s end=%s",
                symbol,
                anchor,
                end_utc,
            )
            continue

        effective_start = start_utc
        if watermark is not None:
            effective_start = max(start_utc, watermark - timedelta(minutes=int(overlap)))
        elif updated_at is not None:
            effective_start = max(start_utc, updated_at)

        selected_symbols.append(symbol)
        start_overrides[symbol] = effective_start
        # EODHD offsets cannot be reused after changing from/to.
        resume_overrides[symbol] = watermark is not None and getattr(config,'news_provider','eodhd') != 'eodhd'

    return selected_symbols, start_overrides, resume_overrides, skipped_symbols

# python ./event_sentiment/importe_news.py --start-date 2025-01-01 --end-date 2025-04-20

def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Importe les news sur une période donnée pour un univers de symboles ciblé. "
            "Par défaut, l'univers provient de stock_scores_all pour couvrir l'union du snapshot courant et de l'historique PIT."
        )
    )
    parser.add_argument(
        "--start-date",
        type=str,
        required=False,
        help=(
            "Date de début au format YYYY-MM-DD (ex: 2024-05-06). Si absente, "
            "fallback sur `initial_backfill_days` du provider choisi."
        ),
    )
    parser.add_argument("--end-date", type=str, required=False, help="Date de fin au format YYYY-MM-DD (ex: 2024-05-10). Par défaut: aujourd'hui.")
    parser.add_argument('--lookback-days',type=int,default=None,
                        help='Fenêtre récente si --start-date absent ; étape 8 : défaut configurable J-7/J.')
    parser.add_argument('--continue-on-symbol-error',action='store_true',
                        help='Isoler les erreurs fournisseur ; poursuivre si couverture configurée suffisante, sinon code 1.')
    parser.add_argument('--summary-path',type=Path,default=None,
                        help='Rapport final explicite, lu par le bilan de fin d’étape 8.')
    parser.add_argument(
        "--symbols",
        type=str,
        default=None,
        help="Liste explicite de symboles séparés par des virgules. Prioritaire sur --symbol-source.",
    )
    parser.add_argument(
        "--symbol-source",
        type=str,
        default="tradable-universe",
        help=(
            "Source des symboles à importer. 'tradable-universe' (défaut) cible le dernier univers PIT canonique complet ; "
            "'stock_scores_all' cible l'union dédupliquée des symboles présents dans stock_scores ou stock_scores_history ; "
            "'stock_scores' limite l'univers aux symboles suivis par le screener ; "
            "'stock_scores_history' cible les symboles déjà présents dans l'historique PIT ; "
            "'stock_bars_daily' conserve l'ancien comportement large ; "
            "'universe-file:<fichier.txt>' charge un fichier de config/univers/."
        ),
    )
    parser.add_argument(
        "--news-provider",
        type=str,
        choices=("alpaca", "finnhub", "eodhd"),
        default="eodhd",
        help="Source de news utilisée pour l'ingestion brute (défaut : eodhd).",
    )
    parser.add_argument(
        "--ticker-relevance-mode",
        type=str,
        choices=("provider_default", "strict", "scored"),
        default="provider_default",
        help="Mode de mapping article -> ticker réutilisé lors de l'import brut.",
    )
    parser.add_argument(
        "--min-relevance-score",
        type=float,
        default=None,
        help="Seuil minimum de pertinence [0,1] quand le mode 'scored' est actif.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=20,
        help="Nombre de symboles par batch d'import. Défaut 20.",
    )
    parser.add_argument(
        "--max-symbols",
        type=int,
        default=None,
        help=(
            "Garde-fou sécurité : si > 0, refuse l'exécution quand l'univers résolu dépasse cette limite. "
            "Exemple : 500."
        ),
    )
    parser.add_argument(
        "--resume-checkpoints",
        action="store_true",
        default=False,
        help=(
            "Réutilise news_ingestion_checkpoint pour reprendre l'import par symbole depuis le watermark connu, "
            "et saute les symboles déjà à jour par rapport à --end-date."
        ),
    )
    parser.add_argument(
        "--sentiment-pending-limit",
        type=int,
        default=None,
        help="Compatibilité CLI : ignoré par l'import brut ; réservé au scoring pending.",
    )
    parser.add_argument(
        "--sentiment-pending-max-batches",
        type=int,
        default=None,
        help="Compatibilité CLI : ignoré par l'import brut ; réservé au scoring pending.",
    )
    parser.add_argument(
        "--finbert-batch-size",
        type=int,
        default=None,
        help="Compatibilité CLI : ignoré par l'import brut ; réservé au scoring FinBERT.",
    )
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()
    runtime = load_import_runtime()
    if args.summary_path is not None and args.summary_path.exists():
        parser.error('--summary-path existe déjà ; choisir un nouveau rapport')
    if args.lookback_days is not None and not 1 <= args.lookback_days <= 36500:
        parser.error('--lookback-days doit être entre 1 et 36500')

    if args.end_date:
        end_date = datetime.strptime(args.end_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        end_date = datetime.now(timezone.utc)

    configure_root_logging(
        level=logging.INFO,
        log_path="./log/importe_news.log",
        fmt="%(asctime)s %(levelname)s %(message)s",
    )
    logger = logging.getLogger("importe_news")

    repository = EventSentimentRepository()
    symbols, symbol_source = resolve_symbols(args, repository, logger)
    _apply_symbol_guardrails(
        symbol_source=symbol_source,
        symbols=symbols,
        max_symbols=(int(args.max_symbols) if args.max_symbols is not None else None),
        logger=logger,
        parser=parser,
    )
    _warn_ignored_scoring_flags(args, logger)
    logger.info("Source de symboles retenue: %s", symbol_source)
    logger.info("%s symbols trouvés.", len(symbols))
    if not symbols:
        logger.warning("Aucun symbole à importer ; exécution terminée sans appel provider.")
        if args.summary_path is not None:
            write_report(args.summary_path,dict(status='COMPLETED',requested=0,failed_symbols=[],
                succeeded_symbols=0,skipped_symbols=0,unattempted_symbols=0,success_ratio=1.,
                coverage_status='COMPLETE',collection_complete=True,
                note='Univers vide : aucune requête fournisseur'))
        return

    config_overrides: dict[str, object] = {
        "provider_ticker_relevance_mode": args.ticker_relevance_mode,
        'news_request_timeout_seconds': runtime.request_timeout_seconds,
        'news_max_attempts': runtime.max_attempts,
    }
    if args.min_relevance_score is not None:
        config_overrides["min_relevance_score"] = float(args.min_relevance_score)
    config = EventSentimentConfig.for_provider(args.news_provider, **config_overrides)
    if args.start_date:
        start_date = datetime.strptime(args.start_date, "%Y-%m-%d").replace(tzinfo=timezone.utc)
    else:
        days = args.lookback_days if args.lookback_days is not None else int(config.initial_backfill_days)
        start_date = end_date - timedelta(days=days)
        logger.info(
            "Fenêtre import demandée | lookback_days=%s origine=%s start=%s end=%s ; checkpoints appliqués ensuite",
            days, 'lookback_days' if args.lookback_days is not None else 'initial_backfill_days',
            start_date,
            end_date,
        )
    ingestion = NewsIngestionService(repository=repository, config=config)

    symbol_start_overrides: dict[str, datetime] | None = None
    symbol_resume_overrides: dict[str, bool] | None = None
    requested_symbols = len(symbols)
    skipped_symbols = 0
    if args.resume_checkpoints:
        symbols, resolved_start_overrides, resolved_resume_overrides, skipped_symbols = _resolve_checkpoint_aware_import_scope(
            symbols=symbols,
            start_utc=start_date,
            end_utc=end_date,
            repository=repository,
            config=config,
            logger=logger,
        )
        symbol_start_overrides = resolved_start_overrides
        symbol_resume_overrides = resolved_resume_overrides
        logger.info(
            "Import checkpoint-aware | selected_symbols=%s skipped_symbols=%s end=%s",
            len(symbols),
            skipped_symbols,
            end_date,
        )
        if not symbols:
            logger.warning("Tous les symboles sont déjà à jour d'après news_ingestion_checkpoint ; aucun import provider nécessaire.")

    totals = dict(fetched=0,deduped=0,landed=0,ticker_maps=0)
    attempted = succeeded = consecutive = 0
    blocking_error = False
    errors = []
    run_id = 'news-import-'+uuid.uuid4().hex
    directory = Path(__file__).resolve().parents[1]/'artifacts/news_import_runs'/run_id
    state = dict(run_id=run_id,provider=args.news_provider,source_name=config.source_name,
                 window=[start_date.isoformat(),end_date.isoformat()],requested=requested_symbols,
                 skipped_symbols=skipped_symbols,status='RUNNING',finished_at=None)
    if args.continue_on_symbol_error:
        write_report(directory/'progress.json',state)
    batch_size = max(1, int(args.batch_size))
    for i in range(0, len(symbols), batch_size):
        batch = symbols[i:i+batch_size]
        logger.info(f"Traitement batch {i//batch_size+1} ({len(batch)} symbols): {batch}")
        resilience = {}
        if args.continue_on_symbol_error:
            def progress(payload):
                write_report(directory/'progress.json',{**state,
                    'attempted_symbols':attempted+payload['current_symbol_index'],
                    'current_symbol':payload['current_symbol'],
                    'effective_window_policy':'CHECKPOINT_SUCCESS_ONLY_REPLAY_EODHD_OFFSET_ZERO'})
            resilience = dict(continue_on_symbol_error=True,
                max_consecutive_failures=runtime.max_consecutive_symbol_failures,
                initial_consecutive_failures=consecutive,progress_callback=progress)
        scope = {}
        if args.resume_checkpoints:
            scope = dict(
                symbol_start_overrides={s:symbol_start_overrides[s] for s in batch} if symbol_start_overrides else None,
                symbol_resume_overrides={s:symbol_resume_overrides[s] for s in batch} if symbol_resume_overrides else None)
        try:
            summary = ingestion.run(start_utc=start_date,end_utc=end_date,symbols=batch,
                                    resume_checkpoints=False,**scope,**resilience)
        except Exception as exc:
            # SQL/programming errors are never downgraded to per-symbol skips.
            state.update(status='FAILED',finished_at=datetime.now(timezone.utc).isoformat(),
                         error=_redact_sensitive_text(str(exc))[:500],failed_symbols=errors,
                         last_committed_batch_metrics=dict(totals),
                         note='Interrupted batch counters may be partial; consult checkpoints, no success inferred')
            if args.continue_on_symbol_error:
                write_report(directory/'progress.json',state)
                write_report(directory/'report.json',state)
            if args.summary_path is not None:
                write_report(args.summary_path,state)
            raise
        logger.info(f"Résultat batch {i//batch_size+1}: {summary}")
        for key in totals:
            totals[key] += summary.get(key,0)
        attempted += summary.get('attempted_symbols',len(batch))
        succeeded += summary.get('succeeded_symbols',len(batch))
        errors.extend(summary.get('failed_symbols',[]))
        consecutive = summary.get('consecutive_failures',0)
        blocking_error = blocking_error or bool(summary.get('blocking_error')) or any(
            e.get('blocking_error') or e.get('status_code') in (401,403,429)
            for e in summary.get('failed_symbols',[]))
        if args.continue_on_symbol_error:
            state.update(attempted_symbols=attempted,succeeded_symbols=succeeded,
                         failed_symbols=errors,unattempted_symbols=len(symbols)-attempted,metrics=totals)
            write_report(directory/'progress.json',state)
        if summary.get('aborted'):
            logger.error('Arrêt borné de l’import : erreur globale/circuit ou échecs consécutifs ; titres restants non exécutés.')
            break

    decision=coverage_decision(requested_symbols,succeeded,skipped_symbols,
        runtime.min_success_ratio if args.continue_on_symbol_error else 1.,blocking_error=blocking_error)
    incomplete = not decision['coverage_accepted']
    state.update(**decision,status='INCOMPLETE' if incomplete else 'COMPLETED',finished_at=datetime.now(timezone.utc).isoformat(),
                 attempted_symbols=attempted,succeeded_symbols=succeeded,failed_symbols=errors,
                 unattempted_symbols=len(symbols)-attempted,metrics=totals,
                 counter_units=dict(requested='symbols',received='successful_or_skipped_symbols',persisted='news_rows'))
    if args.continue_on_symbol_error:
        write_report(directory/'progress.json',state)
        write_report(directory/'report.json',state)
        logger.info('Bilan import : %s ; rapport=%s',state['status'],directory/'report.json')
    if args.summary_path is not None:
        write_report(args.summary_path,state)
    logger.info('Bilan import news : %s symbole(s) KO / %s ; %s non exécuté(s) ; couverture %.2f%% ; %s',
                len(errors),requested_symbols,len(symbols)-attempted,100*decision['success_ratio'],decision['coverage_status'])
    print('::alpha_trade_run_summary::'+json.dumps(dict(batch='news_import',status=state['status'],
        requested=requested_symbols,received=succeeded+skipped_symbols,persisted=totals['landed'],
        failed=len(errors),warning_count=int(decision['coverage_status']=='PARTIAL_ACCEPTED'),
        error_message=f'{len(errors)} titre(s) en échec ; {len(symbols)-attempted} non exécuté(s)' if incomplete else '',
        details=state),ensure_ascii=False),flush=True)
    if incomplete:
        raise SystemExit(1)
    logger.info("Import des news terminé ; couverture acceptée selon le seuil configuré.")

if __name__ == "__main__":
    main()

