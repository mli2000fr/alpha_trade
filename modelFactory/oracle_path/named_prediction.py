"""Keep the fitted feature contract through preprocessing and LightGBM.

Older per-symbol pipelines impute to NumPy arrays. LightGBM assigned these
columns the names Column_0, Column_1, etc. Preserve those archived names after
checking the original input and transformed column order; never edit weights.
"""
import pandas as pd


def predict_proba(model, frame, expected_features):
    from lightgbm import LGBMClassifier
    from sklearn.pipeline import Pipeline

    expected = list(expected_features)
    if (not isinstance(frame, pd.DataFrame) or frame.columns.has_duplicates
            or list(frame.columns) != expected):
        raise ValueError('Per-symbol : noms ou ordre des variables incompatibles avec le contrat')
    fitted = getattr(model, 'feature_names_in_', None)
    if fitted is not None and list(fitted) != expected:
        raise ValueError('Per-symbol : variables du modèle différentes du contrat')
    if not isinstance(model, Pipeline) or not isinstance(model.steps[-1][1], LGBMClassifier):
        return model.predict_proba(frame)

    preprocessing, estimator = model[:-1], model.steps[-1][1]
    transformed_names = list(preprocessing.get_feature_names_out(expected))
    values = preprocessing.transform(frame)
    fitted_names = list(estimator.feature_name_)
    legacy_names = [f'Column_{i}' for i in range(len(transformed_names))]
    if fitted_names not in (transformed_names, legacy_names):
        raise ValueError('Per-symbol : colonnes LightGBM différentes de la préparation entraînée')
    if isinstance(values, pd.DataFrame):
        if list(values.columns) != transformed_names:
            raise ValueError('Per-symbol : ordre des colonnes transformées incompatible')
        values = values.to_numpy(copy=False)
    if values.shape != (len(frame), len(fitted_names)):
        raise ValueError('Per-symbol : dimension transformée incompatible avec LightGBM')
    named = pd.DataFrame(values, index=frame.index, columns=fitted_names)
    return estimator.predict_proba(named, validate_features=True)
