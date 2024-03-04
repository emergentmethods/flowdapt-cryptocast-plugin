# Flowdapt ccxt plugin

The plug-in lets you track a `whitelist` of crypto tokens on any exchange supported by CCXT while adaptively retraining and making predictions.

## Installation

For development, run the following commands:
```bash
git clone git@gitlab.com:emergentmethods/flowdapt-cryptocast-plugin.git
cd flowdapt-cryptocast-plugin
python3 -m venv .venv
source .venv/bin/activate
  # Make sure poetry is installed
curl -sSL https://install.python-poetry.org | python3 -
poetry config http-basic.gitlab "dependencies" "$CI_DEP_TOKEN"
poetry install
pre-commit install
```

This repo adds `flowctl`, and `flowdapt_sdk` in the dependencies already for convenience, so `poetry install` already installs them for you. But since they are not technically dependencies, the proper approach is to install them separately into your venv:

```bash
pip install flowdapt_sdk
pip install flowctl
```


## Usage

After the plug-in is installed, you can run the following commands. Open a terminal and run:

```bash
flowdapt run
```

Next, open a separate and run the following commands:


```bash
flowctl apply -p flowdapt_cryptocast_plugin/workflows
flowctl apply -p flowdapt_cryptocast_plugin/configs
flowctl run create_features
flowctl run train
flowctl run predict_one --asset ETH-USDT
```

If you want your data scraping and train workflows to be scheduled, you can apply the schedule trigger:

```bash
flowctl apply -p flowdapt_cryptocast_plugin/schedules
```

While this is a simple approach to getting predictions from the command line, in practice, we will want to get these predictions into any other service running anywhere else on the internet. That is where the `flowdapt_sdk

## Getting predictions from the server

Getting predictions into any other application is easy, you simply use the `flowdapt_sdk`. You can find the example usage of the `flowdapt_sdk` in `scripts/test_client.py`:

```py
from flowdapt_sdk import FlowdaptSDK
import asyncio

"""
Example of how to use the FlowdaptSDK to run a workflow and obtain the
result.

This exact code can be placed inside `populate_indicators` to get a prediction
and use it in entry/exit critera.
"""

async def run_flowdapt_workflow(
    workflow_name: str,
    payload: dict
):

    async with FlowdaptSDK("http://localhost:8080", timeout=20) as client:
        response = await client.workflows.run_workflow(
            workflow_name,
            input=payload
        )

    return response.result


def main():
    payload = {"asset": "ETH-USDT"}
    response = asyncio.run(run_flowdapt_workflow("predict", payload))
    print(response)


if __name__ == '__main__':
    main()
```

## Configuring your Flowdapt server

By default, your flowdapt server will run with the `LocalExecutor`, which is great for local debugging. But when you are ready to run in production and at scale, you will want to configure your server to run with the `RayExecutor`. This can be done by changing one line in your `flowdapt.yaml` config (located by default at `/home/<USER>/.flowdapt/flowdapt.yaml` if you ran Flowdapt once already):

```yaml
name: flowdapt.blue-mink
rpc:
  api:
    host: 127.0.0.1
    port: 8080
  event_bus:
    url: memory://
database:
  __target__: flowdapt.lib.database.storage.tdb.TinyDBStorage
logging:
  level: DEBUG
  format: console
  include_trace_id: false
  show_tracebacks: true
  traceback_show_locals: false
  traceback_max_frames: 10
storage:
  protocol: file
  base_path: /home/<USER>/.flowdapt
  parameters: {}

services:
  compute:
    default_namespace: cryptocast
    run_retention_duration: 0
    executor:
      __target__: flowdapt.compute.executor.ray.RayExecutor
      cpus: 4
      gpus: "auto"
      resources:
        unique_resource: 2
```

You can also see that this is where you can add custom resources to your executor, make GPUs available, change the storage type (use S3 in production), change your DB type (use MongoDB in production).

More details about choosing/configuring your executor can be found [here](https://docs.flowdapt.ai/concepts/executor/#configuring-the-executor). Meanwhile, the full configuration options are available [here](https://docs.flowdapt.ai/reference/configuration/).


## Testing the plug-in

To test the stages and workflows, you have 2 options:

1. Run the command `pytest`, this will run the test suite which includes `test_stages.py` where the actual stage functions are tested in dummy workflows. The create_features, train, and predict workflows all run together in a session to  ensure the stage functions are working.
