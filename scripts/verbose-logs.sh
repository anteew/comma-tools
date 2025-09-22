cd /data/openpilot/selfdrive/debug/
export LOG_TIMESTAMPS=1 
python3 filter_log_message.py --level DEBUG | grep -i safety