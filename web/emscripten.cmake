# WebAssembly (Emscripten) build of eZeus.
# Included from the main CMakeLists.txt when EMSCRIPTEN is set.

# libnoise is not an Emscripten port, so build it from source.
FetchContent_Declare(
    libnoise
    GIT_REPOSITORY https://github.com/qknight/libnoise.git
    GIT_TAG master
    GIT_SHALLOW TRUE
)
FetchContent_GetProperties(libnoise)
if(NOT libnoise_POPULATED)
    FetchContent_Populate(libnoise)
endif()

file(GLOB NOISE_SOURCES
    ${libnoise_SOURCE_DIR}/src/*.cpp
    ${libnoise_SOURCE_DIR}/src/model/*.cpp
    ${libnoise_SOURCE_DIR}/src/module/*.cpp
)
add_library(noise STATIC ${NOISE_SOURCES})
target_include_directories(noise PRIVATE ${libnoise_SOURCE_DIR}/src/noise)

# eZeus includes <libnoise/noise.h>, so expose the headers under that name.
set(NOISE_INCLUDE_ROOT ${CMAKE_BINARY_DIR}/noise_include)
file(COPY ${libnoise_SOURCE_DIR}/src/noise/ DESTINATION ${NOISE_INCLUDE_ROOT}/libnoise)
target_include_directories(eZeus PRIVATE ${NOISE_INCLUDE_ROOT})
target_link_libraries(eZeus PRIVATE noise)

set(EZEUS_WEB_COMMON_FLAGS
    -pthread
    "-sUSE_SDL=2"
    "-sUSE_SDL_TTF=2"
    "-sUSE_SDL_IMAGE=2"
    "-sUSE_SDL_MIXER=2"
    "-sSDL2_IMAGE_FORMATS=[\"png\",\"jpg\"]"
    "-sSDL2_MIXER_FORMATS=[\"mp3\",\"wav\"]"
)
target_compile_options(eZeus PRIVATE ${EZEUS_WEB_COMMON_FLAGS})
target_compile_options(noise PRIVATE -pthread)

target_link_options(eZeus PRIVATE
    ${EZEUS_WEB_COMMON_FLAGS}
    "-sWASMFS"
    # SDL_image asks for browser-preloaded images through PATH_FS, which
    # WASMFS does not pull in by itself.
    "-sDEFAULT_LIBRARY_FUNCS_TO_INCLUDE=[\"$PATH_FS\"]"
    "-sPTHREAD_POOL_SIZE=8"
    "-sALLOW_MEMORY_GROWTH"
    "-sINITIAL_MEMORY=256MB"
    "-sMAXIMUM_MEMORY=4GB"
    "-sSTACK_SIZE=8MB"
    "-sDEFAULT_PTHREAD_STACK_SIZE=4MB"
    "-sENVIRONMENT=web,worker"
    "-sEXIT_RUNTIME=0"
    "-sEXPORTED_RUNTIME_METHODS=[\"callMain\"]"
    "-sINVOKE_RUN=0"
    "--shell-file=${CMAKE_CURRENT_SOURCE_DIR}/web/shell.html"
)
set_target_properties(eZeus PROPERTIES
    SUFFIX ".html"
    LINK_DEPENDS ${CMAKE_CURRENT_SOURCE_DIR}/web/shell.html
)

# The start page's background and font, copied next to it on every build.
add_custom_target(web_static ALL
    COMMAND ${CMAKE_COMMAND} -E copy_directory
            ${CMAKE_CURRENT_SOURCE_DIR}/web/static ${CMAKE_BINARY_DIR}/static
)
