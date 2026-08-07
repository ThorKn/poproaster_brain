# == DO NOT EDIT THE FOLLOWING LINES for the Raspberry Pi Pico VS Code Extension to work ==
if(WIN32)
    set(USERHOME $ENV{USERPROFILE})
else()
    set(USERHOME $ENV{HOME})
endif()
set(sdkVersion 2.3.0)
set(toolchainVersion 15_2_Rel1)
set(picotoolVersion 2.3.0)
set(picoVscode ${USERHOME}/.pico-sdk/cmake/pico-vscode.cmake)
if (EXISTS ${picoVscode})
    include(${picoVscode})
endif()
# ====================================================================================
set(PICO_BOARD pico CACHE STRING "Board type")

cmake_minimum_required(VERSION 3.13)

# Include Pico SDK import helper
include(pico_sdk_import.cmake)

project(poproaster_brain C CXX ASM)

set(CMAKE_C_STANDARD 11)
set(CMAKE_CXX_STANDARD 17)

# Initialize the Raspberry Pi Pico SDK
pico_sdk_init()

# Define paths
set(CONFIG_JSON "${CMAKE_CURRENT_SOURCE_DIR}/config.json")
set(GENERATED_HEADER "${CMAKE_CURRENT_SOURCE_DIR}/include/generated_config.h")
set(CONFIG_SCRIPT "${CMAKE_CURRENT_SOURCE_DIR}/tools/config_generator.py")

# Pre-compile configuration validation and header generation command
add_custom_target(generate_config ALL
    COMMAND python3 ${CONFIG_SCRIPT} ${CONFIG_JSON} ${GENERATED_HEADER}
    DEPENDS ${CONFIG_JSON} ${CONFIG_SCRIPT}
    COMMENT "Validating config.json and generating C++ header..."
    VERBATIM
)

# Source files
set(SOURCE_FILES
    src/main.cpp
    src/pwm_actors.cpp
    src/max6675_sensor.cpp
    src/ssd1306_display.cpp
    src/modbus_slave.cpp
)

# Create executable
add_executable(poproaster_brain ${SOURCE_FILES})

# Ensure generated_config.h is generated before compiling sources
add_dependencies(poproaster_brain generate_config)

# Include directories
target_include_directories(poproaster_brain PRIVATE
    ${CMAKE_CURRENT_SOURCE_DIR}/include
)

# Target link libraries
target_link_libraries(poproaster_brain PRIVATE
    pico_stdlib
    hardware_pwm
    hardware_spi
    pico_multicore
    pico_time
)

# Enable USB CDC stdio (virtual COM port) and disable UART stdio
pico_enable_stdio_usb(poproaster_brain 1)
pico_enable_stdio_uart(poproaster_brain 0)

# Create extra outputs (.uf2, .hex, .bin, .elf)
pico_add_extra_outputs(poproaster_brain)
