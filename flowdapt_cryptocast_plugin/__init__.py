# We can't use package metadata to get the version number because
# Ray has a bug where it doesn't install the module given the way we
# send it to the cluster. The code still runs there is just no
# package installation so the metadata is not available.
__version__ = "0.1.0"
