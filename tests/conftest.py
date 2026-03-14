"""Shared test fixtures for pyunifiapi tests."""

from __future__ import annotations

import pytest

from pyunifiapi._types import ControllerConfig, SSHConfig, TurnCredentials


@pytest.fixture
def controller_config() -> ControllerConfig:
    return ControllerConfig(
        host='192.168.1.1',
        username='admin',
        password='password',
        port=443,
        site='default',
    )


@pytest.fixture
def ssh_config() -> SSHConfig:
    return SSHConfig(
        mac='aa:bb:cc:dd:ee:ff',
        username='ubnt',
        password='ubnt',
    )


@pytest.fixture
def turn_credentials() -> TurnCredentials:
    return TurnCredentials(
        stun_urls=['stun:stun.example.com:3478'],
        turn_urls=['turn:turn.example.com:3478'],
        turn_username='turn-user',
        turn_password='turn-pass',
    )
