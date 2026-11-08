# Replay Winner : prix daily présents et volume nul

Le run IHM `20261108_113321_fbd87bec` s'est arrêté pour une position TPB
détenue le 18 juin 2026 : `Missing daily opening for held positions`.

La lecture SQL a confirmé une ligne EODHD non remplie artificiellement,
ajustée split : ouverture 79,76, haut 82,18, bas 78,49, clôture 82,02,
mais volume déclaré 0. Les 69 bougies SIP régulières ne couvrent pas les
78 créneaux attendus. Le lecteur daily rejetait tous les champs lorsque le
volume n'était pas strictement positif ; le repli OHLC perdait alors aussi
l'ouverture pourtant présente.

`backtesting/winner_data.py` qualifie désormais les prix séparément du volume :
les prix OHLC doivent rester positifs et cohérents ; le volume doit être connu
et non négatif. Un zéro est conservé à zéro, avec avertissement listant au plus
vingt couples symbole/date. Aucun volume, aucune bougie, aucune exécution
intermédiaire n'est inventé. Les lignes remplies, raw, sans ouverture,
incohérentes ou à volume négatif/inconnu restent rejetées. La préférence de
fournisseur reste inchangée.

Le mode journalier utilise les protections OHLC déjà existantes lorsque la
séance 5m est incomplète. La précision reste limitée et le statut de couverture
incomplète reste visible. Une position réellement sans prix utilisable continue
à bloquer ; elle n'est pas effacée rétrospectivement.

Validation : cours TPB retrouvés avec le lecteur corrigé en SQL lecture seule ;
16 tests passent (prix daily et protections journalières, dont sortie d'une
position détenue avec volume nul et séance 5m incomplète). Aucun changement
SQL ni appel fournisseur. Les anciens artefacts et entrées de recherche figées
ne sont pas réécrits ; un nouveau lancement IHM relit le lecteur corrigé.

Le FutureWarning pandas sur la concaténation n'est pas la cause de l'arrêt.
