"""The tests for the MQTT switch platform."""
from asynctest import patch
import pytest

from homeassistant.components import switch
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
import homeassistant.core as ha
from homeassistant.setup import async_setup_component

from .common import (
    help_test_discovery_broken,
    help_test_discovery_removal,
    help_test_discovery_update,
    help_test_discovery_update_attr,
    help_test_entity_device_info_update,
    help_test_entity_device_info_with_identifier,
    help_test_entity_id_update,
    help_test_setting_attribute_via_mqtt_json_message,
    help_test_unique_id,
    help_test_update_with_json_attrs_bad_JSON,
    help_test_update_with_json_attrs_not_dict,
)

from tests.common import async_fire_mqtt_message, async_mock_mqtt_component, mock_coro
from tests.components.switch import common

DEFAULT_CONFIG_ATTR = {
    switch.DOMAIN: {
        "platform": "mqtt",
        "name": "test",
        "command_topic": "test-topic",
        "json_attributes_topic": "attr-topic",
    }
}

DEFAULT_CONFIG_DEVICE_INFO = {
    "platform": "mqtt",
    "name": "Test 1",
    "state_topic": "test-topic",
    "command_topic": "test-command-topic",
    "device": {
        "identifiers": ["helloworld"],
        "connections": [["mac", "02:5b:26:a8:dc:12"]],
        "manufacturer": "Whatever",
        "name": "Beer",
        "model": "Glass",
        "sw_version": "0.1-beta",
    },
    "unique_id": "veryunique",
}


@pytest.fixture
def mock_publish(hass):
    """Initialize components."""
    yield hass.loop.run_until_complete(async_mock_mqtt_component(hass))


async def test_controlling_state_via_topic(hass, mock_publish):
    """Test the controlling state via topic."""
    assert await async_setup_component(
        hass,
        switch.DOMAIN,
        {
            switch.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "payload_on": 1,
                "payload_off": 0,
            }
        },
    )

    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", "1")

    state = hass.states.get("switch.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "state-topic", "0")

    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF


async def test_sending_mqtt_commands_and_optimistic(hass, mock_publish):
    """Test the sending MQTT commands in optimistic mode."""
    fake_state = ha.State("switch.test", "on")

    with patch(
        "homeassistant.helpers.restore_state.RestoreEntity.async_get_last_state",
        return_value=mock_coro(fake_state),
    ):
        assert await async_setup_component(
            hass,
            switch.DOMAIN,
            {
                switch.DOMAIN: {
                    "platform": "mqtt",
                    "name": "test",
                    "command_topic": "command-topic",
                    "payload_on": "beer on",
                    "payload_off": "beer off",
                    "qos": "2",
                }
            },
        )

    state = hass.states.get("switch.test")
    assert state.state == STATE_ON
    assert state.attributes.get(ATTR_ASSUMED_STATE)

    await common.async_turn_on(hass, "switch.test")

    mock_publish.async_publish.assert_called_once_with(
        "command-topic", "beer on", 2, False
    )
    mock_publish.async_publish.reset_mock()
    state = hass.states.get("switch.test")
    assert state.state == STATE_ON

    await common.async_turn_off(hass, "switch.test")

    mock_publish.async_publish.assert_called_once_with(
        "command-topic", "beer off", 2, False
    )
    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF


async def test_controlling_state_via_topic_and_json_message(hass, mock_publish):
    """Test the controlling state via topic and JSON message."""
    assert await async_setup_component(
        hass,
        switch.DOMAIN,
        {
            switch.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "payload_on": "beer on",
                "payload_off": "beer off",
                "value_template": "{{ value_json.val }}",
            }
        },
    )

    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF

    async_fire_mqtt_message(hass, "state-topic", '{"val":"beer on"}')

    state = hass.states.get("switch.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "state-topic", '{"val":"beer off"}')

    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF


async def test_default_availability_payload(hass, mock_publish):
    """Test the availability payload."""
    assert await async_setup_component(
        hass,
        switch.DOMAIN,
        {
            switch.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "availability_topic": "availability_topic",
                "payload_on": 1,
                "payload_off": 0,
            }
        },
    )

    state = hass.states.get("switch.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability_topic", "online")

    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "availability_topic", "offline")

    state = hass.states.get("switch.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "state-topic", "1")

    state = hass.states.get("switch.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability_topic", "online")

    state = hass.states.get("switch.test")
    assert state.state == STATE_ON


async def test_custom_availability_payload(hass, mock_publish):
    """Test the availability payload."""
    assert await async_setup_component(
        hass,
        switch.DOMAIN,
        {
            switch.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "availability_topic": "availability_topic",
                "payload_on": 1,
                "payload_off": 0,
                "payload_available": "good",
                "payload_not_available": "nogood",
            }
        },
    )

    state = hass.states.get("switch.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability_topic", "good")

    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "availability_topic", "nogood")

    state = hass.states.get("switch.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "state-topic", "1")

    state = hass.states.get("switch.test")
    assert state.state == STATE_UNAVAILABLE

    async_fire_mqtt_message(hass, "availability_topic", "good")

    state = hass.states.get("switch.test")
    assert state.state == STATE_ON


async def test_custom_state_payload(hass, mock_publish):
    """Test the state payload."""
    assert await async_setup_component(
        hass,
        switch.DOMAIN,
        {
            switch.DOMAIN: {
                "platform": "mqtt",
                "name": "test",
                "state_topic": "state-topic",
                "command_topic": "command-topic",
                "payload_on": 1,
                "payload_off": 0,
                "state_on": "HIGH",
                "state_off": "LOW",
            }
        },
    )

    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF
    assert not state.attributes.get(ATTR_ASSUMED_STATE)

    async_fire_mqtt_message(hass, "state-topic", "HIGH")

    state = hass.states.get("switch.test")
    assert state.state == STATE_ON

    async_fire_mqtt_message(hass, "state-topic", "LOW")

    state = hass.states.get("switch.test")
    assert state.state == STATE_OFF


async def test_setting_attribute_via_mqtt_json_message(hass, mqtt_mock):
    """Test the setting of attribute via MQTT with JSON payload."""
    await help_test_setting_attribute_via_mqtt_json_message(
        hass, mqtt_mock, switch.DOMAIN, DEFAULT_CONFIG_ATTR
    )


async def test_update_with_json_attrs_not_dict(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_not_dict(
        hass, mqtt_mock, caplog, switch.DOMAIN, DEFAULT_CONFIG_ATTR
    )


async def test_update_with_json_attrs_bad_JSON(hass, mqtt_mock, caplog):
    """Test attributes get extracted from a JSON result."""
    await help_test_update_with_json_attrs_bad_JSON(
        hass, mqtt_mock, caplog, switch.DOMAIN, DEFAULT_CONFIG_ATTR
    )


async def test_discovery_update_attr(hass, mqtt_mock, caplog):
    """Test update of discovered MQTTAttributes."""
    data1 = (
        '{ "name": "test",'
        '  "command_topic": "test_topic",'
        '  "json_attributes_topic": "attr-topic1" }'
    )
    data2 = (
        '{ "name": "test",'
        '  "command_topic": "test_topic",'
        '  "json_attributes_topic": "attr-topic2" }'
    )
    await help_test_discovery_update_attr(
        hass, mqtt_mock, caplog, switch.DOMAIN, data1, data2
    )


async def test_unique_id(hass):
    """Test unique id option only creates one switch per unique_id."""
    config = {
        switch.DOMAIN: [
            {
                "platform": "mqtt",
                "name": "Test 1",
                "state_topic": "test-topic",
                "command_topic": "command-topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
            {
                "platform": "mqtt",
                "name": "Test 2",
                "state_topic": "test-topic",
                "command_topic": "command-topic",
                "unique_id": "TOTALLY_UNIQUE",
            },
        ]
    }
    await help_test_unique_id(hass, switch.DOMAIN, config)


async def test_discovery_removal_switch(hass, mqtt_mock, caplog):
    """Test removal of discovered switch."""
    data = (
        '{ "name": "test",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    await help_test_discovery_removal(hass, mqtt_mock, caplog, switch.DOMAIN, data)


async def test_discovery_update_switch(hass, mqtt_mock, caplog):
    """Test update of discovered switch."""
    data1 = (
        '{ "name": "Beer",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    data2 = (
        '{ "name": "Milk",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    await help_test_discovery_update(
        hass, mqtt_mock, caplog, switch.DOMAIN, data1, data2
    )


async def test_discovery_broken(hass, mqtt_mock, caplog):
    """Test handling of bad discovery message."""
    data1 = '{ "name": "Beer" }'
    data2 = (
        '{ "name": "Milk",'
        '  "state_topic": "test_topic",'
        '  "command_topic": "test_topic" }'
    )
    await help_test_discovery_broken(
        hass, mqtt_mock, caplog, switch.DOMAIN, data1, data2
    )


async def test_entity_device_info_with_identifier(hass, mqtt_mock):
    """Test MQTT switch device registry integration."""
    await help_test_entity_device_info_with_identifier(
        hass, mqtt_mock, switch.DOMAIN, DEFAULT_CONFIG_DEVICE_INFO
    )


async def test_entity_device_info_update(hass, mqtt_mock):
    """Test device registry update."""
    await help_test_entity_device_info_update(
        hass, mqtt_mock, switch.DOMAIN, DEFAULT_CONFIG_DEVICE_INFO
    )


async def test_entity_id_update(hass, mqtt_mock):
    """Test MQTT subscriptions are managed when entity_id is updated."""
    config = {
        switch.DOMAIN: [
            {
                "platform": "mqtt",
                "name": "beer",
                "state_topic": "test-topic",
                "command_topic": "command-topic",
                "availability_topic": "avty-topic",
                "unique_id": "TOTALLY_UNIQUE",
            }
        ]
    }
    await help_test_entity_id_update(hass, mqtt_mock, switch.DOMAIN, config)
