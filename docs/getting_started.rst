Getting Started
===============

Welcome to Comma Tools! This guide will help you get up and running with analyzing openpilot logs and CAN bus data.

Installation
------------

Prerequisites
~~~~~~~~~~~~~

- Python 3.8 or higher
- Git LFS (for test fixtures)
- openpilot checkout (for some tools)

Basic Installation
~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   git clone https://github.com/anteew/comma-tools.git
   cd comma-tools
   pip install -e .

Development Installation
~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: bash

   pip install -e ".[dev,docs]"

Managed External Repositories
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

The tools automatically clone the required openpilot and opendbc repositories if they are not available locally.

- openpilot: https://github.com/commaai/openpilot.git (branch ``master`` by default)
- opendbc: https://github.com/commaai/opendbc.git (branch ``master`` by default)

To track a different release channel, set ``OPENPILOT_BRANCH`` (for example ``release3`` or ``nightly``) before running the tools. The environment variables below also let you reuse existing clones:

Clones are stored under ``~/.cache/comma-tools/repos/`` so existing checkouts in your workspace are never touched. Set these environment variables before running tools if you want to reuse your own clones or select a different branch::

   export OPENPILOT_PATH=/path/to/openpilot
   export OPENPILOT_BRANCH=my-openpilot-branch
   export OPENDBC_PATH=/path/to/opendbc
   export OPENDBC_BRANCH=my-opendbc-branch

Directory Structure
-------------------

The repository is organized as follows:

.. code-block:: text

   comma-tools/
   ├── src/comma_tools/           # Main package
   │   ├── analyzers/            # Log analysis tools
   │   ├── monitors/             # Real-time monitoring
   │   ├── can/                  # CAN bus utilities
   │   ├── utils/                # Shared utilities
   │   └── visualization/        # Plotting tools
   ├── tests/                    # Test suite
   ├── scripts/                  # Shell script wrappers
   ├── docs/                     # Documentation
   └── knowledge/                # Technical knowledge base

Core Tools
----------

Cruise Control Analyzer
~~~~~~~~~~~~~~~~~~~~~~~~

The primary tool for analyzing cruise control behavior in openpilot logs:

.. code-block:: bash

   # Analyze a log file (first run)
   cruise-control-analyzer /path/to/logfile.zst --install-missing-deps

   # With custom speed range
   cruise-control-analyzer /path/to/logfile.zst --speed-min 50 --speed-max 60

RLog to CSV Converter
~~~~~~~~~~~~~~~~~~~~~

Convert openpilot rlog files to CSV format for further analysis:

.. code-block:: bash

   rlog-to-csv --rlog /path/to/logfile.zst --out output.csv --window-start 100.0 --window-dur 30.0

CAN Bitwatch Analyzer
~~~~~~~~~~~~~~~~~~~~~

Analyze CAN message bit patterns and changes:

.. code-block:: bash

   can-bitwatch --csv output.csv --output-prefix analysis/results --watch 0x027:B4b5 0x321:B5b1

Real-time Monitoring
~~~~~~~~~~~~~~~~~~~~

Monitor live CAN bus activity and Panda safety states:

.. code-block:: bash

   # Monitor Panda safety states
   python -m comma_tools.monitors.hybrid_rx_trace

   # Check CAN bus activity
   python -m comma_tools.monitors.can_bus_check

Testing
-------

The project ships with unit and integration tests. ``pytest`` now filters to the
unit suite by default so new contributors can get fast feedback without cloning
``openpilot`` or downloading large fixtures. Use these commands when working on
changes:

.. code-block:: bash

   # Run the default unit suite
   pytest

   # Focus on an individual module or test
   pytest tests/unit/test_cts_cli.py -k Renderer

   # Opt in to the integration scenarios
   pytest -m integration --real-log-file /path/to/log.zst

Install the optional CTS client extras (``pip install -e ".[client]"``) before
running the Connect CLI tests locally. They are skipped automatically when the
client dependencies are missing.

Next Steps
----------

- Check out the :doc:`api_reference` for detailed function documentation
- Browse the :doc:`examples` for common use cases
- Explore the :doc:`knowledge_base` for technical background
