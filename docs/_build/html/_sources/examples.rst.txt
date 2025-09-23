Examples
========

This section provides practical examples of using Comma Tools for common analysis tasks.

Analyzing Cruise Control Behavior
----------------------------------

Basic Analysis
~~~~~~~~~~~~~~

.. code-block:: python

   from comma_tools.analyzers.cruise_control_analyzer import CruiseControlAnalyzer
   from comma_tools.analyzers.event_detection import EventDetector
   from comma_tools.can import SubaruCANDecoder

   # Initialize analyzer
   analyzer = CruiseControlAnalyzer("/path/to/logfile.zst")
   
   # Run analysis with custom speed range
   analyzer.run_analysis(target_speed_min=50.0, target_speed_max=60.0)

Using the Event Detector
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Extract event detection functionality
   detector = EventDetector(
       decoder=SubaruCANDecoder(),
       speed_data=analyzer.speed_data,
       can_data=analyzer.can_data
   )
   
   # Find target speed events
   events = detector.find_target_speed_events(55.0, 56.0)
   
   # Analyze cruise control signals
   signal_analysis = detector.analyze_cruise_control_signals()

CAN Message Decoding
---------------------

Decoding Wheel Speeds
~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from comma_tools.can.decoders import SubaruCANDecoder

   # Sample CAN data (8 bytes)
   can_data = b'\x12\x34\x56\x78\x9a\xbc\xde\xf0'
   
   # Decode wheel speeds
   speeds = SubaruCANDecoder.decode_wheel_speeds(can_data)
   if speeds:
       print(f"Average speed: {speeds['avg_mph']:.1f} MPH")
       print(f"Individual wheels: FL={speeds['FL']:.1f}, FR={speeds['FR']:.1f}")

Decoding Cruise Control Buttons
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Decode cruise control button states
   buttons = SubaruCANDecoder.decode_cruise_buttons(can_data)
   if buttons:
       if buttons['set']:
           print("Set button pressed!")
       if buttons['resume']:
           print("Resume button pressed!")

Generic Message Decoding
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   # Decode any supported message by address
   address = 0x13A  # Wheel speeds address
   decoded = SubaruCANDecoder.decode_message(address, can_data)
   
   # Get all supported addresses
   supported = SubaruCANDecoder.get_supported_addresses()
   for addr, name in supported.items():
       print(f"0x{addr:03X}: {name}")

Bit Pattern Analysis
--------------------

Analyzing CAN Bit Changes
~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from comma_tools.can.bit_analysis import BitAnalyzer, CanMessage

   analyzer = BitAnalyzer()
   
   # Create CAN messages
   msg1 = CanMessage(timestamp=1.0, address=0x123, data=b'\x00\x01\x02\x03')
   msg2 = CanMessage(timestamp=2.0, address=0x123, data=b'\x00\x01\x06\x03')
   
   # Find changed bits
   changed_bits = analyzer.find_changed_bits(msg1.data, msg2.data)
   print(f"Changed bits: {changed_bits}")

Data Visualization
------------------

Creating Speed Timeline Plots
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from comma_tools.visualization.plotting import SpeedTimelinePlotter

   plotter = SpeedTimelinePlotter(figsize=(15, 8))
   
   # Plot speed timeline with events
   plotter.plot_speed_timeline(
       speed_data=analyzer.speed_data,
       events=target_events,
       output_file="speed_analysis.png",
       title="Vehicle Speed Analysis"
   )

Converting Logs to CSV
----------------------

Basic Conversion
~~~~~~~~~~~~~~~~

.. code-block:: python

   from comma_tools.analyzers.rlog_to_csv import main
   import sys

   # Set up arguments for conversion
   sys.argv = [
       'rlog_to_csv.py',
       '--rlog', '/path/to/logfile.zst',
       '--out', 'output.csv',
       '--window-start', '100.0',
       '--window-dur', '30.0'
   ]
   
   main()

Error Handling
--------------

Robust CAN Decoding
~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from comma_tools.can.decoders import CANDecodingError

   try:
       speeds = SubaruCANDecoder.decode_wheel_speeds(can_data, validate=True)
       if speeds is None:
           print("Failed to decode wheel speeds")
       else:
           print(f"Decoded speeds: {speeds}")
   except CANDecodingError as e:
       print(f"Validation failed: {e}")

Environment Setup
-----------------

Setting up OpenPilot Environment
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

   from comma_tools.utils.openpilot_utils import (
       find_repo_root,
       prepare_environment,
       ensure_python_packages,
       load_external_modules
   )

   # Find openpilot installation
   repo_root = find_repo_root()
   deps_dir = repo_root / "comma-depends"
   
   # Prepare environment
   prepare_environment(repo_root, deps_dir)
   
   # Load required modules
   modules = load_external_modules()
   np = modules['np']
   LogReader = modules['LogReader']
