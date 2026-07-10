cmake_minimum_required(VERSION 3.20)

project(thgem_sim LANGUAGES CXX)

set(CMAKE_CXX_STANDARD 20)
set(CMAKE_CXX_STANDARD_REQUIRED ON)
set(CMAKE_CXX_EXTENSIONS OFF)

set(THGEM_SHARED_GARFIELD_HINT "${CMAKE_SOURCE_DIR}/../../local/garfield")

if(DEFINED ENV{ROOTSYS})
  list(PREPEND CMAKE_PREFIX_PATH "$ENV{ROOTSYS}")
endif()
if(DEFINED ENV{GARFIELD_INSTALL} AND NOT "$ENV{GARFIELD_INSTALL}" STREQUAL "")
  list(PREPEND CMAKE_PREFIX_PATH "$ENV{GARFIELD_INSTALL}")
elseif(EXISTS "${THGEM_SHARED_GARFIELD_HINT}/lib/cmake/Garfield/GarfieldConfig.cmake")
  list(PREPEND CMAKE_PREFIX_PATH "${THGEM_SHARED_GARFIELD_HINT}")
endif()

find_package(ROOT REQUIRED COMPONENTS Core RIO Hist Graf Gpad)
find_package(Garfield CONFIG QUIET)

if(NOT Garfield_FOUND)
  message(FATAL_ERROR
    "Garfield++ was not found. Set GARFIELD_INSTALL or CMAKE_PREFIX_PATH to a Garfield installation, "
    "or source ../../local/garfield/share/Garfield/setupGarfield.sh when using the shared workspace install."
  )
endif()

add_executable(thgem_sim
  src/thgem_sim.cc
)

target_include_directories(thgem_sim PRIVATE
  ${CMAKE_SOURCE_DIR}/third_party
)

# neBEM is pulled in transitively by the Garfield::Garfield imported target
# (the THGEM field is solved by ComponentNeBem3d).
target_link_libraries(thgem_sim PRIVATE
  Garfield::Garfield
  ROOT::Core
  ROOT::RIO
  ROOT::Hist
  ROOT::Graf
  ROOT::Gpad
)

target_compile_options(thgem_sim PRIVATE
  $<$<OR:$<CXX_COMPILER_ID:Clang>,$<CXX_COMPILER_ID:AppleClang>,$<CXX_COMPILER_ID:GNU>>:
    -Wall
    -Wextra
    -Wpedantic
    -Wshadow
  >
)

set(_runtime_paths "")
if(DEFINED ENV{GARFIELD_INSTALL} AND NOT "$ENV{GARFIELD_INSTALL}" STREQUAL "")
  list(APPEND _runtime_paths "$ENV{GARFIELD_INSTALL}/lib")
elseif(EXISTS "${THGEM_SHARED_GARFIELD_HINT}/lib")
  list(APPEND _runtime_paths "${THGEM_SHARED_GARFIELD_HINT}/lib")
endif()
if(DEFINED ENV{ROOTSYS})
  list(APPEND _runtime_paths "$ENV{ROOTSYS}/lib")
endif()

set_target_properties(thgem_sim PROPERTIES
  BUILD_RPATH "${_runtime_paths}"
  INSTALL_RPATH "${_runtime_paths}"
)

include(CTest)

if(BUILD_TESTING)
  add_test(
    NAME smoke_thgem_sim
    COMMAND thgem_sim
      --config ${CMAKE_SOURCE_DIR}/config/smoke_thgem.json
      --out ${CMAKE_BINARY_DIR}/smoke-output
  )
  set_tests_properties(smoke_thgem_sim PROPERTIES
    ENVIRONMENT
      "GARFIELD_INSTALL=${THGEM_SHARED_GARFIELD_HINT};HEED_DATABASE=${THGEM_SHARED_GARFIELD_HINT}/share/Heed/database"
    TIMEOUT 600
  )
endif()
