#!/usr/bin/env python3
"""
Cruise Control Analyzer for rlog.zst files

This script analyzes rlog.zst files to identify CAN messages related to cruise control
"set" button presses. It parses raw CAN messages and uses Subaru DBC specifications
to decode wheel speeds and cruise control signals.
"""

import sys
import os
import struct
import matplotlib.pyplot as plt
import numpy as np
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Optional
import argparse

sys.path.append('/home/ubuntu/repos/openpilot')

try:
    from tools.lib.logreader import LogReader
    import cereal.messaging as messaging
except ImportError as e:
    print(f"Error importing openpilot modules: {e}")
    print("Make sure you're running this from the openpilot directory with the virtual environment activated")
    sys.exit(1)


class SubaruCANDecoder:
    """Decoder for Subaru CAN messages based on DBC specifications"""
    
    WHEEL_SPEEDS_ADDR = 0x13A  # 314 decimal
    CRUISE_BUTTONS_ADDR = 0x146  # 326 decimal  
    CRUISE_STATUS_ADDR = 0x241  # 577 decimal
    ES_BRAKE_ADDR = 0x220  # 544 decimal
    BRAKE_PEDAL_ADDR = 0x139  # 313 decimal
    
    @staticmethod
    def decode_wheel_speeds(data: bytes) -> Optional[Dict[str, float]]:
        """Decode wheel speeds from address 0x13A (314)"""
        if len(data) < 8:
            return None
            
        try:
            
            raw_data = int.from_bytes(data, byteorder='little')
            
            fr_raw = (raw_data >> 12) & 0x1FFF  # bits 12-24
            rr_raw = (raw_data >> 25) & 0x1FFF  # bits 25-37
            rl_raw = (raw_data >> 38) & 0x1FFF  # bits 38-50
            fl_raw = (raw_data >> 51) & 0x1FFF  # bits 51-63
            
            conversion_factor = 0.057
            
            speeds = {
                'FL': fl_raw * conversion_factor,  # Front Left
                'FR': fr_raw * conversion_factor,  # Front Right
                'RL': rl_raw * conversion_factor,  # Rear Left
                'RR': rr_raw * conversion_factor,  # Rear Right
            }
            
            speeds['avg_kph'] = (speeds['FL'] + speeds['FR'] + speeds['RL'] + speeds['RR']) / 4
            speeds['avg_mph'] = speeds['avg_kph'] * 0.621371  # Convert kph to mph
            
            return speeds
            
        except Exception as e:
            return None
    
    @staticmethod
    def decode_cruise_buttons(data: bytes) -> Optional[Dict[str, bool]]:
        """Decode cruise control buttons from address 0x146 (326)"""
        if len(data) < 8:
            return None
            
        try:
            raw_data = int.from_bytes(data, byteorder='little')
            
            
            buttons = {
                'main': bool((raw_data >> 42) & 0x1),
                'set': bool((raw_data >> 43) & 0x1),
                'resume': bool((raw_data >> 44) & 0x1),
            }
            
            return buttons
            
        except Exception as e:
            return None
    
    @staticmethod
    def decode_cruise_status(data: bytes) -> Optional[Dict[str, any]]:
        """Decode cruise status from address 0x241 (577)"""
        if len(data) < 8:
            return None
            
        try:
            raw_data = int.from_bytes(data, byteorder='little')
            
            
            status = {
                'cruise_set_speed': (raw_data >> 51) & 0xFFF,  # 12 bits
                'cruise_on': bool((raw_data >> 54) & 0x1),
                'cruise_activated': bool((raw_data >> 55) & 0x1),
            }
            
            return status
            
        except Exception as e:
            return None
    
    @staticmethod
    def decode_es_brake(data: bytes) -> Optional[Dict[str, any]]:
        """Decode ES_Brake from address 0x220 (544)"""
        if len(data) < 8:
            return None
            
        try:
            raw_data = int.from_bytes(data, byteorder='little')
            
            
            brake_info = {
                'cruise_brake_active': bool((raw_data >> 38) & 0x1),
                'cruise_activated': bool((raw_data >> 39) & 0x1),
            }
            
            return brake_info
            
        except Exception as e:
            return None


class CruiseControlAnalyzer:
    def __init__(self, log_file: str):
        self.log_file = log_file
        self.speed_data = []
        self.can_data = defaultdict(list)
        self.target_speed_events = []
        self.candidate_addresses = {}
        self.decoder = SubaruCANDecoder()
        
        self.target_addresses = {
            self.decoder.WHEEL_SPEEDS_ADDR: "Wheel_Speeds",
            self.decoder.CRUISE_BUTTONS_ADDR: "Cruise_Buttons", 
            self.decoder.CRUISE_STATUS_ADDR: "Cruise_Status",
            self.decoder.ES_BRAKE_ADDR: "ES_Brake",
            self.decoder.BRAKE_PEDAL_ADDR: "Brake_Pedal",
        }
        
    def parse_log_file(self):
        """Parse the rlog.zst file and extract speed and CAN data"""
        print(f"Parsing log file: {self.log_file}")
        
        try:
            lr = LogReader(self.log_file)
            message_count = 0
            can_count = 0
            speed_extracted_count = 0
            
            for msg in lr:
                message_count += 1
                
                if msg.which() == 'can':
                    can_count += 1
                    timestamp = msg.logMonoTime / 1e9
                    
                    for can_msg in msg.can:
                        address = can_msg.address
                        data = can_msg.dat
                        
                        if address in self.target_addresses:
                            self.can_data[address].append({
                                'timestamp': timestamp,
                                'data': data,
                                'bus': can_msg.src
                            })
                        
                        if address == self.decoder.WHEEL_SPEEDS_ADDR:
                            speeds = self.decoder.decode_wheel_speeds(data)
                            if speeds:
                                self.speed_data.append({
                                    'timestamp': timestamp,
                                    'speed_mph': speeds['avg_mph'],
                                    'speed_kph': speeds['avg_kph'],
                                    'wheel_speeds': speeds
                                })
                                speed_extracted_count += 1
                
                if message_count > 100000:
                    break
                    
            print(f"Processed {message_count} messages")
            print(f"Found {can_count} CAN messages")
            print(f"Extracted {speed_extracted_count} speed data points")
            print(f"Monitoring {len([addr for addr in self.target_addresses if addr in self.can_data])} target CAN addresses")
            
            for addr, name in self.target_addresses.items():
                count = len(self.can_data.get(addr, []))
                print(f"  0x{addr:03X} ({name}): {count} messages")
            
        except Exception as e:
            print(f"Error parsing log file: {e}")
            return False
            
        return True
    
    def find_target_speed_events(self, target_speed_min=55.0, target_speed_max=56.0):
        """Find time windows when the vehicle was at target speed (55-56 MPH)"""
        print(f"Looking for events at {target_speed_min}-{target_speed_max} MPH...")
        
        if not self.speed_data:
            print("No speed data available - could not extract from wheel speed CAN messages")
            print("Will analyze all CAN message patterns during the entire drive")
            return
        
        target_events = []
        in_target_range = False
        event_start = None
        
        for data_point in self.speed_data:
            speed = data_point['speed_mph']
            timestamp = data_point['timestamp']
            
            if target_speed_min <= speed <= target_speed_max:
                if not in_target_range:
                    in_target_range = True
                    event_start = timestamp
            else:
                if in_target_range:
                    in_target_range = False
                    if event_start is not None:
                        target_events.append({
                            'start_time': event_start,
                            'end_time': timestamp,
                            'duration': timestamp - event_start
                        })
        
        if in_target_range and event_start is not None:
            target_events.append({
                'start_time': event_start,
                'end_time': self.speed_data[-1]['timestamp'],
                'duration': self.speed_data[-1]['timestamp'] - event_start
            })
        
        self.target_speed_events = target_events
        print(f"Found {len(target_events)} events at target speed")
        
        for i, event in enumerate(target_events):
            print(f"Event {i+1}: {event['start_time']:.1f}s - {event['end_time']:.1f}s (duration: {event['duration']:.1f}s)")
    
    def analyze_cruise_control_signals(self):
        """Analyze specific cruise control CAN signals"""
        print("Analyzing Subaru cruise control signals...")
        
        signal_analysis = {}
        
        if self.decoder.CRUISE_BUTTONS_ADDR in self.can_data:
            button_messages = self.can_data[self.decoder.CRUISE_BUTTONS_ADDR]
            print(f"\nAnalyzing Cruise Buttons (0x{self.decoder.CRUISE_BUTTONS_ADDR:03X}): {len(button_messages)} messages")
            
            button_changes = []
            prev_buttons = None
            
            for msg in button_messages:
                buttons = self.decoder.decode_cruise_buttons(msg['data'])
                if buttons:
                    if prev_buttons and buttons != prev_buttons:
                        button_changes.append({
                            'timestamp': msg['timestamp'],
                            'old_state': prev_buttons.copy(),
                            'new_state': buttons.copy(),
                            'changes': {k: v for k, v in buttons.items() if prev_buttons.get(k) != v}
                        })
                    prev_buttons = buttons
            
            signal_analysis['cruise_buttons'] = {
                'total_messages': len(button_messages),
                'changes': button_changes,
                'set_button_presses': [c for c in button_changes if c['changes'].get('set') == True]
            }
            
            print(f"  Button state changes: {len(button_changes)}")
            print(f"  'Set' button presses detected: {len(signal_analysis['cruise_buttons']['set_button_presses'])}")
        
        if self.decoder.CRUISE_STATUS_ADDR in self.can_data:
            status_messages = self.can_data[self.decoder.CRUISE_STATUS_ADDR]
            print(f"\nAnalyzing Cruise Status (0x{self.decoder.CRUISE_STATUS_ADDR:03X}): {len(status_messages)} messages")
            
            status_changes = []
            prev_status = None
            
            for msg in status_messages:
                status = self.decoder.decode_cruise_status(msg['data'])
                if status:
                    if prev_status and status != prev_status:
                        status_changes.append({
                            'timestamp': msg['timestamp'],
                            'old_state': prev_status.copy(),
                            'new_state': status.copy(),
                            'changes': {k: v for k, v in status.items() if prev_status.get(k) != v}
                        })
                    prev_status = status
            
            signal_analysis['cruise_status'] = {
                'total_messages': len(status_messages),
                'changes': status_changes,
                'activation_events': [c for c in status_changes if c['changes'].get('cruise_activated') == True]
            }
            
            print(f"  Status changes: {len(status_changes)}")
            print(f"  Cruise activation events: {len(signal_analysis['cruise_status']['activation_events'])}")
        
        if self.decoder.ES_BRAKE_ADDR in self.can_data:
            brake_messages = self.can_data[self.decoder.ES_BRAKE_ADDR]
            print(f"\nAnalyzing ES_Brake (0x{self.decoder.ES_BRAKE_ADDR:03X}): {len(brake_messages)} messages")
            
            brake_changes = []
            prev_brake = None
            
            for msg in brake_messages:
                brake_info = self.decoder.decode_es_brake(msg['data'])
                if brake_info:
                    if prev_brake and brake_info != prev_brake:
                        brake_changes.append({
                            'timestamp': msg['timestamp'],
                            'old_state': prev_brake.copy(),
                            'new_state': brake_info.copy(),
                            'changes': {k: v for k, v in brake_info.items() if prev_brake.get(k) != v}
                        })
                    prev_brake = brake_info
            
            signal_analysis['es_brake'] = {
                'total_messages': len(brake_messages),
                'changes': brake_changes,
                'cruise_activation_events': [c for c in brake_changes if c['changes'].get('cruise_activated') == True]
            }
            
            print(f"  Brake signal changes: {len(brake_changes)}")
            print(f"  Cruise activation via brake signal: {len(signal_analysis['es_brake']['cruise_activation_events'])}")
        
        return signal_analysis
    
    def analyze_can_bit_changes(self):
        """Analyze bit-level changes in all target CAN addresses"""
        print("Analyzing bit-level changes in target CAN addresses...")
        
        bit_analysis = {}
        
        for address, name in self.target_addresses.items():
            if address not in self.can_data:
                continue
                
            messages = self.can_data[address]
            if len(messages) < 2:
                continue
            
            print(f"\nAnalyzing {name} (0x{address:03X}): {len(messages)} messages")
            
            bit_changes = []
            prev_data = None
            
            for msg in messages:
                if prev_data is not None:
                    changed_bits = self.find_changed_bits(prev_data, msg['data'])
                    if changed_bits:
                        bit_changes.append({
                            'timestamp': msg['timestamp'],
                            'old_data': prev_data,
                            'new_data': msg['data'],
                            'changed_bits': changed_bits,
                            'changed_bytes': self.find_changed_bytes(prev_data, msg['data'])
                        })
                prev_data = msg['data']
            
            if bit_changes:
                bit_frequency = Counter()
                for change in bit_changes:
                    for bit_pos in change['changed_bits']:
                        bit_frequency[bit_pos] += 1
                
                bit_analysis[address] = {
                    'name': name,
                    'total_changes': len(bit_changes),
                    'changes': bit_changes,
                    'bit_frequency': dict(bit_frequency.most_common(10))
                }
                
                print(f"  Total bit changes: {len(bit_changes)}")
                print(f"  Most frequently changing bits: {list(bit_frequency.most_common(5))}")
        
        return bit_analysis
    
    def find_changed_bits(self, old_data: bytes, new_data: bytes) -> List[int]:
        """Find which bits changed between two CAN messages"""
        changed_bits = []
        min_len = min(len(old_data), len(new_data))
        
        for byte_idx in range(min_len):
            if old_data[byte_idx] != new_data[byte_idx]:
                xor_result = old_data[byte_idx] ^ new_data[byte_idx]
                for bit_idx in range(8):
                    if xor_result & (1 << bit_idx):
                        bit_position = byte_idx * 8 + bit_idx
                        changed_bits.append(bit_position)
        
        return changed_bits
    
    def find_changed_bytes(self, old_data: bytes, new_data: bytes) -> List[int]:
        """Find which bytes changed between two CAN messages"""
        changed_bytes = []
        min_len = min(len(old_data), len(new_data))
        
        for i in range(min_len):
            if old_data[i] != new_data[i]:
                changed_bytes.append(i)
        
        return changed_bytes
    
    def correlate_signals_with_speed(self, signal_analysis):
        """Correlate cruise control signals with speed data"""
        print("\nCorrelating cruise control signals with speed data...")
        
        if not self.speed_data:
            print("No speed data available for correlation")
            return
        
        correlations = {}
        
        if 'cruise_buttons' in signal_analysis:
            set_presses = signal_analysis['cruise_buttons']['set_button_presses']
            speed_correlations = []
            
            for press in set_presses:
                press_time = press['timestamp']
                closest_speed = None
                min_time_diff = float('inf')
                
                for speed_data in self.speed_data:
                    time_diff = abs(speed_data['timestamp'] - press_time)
                    if time_diff < min_time_diff:
                        min_time_diff = time_diff
                        closest_speed = speed_data
                
                if closest_speed and min_time_diff < 2.0:
                    speed_correlations.append({
                        'press_time': press_time,
                        'speed_mph': closest_speed['speed_mph'],
                        'time_diff': min_time_diff
                    })
            
            correlations['set_button_speeds'] = speed_correlations
            
            target_range_presses = [
                c for c in speed_correlations 
                if 55.0 <= c['speed_mph'] <= 56.0
            ]
            
            print(f"Set button presses: {len(set_presses)}")
            print(f"Set presses with speed data: {len(speed_correlations)}")
            print(f"Set presses in target range (55-56 MPH): {len(target_range_presses)}")
            
            if target_range_presses:
                print("Set button presses in target speed range:")
                for i, press in enumerate(target_range_presses):
                    print(f"  {i+1}. Time {press['press_time']:.1f}s, Speed {press['speed_mph']:.1f} MPH")
        
        return correlations
    
    def generate_report(self):
        """Generate a detailed analysis report"""
        print("\n" + "="*80)
        print("SUBARU CRUISE CONTROL ANALYSIS REPORT")
        print("="*80)
        
        print(f"\nLog file: {self.log_file}")
        print(f"Total speed data points: {len(self.speed_data)}")
        print(f"Target CAN addresses monitored: {len([addr for addr in self.target_addresses if addr in self.can_data])}")
        
        if self.speed_data:
            speeds = [d['speed_mph'] for d in self.speed_data]
            print(f"Speed range: {min(speeds):.1f} - {max(speeds):.1f} MPH")
            print(f"Average speed: {np.mean(speeds):.1f} MPH")
        
        signal_analysis = self.analyze_cruise_control_signals()
        
        bit_analysis = self.analyze_can_bit_changes()
        
        correlations = self.correlate_signals_with_speed(signal_analysis)
        
        print(f"\nKEY FINDINGS:")
        print("-" * 50)
        
        if 'cruise_buttons' in signal_analysis:
            buttons = signal_analysis['cruise_buttons']
            print(f"1. CRUISE BUTTONS (0x{self.decoder.CRUISE_BUTTONS_ADDR:03X}):")
            print(f"   - Total messages: {buttons['total_messages']}")
            print(f"   - Button state changes: {len(buttons['changes'])}")
            print(f"   - 'Set' button presses: {len(buttons['set_button_presses'])}")
            
            if buttons['set_button_presses']:
                print("   - Set button press times:")
                for i, press in enumerate(buttons['set_button_presses'][:10]):
                    print(f"     {i+1}. Time {press['timestamp']:.1f}s")
        
        if 'cruise_status' in signal_analysis:
            status = signal_analysis['cruise_status']
            print(f"\n2. CRUISE STATUS (0x{self.decoder.CRUISE_STATUS_ADDR:03X}):")
            print(f"   - Total messages: {status['total_messages']}")
            print(f"   - Status changes: {len(status['changes'])}")
            print(f"   - Activation events: {len(status['activation_events'])}")
        
        if 'es_brake' in signal_analysis:
            brake = signal_analysis['es_brake']
            print(f"\n3. ES_BRAKE (0x{self.decoder.ES_BRAKE_ADDR:03X}):")
            print(f"   - Total messages: {brake['total_messages']}")
            print(f"   - Signal changes: {len(brake['changes'])}")
            print(f"   - Cruise activation events: {len(brake['cruise_activation_events'])}")
        
        print(f"\n4. BIT-LEVEL ANALYSIS:")
        active_addresses = sorted(bit_analysis.items(), key=lambda x: x[1]['total_changes'], reverse=True)
        for addr, analysis in active_addresses[:5]:
            print(f"   - {analysis['name']} (0x{addr:03X}): {analysis['total_changes']} changes")
            if analysis['bit_frequency']:
                top_bits = list(analysis['bit_frequency'].items())[:3]
                print(f"     Most active bits: {top_bits}")
        
        print(f"\nRECOMMENDATIONS:")
        print("-" * 20)
        
        if 'cruise_buttons' in signal_analysis and signal_analysis['cruise_buttons']['set_button_presses']:
            print("✓ SUCCESS: Detected 'Set' button presses in cruise control CAN messages!")
            print(f"  - Address: 0x{self.decoder.CRUISE_BUTTONS_ADDR:03X} (Cruise_Buttons)")
            print("  - Signal: Bit 43 (Set button)")
            print("  - This is your primary cruise control activation signal")
        else:
            print("⚠ No clear 'Set' button presses detected in expected address")
        
        print(f"\nNEXT STEPS:")
        print("1. Monitor address 0x{:03X} (Cruise_Buttons) in real-time".format(self.decoder.CRUISE_BUTTONS_ADDR))
        print("2. Watch for bit 43 transitions when pressing 'Set' button")
        print("3. Verify address 0x{:03X} (Cruise_Status) for activation confirmation".format(self.decoder.CRUISE_STATUS_ADDR))
        print("4. Use openpilot's cabana tool for real-time CAN monitoring")
        
        print(f"\nCABANA COMMANDS:")
        print(f"cd /home/ubuntu/repos/openpilot && tools/cabana")
        print(f"# Focus on addresses: 0x{self.decoder.CRUISE_BUTTONS_ADDR:03X}, 0x{self.decoder.CRUISE_STATUS_ADDR:03X}, 0x{self.decoder.ES_BRAKE_ADDR:03X}")
    
    def plot_speed_timeline(self):
        """Create a plot showing speed over time with target events highlighted"""
        if not self.speed_data:
            print("No speed data to plot")
            return
        
        timestamps = [d['timestamp'] for d in self.speed_data]
        speeds = [d['speed_mph'] for d in self.speed_data]
        
        plt.figure(figsize=(12, 6))
        plt.plot(timestamps, speeds, 'b-', linewidth=1, alpha=0.7, label='Vehicle Speed')
        
        plt.axhline(y=55, color='r', linestyle='--', alpha=0.5, label='Target Speed Range')
        plt.axhline(y=56, color='r', linestyle='--', alpha=0.5)
        plt.fill_between(timestamps, 55, 56, alpha=0.2, color='red')
        
        for i, event in enumerate(self.target_speed_events):
            plt.axvspan(event['start_time'], event['end_time'], 
                       alpha=0.3, color='green', label='Target Speed Event' if i == 0 else '')
        
        plt.xlabel('Time (seconds)')
        plt.ylabel('Speed (MPH)')
        plt.title('Vehicle Speed Timeline - Extracted from Wheel Speed CAN Messages')
        plt.legend()
        plt.grid(True, alpha=0.3)
        
        plot_filename = 'speed_timeline.png'
        plt.savefig(plot_filename, dpi=150, bbox_inches='tight')
        print(f"Speed timeline plot saved as: {plot_filename}")
        plt.close()
    
    def run_analysis(self):
        """Run the complete analysis"""
        print("Starting Subaru cruise control analysis...")
        
        if not self.parse_log_file():
            return False
        
        self.find_target_speed_events()
        self.generate_report()
        
        if self.speed_data:
            self.plot_speed_timeline()
        
        return True


def main():
    parser = argparse.ArgumentParser(description='Analyze rlog.zst files for Subaru cruise control signals')
    parser.add_argument('log_file', help='Path to the rlog.zst file')
    parser.add_argument('--speed-min', type=float, default=55.0, 
                       help='Minimum target speed in MPH (default: 55.0)')
    parser.add_argument('--speed-max', type=float, default=56.0,
                       help='Maximum target speed in MPH (default: 56.0)')
    
    args = parser.parse_args()
    
    if not os.path.exists(args.log_file):
        print(f"Error: Log file not found: {args.log_file}")
        return 1
    
    analyzer = CruiseControlAnalyzer(args.log_file)
    
    if analyzer.run_analysis():
        print("\nAnalysis completed successfully!")
        return 0
    else:
        print("\nAnalysis failed!")
        return 1


if __name__ == "__main__":
    sys.exit(main())
