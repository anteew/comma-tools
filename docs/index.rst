Comma Tools Documentation
==========================

Debugging and analysis tools for the openpilot autonomous driving system.

.. toctree::
   :maxdepth: 2
   :caption: Contents:

   getting_started
   api_reference
   examples
   knowledge_base
   PHONE_A_FRIEND_MCP_PLAN

Getting Started
===============

Comma Tools is a collection of debugging and analysis tools for the openpilot autonomous driving system. The tools are primarily focused on Controller Area Network (CAN) bus analysis, safety system monitoring, and vehicle behavior debugging.

Installation
------------

.. code-block:: bash

   # Clone the repository
   git clone https://github.com/anteew/comma-tools.git
   cd comma-tools

   # Install in development mode
   pip install -e .

   # Or install with development dependencies
   pip install -e ".[dev]"

Quick Start
-----------

Analyze a cruise control log:

.. code-block:: bash

   # First run - installs dependencies
   cruise-control-analyzer /path/to/logfile.zst --install-missing-deps

   # Subsequent runs
   cruise-control-analyzer /path/to/logfile.zst

Convert rlog to CSV for analysis:

.. code-block:: bash

   rlog-to-csv --rlog /path/to/logfile.zst --out output.csv --window-start 100.0 --window-dur 30.0

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
