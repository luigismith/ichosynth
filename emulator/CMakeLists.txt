cmake_minimum_required(VERSION 3.16)
project(ni404emu CXX)

set(CMAKE_CXX_STANDARD 17)
set(CMAKE_CXX_STANDARD_REQUIRED ON)

if(NOT CMAKE_BUILD_TYPE)
  set(CMAKE_BUILD_TYPE Release)
endif()

find_package(SDL2 REQUIRED)

# Two emulators share this frontend + compat layer:
#   toernemu  the REAL ichosynth firmware: the pinned TŒRN sketch staged and patched by
#             ../firmware/build_toern.py --stage-only (the same step the Teensy build
#             runs), compiled with the real hardware drivers from ../firmware/libraries
#             (KY-040 i2cEncoderLibV2, FastTouch, IchosOled). Needs Python 3 and the TŒRN
#             sources in emulator/toern-src/ (emulator/run.py fetches them, pinned).
#   ni404emu  the legacy NI404-based bench firmware (../legacy/soundpauli_ni404).
option(EMU_BUILD_TOERN "Build toernemu (the real TŒRN firmware, staged by firmware/build_toern.py)" ON)

# FIRMWARE_DIR = repo root (for sdcard); the sketch and its quote-includes
# (config.h, colors.h, files.h, audioinit.h, display.h) live in LEGACY_DIR.
get_filename_component(FIRMWARE_DIR "${CMAKE_SOURCE_DIR}/.." ABSOLUTE)
set(LEGACY_DIR "${FIRMWARE_DIR}/legacy/soundpauli_ni404")

add_executable(ni404emu
  src/main.cpp
  src/firmware.cpp
  src/audio_engine.cpp
  src/host_io.cpp
  src/host_os.cpp
  src/i2c_bus.cpp
  src/midi_in.cpp
  src/midi_map.cpp
  src/menu.cpp
  src/sample_import.cpp
  src/audio_decode.cpp
  src/audio_capture.cpp
)

# On Windows build as a GUI app (subsystem:windows) so no console window appears
# behind it when double-clicked. main() reattaches to the parent console when run
# from a terminal (see AttachConsole in main.cpp), so CLI logs still work.
if(WIN32)
  set_target_properties(ni404emu PROPERTIES WIN32_EXECUTABLE TRUE)
endif()

target_include_directories(ni404emu PRIVATE
  "${CMAKE_SOURCE_DIR}/compat"
  "${CMAKE_SOURCE_DIR}/vendor"
  "${LEGACY_DIR}"
  ${SDL2_INCLUDE_DIRS}
)

# We drive main() ourselves; tell SDL not to hijack it (avoids SDL2main).
# The bench keeps a few conveniences of its own: the "samples/" alias for its old card
# layout, private names for its root-level *.txt saves (they differ from TŒRN's), and a
# zero-filled fresh EEPROM (it cannot boot from an erased, 0xFF one; see EEPROM.h).
target_compile_definitions(ni404emu PRIVATE SDL_MAIN_HANDLED NI404_EMULATOR=1 OLED_ENABLED=1
  EMU_TARGET_NAME="ni404emu" EMU_SD_LEGACY_SAMPLES_ALIAS=1 EMU_SD_PRIVATE_SUFFIX="-ni404emu"
  EMU_EEPROM_ERASED=0x00)

# The Arduino/Teensy core builds sketches with -fpermissive (e.g. the firmware
# assigns to a `const String[]` element). Match that so the unmodified .ino
# compiles as it does in the Arduino IDE.
target_compile_options(ni404emu PRIVATE -fpermissive)

if(TARGET SDL2::SDL2)
  target_link_libraries(ni404emu PRIVATE SDL2::SDL2)
else()
  target_link_libraries(ni404emu PRIVATE ${SDL2_LIBRARIES})
endif()

# Real MIDI input backend dependencies. On macOS CoreMIDI is only used by a Clang
# build (src/midi_in.cpp: its headers need Clang's blocks); the GCC build that the
# sketches require has no MIDI input.
if(WIN32)
  target_link_libraries(ni404emu PRIVATE winmm)
elseif(APPLE AND CMAKE_CXX_COMPILER_ID MATCHES "Clang")
  target_link_libraries(ni404emu PRIVATE "-framework CoreMIDI" "-framework CoreFoundation")
endif()

# Bundle the SD card path so the firmware finds samples at ../sdcard.
target_compile_definitions(ni404emu PRIVATE
  NI404_SDCARD_PATH="${FIRMWARE_DIR}/sdcard")

# Statically link the mingw C++ runtime so the .exe runs on any Windows machine
# (no libstdc++-6.dll / libgcc_s_seh-1.dll / libwinpthread-1.dll needed; only
# SDL2.dll is still shipped alongside).
if(WIN32 AND CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
  target_link_options(ni404emu PRIVATE
    -static-libgcc -static-libstdc++ -Wl,-Bstatic -lwinpthread -Wl,-Bdynamic)
endif()
# On macOS with Homebrew GCC, statically link the GCC runtime so the binary does
# not depend on Homebrew's libstdc++/libgcc dylibs (only SDL2 is bundled).
if(APPLE AND CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
  target_link_options(ni404emu PRIVATE -static-libgcc -static-libstdc++)
endif()

# ===========================================================================
# toernemu — the real ichosynth firmware (see the top of this file).
# ===========================================================================
set(TOERN_SRC "${CMAKE_SOURCE_DIR}/toern-src")
set(FW_DIR "${FIRMWARE_DIR}/firmware")
set(FW_LIBS "${FW_DIR}/libraries")
if(EMU_BUILD_TOERN AND NOT EXISTS "${TOERN_SRC}/toern.ino")
  message(WARNING "toernemu skipped: no TŒRN sources in ${TOERN_SRC}. "
                  "Run 'python emulator/run.py' (it fetches them at the commit pinned in "
                  "firmware/build_toern.py), or clone soundpauli/toern there at that commit.")
elseif(EMU_BUILD_TOERN)
  find_package(Python3 REQUIRED COMPONENTS Interpreter)
  # Stage + patch the sketch exactly as the Teensy build does. Re-run whenever the
  # script, the upstream sources or the drivers change (CMAKE_CONFIGURE_DEPENDS);
  # only changed files are rewritten, so an unchanged sketch is not recompiled.
  set(TOERN_STAGE "${CMAKE_BINARY_DIR}/toern-staged")
  execute_process(
    COMMAND "${CMAKE_COMMAND}" -E env PYTHONIOENCODING=utf-8
            "${Python3_EXECUTABLE}" "${FW_DIR}/build_toern.py" --stage-only "${TOERN_STAGE}"
    RESULT_VARIABLE stage_rc OUTPUT_VARIABLE stage_out ERROR_VARIABLE stage_err)
  if(NOT stage_rc EQUAL 0)
    message(FATAL_ERROR "firmware/build_toern.py --stage-only failed:\n${stage_out}${stage_err}")
  endif()
  message(STATUS "TŒRN sketch staged by firmware/build_toern.py -> ${TOERN_STAGE}/toern")
  file(GLOB TOERN_INPUTS "${TOERN_SRC}/*.ino" "${TOERN_SRC}/*.h" "${TOERN_SRC}/src/*")
  set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS
    "${FW_DIR}/build_toern.py" "${FW_LIBS}/IchosOled/IchosOled.h" ${TOERN_INPUTS})
  set(TOERN_SKETCH "${TOERN_STAGE}/toern")

  add_executable(toernemu
    src/main.cpp
    src/firmware_toern.cpp
    src/audio_engine.cpp
    src/host_io.cpp
    src/host_os.cpp
    src/i2c_bus.cpp
    src/midi_in.cpp
    src/midi_map.cpp
    src/menu.cpp
    src/sample_import.cpp
    src/audio_decode.cpp
    src/audio_capture.cpp
    "${FW_LIBS}/IchosOled/IchosOled.cpp"
    "${TOERN_SKETCH}/src/effect_freeverb_dmabuf.cpp"
  )
  if(WIN32)
    set_target_properties(toernemu PROPERTIES WIN32_EXECUTABLE TRUE)
  endif()
  # Order matters: the staged sketch, then the REAL drivers (they win over any shim),
  # then the desktop compat layer for the Teensy core / Audio / SD / Wire APIs.
  target_include_directories(toernemu PRIVATE
    "${TOERN_SKETCH}"
    "${FW_LIBS}/i2cEncoderLibV2" "${FW_LIBS}/FastTouch" "${FW_LIBS}/IchosOled"
    "${CMAKE_SOURCE_DIR}/compat" "${CMAKE_SOURCE_DIR}/vendor" ${SDL2_INCLUDE_DIRS})
  target_compile_definitions(toernemu PRIVATE
    SDL_MAIN_HANDLED NI404_EMULATOR=1 EMU_TARGET_TOERN=1 EMU_TARGET_NAME="toernemu"
    NI404_SDCARD_PATH="${FIRMWARE_DIR}/sdcard")
  target_compile_options(toernemu PRIVATE -fpermissive)
  # The vendored freeverb's DSP body is gated on __ARM_ARCH_7EM__ but is portable
  # C; enable it for that file only (NOT globally — would break std headers).
  set_source_files_properties("${TOERN_SKETCH}/src/effect_freeverb_dmabuf.cpp"
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
    if(CMAKE_CXX_COMPILER_ID MATCHES "Clang")   # see the ni404emu note on CoreMIDI
      target_link_libraries(toernemu PRIVATE "-framework CoreMIDI" "-framework CoreFoundation")
    endif()
    if(CMAKE_CXX_COMPILER_ID STREQUAL "GNU")
      target_link_options(toernemu PRIVATE -static-libgcc -static-libstdc++)
    endif()
  endif()
endif()
