# Flowdapt ccxt plugin

The plug-in lets you track a `whitelist` of crypto tokens on any exchange supported by CCXT while adaptively retraining and making predictions.

## Usage

After the plug-in is installed (see below), you can run the following commands (assuming `flowdapt run` was launched in a separate terminal to start the server):

```bash
flowctl apply -p flowdapt_cryptocast_plugin/workflows
flowctl apply -p flowdapt_cryptocast_plugin/configs
flowctl run create_features
flowctl run train
flowctl run predict --pair BTC/USDT:USDT
```

If you want your data scraping and train workflows to be scheduled, you can apply the schedule trigger:

```bash
flowctl apply -p flowdapt_cryptocast_plugin/schedules
```

## Getting predictions from the server

Getting predictions into any other application is easy, you simply use the `flowdapt_sdk`.



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

This repo adds `flowctl`, and `flowdapt_sdk` in the dependencies for convenience, so `poetry install` already installs them for you. But since they are not technically dependencies, the proper approach is to install them separately into your venv if you plan to use them.

```bash
pip install flowdapt_sdk
pip install flowctl
```



To test the stages and workflows, you have 2 options:

1. Run the command `pytest`, this will run the test suite which includes `test_stages.py` where the actual stage functions are tested in dummy workflows. The create_features, train, and predict workflows all run together in a session to  ensure the stage functions are working.

2. Run `flowdapt plugins install file://path/to/flowdapt-ccxt-plugin` to install the plugin in editable mode via flowdapt. To install AND add all of the definitions found in the plugin then install with `flowctl plugins install file://path/to/flowdapt-ccxt-plugin --include-definitions` while the server is running.