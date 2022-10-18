from pydub import AudioSegment
from pydub.utils import mediainfo
from pathlib import Path
import getopt
import sys
import yaml
import cv2
import shutil


def get_flac_album_path(flac_albums_dir, num_albums_to_show, latest):
    '''Fetches folders inside flac_albums_dir sorted by their modification
       time, takes user input on which one should be chosen; returns the first
       one without asking if 'latest' is set to True'''

    folder_paths_to_show = sorted([x for x in flac_albums_dir.glob("*")
                                  if x.is_dir()],
                                  key=lambda x: x.lstat().st_mtime,
                                  reverse=True)
    if not folder_paths_to_show:
        raise Exception("No directories found in the flac_album_path "
                        + f"({flac_albums_dir})")

    if latest:
        return folder_paths_to_show[0]

    print("\n\n--- Albums ---\n")
    folder_names_to_show = [x.name for x in folder_paths_to_show]

    for i in range(min(len(folder_paths_to_show), num_albums_to_show)):
        print(f"{i}: ", str(folder_names_to_show[i]))

    answer = input("\nChoose the album\n:")
    return folder_paths_to_show[int(answer)]


def pick_songs(flac_album_path, entire):
    '''Fetches all the flac files found in the album path, takes user input
       on which ones should be chosen and returns the paths for those. Returns
       all paths found if 'entire' is set to True.'''

    all_flac_files_paths = list(flac_album_path.rglob("*.flac"))

    if not entire:
        print("\n\n--- Songs ---\n")
        for nr, f in enumerate([x.name for x in all_flac_files_paths]):
            print(nr, ": ", f)
        print()

        answer = input("Choose songs, comma separated\n:")
        song_picks = [int(x) for x in str(answer).split(',')]
    elif entire:
        song_picks = list(range(len(all_flac_files_paths)))
    return [all_flac_files_paths[x] for x in song_picks]


def get_dst_album_path(song_picks_paths, dst_albums_dir, dir_prompts):
    '''Proposes an artist/album combo for the destination dir and subdir names
       based on the flac's metadata. Takes confirmation or custom names as
       input. Constructs and returns a full destination folder path.'''

    artist_name = mediainfo(song_picks_paths[0]).get('TAG', None)['ARTIST']
    album_name = mediainfo(song_picks_paths[0]).get('TAG', None)['ALBUM']

    if dir_prompts:
        print("\n\n--- Destination folder name ---\n")
        print(f"Proposed artist folder name: " + f"{artist_name}")
        print("Type \"y\" to confirm or enter the desired artist name instead")
        artist_name_answer = input(":")
        if artist_name_answer.lower() == "y":
            dst_album_path = dst_albums_dir / f"{artist_name}"
        else:
            dst_album_path = dst_albums_dir / artist_name_answer
    else:
        dst_album_path = dst_albums_dir / f"{artist_name}"

    if dir_prompts:
        print(f"\nProposed album folder name: " + f"{album_name}")
        print("Type \"y\" to confirm or enter the desired album name instead")
        album_name_answer = input(":")
        if album_name_answer.lower() == "y":
            dst_album_path = dst_album_path / f"{album_name}"
        else:
            dst_album_path = dst_album_path / album_name_answer
    else:
        dst_album_path = dst_album_path / f"{album_name}"
    return dst_album_path


def copy_cover_art(flac_album_path, dst_album_path,
                   default_cover_art_name, cover_art_suffixes):
    '''Fetches all images with proper suffixes found in the flac_album_path.
       Offers options to choose a main cover art file (copied directly into the
       destination folder), copy additional cover art preserving the folder
       structure and preview files (using OpenCV). Checks for existing files
       before copying.'''

    all_images_paths = []
    for suffix in cover_art_suffixes:
        all_images_paths.extend(list(flac_album_path.rglob(f"*.{suffix}")))

    print("\n\n--- Cover Art ---\n")
    for nr, f in enumerate([x.relative_to(flac_album_path)
                            for x in all_images_paths]):
        print(nr, ": ", f)

    print("\n<number> - pick cover art to be copied to the"
          + f"destination folder as \"{default_cover_art_name}\"."
          + "\np<number> - preview the image \nc<number> - copy "
          + "an additional file directly without changing "
          + "its name\nq - finish copying metadata and proceed\n"
          + "h - see this prompt again\n")

    while True:
        answer = input(":")
        if answer[0] == "p":
            img = cv2.imread(str(all_images_paths[int(answer[1:])]))
            cv2.namedWindow("cover")
            cv2.imshow("cover", img)
            # The loop breaks on a closed window as well as on any keypress
            while cv2.getWindowProperty("cover", cv2.WND_PROP_VISIBLE) >= 1:
                cv2.waitKey(100)
        elif answer[0] == "c":
            misc_src = all_images_paths[int(answer[1:])]
            misc_dest = (dst_album_path
                         / misc_src.relative_to(flac_album_path))

            if not misc_dest.exists():
                misc_dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(misc_src, misc_dest)
                print("Misc cover art succesfully copied as " + f"{misc_dest}")
            else:
                print("Misc cover art already copied, skipping...")
        elif answer.isnumeric():
            main_src = all_images_paths[int(answer)]
            main_dest = (dst_album_path
                         / (default_cover_art_name
                            + all_images_paths[int(answer)].suffix))

            if not main_dest.exists():
                dst_album_path.mkdir(parents=True, exist_ok=True)
                shutil.copy2(main_src, main_dest)
                print("Main cover art succesfully copied as "
                      + f"{main_dest.stem}")
            else:
                print("Main cover art already copied, skipping...")
        elif answer[0] == "h":
            print()
            for nr, f in enumerate([x.name for x in all_images_paths]):
                print(nr, ": ", f)
            print("\n<number> - pick cover art to be copied to the"
                  + f"destination folder as \"{default_cover_art_name}\"."
                  + "\np<number> - preview the image \nc<number> - copy "
                  + "an additional file directly without changing "
                  + "its name\nq - finish copying metadata and proceed\n"
                  + "h - see this prompt again\n")
        elif answer[0] == "q":
            break
    return


def convert_songs(dst_album_path, song_picks_paths,
                  flac_album_path, ffmpeg_params, dst_format):
    '''Converts all flac files into dst_format preserving subdirs. Checks if
       songs already exist. Makes subdirs if they don't exist.'''

    for song_flac in song_picks_paths:
        dst_song_path = (dst_album_path
                         / song_flac.parent.relative_to(flac_album_path)
                         / (song_flac.stem + "." + dst_format))
        print()
        if not dst_song_path.exists():
            print("Processing \"" + song_flac.name + "\"...", end='')
            sys.stdout.flush()
            seg = AudioSegment.from_file(song_flac)
            dst_song_path.parent.mkdir(parents=True, exist_ok=True)
            seg.export(dst_song_path, format=dst_format,
                       parameters=ffmpeg_params.split(),
                       tags=mediainfo(song_flac).get('TAG', {}))
            print("DONE")
        else:
            print(f"\n{dst_song_path.stem} already exists, skipping...")
    print("\nAll conversions done.")
    return


def main():
    opts, args = getopt.getopt(sys.argv[1:], "hes:n:d:c:l",
                               ["help", "entire", "source=", "number=",
                                "destination=", "config=", "latest",
                                "skip-cover-art", "skip-dir-prompts"])

    config_file = 'config.yaml'
    flac_album_path = None
    dst_album_path = None
    entire = None
    latest = None
    get_cover_art = None
    dir_prompts = None

    for opt, arg in opts:
        if opt in ["-h", "--help"]:
            print("\n----- flac2lib by PokerFacowaty -----",
                  "\nPossible options:",
                  "\n[-h, --help] - open this prompt",
                  "\n[-c, --config] - point to a specific yaml config file",
                  "\n[-e, --entire] - convert an entire folder",
                  "\n[-s, --source] - provide the source album folder",
                  "\n[-d, --destination] - provide the destination folder",
                  "\n[-l, --latest] - convert the most recently modified",
                  "folder",
                  "\n[--skip-cover-art] - skip copying the cover art",
                  "\n[--skip-dir-prompts] - use ARTIST and ALBUM tags for",
                  "directory names without asking",
                  "\nDocs: https://github.com/PokerFacowaty/flac2lib\n")
            return
        elif opt in ["-c", "--config"]:
            config_file = arg
        elif opt in ["-e", "--entire"]:
            entire = True
        elif opt in ["-s", "--source"]:
            flac_album_path = Path(arg)
        elif opt in ["-d", "--destination"]:
            dst_album_path = Path(arg)
        elif opt in ["-l", "--latest"]:
            latest = True
        elif opt in ["--skip-cover-art"]:
            get_cover_art = False
        elif opt in ["--skip-dir-prompts"]:
            dir_prompts = False

    config = yaml.safe_load(open(config_file))
    flac_albums_dir = Path(config["flac_albums_dir"])
    dst_albums_dir = Path(config["dst_albums_dir"])
    if entire is None:
        entire = config["entire"]
    num_albums_to_show = config["num_albums_to_show"]
    if dir_prompts is None:
        dir_prompts = config["dir_name_prompts"]
    if latest is None:
        latest = config["latest"]
    if get_cover_art is None:
        get_cover_art = config["get_cover_art"]
    default_cover_art_name = config["default_cover_art_name"]
    covert_art_suffixes = config["cover_art_suffixes"]
    dst_format = config["destination_format"]
    ffmpeg_params = config["ffmpeg_params"]

    print("\n----- flac2lib.py by PokerFacowaty -----")
    print("https://github.com/PokerFacowaty/flac2lib")

    if flac_album_path is None:
        flac_album_path = get_flac_album_path(flac_albums_dir,
                                              num_albums_to_show, latest)

    song_picks_paths = pick_songs(flac_album_path, entire)

    if dst_album_path is None:
        dst_album_path = get_dst_album_path(song_picks_paths, dst_albums_dir,
                                            dir_prompts)

    if get_cover_art:
        copy_cover_art(flac_album_path, dst_album_path,
                       default_cover_art_name, covert_art_suffixes)

    convert_songs(dst_album_path, song_picks_paths,
                  flac_album_path, ffmpeg_params, dst_format)


if __name__ == "__main__":
    main()
