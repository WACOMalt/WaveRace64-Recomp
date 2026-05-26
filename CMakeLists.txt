cmake_minimum_required(VERSION 3.20)
project(WaveRace64Recomp VERSION 0.1.0 LANGUAGES C CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

# Options
option(BUILD_RT64 "Build RT64 rendering backend" ON)

# TODO: Add N64Recomp integration
# TODO: Add RT64 as rendering backend
# TODO: Add N64ModernRuntime linking
# TODO: Add game-specific patches

message(STATUS "WaveRace64-Recomp v${PROJECT_VERSION}")
message(STATUS "Build type: ${CMAKE_BUILD_TYPE}")
