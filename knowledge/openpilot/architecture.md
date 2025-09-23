# OpenPilot Architecture Diagrams & Explanations

## Overview
This document explains how openpilot works from a process and safety perspective, focusing on the startup sequence, process dependencies, Panda communication, and safety model transitions.

## 1. Main Process Startup Flow

```mermaid
graph TD
    A[launch_openpilot.sh] --> B[launch_chffrplus.sh]
    B --> C[system/manager/manager.py]
    C --> D[manager_init]
    D --> E[Load managed_processes]
    E --> F[Start Core Processes]
    
    F --> G[pandad - Always Running]
    F --> H[card - Only Onroad]
    F --> I[controlsd - Only Onroad]
    F --> J[UI - Always Running]
    F --> K[Other Processes...]
    
    G --> L[Panda Communication]
    H --> M[Car Interface]
    I --> N[Vehicle Control]
```

**Key Points:**
- `manager.py` is the main orchestrator that starts/stops all processes
- Processes are defined in `process_config.py` with conditions (always_run, only_onroad, etc.)
- `pandad` runs continuously to maintain Panda communication
- `card` and `controlsd` only run when the vehicle is onroad

## 2. Process Dependencies & Communication

```mermaid
graph LR
    subgraph "Core Processes"
        A[pandad] --> B[CAN Bus]
        C[card] --> D[Car Interface]
        E[controlsd] --> F[Vehicle Control]
        G[modeld] --> H[AI Models]
    end
    
    subgraph "Message Passing"
        B --> I[can messages]
        D --> J[carState]
        F --> K[carControl]
        H --> L[modelV2]
    end
    
    subgraph "Safety Chain"
        A --> M[pandaStates]
        C --> N[carParams]
        E --> O[controlsReady]
    end
    
    I --> C
    J --> E
    K --> C
    M --> C
    N --> A
    O --> A
```

**Process Roles:**
- **pandad**: Manages Panda hardware, CAN communication, safety modes
- **card**: Car interface, reads CAN messages, publishes car state
- **controlsd**: Main control logic, sends steering/acceleration commands
- **modeld**: AI model inference for path planning and object detection

## 3. Panda Communication & Safety Model Flow

```mermaid
sequenceDiagram
    participant OP as OpenPilot
    participant PD as Pandad
    participant P as Panda Hardware
    participant C as Car CAN Bus
    
    Note over OP,C: Startup Sequence
    OP->>PD: Start pandad process
    PD->>P: Initialize connection
    P->>PD: Hardware status
    
    Note over OP,C: Initial Safety Mode (Fingerprinting)
    PD->>P: Set ELM327 safety mode
    P->>C: Listen for CAN messages
    C->>P: Vehicle CAN data
    P->>PD: Forward CAN messages
    PD->>OP: Publish 'can' messages
    
    Note over OP,C: Car Detection & Safety Transition
    OP->>OP: Fingerprint car model
    OP->>OP: Generate CarParams
    OP->>PD: Set ControlsReady=True
    PD->>P: Switch to car-specific safety mode
    
    Note over OP,C: Operational Mode
    OP->>PD: Send control commands
    PD->>P: Validate & forward commands
    P->>C: Send control CAN messages
    C->>P: Receive car responses
    P->>PD: Forward responses
    PD->>OP: Publish car state
```

## 4. Safety Model Transition Details

```mermaid
stateDiagram-v2
    [*] --> ELM327: Panda startup
    
    state ELM327 {
        [*] --> Fingerprinting
        Fingerprinting --> OBD_Queries
        OBD_Queries --> Car_Detection
    }
    
    ELM327 --> Car_Specific: ControlsReady=True
    
    state Car_Specific {
        [*] --> Toyota_Safety: If Toyota detected
        [*] --> Honda_Safety: If Honda detected
        [*] --> GM_Safety: If GM detected
        [*] --> Other_Safety: If other brand
        
        Toyota_Safety --> Active_Control
        Honda_Safety --> Active_Control
        GM_Safety --> Active_Control
        Other_Safety --> Active_Control
    }
    
    Car_Specific --> NO_OUTPUT: Ignition off
    NO_OUTPUT --> Car_Specific: Ignition on
    Car_Specific --> SILENT: Emergency/Error
```

**Safety Mode Purposes:**
- **ELM327**: Diagnostic mode for initial car fingerprinting
- **Car-Specific**: Brand-specific safety logic (Toyota, Honda, etc.)
- **NO_OUTPUT**: Safe mode when car is off or openpilot disabled
- **SILENT**: Emergency fallback mode

## 5. File Relationships & Code Structure

```mermaid
graph TB
    subgraph "Safety Implementation"
        A[opendbc/safety/safety.h] --> B[Brand Safety Headers]
        B --> C[toyota.h]
        B --> D[honda.h] 
        B --> E[gm.h]
        B --> F[elm327.h]
    end
    
    subgraph "Car Interface Layer"
        G[opendbc/car/brand/interface.py] --> H[CarInterface]
        I[opendbc/car/brand/carstate.py] --> J[CarState]
        K[opendbc/car/brand/carcontroller.py] --> L[CarController]
    end
    
    subgraph "CAN Definitions"
        M[opendbc/brand_messages.dbc] --> N[CAN Message Formats]
        N --> O[Address Mappings]
        N --> P[Signal Definitions]
    end
    
    subgraph "Integration"
        A --> Q[Panda Firmware]
        G --> R[card.py]
        M --> R
        Q --> S[pandad.cc]
        R --> S
    end
```

**File Relationships:**
- **.h files**: C safety logic running on Panda hardware
- **.py files**: Python car interfaces running on openpilot device
- **.dbc files**: CAN message format definitions
- **Panda**: Hardware that enforces safety and bridges CAN buses

## 6. Bidirectional Communication Flow

```mermaid
graph LR
    subgraph "OpenPilot Device"
        A[controlsd] --> B[card.py]
        B --> C[CarInterface]
        C --> D[pandad]
    end
    
    subgraph "Panda Hardware"
        D --> E[Safety Logic]
        E --> F[CAN Controller]
    end
    
    subgraph "Vehicle"
        F --> G[Car CAN Bus]
        G --> H[ECUs]
    end
    
    subgraph "RX Path (Car → OpenPilot)"
        H --> I[CAN Messages]
        I --> F
        F --> J[Filter & Forward]
        J --> D
        D --> K[Publish 'can']
        K --> B
        B --> L[Parse CarState]
        L --> A
    end
    
    subgraph "TX Path (OpenPilot → Car)"
        A --> M[Generate CarControl]
        M --> B
        B --> N[Generate CAN Commands]
        N --> D
        D --> O[Safety Check]
        O --> F
        F --> P[Send to Car]
        P --> H
    end
```

## 7. Key Concepts Explained

### Why ELM327 First?
- **ELM327** is a diagnostic protocol that allows reading car data without sending control commands
- Used during startup to safely fingerprint the car model
- Once car is identified, switches to car-specific safety mode

### Safety Model Hierarchy
1. **Hardware Safety (Panda)**: C code, cannot be bypassed, runs on separate microcontroller
2. **Software Safety (OpenPilot)**: Python code, additional checks and logic
3. **Car Safety (Vehicle)**: Built-in vehicle safety systems

### Process Communication
- Uses **cereal** messaging system (similar to ROS)
- Processes publish/subscribe to named topics
- Examples: 'can', 'carState', 'carControl', 'pandaStates'

### Car Porting Components
When adding a new car, you need:
1. **Safety header (.h)**: Hardware safety logic for Panda
2. **DBC file**: CAN message definitions
3. **Python interface**: CarInterface, CarState, CarController
4. **Fingerprinting**: Logic to detect the specific car model

This architecture ensures safety through multiple layers while maintaining flexibility for different vehicle types.
