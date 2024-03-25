.. _annotation_ref:

Time series annotation
======================

The :mod:`sktime.annotation` module contains algorithms and tools
for time series annotation tasks, like anomaly/outlier detection,
and time series segmentation.

Time Series Segmentation
------------------------

.. currentmodule:: sktime.annotation

.. autosummary::
    :toctree: auto_generated/
    :template: class.rst

    ClaSPSegmentation
    EAgglo
    HMM
    PoissonHMM
    GaussianHMM
    GMMHMM
    GreedyGaussianSegmentation
    InformationGainSegmentation
    STRAY

Adapters
--------

.. currentmodule:: sktime.annotation.adapters

.. autosummary::
    :toctree: auto_generated/
    :template: class.rst

    PyODAnnotator

Data Generation
---------------

.. automodule:: sktime.annotation.datagen
    :no-members:
    :no-inherited-members:
