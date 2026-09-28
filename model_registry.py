"""Reproducible search spaces for chronological model validation."""
from sklearn.ensemble import RandomForestClassifier, RandomForestRegressor, GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.linear_model import LogisticRegression, Ridge
from sklearn.svm import SVC, SVR
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler


def candidates(seed):
    result = {
        "logistic_regression": (LogisticRegression(max_iter=3000, random_state=seed),
                                Ridge(), {"C": [.01, .05, .1, .5, 1., 5., 10., 50.]}),
        "random_forest": (RandomForestClassifier(n_estimators=250, random_state=seed, n_jobs=-1),
                          RandomForestRegressor(n_estimators=250, random_state=seed, n_jobs=-1),
                          {"max_depth": [4, 8, 12, None],
                           "min_samples_leaf": [1, 3, 5, 10],
                           "max_features": ["sqrt", .7, 1.0]}),
        "gradient_boosting": (GradientBoostingClassifier(random_state=seed), GradientBoostingRegressor(random_state=seed),
                              {"n_estimators": [80, 150, 250],
                               "learning_rate": [.02, .05, .1],
                               "max_depth": [1, 2, 3],
                               "subsample": [.7, .85, 1.0]}),
        "svm": (SVC(), SVR(), {"C": [.1, .5, 1., 5., 10., 50.],
                                "kernel": ["linear", "rbf"],
                                "gamma": ["scale", .01, .1]}),
    }
    skipped = {}
    try:
        from xgboost import XGBClassifier, XGBRegressor
        result["xgboost"] = (XGBClassifier(n_estimators=200, n_jobs=1, random_state=seed),
                             XGBRegressor(n_estimators=200, n_jobs=1, random_state=seed),
                             {"max_depth": [2, 3, 5],
                              "learning_rate": [.02, .05, .1],
                              "reg_lambda": [1., 5., 10.],
                              "subsample": [.8, 1.0],
                              "colsample_bytree": [.8, 1.0]})
    except ImportError:
        skipped["xgboost"] = "Install requirements-optional.txt to include XGBoost"
    try:
        from lightgbm import LGBMClassifier, LGBMRegressor
        result["lightgbm"] = (LGBMClassifier(n_estimators=200, n_jobs=1, random_state=seed, verbosity=-1),
                              LGBMRegressor(n_estimators=200, n_jobs=1, random_state=seed, verbosity=-1),
                              {"num_leaves": [7, 15, 31],
                               "min_child_samples": [10, 20, 40],
                               "learning_rate": [.02, .05, .1],
                               "reg_lambda": [0., 1., 5.]})
    except ImportError:
        skipped["lightgbm"] = "Install requirements-optional.txt to include LightGBM"
    return result, skipped


def construct(name, classifier, regressor, params):
    from sklearn.base import clone
    params = dict(params)
    # This is a training control, not an estimator constructor argument.
    balance_alpha = float(params.pop("balance_alpha", 0.0))
    c, r = clone(classifier), clone(regressor)
    c.set_params(**params)
    rp = {key: value for key, value in params.items() if key in r.get_params()}
    if name == "logistic_regression":
        rp = {"alpha": 1 / params.get("C", 1)}
    r.set_params(**rp)
    # Fold-fitted scaling prevents full-dataset preprocessing leakage.
    if name in {"logistic_regression", "svm"}:
        c, r = make_pipeline(StandardScaler(), c), make_pipeline(StandardScaler(), r)
    c._trendsense_balance_alpha = balance_alpha
    return c, r
