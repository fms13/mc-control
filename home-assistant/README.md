

create /etc/systemd/system/detect-override-for-HA@homeassistant.service

Restart=on-failure

chown homeassistant.homeassistant /usr/local/bin/detect-event-in-OZW_Log.py

systemctl --system daemon-reload

systemctl enable detect-override-for-HA@homeassistant

systemctl start detect-override-for-HA@homeassistant

HASS config in automations and input_boolean