
import os
import os.path
import argparse
import sys
import shutil
import subprocess
import glob

ver_str = "0.1.0"
windows_ver = "0, 1, 0, 0"
file_description = "Leading Brand DELTARUNE-type Software"
is_standalone = True

build_path = "build"
output_path = "output"
kristal_path = "Kristal"


# --------------------------------------------------
# UTILITIES
# --------------------------------------------------

def fatal(error):
    print(error, file=sys.stderr)
    sys.exit(1)


def make_directory(path):
    os.makedirs(path, exist_ok=True)


def clean_directory(path):
    if os.path.isdir(path):
        shutil.rmtree(path)
    os.makedirs(path, exist_ok=True)


def copy_kristal_sources():
    print("Copying engine files...")

    clean_directory(os.path.join(build_path, "kristal"))

    ignorefiles = [
        ".github",
        ".git",
        ".vscode",
        "docs",
        "build",
        "output",
        "__pycache__"
    ]

    if not is_standalone:
        ignorefiles.append("mods")

    for file in os.listdir(kristal_path):
        if file in ignorefiles:
            continue

        source = os.path.join(kristal_path, file)
        destination = os.path.join(build_path, "kristal", file)

        if os.path.isfile(source):
            shutil.copy2(source, destination)

        elif os.path.isdir(source):
            shutil.copytree(source, destination)


def create_love_package():
    print("Creating .love package...")

    kristal_love_path = os.path.join(
        build_path,
        "lovepkg",
        "kristal.love"
    )

    make_directory(os.path.dirname(kristal_love_path))

    if os.path.exists(kristal_love_path):
        os.remove(kristal_love_path)

    shutil.make_archive(
        os.path.join(build_path, "kristal"),
        "zip",
        os.path.join(build_path, "kristal")
    )

    shutil.move(
        os.path.join(build_path, "kristal.zip"),
        kristal_love_path
    )

    shutil.rmtree(os.path.join(build_path, "kristal"))

    return kristal_love_path


def read_version():
    global ver_str, windows_ver

    print("Reading Kristal version...")

    try:
        with open(
            os.path.join(kristal_path, "VERSION"),
            "r",
            encoding="utf-8"
        ) as file:
            ver_str = file.read().strip()

        windows_ver = Version(ver_str).format()

    except Exception:
        print("Warning: Could not read VERSION. Using default version.")


# --------------------------------------------------
# VERSION SUPPORT (WINDOWS)
# --------------------------------------------------

class Version:
    def __init__(self, s):
        s = s.strip()

        for suffix in ("-beta", "-alpha", "-dev"):
            s = s.replace(suffix, "")

        parts = s.split(",")

        if len(parts) == 1:
            parts = parts[0].split(".")

        self._parts = [
            int(part.strip())
            for part in parts
        ]

        if (
            not self._parts
            or len(self._parts) > 4
            or any(
                part < 0 or part >= 2**16
                for part in self._parts
            )
        ):
            raise ValueError("invalid version")

        while len(self._parts) < 4:
            self._parts.append(0)

    def get_ms_ls(self):
        ms = (self._parts[0] << 16) + self._parts[1]
        ls = (self._parts[2] << 16) + self._parts[3]

        return ms, ls

    def format(self):
        return ", ".join(
            str(part)
            for part in self._parts
        )


class _IdentityReplace:
    def __init__(self, val):
        self._val = val

    def __call__(self, s):
        return self._val


# --------------------------------------------------
# WINDOWS RESOURCE SUPPORT
# --------------------------------------------------

def setInfo(key, value):
    ver_data = None

    for name in resources.get(RT_VERSION, ()):
        for lang in resources[RT_VERSION][name]:

            if ver_data is not None:
                print(
                    "error: multiple manifest resources found",
                    file=sys.stderr
                )
                return 4

            ver_data = resources[RT_VERSION][name][lang]
            ver_name = name
            ver_lang = lang

    if ver_data is None:
        ver_data = VersionInfo()

    params = {
        key: _IdentityReplace(value)
    }

    vi = parse_version_info(ver_data)

    fvi = vi.get_fixed_info()

    if "FileVersion" in params:
        ver = Version(params["FileVersion"](None))
        fvi.dwFileVersionMS, fvi.dwFileVersionLS = ver.get_ms_ls()

    if "ProductVersion" in params:
        ver = Version(params["ProductVersion"](None))
        fvi.dwProductVersionMS, fvi.dwProductVersionLS = ver.get_ms_ls()

    vi.set_fixed_info(fvi)

    sfi = vi.string_file_info()

    for _, strings in sfi.items():
        for k, fn in params.items():

            val = fn(strings.get(k, ""))

            if val:
                strings[k] = val

            elif k in strings:
                del strings[k]

    vi.set_string_file_info(sfi)

    resources[RT_VERSION][ver_name][ver_lang] = vi.pack()


# --------------------------------------------------
# ANDROID BUILD
# --------------------------------------------------

def build_android(kristal_love_path, love_android_path):

    print("")
    print("===================================")
    print("       KRISTAL ANDROID BUILD")
    print("===================================")

    if not os.path.isdir(love_android_path):
        fatal(
            "Error: LÖVE Android repository not found: "
            + love_android_path
        )

    embed_assets = os.path.join(
        love_android_path,
        "app",
        "src",
        "embed",
        "assets"
    )

    if not os.path.isdir(os.path.dirname(embed_assets)):
        fatal(
            "Error: Android embed directory not found. "
            "Check the LÖVE Android repository structure."
        )

    make_directory(embed_assets)

    print("Copying Kristal game package...")

    game_love = os.path.join(
        embed_assets,
        "game.love"
    )

    shutil.copy2(
        kristal_love_path,
        game_love
    )

    print("Preparing Gradle...")

    gradlew = os.path.join(
        love_android_path,
        "gradlew"
    )

    if not os.path.isfile(gradlew):
        fatal("Error: Gradle wrapper not found!")

    os.chmod(gradlew, 0o755)

    print("Building Android APK...")

    try:
        subprocess.run(
            [
                "bash",
                "gradlew",
                "assembleEmbedNoRecordRelease"
            ],
            cwd=love_android_path,
            check=True
        )

    except subprocess.CalledProcessError as error:
        fatal(
            "Android Gradle build failed. Exit code: "
            + str(error.returncode)
        )

    apk_directory = os.path.join(
        love_android_path,
        "app",
        "build",
        "outputs",
        "apk",
        "embedNoRecord",
        "release"
    )

    apk_files = glob.glob(
        os.path.join(apk_directory, "*.apk")
    )

    if not apk_files:
        fatal("Error: No Android APK was generated!")

    apk_files.sort(
        key=os.path.getmtime,
        reverse=True
    )

    make_directory(output_path)

    final_apk = os.path.join(
        output_path,
        "Kristal-Android.apk"
    )

    shutil.copy2(
        apk_files[0],
        final_apk
    )

    print("")
    print("Android build completed!")
    print("Generated files:")
    print("> " + final_apk)


# --------------------------------------------------
# WINDOWS BUILD
# --------------------------------------------------

def build_windows(kristal_love_path, love2d_path):

    import grope

    from pe_tools import (
        parse_pe,
        IMAGE_DIRECTORY_ENTRY_RESOURCE
    )

    from pe_tools.rsrc import (
        parse_pe_resources,
        pe_resources_prepack,
        parse_prelink_resources,
        KnownResourceTypes
    )

    from pe_tools.version_info import (
        parse_version_info,
        VersionInfo
    )

    global resources, RT_VERSION

    RT_VERSION = KnownResourceTypes.RT_VERSION

    print("")
    print("===================================")
    print("        KRISTAL WINDOWS BUILD")
    print("===================================")

    if not love2d_path:
        print("Finding LÖVE...")
        path_var = os.getenv("PATH")

        if path_var is None:
            fatal(
                "Error: PATH not found! "
                "Please specify --love."
            )

        for path in path_var.split(os.pathsep):

            if not path:
                continue

            if os.path.isfile(
                os.path.join(path, "love.exe")
            ):
                love2d_path = path
                break

        if not love2d_path:
            fatal(
                "Error: LÖVE not found! "
                "Please specify --love."
            )

    if not os.path.isfile(
        os.path.join(love2d_path, "love.exe")
    ):
        fatal("Error: LÖVE not found at passed directory!")

    print("Compiling into exe...")

    try:
        with open(
            os.path.join(love2d_path, "love.exe"),
            "rb"
        ) as file1, open(
            kristal_love_path,
            "rb"
        ) as file2, open(
            os.path.join(build_path, "kristal_noicon.exe"),
            "wb"
        ) as output:

            output.write(file1.read())
            output.write(file2.read())

    except FileNotFoundError:
        fatal("Error: LÖVE or Kristal not found!")

    print("Patching custom icon...")

    fin = open(
        os.path.join(build_path, "kristal_noicon.exe"),
        "rb"
    )

    pe = parse_pe(grope.wrap_io(fin))
    resources = pe.parse_resources()

    try:
        res_fin = open(
            os.path.join(kristal_path, "icon.res"),
            "rb"
        )

    except FileNotFoundError:
        fatal(
            'Error: icon.res not found! '
            'Run "rc icon.rc" in a Visual Studio developer console.'
        )

    r = parse_prelink_resources(
        grope.wrap_io(res_fin)
    )

    for resource_type in r:
        for name in r[resource_type]:
            for lang in r[resource_type][name]:

                resources.setdefault(
                    resource_type, {}
                ).setdefault(
                    name, {}
                )[lang] = r[resource_type][name][lang]

    print("Patching version information...")

    setInfo("FileVersion", windows_ver)
    setInfo("ProductVersion", windows_ver)
    setInfo("FileDescription", file_description)
    setInfo("InternalName", "Kristal")
    setInfo("LegalCopyright", "Copyright © 2026 Kristal Team")
    setInfo("OriginalFilename", "kristal.exe")
    setInfo("ProductName", "Kristal")

    prepacked = pe_resources_prepack(resources)

    addr = pe.resize_directory(
        IMAGE_DIRECTORY_ENTRY_RESOURCE,
        prepacked.size
    )

    pe.set_directory(
        IMAGE_DIRECTORY_ENTRY_RESOURCE,
        prepacked.pack(addr)
    )

    print("Writing executable...")

    executable_path = os.path.join(
        build_path,
        "executable",
        "kristal.exe"
    )

    make_directory(
        os.path.dirname(executable_path)
    )

    with open(executable_path, "wb") as fout:
        grope.dump(
            pe.to_blob(),
            fout
        )

    res_fin.close()
    fin.close()

    print("Copying LÖVE files...")

    copyfiles = [
        "SDL2.dll",
        "OpenAL32.dll",
        "license.txt",
        "love.dll",
        "lua51.dll",
        "mpg123.dll",
        "msvcp120.dll",
        "msvcr120.dll"
    ]

    for file in copyfiles:

        source = os.path.join(love2d_path, file)

        if os.path.isfile(source):
            shutil.copy2(
                source,
                os.path.join(build_path, "executable", file)
            )

    print("Copying libraries...")

    lib_path = os.path.join(
        kristal_path,
        "lib"
    )

    if os.path.isdir(lib_path):

        for file in os.listdir(lib_path):

            source = os.path.join(lib_path, file)

            if os.path.isfile(source):

                if file.endswith(".dll"):
                    shutil.copy2(
                        source,
                        os.path.join(build_path, "executable", file)
                    )

                shutil.copy2(
                    source,
                    os.path.join(build_path, "lovepkg", file)
                )

    print("Creating Windows packages...")

    make_directory(output_path)

    shutil.make_archive(
        os.path.join(
            output_path,
            "kristal-" + ver_str + "-love"
        ),
        "zip",
        os.path.join(build_path, "lovepkg")
    )

    shutil.make_archive(
        os.path.join(
            output_path,
            "kristal-" + ver_str + "-win"
        ),
        "zip",
        os.path.join(build_path, "executable")
    )

    print("Packaging example project...")

    example_source = os.path.join(
        kristal_path,
        "mods",
        "example"
    )

    example_destination = os.path.join(
        build_path,
        "example"
    )

    clean_directory(example_destination)

    example_files = [
        "assets",
        "scripts"
    ]

    for folder in example_files:

        source = os.path.join(
            example_source,
            folder
        )

        if os.path.isdir(source):
            shutil.copytree(
                source,
                os.path.join(example_destination, folder)
            )

    for file in [
        "mod.json",
        "mod.lua",
        "example.tiled-project"
    ]:

        source = os.path.join(
            example_source,
            file
        )

        if os.path.isfile(source):
            shutil.copy2(
                source,
                os.path.join(example_destination, file)
            )

    shutil.make_archive(
        os.path.join(output_path, "example-project"),
        "zip",
        example_destination
    )

    print("Windows build completed!")

    print("Generated files:")
    print("> kristal-" + ver_str + "-love.zip")
    print("> kristal-" + ver_str + "-win.zip")
    print("> example-project.zip")


# --------------------------------------------------
# MAIN
# --------------------------------------------------

def main():

    global kristal_path

    parser = argparse.ArgumentParser(
        prog="build.py",
        description="Utility script to compile Kristal."
    )

    parser.add_argument(
        "--love",
        nargs=1,
        help="The path to the LÖVE folder (not the executable)"
    )

    parser.add_argument(
        "--kristal",
        nargs=1,
        help="The path to the Kristal folder"
    )

    parser.add_argument(
        "--android",
        action="store_true",
        help="Build Kristal for Android"
    )

    parser.add_argument(
        "--love-android",
        nargs=1,
        help="Path to the LÖVE Android repository"
    )

    args = parser.parse_args()

    if args.kristal:
        kristal_path = args.kristal[0]

    if not os.path.isdir(kristal_path):
        fatal(
            'Error: "' + kristal_path +
            '" folder missing!'
        )

    make_directory(build_path)
    make_directory(output_path)
    make_directory(os.path.join(build_path, "executable"))
    make_directory(os.path.join(build_path, "lovepkg"))

    print("Compiling Kristal...")

    read_version()

    copy_kristal_sources()

    kristal_love_path = create_love_package()

    if args.android:

        if not args.love_android:
            fatal(
                "Error: Please specify --love-android"
            )

        build_android(
            kristal_love_path,
            args.love_android[0]
        )

    else:

        love2d_path = (
            args.love[0]
            if args.love
            else None
        )

        build_windows(
            kristal_love_path,
            love2d_path
        )

    print("")
    print("Done!")


if __name__ == "__main__":
    main()
