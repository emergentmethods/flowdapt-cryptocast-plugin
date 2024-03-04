import pytest
import logging

from flowdapt.compute.resources.workflow.execute import execute_workflow
# from flowdapt.compute.executor.ray import RayExecutor
from flowdapt.compute.executor.local import LocalExecutor

from flowdapt_cryptocast_plugin.stages import (
    create_asset_lists,
    get_asset_list,
    get_unique_assets,
    get_corr_assets,
    get_and_publish_data,
    construct_dataframes,
    train_pipeline,
    predict_pipeline,
)
from contextlib import contextmanager
import os

logger = logging.getLogger(__name__)

TESTING_NAMESPACE = "testing"


@contextmanager
def use_storage_config(protocol: str, base_path: str):
    os.environ["FLOWDAPT__STORAGE__PROTOCOL"] = protocol
    os.environ["FLOWDAPT__STORAGE__BASE_PATH"] = base_path

    yield

    del os.environ["FLOWDAPT__STORAGE__PROTOCOL"]
    del os.environ["FLOWDAPT__STORAGE__BASE_PATH"]



# Use a Session scoped Executor so any data persisted to the object store
# lives for the entire test run
@pytest.fixture(scope="session")
async def executor():
    try:
        executor = LocalExecutor(use_processes=False)  # RayExecutor(gpus=1)
        logger.info("Starting Executor")
        await executor.start()
        yield executor
    finally:
        logger.info("Closing Executor")
        await executor.close()

@pytest.fixture
def workflow_config():
    return {
        "study_identifier": "okx_test",
        "model_train_parameters": {
            "n_jobs": 4,
            "n_estimators": 5,
            "verbosity": 1,
            "epochs": 2,
            "batch_size": 5,
            "lookback": 6,
            "hidden_dim": 2048,
            "shuffle": False,
        },
        "data_config": {
            "origins": "okx",
            "frequencies": "5m",
            "whitelist": ["ETH-USDT", "ADA-USDT", "SOL-USDT"],
            "include_corr_pairlist": ["BTC-USDT"],
            "prediction_points": 5
        },
        "lookback": 6,
        "weight_factor": 0.9,
        "di_threshold": 5.0,
        "model_str": "flowml.PyTorchTransformer",
        "num_points": 450,
        "data_split_parameters": {
            "test_size": 0.05,
            "shuffle": False,
        },
        # We need this here for testing so we aren't actually writing any files
        "storage": {
            "protocol": "memory",
            "base_path": "test_data",
        }
    }


@pytest.fixture
def create_features_workflow():
    return {
        "metadata": {
            "name": "create_features",
        },
        "spec": {
            "stages": [
                {
                    "name": "create_asset_lists",
                    "target": create_asset_lists,
                },
                {
                    "name": "get_unique_assets",
                    "target": get_unique_assets,
                    "depends_on": ["create_asset_lists"]
                },
                {
                    "name": "get_and_publish_data",
                    "target": get_and_publish_data,
                    "depends_on": ["get_unique_assets"],
                    "type": "parameter"
                },
                {
                    "name": "get_asset_list",
                    "target": get_asset_list,
                    "depends_on": ["get_and_publish_data"],
                },
                {
                    "name": "construct_dataframes",
                    "target": construct_dataframes,
                    "depends_on": ["get_asset_list"],
                    "type": "parameter"
                }
            ]
        }
    }


@pytest.fixture
def train_pipeline_workflow():
    return {
        "metadata": {
            "name": "train",
        },
        "spec": {
            "stages": [
                {
                    "name": "get_asset_list",
                    "target": get_asset_list,
                },
                {
                    "name": "train_pipeline",
                    "target": train_pipeline,
                    "depends_on": ["get_asset_list"],
                    "type": "parameter",
                    "resources": {
                        "gpus": 0
                    }
                },
            ]
        }
    }

@pytest.fixture
def predict_pipeline_workflow():
    return {
        "metadata": {
            "name": "predict",
        },
        "spec": {
        "stages": [
            {
                "name": "get_asset_list",
                "target": get_asset_list,
            },
            {
                "name": "predict_pipeline",
                "target": predict_pipeline,
                "depends_on": ["get_asset_list"],
                "type": "parameter",
                "resources": {
                    "gpus": 0
                }
            },
        ]
    }
    }


async def test_create_features(create_features_workflow, executor, workflow_config):
    # We set return_result to True so any errors that are raised in the stage
    # are bubbled up here so we can see the traceback
    with use_storage_config(protocol="memory", base_path="testing_data"):
        result = await execute_workflow(
            workflow=create_features_workflow,
            input={},
            namespace=TESTING_NAMESPACE,
            return_result=True,
            executor=executor,
            config=workflow_config
        )



async def test_train_pipeline(train_pipeline_workflow, executor, workflow_config):
    with use_storage_config(protocol="memory", base_path="testing_data"):
        result = await execute_workflow(
            workflow=train_pipeline_workflow,
            input={},
            namespace=TESTING_NAMESPACE,
            return_result=True,
            executor=executor,
            config=workflow_config
        )



async def test_predict_pipeline(predict_pipeline_workflow, executor, workflow_config):
    with use_storage_config(protocol="memory", base_path="testing_data"):
        result = await execute_workflow(
            workflow=predict_pipeline_workflow,
            input={},
            namespace=TESTING_NAMESPACE,
            return_result=True,
            executor=executor,
            config=workflow_config
        )

