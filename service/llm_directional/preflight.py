"""Read-only readiness check; GET model metadata does not generate a response."""
import argparse
import os
from sqlalchemy import inspect
from .config import load_filter_config
from .repository import Repository, metadata
from .runner import assert_paper_account


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check-api', action='store_true', help='GET metadata modèle, aucun appel d’analyse')
    args = parser.parse_args()
    from dotenv import load_dotenv
    load_dotenv()
    config = load_filter_config()
    assert_paper_account()
    from database.connection import get_sqlalchemy_engine
    engine = get_sqlalchemy_engine()
    Repository(engine)
    missing = set(metadata.tables) - set(inspect(engine).get_table_names())
    print(f'Compte default PAPER; Oracle TOP{config.oracle_top_n} -> au plus {config.max_selected} LONG')
    print('Tables : ' + ('OK' if not missing else 'manquantes '+','.join(sorted(missing))))
    key = os.environ.get(config.api_key_env)
    print('OPENAI_API_KEY : ' + ('présente (valeur non affichée)' if key else 'absente'))
    if not key or missing:
        raise SystemExit(1)
    if args.check_api:
        from common.verified_http import verified_session
        try:
            response = verified_session().get(f'https://api.openai.com/v1/models/{config.model}',
                headers={'Authorization': f'Bearer {key}'}, timeout=(10, 20), allow_redirects=False)
        except Exception as exc:
            print(f'Accès API indisponible : {type(exc).__name__} (TLS reste vérifié)')
            raise SystemExit(1) from None
        print(f'Modèle {config.model} : HTTP {response.status_code}')
        if response.status_code != 200:
            print('Vérifier clé, projet et accès au modèle. Aucun modèle de remplacement automatique.')
            raise SystemExit(1)


if __name__ == '__main__':
    main()
