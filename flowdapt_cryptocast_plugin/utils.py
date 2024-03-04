from importlib import resources
from pathlib import Path
from flowdapt.compute import object_store
from flowdapt.compute.artifacts.misc import json_to_artifact, json_from_artifact


def get_package_datafile_path(filepath: str, package_name: str) -> Path:
    """
    Get the path of a file in the package data directory.

    :param filepath: Path to file in package data directory.
    :type filepath: str
    :param package_name: Name of package.
    :type package_name: str
    :return: The absolute file path.
    :rtype: str
    """
    return resources.files(package_name) / filepath


def signal_metric(workflow, metric_name, metric_value):
    """
    Helper function to signal a metric to the metric tracker
    """
    try:
        metric_tracker = object_store.get(
            "metric_tracker",
            artifact_only=True,
            load_artifact_hook=json_from_artifact()
        )
    except FileNotFoundError:
        metric_tracker = {}

    if workflow not in metric_tracker:
        metric_tracker[workflow] = {}
    if metric_name not in metric_tracker[workflow]:
        metric_tracker[workflow][metric_name] = []

    metric_tracker[workflow][metric_name].append(metric_value)

    if metric_name == "end_time":
        if "duration" not in metric_tracker[workflow]:
            metric_tracker[workflow]["duration"] = []
        duration = (metric_value - metric_tracker[workflow]["start_time"][-1]) / 60
        metric_tracker[workflow]["duration"].append(duration)

    object_store.put(
        "metric_tracker",
        metric_tracker,
        artifact_only=True,
        save_artifact_hook=json_to_artifact()
    )
