cmake_minimum_required(VERSION 3.16)
project(ni404emu CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

find_package(SDL2 REQUIRED)

# The firmware lives one level up; its quote-includes (config.h, colors.h,
# files.h, audioinit.h, display.h) resolve relative to its own directory.
get_filename_component(FIRMWARE_DIR "${CMAKE_SOURCE_DIR}/.." ABSOLUTE)

add_executable(ni404emu
  src/main.cpp
  src/firmware.cpp
  src/audio_engine.cpp
  src/host_io.cpp
  src/midi_in.cpp
  src/midi_map.cpp
  src/menu.cpp
  src/sample_import.cpp
)

# On Windows build as a GUI app (subsystem:windows) so no console window appears
# behind it when double-clicked. main() reattaches to the parent console when run
# from a terminal (see AttachConsole in main.cpp), so CLI logs still work.
if(WIN32)
  set_target_properties(ni404emu PROPERTIES WIN32_EXECUTABLE TRUE)
endif()

target_include_directories(ni404emu PRIVATE
  "${CMAKE_SOURCE_DIR}/compat"
  "${FIRMWARE_DIR}"
  ${SDL2_INCLUDE_DIRS}
)

# We drive main() ourselves; tell SDL not to hijack it (avoids SDL2main).
target_compile_definitions(ni404emu PRIVATE SDL_MAIN_HANDLED NI404_EMULATOR=1 OLED_ENABLED=1)

# The Arduino/Teensy core builds sketches with -fpermissive (e.g. the firmware
# assigns to a `const String[]` element). Match that so the unmodified .ino
# compiles as it does in the Arduino IDE.
target_compile_options(ni404emu PRIVATE -fpermissive)

if(TARGET SDL2::SDL2)
  target_link_libraries(ni404emu PRIVATE SDL2::SDL2)
else()
  target_link_libraries(ni404emu PRIVATE ${SDL2_LIBRARIES})
endif()

# Real MIDI input backend dependencies.
if(WIN32)
  target_link_libraries(ni404emu PRIVATE winmm)
elseif(APPLE)
  target_link_libraries(ni404emu PRIVATE "-framework CoreMIDI" "-framework CoreFoundation")
endif()

# Bundle the SD card path so the firmware finds samples at ../_SDCARD.
target_compile_definitions(ni404emu PRIVATE
  NI404_SDCARD_PATH="${FIRMWARE_DIR}/_SDCARD")

# Statically link the mingw C++ runtime so the .exe runs on any Windows machine
# (no libstdc++-6.dll / libgcc_s_seh-1.dll / libwinpthread-1.dll needed; only
# SDL2.dll is still shipped alongside).
if(WIN32 AND CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
  target_link_options(ni404emu PRIVATE
    -static-libgcc -static-libstdc++ -Wl,-Bstatic -lwinpthread -Wl,-Bdynamic)
endif()

# ===========================================================================
# TŒRN emulator target — runs the real toern firmware (emulator/toern-src/).
# ===========================================================================
set(TOERN_SRC "${CMAKE_SOURCE_DIR}/toern-src")
if(EXISTS "${TOERN_SRC}/toern.ino")
  add_executable(toernemu
    src/main.cpp
    src/firmware_toern.cpp
    src/audio_engine.cpp
    src/host_io.cpp
    src/midi_in.cpp
    src/midi_map.cpp
    src/menu.cpp
    src/sample_import.cpp
    "${TOERN_SRC}/src/effect_freeverb_dmabuf.cpp"
  )
  if(WIN32)
    set_target_properties(toernemu PROPERTIES WIN32_EXECUTABLE TRUE)
  endif()
  target_include_directories(toernemu PRIVATE
    "${CMAKE_SOURCE_DIR}/compat" "${TOERN_SRC}" ${SDL2_INCLUDE_DIRS})
  target_compile_definitions(toernemu PRIVATE
    SDL_MAIN_HANDLED NI404_EMULATOR=1
    NI404_SDCARD_PATH="${FIRMWARE_DIR}/_SDCARD")
  target_compile_options(toernemu PRIVATE -fpermissive)
  # The vendored freeverb's DSP body is gated on __ARM_ARCH_7EM__ but is portable
  # C; enable it for that file only (NOT globally — would break std headers).
  set_source_files_properties("${TOERN_SRC}/src/effect_freeverb_dmabuf.cpp"
    PROPERTIES COMPILE_DEFINITIONS "__ARM_ARCH_7EM__")
  if(TARGET SDL2::SDL2)
    target_link_libraries(toernemu PRIVATE SDL2::SDL2)
  else()
    target_link_libraries(toernemu PRIVATE ${SDL2_LIBRARIES})
  endif()
  if(WIN32)
    target_link_libraries(toernemu PRIVATE winmm)
    if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
      target_link_options(toernemu PRIVATE
        -static-libgcc -static-libstdc++ -Wl,-Bstatic -lwinpthread -Wl,-Bdynamic)
    endif()
  elseif(APPLE)
    target_link_libraries(toernemu PRIVATE "-framework CoreMIDI" "-framework CoreFoundation")
  endif()
endif()
