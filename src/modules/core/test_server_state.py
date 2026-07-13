#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tests for ServerState class."""

import pytest
import sys
import os

# Add the parent directory to the path to allow imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

# Import directly from the module file to avoid __init__.py issues
import importlib.util
spec = importlib.util.spec_from_file_location(
    "server_state",
    os.path.join(os.path.dirname(__file__), "server_state.py")
)
server_state_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(server_state_module)
ServerState = server_state_module.ServerState


def test_server_state_initialization():
    """Test that ServerState initializes with all expected attributes."""
    state = ServerState()
    
    # Verify all attributes are initialized
    assert hasattr(state, 'websocket_users')
    assert hasattr(state, 'model_asr')
    assert hasattr(state, 'model_asr_streaming')
    assert hasattr(state, 'model_asr_upload')
    assert hasattr(state, 'model_vad')
    assert hasattr(state, 'model_punc')
    assert hasattr(state, 'model_lm')
    assert hasattr(state, 'model_itn')
    assert hasattr(state, 'model_speaker')
    assert hasattr(state, 'model_translation')
    assert hasattr(state, 'model_segmentation')
    assert hasattr(state, 'hotword_map')
    assert hasattr(state, 'args')
    assert hasattr(state, 'logger')
    assert hasattr(state, 'subtitle_settings')
    
    # Verify initial values
    assert isinstance(state.websocket_users, set)
    assert len(state.websocket_users) == 0
    assert state.model_asr is None
    assert state.model_asr_streaming is None
    assert state.model_asr_upload is None
    assert state.model_vad is None
    assert state.model_punc is None
    assert state.model_lm is None
    assert state.model_itn is None
    assert state.model_speaker is None
    assert state.model_translation is None
    assert state.model_segmentation is None
    assert isinstance(state.hotword_map, dict)
    assert len(state.hotword_map) == 0
    assert state.args is None
    assert state.logger is None
    assert state.subtitle_settings is None


def test_subtitle_settings_can_be_set():
    """Test that subtitle_settings can be set to a dictionary."""
    state = ServerState()
    
    # Set subtitle settings
    test_settings = {
        "windowWidth": 80,
        "cornerRadius": 10,
        "backgroundColor": "#000000",
        "backgroundOpacity": 75,
        "fontFamily": "宋体",
        "fontSize": 14,
        "fontColor": "默认",
        "isBold": False,
        "isItalic": False,
        "showEnglish": False,
        "maxDisplayLines": 2,
        "scrollSpeed": 60,
        "webSocketUrl": "ws://127.0.0.1:10095/"
    }
    
    state.subtitle_settings = test_settings
    
    # Verify settings were stored
    assert state.subtitle_settings is not None
    assert state.subtitle_settings == test_settings
    assert state.subtitle_settings["windowWidth"] == 80
    assert state.subtitle_settings["fontFamily"] == "宋体"


def test_subtitle_settings_can_be_updated():
    """Test that subtitle_settings can be updated."""
    state = ServerState()
    
    # Set initial settings
    initial_settings = {
        "windowWidth": 80,
        "fontSize": 14
    }
    state.subtitle_settings = initial_settings
    
    # Update settings
    updated_settings = {
        "windowWidth": 90,
        "fontSize": 16
    }
    state.subtitle_settings = updated_settings
    
    # Verify settings were updated
    assert state.subtitle_settings["windowWidth"] == 90
    assert state.subtitle_settings["fontSize"] == 16


def test_subtitle_settings_can_be_cleared():
    """Test that subtitle_settings can be cleared by setting to None."""
    state = ServerState()
    
    # Set settings
    state.subtitle_settings = {"windowWidth": 80}
    assert state.subtitle_settings is not None
    
    # Clear settings
    state.subtitle_settings = None
    assert state.subtitle_settings is None


if __name__ == "__main__":
    # Run tests directly
    print("Running ServerState tests...")
    
    print("Test 1: server_state_initialization")
    test_server_state_initialization()
    print("✓ Passed")
    
    print("Test 2: subtitle_settings_can_be_set")
    test_subtitle_settings_can_be_set()
    print("✓ Passed")
    
    print("Test 3: subtitle_settings_can_be_updated")
    test_subtitle_settings_can_be_updated()
    print("✓ Passed")
    
    print("Test 4: subtitle_settings_can_be_cleared")
    test_subtitle_settings_can_be_cleared()
    print("✓ Passed")
    
    print("\nAll tests passed! ✓")
