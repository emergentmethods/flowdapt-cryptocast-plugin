import pandas as pd
from datetime import timezone

from flowdapt.lib.logger import get_logger

from flowdapt.builtins.utils import (
    get_data_gap,
    merge_dataframes
)
from .api import download_data
import pandas_ta as ta

from flowdapt.compute import object_store
from flowdapt.compute.resources.workflow.context import get_run_context
from flowml.pipefill import PipeFill
import datasieve.transforms as ds
from datasieve.pipeline import Pipeline
from datasieve.transforms import SKLearnWrapper
from sklearn.preprocessing import MinMaxScaler
from flowdapt.compute.artifacts.dataset import dataframe_to_artifact, dataframe_from_artifact
from flowdapt.builtins import utils
import flowml.utils as mlutils

ATF_ONLY = False

logger = get_logger(__name__)


def create_asset_lists():
    """
    STAGE
    Creates the asset list that will be used for parameterized
    stages.
    """
    data_config = get_run_context().config["data_config"]

    asset_list = data_config["whitelist"]
    corr_assets = data_config["include_corr_pairlist"]
    # make new list from all unique calues of asset_list and corr_assets
    unique_assets = list(set(asset_list + corr_assets))
    object_store.put("asset_list", asset_list)
    object_store.put("unique_assets", unique_assets)
    object_store.put("corr_assets", corr_assets)
    return

def get_asset_list(*args):
    return object_store.get("asset_list")

def get_unique_assets(*args):
    return object_store.get("unique_assets")

def get_corr_assets(*args):
    return object_store.get("corr_assets")


def get_and_publish_data(asset: str):

    logger.info(f"Updating data for {asset}")
    ml_config = get_run_context().config
    data_config = ml_config["data_config"]
    name_str = utils.artifact_name_from_dict(
        {"exchange": data_config["origins"], "symbol": asset,
         "interval": data_config["frequencies"]}
    )

    # FIXME: should we wrap this sort of stuff up into a function or keep it here?
    try:
        df = object_store.get(f"{name_str}_raw", artifact_only=True,
                              load_artifact_hook=dataframe_from_artifact(format="parquet"))
        logger.info(f"Found {name_str}_raw in artifact with len {len(df.index)}")
    except FileNotFoundError:
        df = pd.DataFrame()

    if len(df.index) == 0:
        n_bars = ml_config["num_points"]
    else:
        if len(df) < ml_config["num_points"]:
            n_bars = ml_config["num_points"]
        else:
            n_bars = get_data_gap(df, timezone.utc)

    if n_bars > 0:
        df_inc = download_data(symbol=asset,
                               exchange=data_config["origins"],
                               interval=data_config["frequencies"],
                               n_bars=n_bars)

        if len(df.index) > 0:
            df = merge_dataframes(df, df_inc)
        else:
            df = df_inc

    object_store.put(f"{name_str}_raw", df, artifact_only=True,
                     save_artifact_hook=dataframe_to_artifact(format="parquet"))
    df = df.tail(ml_config["num_points"])

    df = feature_engineering(asset, df)

    object_store.put(
        f"{name_str}_features",
        df,
        save_artifact_hook=dataframe_to_artifact(format="parquet")
    )

    return


def construct_dataframes(asset: str) -> str:
    """
    STAGE
    Look for published features and concatenates them into
    a single DF to be used for training.
    """

    ml_config = get_run_context().config
    data_config = ml_config["data_config"]
    name_dict = {"exchange": data_config["origins"], "symbol": asset,
                 "interval": data_config["frequencies"]}
    name_str = utils.artifact_name_from_dict(name_dict)

    # get features for the current source
    df = object_store.get(f"{name_str}_features")

    # concatenate features from all auxilary sources
    for name in data_config["include_corr_pairlist"]:
        if name == asset:
            # avoid grabbing the current source twice
            continue
        name_dict["symbol"] = name
        aux_str = f'{utils.artifact_name_from_dict(name_dict)}_features'

        # pull auxilary features from cluster memory
        df_aux = object_store.get(aux_str)
        df = pd.merge(df, df_aux, how='left', on='date')

    df = set_targets(asset, df)

    object_store.put(f"{name_str}_prepped_df", df,
                     save_artifact_hook=dataframe_to_artifact(format="parquet"))

    return asset


def feature_engineering(asset: str, df) -> dict:
    """
    User created feature engineering stage
    """

    # add features by prepending columns with "%"
    def add_features(df: pd.DataFrame, aux_df: pd.DataFrame, name: str):
        df = df.copy()
        df[f"%-{name}-raw_close"] = aux_df["close"]
        df[f"%-{name}-raw_open"] = aux_df["open"]
        df[f"%-{name}-raw_low"] = aux_df["low"]
        df[f"%-{name}-raw_high"] = aux_df["high"]
        df[f"%-{name}-RSI_20"] = ta.rsi(df["close"], length=20)
        df[f"%-{name}-EMA_40"] = ta.ema(df["close"], length=40)
        df[f"%-{name}-SMA_10"] = ta.sma(df["close"], length=10)
        return df

    df = add_features(df, df, asset)

    skip_columns = [
        s for s in ["open", "high", "low", "close", "volume"]
    ]
    df = df.drop(columns=skip_columns)

    return df


def set_targets(asset: str, df: pd.DataFrame):
    """
    STAGE
    User created stage for setting the targets in the training
    workflow.
    """
    col = f"%-{asset}-raw_close"
    df["&-close"] = df[col].shift(-5).rolling(5).mean() / \
        df[col] - 1

    return df


def train_pipeline(asset: str):
    """
    Parameterized Stage
    Training pipeline
    :param asset: one asset from the parameterized list for
    this stage.
    """

    ml_config = get_run_context().config
    data_config = ml_config["data_config"]
    name_str = utils.artifact_name_from_dict(
        {"exchange": data_config["origins"], "symbol": asset,
         "interval": data_config["frequencies"]}
    )

    # check the object store, prefering cluster memory
    # FIXME: should we wrap this try except up or leave it here?
    # Load the pipefill from the object store
    try:
        pf: PipeFill = object_store.get(
            f"pipefill-{name_str}",
            artifact_only=ATF_ONLY,
            load_artifact_hook=PipeFill.from_artifact()
        )
    except (KeyError, FileNotFoundError):
        pf = PipeFill(
            name_str=f"pipefill-{name_str}",
            namespace=ml_config["study_identifier"],
            model_str=ml_config["model_str"],
            model_train_params=ml_config["model_train_parameters"],
            data_split_params=ml_config["data_split_parameters"],
            extras=ml_config
        )

    raw_df = object_store.get(f"{name_str}_prepped_df",
                              load_artifact_hook=dataframe_from_artifact(format="parquet"))

    raw_df = utils.remove_none_columns(raw_df, threshold=40)
    raw_df = utils.remove_rows_with_nans(raw_df)

    logger.info(f"Analyzed df for {asset}, {raw_df}")
    features, labels = utils.extract_features_and_labels(raw_df)

    if features.empty or labels.empty:
        logger.warning(f"No features or labels found for {asset}")
        return 4

    # helper function to automatically split the train and test datasets inside the
    # pipefill and create the eval_set
    # labels = labels.filter(regex=target)
    pf.feature_list = features.columns
    pf.label_list = labels.columns

    data_params = ml_config["data_split_parameters"]
    w_factor = ml_config["weight_factor"]
    X, X_test, y, y_test, w, w_test = mlutils.make_train_test_datasets(
        features,
        labels,
        w_factor,
        data_params
    )

    # make the data preprocessing pipeline dict containing all the params that the user
    # wants to pass to each step. They can miss them if they dont want to pass values
    # (use defaults)
    fitparams: dict[str, dict] = {}
    pf.feature_pipeline = Pipeline([
        ("raw_scaler", SKLearnWrapper(MinMaxScaler())),
        ("detect_constants", ds.VarianceThreshold(threshold=0)),
    ],
        fitparams)

    # fit the feature pipeline to the features and transform them in one call
    X, y, w = pf.feature_pipeline.fit_transform(X, y, w)
    # transform the test set using the fitted pipeline
    X_test, y_test, w_test = pf.feature_pipeline.transform(X_test, y_test, w_test)

    # the labels require a separate pipeline (the objects are fit in a the label parameter
    # space.)
    pf.target_pipeline = Pipeline([
        ("scaler", SKLearnWrapper(MinMaxScaler()))
    ], fitparams)

    y, _, _ = pf.target_pipeline.fit_transform(y)
    y_test, _, _ = pf.target_pipeline.transform(y_test)

    eval_set = [(X_test, y_test)]

    pf.model.fit(X, y, eval_set=eval_set)

    pf.set_trained_timestamp()
    # Add to cluster memory for quicker access
    object_store.put(
        f"pipefill-{name_str}",
        pf,
        artifact_only=ATF_ONLY,
        save_artifact_hook=pf.to_artifact()
    )

    return


def predict_pipeline(asset: str):
    """
    Parameterized Stage
    Predict stage
    """
    ml_config = get_run_context().config
    data_config = ml_config["data_config"]
    name_str = utils.artifact_name_from_dict(
        {"exchange": data_config["origins"], "symbol": asset,
         "interval": data_config["frequencies"]}
    )

    num_points = ml_config["lookback"]

    pf = object_store.get(f"pipefill-{name_str}",
                          load_artifact_hook=PipeFill.from_artifact())
    raw_df = object_store.get(f"{name_str}_prepped_df",
                              load_artifact_hook=dataframe_from_artifact(format="parquet"))
    raw_df = raw_df.tail(num_points)
    logger.info(f"Analyzed pred df for {asset}, {raw_df}")

    features, _ = utils.extract_features_and_labels(raw_df)
    features = features.filter(items=pf.feature_list, axis=1)
    features = utils.remove_rows_with_nans(features)

    features, _, _ = pf.feature_pipeline.transform(features)

    preds = pf.model.predict(features)

    preds, _, _ = pf.target_pipeline.inverse_transform(preds.reshape(-1, 1))

    preds = preds.to_numpy()

    logger.info(f"preds for {asset} \n {preds} ")

    return {"asset": asset, "preds": preds.tolist()}
