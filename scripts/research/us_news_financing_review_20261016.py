"""Fixed technical reading of the frozen 20 screened pairs and 10 controls.

Not an extractor, LLM API call, independent review, historical signal or PnL.
Unknown texts or changed quotations require a new reading, not inference.
"""
from collections import Counter
from datetime import datetime, timezone
import argparse
import json
from pathlib import Path

from sqlalchemy import bindparam, create_engine, text

from scripts.research import us_news_event_qualification as evidence


def note(issuer,kind,symbols,category,quote,explanation,instrument=None):
    return dict(issuer=issuer,kind=kind,symbols=set(symbols),category=category,
                quote=quote,explanation=explanation,instrument=instrument)


NOTES={
 'eodhd:c05d358864ecca1d610e670d':note('SentinelOne','DEBT_ONLY',{'S'},'OTHER_ISSUER_FINANCING',
    'the company announced plans to offer $1.25 billion in convertible senior notes due 2031 in a private placement.',
    'The debt issue belongs to SentinelOne, not FLEX; Flex has a spin-off discussion.'),
 'eodhd:ff92f25a0c589c9b5e01d58d':note('IonQ','PRIMARY_EQUITY_FINANCING',{'IONQ'},'OTHER_ISSUER_FINANCING',
    'the company announced the pricing of a $2.0 billion equity offering to accelerate the commercialization of its full-stack quantum platform.',
    'The offering belongs to IONQ, not BAC; BAC is discussed for earnings and a penalty.'),
 'eodhd:73ae9051b1fcc65ba77270e1':note('Brookfield Corporation','PRIMARY_EQUITY_FINANCING',{'BN'},'PREFERRED_NOT_COMMON',
    'The Preferred Shares, Series 56 will be issued at a price of C$25.00 per share, for aggregate gross proceeds of C$150,000,000',
    'Issuer BN is explicit. Canadian preferred shares, not a new common-share issue. Prior announcement history is not certified.',
    'PREFERRED_SHARES'),
 'eodhd:3afc410927742cb90b78cdd8':note('Onto Innovation','DEBT_ONLY',{'ONTO'},'OTHER_ISSUER_HISTORICAL_DEBT',
    'In May, ONTO issued $1.5 billion of 0% convertible notes due in 2031.',
    'Old ONTO debt is not a new issuance by competitor Nova/NVMI. Nova is discussed for cash and a September buyback.'),
 'eodhd:3b899efb6359b38640293748':note('Tesla','OTHER',{'TSLA'},'MARKET_ROUNDUP_NOT_ISSUANCE',
    'Tesla unveiled a redesigned Roadster on Thursday evening which used SpaceX rocket technology to jump off a ramp and perform a controlled landing.',
    'Product launch, macro roundup and possible Anthropic IPO; no new Tesla equity financing.'),
 'eodhd:c42b7d80e3215b5fb09cb083':note('Primo Brands Corporation','SECONDARY_RESALE',{'PRMB'},'RETROSPECTIVE_SECONDARY_RESALE',
    'a large shareholder announced plans to liquidate a portion of its position through a secondary offering',
    'Q3 fund-letter retrospective: selling shareholder and company repurchase, not a newly announced primary capital raise. COKE is a related-story link.'),
 'eodhd:d28dc83d1e4bbae0dd8cc510':note('Synopsys, Inc.','PRIMARY_EQUITY_FINANCING',{'SNPS'},'HISTORICAL_FINANCING',
    'In 2025, Synopsys issued about 4.8 million shares in a private placement with NVIDIA for $2 billion of net proceeds.',
    'Explicit 2025 financing recalled in 2026 investment commentary; not a new event.'),
 'eodhd:a9b78f8f0add2d36f16e9e5a':note('Cracker Barrel','DEBT_ONLY',{'CBRL'},'HISTORICAL_DEBT_REPAYMENT',
    'the company repaid $150 million of maturing convertible notes',
    'Repayment of old Cracker Barrel debt within a multi-company broker-screen article. Not a new equity raise for CBRL, BZH, CLF or BBWI.'),
 'eodhd:fb11162c382e8f16463cee0d':note('Stardust Solar Energy Inc.','DEBT_ONLY',set(),'CROSS_MARKET_TICKER_COLLISION',
    'Stardust Solar Energy Inc. (TSXV: SUN) (OTCQB: SUNXF)',
    'Canadian SUN/SUNXF is not NYSE Sunoco SUN. Previously announced convertible debenture units with warrants, not an issue by Sunoco.',
    'CONVERTIBLE_DEBENTURES_WITH_WARRANTS'),
 'eodhd:7a90304349ecda45b93b3293':note('Sysco Corporation','OTHER',{'SYY'},'RELATED_STORY_LINK_ONLY',
    'Sysco prices 12.3M-share offering at $81 each to help finance Jetro purchase',
    'Offering is a MORE ON SYSCO related link; the article body is a labor agreement. No offering publication date or new-issue proof from that link.'),
 'eodhd:fc17a6bd1387f61f31f5790e':note('American Electric Power Company, Inc.','PRIMARY_EQUITY_FINANCING',{'AEP'},'HISTORICAL_FINANCING',
    'it announced a $2.6 billion stock offering in May 2026',
    'Explicit May financing recalled in October commentary, not a new announcement.'),
 'eodhd:73e32cf6233bdb995ab220cb':note('Elite Express Holding Inc.','OTHER',{'ETS'},'OTHER_ISSUER_OLD_IPO',
    'Elite Express Holding Inc. ("ETS" or the "Company") (Nasdaq: ETS)',
    'ETS earnings and use of previous IPO proceeds, not a new IPO or primary issue by Costco COST.'),
 'eodhd:d26ef885d661e29fd63e98d2':note('Aircastle Limited','DEBT_ONLY',set(),'OTHER_ISSUER_BOILERPLATE',
    'statements relating to our proposed public offering of notes',
    'Aircastle earnings; offering wording is in forward-looking boilerplate. Aircraft purchases do not make Airbus EADSY the financing issuer.'),
 'eodhd:fbc3f4226b1f1d85c71eec43':note('United Therapeutics','OTHER',{'UTHR'},'MARKET_ROUNDUP_NOT_ISSUANCE',
    'resolving six ongoing lawsuits and securing continued commercialization of YUTREPIA',
    'UTHR is party to a settlement. IPO wording concerns Moonshot and Bank of America, not financing by UTHR.'),
 'eodhd:58edc8a43a0af35f7a7a1282':note('Red Lake Gold Inc.','PRIMARY_EQUITY_FINANCING',set(),'CROSS_MARKET_TICKER_COLLISION',
    'Red Lake Gold Inc. (CSE: RGLD)',
    'CSE Red Lake Gold is not NASDAQ Royal Gold RGLD. Closing of a second tranche previously announced on August 31; do not backdate a new signal.'),
 'eodhd:4dfb14c73131447372f692b6':note('Iambic Therapeutics Inc.','PRIMARY_EQUITY_FINANCING',{'IAM'},'OTHER_ISSUER_FINANCING',
    'The company trades on the Nasdaq Global Select Market under the symbol IAM.',
    'IPO issuer is IAM; TAK is a relationship/partner, not the issuing company. Repeated IPO stories must not be counted as independent events.'),
 'eodhd:e51dc9d6a3c38988ae80bb81':note('First BanCorp.','OTHER',{'FBP'},'WRONG_ISSUER_CONTROL',
    'First BanCorp (FBP) is expected to deliver a year-over-year increase in earnings',
    'FBP earnings preview is not FB Financial FBK. No primary equity event.'),
 'eodhd:8ab80a2af7733b9900931a12':note('Emerson Electric','OTHER',{'EMR'},'ANALYST_COMMENTARY_CONTROL',
    '3. Emerson Electric (EMR)',
    'Analyst sector picks, operational forecasts and guidance discussion, not new equity issuance.'),
 'eodhd:385df8014e1a754fa3c6bcfa':note('Cameco Corporation','OTHER',{'CCJ'},'SECTOR_COMMENTARY_CONTROL',
    'Cameco supplies uranium fuel, reactor technology, and related services',
    'Canadian Cameco discussed as a thematic holding. Current local metadata identifies CCJ as Cameco; no historical cross-listing proof or new financing.'),
 'eodhd:f4f3388bc154f15b2f5ba09f':note('Visa','OTHER',{'V'},'OPERATING_EVENT_CONTROL',
    'Visa advanced its stablecoin strategy by moving Visa Direct stablecoin prefunding from pilots into commercial use',
    'Commercial payout/funding product is not a primary share issue by Visa.'),
 'eodhd:21ebf18eca6c621814d23983':note('Morgan Stanley','OTHER',{'MS'},'OTHER_ISSUER_CONTROL',
    'Morgan Stanley is set to report third-quarter earnings before the opening bell Wednesday.',
    'JPM is a comparator in Morgan Stanley earnings preview, not the reporting issuer. No new primary financing.'),
 'eodhd:3ef57f937144f2af7c829c53':note('Skyworks Solutions','OTHER',{'SWKS'},'INVESTMENT_COMMENTARY_CONTROL',
    'Skyworks Solutions (NASDAQ: SWKS) is a designer and manufacturer of chips',
    'Multi-company valuation/operating commentary, no new issue. Historical promotional returns are not evidence of a signal.'),
 'eodhd:ad987b2c964d3a679bdb27b6':note('Taiwan Semiconductor Manufacturing Co.','OTHER',{'TSM'},'MARKET_COMMENTARY_CONTROL',
    'earnings due later Thursday from Taiwan Semiconductor Manufacturing Co.',
    'Semiconductor market/rates roundup; financial stress of another company does not establish financing by TSM.'),
 'eodhd:be4a466203e8ca1734c5a76e':note('Nutrien Ltd.','OTHER',{'NTR'},'INVESTMENT_COMMENTARY_CONTROL',
    'Nutrien Ltd. NTR is benefiting from favorable demand for crop nutrients',
    'Demand, cost and guidance commentary, not a new equity issue.'),
 'eodhd:8f2d55a7bd8b726294b19403':note('Vital Farms','OTHER',{'VITL'},'PARTNER_CONTROL',
    'Vital Farms (Nasdaq: VITL) announced today the launch of the "Behind Every Carton" campaign',
    'Vital Farms brand campaign hosted partly in Sprouts SFM stores. SFM is a distributor/partner, not an equity issuer.'),
 'eodhd:bb78ad988345c3b1df95cfac':note('MSCI Inc.','OTHER',{'MSCI'},'INDEX_DECISION_CONTROL',
    'MSCI considers Indonesia\'s continued classification as an Emerging Market no longer appropriate',
    'Index-classification consultation, not a capital raise by MSCI; do not infer MSCI-share direction from the Indonesian index move.'),
}


def annotations(items,now,reference_hash):
    if len(items)!=30 or sum(r['screened'] for r in items)!=20 or {r['article_id'] for r in items}!=set(NOTES):
        raise ValueError('This fixed reading requires exactly the frozen 20+10 sample')
    reviews=[]
    for item in items:
        record=NOTES[item['article_id']]
        quote=record['quote']
        start=item['fields']['content'].index(quote)
        category=record['category']
        if item['article_id']=='eodhd:c42b7d80e3215b5fb09cb083' and item['symbol']=='COKE':
            category='OTHER_ISSUER_SECONDARY_RESALE'
        reviews.append(dict(evidence_key=item['evidence_key'],
            reviewer='Codex technical reading; NOT independent human review',reviewed_at_utc=now.isoformat(),
            issuer_name=record['issuer'],identity_verified=item['symbol'] in record['symbols'],
            identity_meaning='Issuer/subject of the financing clause, not every company mentioned in the article',
            event_type=record['kind'],new_announcement_verified=None if category=='PREFERRED_NOT_COMMON' else False,
            prior_comparison_complete=False,
            novelty_evidence='Frozen archive is a bounded J-7/J collection; earlier announcements and all syndication are not certified. '+record['explanation'],
            quotes=[dict(field='content',start=start,end=start+len(quote),text=quote)],facts=[],
            notes=record['explanation'],review_category=category,instrument_class=record['instrument'],
            common_equity_scope_qualified=False,
            full_archived_body_read=True,reading_display='Full body text, URL destinations masked for readability; original source offsets retained',
            current_reference_sha256=reference_hash,current_reference_is_historical_pit=False))
    return reviews


def run(pack):
    report=json.loads((pack/'report.json').read_text(encoding='utf-8'))
    for name,expected in report['files'].items():
        if Path(name).name!=name or evidence.sha(pack/name)!=expected:
            raise ValueError('Changed source pack')
    items=json.loads((pack/'evidence.json').read_text(encoding='utf-8'))
    from database.connection import get_sqlalchemy_engine
    engine=create_engine(get_sqlalchemy_engine().url,pool_size=1,max_overflow=0,pool_pre_ping=True,
        connect_args={'connect_timeout':10,'read_timeout':25,'write_timeout':10},echo=False)
    try:
        with engine.connect() as conn:
            conn.execute(text('SET SESSION TRANSACTION READ ONLY'))
            conn.execute(text('SET SESSION MAX_EXECUTION_TIME=15000'))
            if conn.execute(text('SELECT DATABASE()')).scalar_one()!='alpha_trade':
                raise ValueError('US schema required')
            query=text('''SELECT symbol,company_name,exchange,data_source,metadata_synced_at
                FROM stock_metadata WHERE symbol IN :symbols''').bindparams(bindparam('symbols',expanding=True))
            references=[dict(r) for r in conn.execute(query,{'symbols':sorted({r['symbol'] for r in items})}).mappings()]
            conn.rollback()
    finally:
        engine.dispose()
    evidence.save(pack/'technical_reference_snapshot.json',dict(rows=references,
        observed_at_utc=datetime.now(timezone.utc),current_only=True,historical_pit=False,
        source='stock_metadata READ ONLY',unknown_metadata_timestamp_not_invented=True))
    rows=annotations(items,datetime.now(timezone.utc),evidence.sha(pack/'technical_reference_snapshot.json'))
    evidence.save(pack/'technical_review_filled.json',rows)
    result=evidence.review_pack(pack,pack/'technical_review_filled.json',pack/'technical_review_result.json')
    screened=[r for r,item in zip(rows,items) if item['screened']]
    summary=dict(status='BOUNDED_REVIEW_COMPLETED_NO_QUALIFIED_NEW_COMMON_EQUITY_EVENT',
        reviewed_pairs=len(rows),screened_pairs=len(screened),control_pairs=len(rows)-len(screened),
        distinct_texts_read=len(NOTES),screened_category_counts=dict(Counter(r['review_category'] for r in screened)),
        control_category_counts=dict(Counter(r['review_category'] for r,item in zip(rows,items) if not item['screened'])),
        qualified_events=sum(r['status']=='QUALIFIED_RESEARCH_EVENT' for r in result['results']),
        reviewed_issuer_subject_mismatch_pairs=sum(not r['identity_verified'] for r in rows),
        unreviewed_selected_pairs=result['unreviewed_pairs'],event_absence_in_full_corpus_proven=False,
        independent_review_certified=False,sql_writes=False,api_calls=0,llm_calls=0,
        source_report_sha256=evidence.sha(pack/'report.json'),code_sha256=evidence.sha(Path(__file__)))
    evidence.save(pack/'technical_review_summary.json',summary)
    return summary


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--pack',type=Path,required=True)
    print(json.dumps(run(parser.parse_args().pack),ensure_ascii=False))
